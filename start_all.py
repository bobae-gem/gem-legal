#!/usr/bin/env python3
"""
보배 법률전략실 통합 시작 스크립트
서버 + 모니터링 스케줄러를 한 번에 시작

사용법:
  python start_all.py              # 서버만 시작 (기본)
  python start_all.py --monitor    # 서버 + 모니터링 스케줄러 함께 시작
  python start_all.py --once       # 서버 시작 + 모니터링 1회 실행
  python start_all.py --service-info  # Windows 서비스/자동시작 설정 안내
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

    if '--service-info' in args:
        print()
        print('=== Windows 자동시작 설정 방법 ===')
        print()
        print('[방법 1] 작업 스케줄러 (권장)')
        print('  → python setup_scheduler.py install')
        print('  → 로그인 시 자동으로 서버가 시작됩니다')
        print()
        print('[방법 2] 시작 프로그램 폴더에 등록')
        print(f'  1. Win+R → shell:startup 입력')
        print(f'  2. 아래 내용으로 .bat 파일 생성:')
        print()
        print(f'     @echo off')
        print(f'     cd /d "{BASE_DIR}"')
        print(f'     start "" "{sys.executable}" -X utf8 start_all.py --monitor')
        print()
        print('[방법 3] NSSM (Windows 서비스 등록, 고급)')
        print('  1. https://nssm.cc 에서 nssm.exe 다운로드')
        print(f'  2. nssm install BobaeServer "{sys.executable}"')
        print(f'  3. nssm set BobaeServer AppParameters "-X utf8 {os.path.join(BASE_DIR, "start_all.py")} --monitor"')
        print(f'  4. nssm set BobaeServer AppDirectory "{BASE_DIR}"')
        print(f'  5. nssm start BobaeServer')
        print()
        print('[현재 권장]')
        print('  python setup_scheduler.py install  ← 가장 간단')

    elif '--monitor' in args:
        t = threading.Thread(target=start_monitoring_scheduler, daemon=True)
        t.start()
        print('[INFO] 모니터링 스케줄러가 백그라운드에서 시작됩니다')
        start_server()

    elif '--once' in args:
        t = threading.Thread(target=run_monitoring_once, daemon=True)
        t.start()
        start_server()

    else:
        start_server()
