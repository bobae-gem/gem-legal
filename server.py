#!/usr/bin/env python3
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from http.server import HTTPServer, SimpleHTTPRequestHandler

DATA_FILE       = 'dashboard_data.json'
PENDING_FILE    = 'dashboard_pending.json'
LOG_FILE        = 'dashboard_log.json'
MONITORING_FILE = 'raw_monitoring.json'
CLASS_FILE      = 'monitoring_classifications.json'

API_MAP = {
    '/api/data':            DATA_FILE,
    '/api/pending':         PENDING_FILE,
    '/api/log':             LOG_FILE,
    '/api/monitoring':      MONITORING_FILE,
    '/api/classifications': CLASS_FILE,
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
        else:
            super().do_GET()

    def do_POST(self):
        if self.path in API_MAP:
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            self._write(API_MAP[self.path], body)
            self._send_json({'ok': True})

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
    print(f'  메인 상황실  -> http://localhost:{port}/상황실.html')
    print(f'  업데이터     -> http://localhost:{port}/업데이터.html')
    print(f'  사건 관리실  -> http://localhost:{port}/사건.html')
    print(f'  콘텐츠 검수  -> http://localhost:{port}/검수실.html')
    print(f'  리서치 센터  -> http://localhost:{port}/리서치.html')
    print(f'  메모리 관리  -> http://localhost:{port}/메모리.html')
    print('================================================')
    print('  종료: Ctrl+C')
    print('================================================')
    try:
        HTTPServer(('', port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('서버 종료.')
