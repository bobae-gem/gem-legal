#!/usr/bin/env python3
import sys, os, json, subprocess, signal
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
