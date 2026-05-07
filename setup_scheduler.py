#!/usr/bin/env python3
"""
Windows 작업 스케줄러 자동 등록 스크립트
보배 법률전략실 서버 및 모니터링 자동 시작

사용법:
  python setup_scheduler.py install          # 서버 + 모니터링 자동 시작 등록
  python setup_scheduler.py install --server # 서버만 등록
  python setup_scheduler.py enable           # 작업 활성화
  python setup_scheduler.py disable          # 작업 비활성화
  python setup_scheduler.py remove           # 작업 제거
  python setup_scheduler.py status           # 현재 상태 확인
"""
import sys, os, subprocess

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE  = sys.executable
SERVER_TASK = 'BobaeServer'
MONITOR_TASK= 'BobaeMonitor'

def run(cmd, capture=True):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=capture,
                           text=True, encoding='utf-8', errors='replace')
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, '', str(e)

def install(server_only=False):
    start_script = os.path.join(BASE_DIR, 'start_all.py')
    flag = '' if server_only else ' --monitor'

    print('[1] 서버 작업 등록 중...')
    cmd_server = (
        f'schtasks /Create /F /TN "{SERVER_TASK}" '
        f'/TR "\\"{PYTHON_EXE}\\" -X utf8 \\"{start_script}\\"{flag}" '
        f'/SC ONLOGON /DELAY 0001:00 /RL HIGHEST'
    )
    code, out, err = run(cmd_server)
    if code == 0:
        print(f'  [OK] {SERVER_TASK} 등록 완료')
        print(f'  시작: {PYTHON_EXE} {start_script}{flag}')
        print(f'  트리거: 로그인 시 자동 시작 (1분 지연)')
    else:
        print(f'  [FAIL] {SERVER_TASK} 등록 실패')
        print(f'  오류: {err or out}')
        print('  → 관리자 권한으로 실행하세요: 우클릭 → 관리자로 실행')
        return

    if not server_only:
        print()
        print('[2] 모니터링 작업 등록 중 (매일 오전 9시)...')
        mon_script = os.path.join(BASE_DIR, 'monitoring_system', 'main.py')
        cmd_monitor = (
            f'schtasks /Create /F /TN "{MONITOR_TASK}" '
            f'/TR "\\"{PYTHON_EXE}\\" -X utf8 \\"{mon_script}\\"" '
            f'/SC DAILY /ST 09:00 /RL HIGHEST'
        )
        code, out, err = run(cmd_monitor)
        if code == 0:
            print(f'  [OK] {MONITOR_TASK} 등록 완료 (매일 09:00 자동 수집)')
        else:
            print(f'  [WARN] {MONITOR_TASK} 등록 실패: {err or out}')

    print()
    print('[완료] 다음 로그인부터 서버가 자동으로 시작됩니다.')
    print(f'  확인: http://localhost:8080/상담실.html')

def enable():
    for task in [SERVER_TASK, MONITOR_TASK]:
        code, _, err = run(f'schtasks /Change /TN "{task}" /Enable')
        print(f'  [{"OK" if code==0 else "FAIL"}] {task} 활성화')

def disable():
    for task in [SERVER_TASK, MONITOR_TASK]:
        code, _, err = run(f'schtasks /Change /TN "{task}" /Disable')
        print(f'  [{"OK" if code==0 else "FAIL"}] {task} 비활성화')

def remove():
    if input('작업을 제거하시겠습니까? (y/n): ').lower() != 'y':
        print('취소됨')
        return
    for task in [SERVER_TASK, MONITOR_TASK]:
        code, _, _ = run(f'schtasks /Delete /TN "{task}" /F')
        print(f'  [{"OK" if code==0 else "없음"}] {task} 제거')

def status():
    print('=== Windows 작업 스케줄러 상태 ===')
    for task in [SERVER_TASK, MONITOR_TASK]:
        code, out, _ = run(f'schtasks /Query /TN "{task}" /FO LIST 2>&1')
        if code == 0:
            lines = [l for l in out.splitlines() if any(k in l for k in ['작업 이름','상태','마지막 실행','다음 실행','TaskName','Status','Last Run','Next Run'])]
            print(f'\n[{task}]')
            for l in lines[:6]: print(f'  {l.strip()}')
        else:
            print(f'\n[{task}] 미등록')

    print()
    print('=== 수동 실행 명령어 ===')
    print(f'  서버만:          python start_all.py')
    print(f'  서버+스케줄러:   python start_all.py --monitor')
    print(f'  1회 수집:        python start_all.py --once')

if __name__ == '__main__':
    args = sys.argv[1:]
    cmd  = args[0] if args else 'status'

    print('=' * 55)
    print('  보배 법률전략실 — 작업 스케줄러 관리')
    print('=' * 55)

    if cmd == 'install':
        install(server_only='--server' in args)
    elif cmd == 'enable':
        enable()
    elif cmd == 'disable':
        disable()
    elif cmd == 'remove':
        remove()
    else:
        status()
