"""
위험도 분석기 — "얼마나 위험한지 판단"
역할: 게시물의 위험 점수 산출 -> 4단계 위험도 분류
"""

def _to_int(val):
    """숫자 문자열을 int로 안전하게 변환"""
    try:
        return int(str(val).replace(",","").strip())
    except:
        return 0

def analyze_risk(post: dict, classification: dict, config: dict) -> dict:
    score = 0
    factors = []
    thresholds = config.get("risk_thresholds", {"urgent":80,"high":60,"mid":35,"low":0})
    spread = config.get("spread_thresholds", {"viral_views":50000,"high_views":10000,"alert_comments":100})

    # 1. 분류 기반 점수
    cls_types = classification.get("types", [])
    type_scores = {
        "허위사실 가능성":     30,
        "명예훼손 가능성":     25,
        "사생활 침해 가능성":  30,
        "모욕 가능성":         15,
        "렉카 확산 가능성":    20,
        "악성 댓글":           10,
        "법적 대응 검토 필요": 15,
        "단순 언급":           5
    }
    for t in cls_types:
        pts = type_scores.get(t, 0)
        if pts > 0:
            score += pts
            factors.append(f"분류: {t}")

    # 2. 조회수
    views = _to_int(post.get("views", 0))
    if views >= spread["viral_views"]:
        score += 25; factors.append(f"바이럴 조회수: {views}회")
    elif views >= spread["high_views"]:
        score += 15; factors.append(f"높은 조회수: {views}회")
    elif views >= 1000:
        score += 5;  factors.append(f"조회수: {views}회")

    # 3. 댓글 수
    comments = _to_int(post.get("comments", 0))
    if comments >= spread["alert_comments"]:
        score += 10; factors.append(f"댓글 활성화: {comments}개")

    # 4. 렉카 채널
    channel = str(post.get("channel", post.get("author", ""))).lower()
    if any(k in channel for k in ["렉카","논란","폭로","정리tv","뉴스킹","알고리즘"]):
        score += 20; factors.append("렉카 채널")

    # 5. 제목 자극성
    title = str(post.get("title", ""))
    danger_words = ["충격","경악","실체","전말","폭로","진실","난리","실화"]
    hits = sum(1 for w in danger_words if w in title)
    if hits >= 2:
        score += 15; factors.append("자극적 제목")

    # 6. 수동 확인 필요 항목
    if post.get("manual_check_needed"):
        score += 10; factors.append("수동 확인 필요")

    score = min(score, 100)
    if score >= thresholds["urgent"]:
        level = "urgent"
    elif score >= thresholds["high"]:
        level = "high"
    elif score >= thresholds["mid"]:
        level = "mid"
    else:
        level = "low"

    return {
        "risk_level": level,
        "risk_score": score,
        "risk_factors": factors
    }
