"""
온라인 모니터링 시스템 — 메인 오케스트레이터
"사람처럼 일하는 AI 법률 모니터링 시스템"

실행 흐름:
  키워드 DB → 플랫폼 순찰 → 수집 → AI 분류 → 증거보존 → 위험도 분석 → 대시보드 전달
"""
import json, os, sys, time, logging
from datetime import datetime

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from monitoring.youtube_monitor    import YouTubeMonitor
from monitoring.news_monitor       import NewsMonitor
from monitoring.community_monitor  import CommunityMonitor
from ai_analysis.classifier        import classify_post
from ai_analysis.risk_analyzer     import analyze_risk
from ai_analysis.spread_analyzer   import SpreadAnalyzer
from evidence_manager              import EvidenceManager
from dashboard_connector           import DashboardConnector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitoring.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


def load_config():
    with open("config.json", encoding="utf-8") as f:
        config = json.load(f)
    # .env 파일에서 API 키 읽기 (config.json에 없으면)
    env_path = os.path.join(BASE_DIR, '..', '.env')
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('YOUTUBE_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    if key:
                        config['youtube_api_key'] = key
    return config

def load_keywords():
    with open("keywords/keywords.json", encoding="utf-8") as f:
        return json.load(f)


def run_cycle(config, keywords):
    """
    단일 모니터링 사이클 실행
    모니터링 → 분류 → 증거보존 → 대시보드 전달
    """
    log.info("=" * 50)
    log.info(f"모니터링 사이클 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 모니터 초기화
    yt      = YouTubeMonitor(config.get("youtube_api_key",""), config.get("max_results_per_search",10))
    news    = NewsMonitor()
    community = CommunityMonitor()
    evidence = EvidenceManager(config.get("evidence_path","evidence_storage"))
    dashboard = DashboardConnector(config.get("dashboard_pending_path","../dashboard_pending.json"))
    spread_analyzer = SpreadAnalyzer(config.get("evidence_path","evidence_storage"))

    # STEP 1~3: 플랫폼 순찰 + 수집
    log.info("[STEP 1-3] 플랫폼 순찰 및 게시물 수집...")
    all_results = []
    all_results.extend(yt.scan_all(keywords))
    all_results.extend(news.scan_all(keywords))
    all_results.extend(community.scan_all(keywords))

    log.info(f"  수집 완료: 총 {len(all_results)}건 (유튜브+뉴스+커뮤니티)")

    if not all_results:
        log.info("  수집된 항목 없음 — 사이클 종료")
        return 0

    # STEP 4~7: AI 분류 + 위험도 + 확산 분석
    pushed = 0
    for post in all_results:
        try:
            # STEP 4: AI 분류
            cls    = classify_post(post)

            # STEP 5: 위험도 분석
            risk   = analyze_risk(post, cls, config)

            # STEP 6: 확산 분석
            spread = spread_analyzer.analyze(post, all_results)

            # 단순 언급 + 낮은 위험도 → 건너뜀 (노이즈 필터)
            if risk["risk_level"] == "low" and cls["types"] == ["단순 언급"]:
                continue

            # STEP 5: 증거보존 (삭제 전 즉시 저장)
            evidence.save(post, cls, risk, spread)

            # STEP 8: 대시보드 전달
            if dashboard.push_to_pending(post, cls, risk, spread):
                pushed += 1

        except Exception as e:
            log.error(f"처리 오류 ({post.get('title','')[:30]}): {e}")

    log.info(f"[STEP 8] 대시보드에 {pushed}건 전달 완료")
    log.info(f"사이클 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 50)
    return pushed


def run_scheduler(config, keywords):
    """
    스케줄러 모드 — 정해진 주기마다 자동 실행
    유튜브: 10분마다 / 뉴스: 30분마다 / 커뮤니티: 1시간마다
    """
    try:
        import schedule
    except ImportError:
        log.warning("schedule 라이브러리 없음. 1회 실행 모드로 전환.")
        run_cycle(config, keywords)
        return

    log.info("스케줄러 시작...")
    log.info(f"  유튜브: {config['check_intervals_sec']['youtube']//60}분마다")
    log.info(f"  뉴스:   {config['check_intervals_sec']['news']//60}분마다")
    log.info(f"  커뮤:   {config['check_intervals_sec']['community']//60}분마다")

    # 즉시 1회 실행
    run_cycle(config, keywords)

    # 스케줄 등록 (가장 짧은 주기로 통합)
    interval = min(config["check_intervals_sec"].values()) // 60
    schedule.every(interval).minutes.do(run_cycle, config=config, keywords=keywords)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    import argparse
    parser = argparse.ArgumentParser(description="monitoring system")
    parser.add_argument("--schedule", action="store_true", help="scheduler mode")
    args = parser.parse_args()

    config   = load_config()
    keywords = load_keywords()

    kw_total = sum(len(v) for v in keywords.values())
    print()
    print("=" * 55)
    print("  [START] Bobae Legal Monitoring System")
    print(f"  Keywords: {kw_total}")
    print(f"  Dashboard: {config['dashboard_pending_path']}")
    print(f"  Evidence: {config['evidence_path']}/")
    print()

    if args.schedule:
        run_scheduler(config, keywords)
    else:
        result = run_cycle(config, keywords)
        print(f"\n[DONE] {result} items -> raw_monitoring.json")
        print("-> http://localhost:8080/모니터링.html (분류실에서 분류 후 상황실 전달)\n")
