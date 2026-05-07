#!/usr/bin/env python3
"""
보배 법률전략실 통합 시작 스크립트
서버 + 모니터링 스케줄러를 한 번에 시작

사용법:
  python start_all.py              # 서버만 시작 (기본)
  python start_all.py --monitor    # 서버 + 모니터링 스케줄러 함께 시작
  python start_all.py --once       # 서버 시작 + 모니터링 1회 실행
"""
import sys, os, threading, time, subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def start_server():
    """대시보드 서버 시작"""
    from server import Handler
    from http.server import HTTPServer
    port = 8080
    print(f'[SERVER] http://localhost:{port} 시작')
    try:
        HTTPServer(('', port), Handler).serve_forever()
    except OSError as e:
        print(f'[SERVER] 포트 {port} 이미 사용중: {e}')
        print('[SERVER] 기존 서버가 실행 중입니다.')

def start_monitoring_scheduler():
    """모니터링 스케줄러 시작 (별도 스레드)"""
    time.sleep(2)  # 서버 먼저 시작 대기
    mon_dir = os.path.join(BASE_DIR, 'monitoring_system')
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', 'main.py', '--schedule'],
            cwd=mon_dir,
            check=False
        )
    except Exception as e:
        print(f'[MONITOR] 스케줄러 오류: {e}')

def run_monitoring_once():
    """모니터링 1회만 실행"""
    mon_dir = os.path.join(BASE_DIR, 'monitoring_system')
    print('[MONITOR] 1회 실행 시작...')
    subprocess.run(
        [sys.executable, '-X', 'utf8', 'main.py'],
        cwd=mon_dir
    )
    print('[MONITOR] 1회 실행 완료')

if __name__ == '__main__':
    args = sys.argv[1:]

    print('=' * 55)
    print('  보배 법률전략실 시작')
    print('=' * 55)
    print(f'  대시보드: http://localhost:8080/상담실.html')
    print(f'  모드: {"스케줄러" if "--monitor" in args else "1회" if "--once" in args else "서버만"}')
    print('=' * 55)

    if '--monitor' in args:
        # 서버 + 스케줄러 동시 실행
        t = threading.Thread(target=start_monitoring_scheduler, daemon=True)
        t.start()
        print('[INFO] 모니터링 스케줄러가 백그라운드에서 시작됩니다')
        start_server()

    elif '--once' in args:
        # 서버 시작 + 모니터링 1회
        t = threading.Thread(target=run_monitoring_once, daemon=True)
        t.start()
        start_server()

    else:
        # 서버만
        start_server()
