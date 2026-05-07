#!/usr/bin/env python3
import sys, os, json, subprocess, signal, re
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

DATA_FILE       = 'dashboard_data.json'
PENDING_FILE    = 'dashboard_pending.json'
LOG_FILE        = 'dashboard_log.json'
MONITORING_FILE = 'raw_monitoring.json'
CLASS_FILE      = 'monitoring_classifications.json'
SCHEDULER_FILE  = 'scheduler_status.json'

API_MAP = {
    '/api/data':            DATA_FILE,
    '/api/pending':         PENDING_FILE,
    '/api/log':             LOG_FILE,
    '/api/monitoring':      MONITORING_FILE,
    '/api/classifications': CLASS_FILE,
}

MONITORING_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'monitoring_system')
PYTHON_EXE      = sys.executable

# 전역 프로세스 핸들
_scheduler_proc = None   # 스케줄러 (--schedule)
_once_proc      = None   # 즉시 실행 (1회)


def _ts():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _load_scheduler():
    try:
        with open(SCHEDULER_FILE, encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"status":"stopped","pid":None,"last_run":None,"next_run":None,
                "auto_start_registered":False,"pending_action":None,"pending_at":None,"log":[]}

def _save_scheduler(data):
    with open(SCHEDULER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _add_log(data, action, note=''):
    entry = {"time": _ts(), "action": action, "note": note}
    data.setdefault("log", []).insert(0, entry)
    data["log"] = data["log"][:50]  # 최대 50개 유지

def _is_running(pid):
    """PID가 살아있는지 확인"""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False

def _check_auto_start():
    """Windows 작업 스케줄러 등록 여부 확인"""
    try:
        r = subprocess.run('schtasks /Query /TN "BobaeServer" /FO LIST',
                          shell=True, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
        return r.returncode == 0
    except:
        return False

def _calc_next_run(data):
    """다음 실행 예정 시간 계산 (현재 + 10분)"""
    from datetime import datetime, timedelta
    if data.get("status") == "running":
        return (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    return None

def handle_scheduler_get():
    """GET /api/scheduler — 현재 상태 반환"""
    global _scheduler_proc
    data = _load_scheduler()

    # 프로세스 생존 여부 체크
    pid = data.get("pid")
    if pid and not _is_running(pid):
        data["status"] = "stopped"
        data["pid"] = None
        _save_scheduler(data)

    # 전역 프로세스 체크
    if _scheduler_proc and _scheduler_proc.poll() is not None:
        _scheduler_proc = None
        data["status"] = "stopped"
        data["pid"] = None
        _save_scheduler(data)

    data["auto_start_registered"] = _check_auto_start()
    data["next_run"] = _calc_next_run(data)
    return data

def handle_scheduler_action(body):
    """POST /api/scheduler/action — 승인된 액션 실행"""
    global _scheduler_proc, _once_proc
    action   = body.get("action")
    approved = body.get("approved", False)
    note     = body.get("note", "")
    data     = _load_scheduler()

    # 승인 없는 요청 → pending 상태로 저장
    if not approved:
        data["pending_action"] = action
        data["pending_at"]     = _ts()
        _save_scheduler(data)
        return {"ok": True, "status": "pending", "action": action}

    # ── 승인된 액션 처리 ──

    if action == "start":
        if data.get("status") == "running":
            return {"ok": False, "error": "이미 실행 중입니다"}
        try:
            proc = subprocess.Popen(
                [PYTHON_EXE, '-X', 'utf8', 'main.py', '--schedule'],
                cwd=MONITORING_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _scheduler_proc = proc
            data["status"]   = "running"
            data["pid"]      = proc.pid
            data["last_run"] = _ts()
            data["pending_action"] = None
            _add_log(data, "started", note or "대표 승인으로 시작")
            _save_scheduler(data)
            return {"ok": True, "status": "running", "pid": proc.pid}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif action == "stop":
        pid = data.get("pid")
        stopped = False
        if _scheduler_proc and _scheduler_proc.poll() is None:
            try:
                _scheduler_proc.terminate()
                _scheduler_proc = None
                stopped = True
            except: pass
        if pid and _is_running(pid):
            try:
                os.kill(int(pid), signal.SIGTERM)
                stopped = True
            except: pass
        data["status"]  = "stopped"
        data["pid"]     = None
        data["pending_action"] = None
        _add_log(data, "stopped", note or "대표 승인으로 중지")
        _save_scheduler(data)
        return {"ok": True, "status": "stopped"}

    elif action == "run_once":
        if _once_proc and _once_proc.poll() is None:
            return {"ok": False, "error": "1회 실행이 이미 진행 중입니다"}
        try:
            proc = subprocess.Popen(
                [PYTHON_EXE, '-X', 'utf8', 'main.py'],
                cwd=MONITORING_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _once_proc = proc
            data["last_run"] = _ts()
            data["pending_action"] = None
            _add_log(data, "run_once", note or "대표 승인으로 즉시 실행")
            _save_scheduler(data)
            return {"ok": True, "status": "running_once", "pid": proc.pid}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif action == "register_auto":
        try:
            setup = os.path.join(os.path.dirname(MONITORING_DIR), 'setup_scheduler.py')
            result = subprocess.run(
                [PYTHON_EXE, setup, 'install'],
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            success = result.returncode == 0
            data["auto_start_registered"] = success
            data["pending_action"] = None
            _add_log(data, "auto_register", "성공" if success else f"실패: {result.stderr[:100]}")
            _save_scheduler(data)
            return {"ok": success, "output": result.stdout or result.stderr}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif action == "unregister_auto":
        try:
            setup = os.path.join(os.path.dirname(MONITORING_DIR), 'setup_scheduler.py')
            result = subprocess.run(
                [PYTHON_EXE, setup, 'disable'],
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            data["auto_start_registered"] = False
            data["pending_action"] = None
            _add_log(data, "auto_unregister", "자동시작 비활성화")
            _save_scheduler(data)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif action == "cancel_pending":
        data["pending_action"] = None
        data["pending_at"]     = None
        _save_scheduler(data)
        return {"ok": True, "status": "pending_cancelled"}

    return {"ok": False, "error": f"알 수 없는 액션: {action}"}


def handle_consult(body):
    """
    POST /api/consult
    사건 기반 AI 법률 상담 엔진
    1) 키워드 분석
    2) 관련 사건·증거·판례·리서치 자동 수집
    3) 강화 프롬프트 생성
    4) (선택) Claude API 직접 호출
    """
    question    = body.get("question", "")
    context_req = body.get("collect_context", True)   # 컨텍스트 수집 여부
    use_api     = body.get("use_api", False)           # Claude API 직접 호출 여부
    category    = body.get("category", "etc")
    urgency     = body.get("urgency", "mid")

    # ── 1. 키워드 추출 (간단 NLP) ──
    stop_words = {'이', '가', '을', '를', '은', '는', '에', '의', '와', '과', '도', '로', '으로',
                  '그', '이런', '저런', '어떤', '어떻게', '지금', '여기', '거기', '이거', '저거',
                  '해야', '해도', '되나요', '될까요', '있어', '없어', '했어', '했는데', '했다',
                  'what', 'how', 'when', 'where', 'why', 'who'}
    words = re.findall(r'[가-힣a-zA-Z]{2,}', question)
    keywords = [w for w in words if w not in stop_words][:10]

    # ── 2. 로컬 데이터에서 컨텍스트 수집 ──
    ctx = {
        "keywords": keywords,
        "cases": [],
        "evidence": [],
        "confirmed_facts": [],
        "analysis": [],
        "monitoring": [],
        "research": []
    }

    if context_req:
        # 사건 확정 사실
        try:
            with open(DATA_FILE, encoding='utf-8') as f:
                dash = json.load(f)
            ctx["cases"]           = dash.get("cases", [])
            ctx["confirmed_facts"] = dash.get("confirmed_facts", [])
            ctx["analysis"]        = dash.get("analysis", [])
            ctx["alerts"]          = dash.get("alerts", [])
        except: pass

        # 모니터링 최근 항목 (위험도 높은 것)
        try:
            with open(MONITORING_FILE, encoding='utf-8') as f:
                mon = json.load(f)
            high_items = [i for i in mon.get("items", [])
                         if i.get("risk") in ("urgent","high")][:5]
            ctx["monitoring"] = high_items
        except: pass

        # 키워드 관련성 점수 계산 (질문 키워드가 얼마나 관련 있는지)
        def relevance(text):
            return sum(1 for kw in keywords if kw in str(text))

        # 정렬
        ctx["confirmed_facts"].sort(key=lambda x: relevance(x.get("content","")), reverse=True)
        ctx["analysis"].sort(key=lambda x: relevance(x.get("detail","")+x.get("title","")), reverse=True)

    # ── 3. 강화 프롬프트 생성 ──
    cat_map = {'urgent':'🚨 긴급','civil':'⚖️ 민사','criminal':'🔒 형사',
               'content':'📱 콘텐츠','contract':'📄 계약','etc':'💬 기타'}
    urg_map = {'emergency':'🔴 긴급','high':'🟠 높음','mid':'🟡 보통','low':'🟢 낮음'}

    prompt_parts = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "보배 법률전략실 — 사건 기반 AI 법률 상담",
        f"카테고리: {cat_map.get(category,'기타')} | 긴급도: {urg_map.get(urgency,'보통')}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"[질문]\n{question}",
        ""
    ]

    # 사건 맥락 추가
    if ctx["cases"]:
        prompt_parts.append("[현재 진행 중인 사건]")
        for c in ctx["cases"][:2]:
            prompt_parts.append(f"• {c.get('name','')} — {c.get('status','')} / {c.get('next','')}")
        prompt_parts.append("")

    # 확정 사실 추가
    if ctx["confirmed_facts"]:
        prompt_parts.append("[확정된 사실관계]")
        for f in ctx["confirmed_facts"][:4]:
            prompt_parts.append(f"• {f.get('content','')} (출처: {f.get('source','')})")
        prompt_parts.append("")

    # 분석 결과 추가
    if ctx["analysis"]:
        prompt_parts.append("[기존 분석 결과]")
        for a in ctx["analysis"][:2]:
            prompt_parts.append(f"• [{a.get('team','')}] {a.get('title','')}: {a.get('detail','')[:100]}...")
        prompt_parts.append("")

    # 모니터링 이슈
    if ctx["monitoring"]:
        prompt_parts.append("[현재 모니터링 위험 항목]")
        for m in ctx["monitoring"][:3]:
            prompt_parts.append(f"• [{m.get('risk','').upper()}] {m.get('platform','')} — {m.get('title','')[:60]}")
        prompt_parts.append("")

    prompt_parts += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "위 질문과 사건 맥락을 바탕으로 10항목 분석해줘:",
        "",
        "1. 상황 요약 (3줄 이내)",
        "2. 법적 위험 (형사·민사 리스크, 최악 시나리오)",
        "3. 즉시 금지 행동 (줄바꿈으로 나열)",
        "4. 허용 행동 (줄바꿈으로 나열)",
        "5. 증거 보존 필요 여부 (예 또는 아니오)",
        "6. 연결 필요 부서",
        "7. 변호사 확인 필요 여부 (예 또는 아니오)",
        "8. 최종 추천 (지금 이 순간 가장 좋은 선택 1가지)",
        "9. AI 신뢰도 (첫 줄: 숫자, 이후: 근거들)",
        "10. 근거 출처 (법령명+조항/판례번호)",
        "",
        "⚠️ AI 법률 보조 시스템. 최종 판단은 변호사 검토 필요.",
        "참고: law.go.kr / glaw.scourt.go.kr"
    ]

    enhanced_prompt = "\n".join(prompt_parts)

    # ── 4. Claude API 직접 호출 (선택) ──
    ai_answer = None
    api_error = None

    if use_api:
        # API 키 확인
        api_key = ""
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    if line.startswith('ANTHROPIC_API_KEY='):
                        api_key = line.split('=',1)[1].strip()

        if not api_key:
            api_error = "ANTHROPIC_API_KEY가 .env에 없습니다"
        else:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",   # 비용 절감: haiku 사용
                    max_tokens=2000,
                    system=(
                        "당신은 보배 법률전략실의 AI 법률 보조 시스템입니다. "
                        "스트리머·유튜버·BJ·인플루언서의 법적 리스크를 전담합니다. "
                        "실제 변호사가 아니며 최종 법률판단은 변호사 검토가 필요합니다. "
                        "답변은 10항목 구조로 명확하게 제공합니다."
                    ),
                    messages=[{"role": "user", "content": enhanced_prompt}]
                )
                ai_answer = msg.content[0].text
            except ImportError:
                api_error = "anthropic 라이브러리 없음 — pip install anthropic"
            except Exception as e:
                api_error = str(e)[:200]

    return {
        "ok": True,
        "keywords": keywords,
        "context": {
            "cases_count":      len(ctx["cases"]),
            "facts_count":      len(ctx["confirmed_facts"]),
            "analysis_count":   len(ctx["analysis"]),
            "monitoring_count": len(ctx["monitoring"])
        },
        "context_detail": ctx,
        "enhanced_prompt": enhanced_prompt,
        "ai_answer": ai_answer,
        "api_error": api_error,
        "api_used": use_api and ai_answer is not None
    }


class Handler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path in API_MAP:
            self._send_json(self._read(API_MAP[self.path]))
        elif self.path == '/api/scheduler':
            self._send_json(handle_scheduler_get())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path in API_MAP:
            n    = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            self._write(API_MAP[self.path], body)
            self._send_json({'ok': True})
        elif self.path == '/api/scheduler/action':
            n    = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            self._send_json(handle_scheduler_action(body))
        elif self.path == '/api/consult':
            n    = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            try:
                self._send_json(handle_consult(body))
            except Exception as e:
                import traceback
                self._send_json({'ok': False, 'error': str(e), 'trace': traceback.format_exc()[:500]})
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self, path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _write(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = 8080
    print('================================================')
    print('  보배 법률전략실 서버 시작')
    print('================================================')
    print(f'  대시보드    -> http://localhost:{port}/상담실.html')
    print(f'  스케줄러    -> http://localhost:{port}/스케줄러.html')
    print(f'  업데이터    -> http://localhost:{port}/업데이터.html')
    print('================================================')
    print('  종료: Ctrl+C')
    print('================================================')
    try:
        HTTPServer(('', port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('서버 종료.')
        if _scheduler_proc:
            _scheduler_proc.terminate()
