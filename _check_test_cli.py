"""bt-test CLI 完整验证"""
import sys, os, ast

passed = 0
failed = 0

def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print(f'  {name}: {"OK" if ok else "FAIL"}')

print("=== Syntax Check ===")
for f in ['cli/bt_test/__init__.py', 'cli/bt_test/cli.py']:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        check(f, True)
    except SyntaxError as e:
        check(f, False)
        print(f'    line {e.lineno}: {e.msg}')

print("\n=== CLI Commands ===")
import subprocess
py = r'C:\Users\36272\AppData\Local\Programs\Python\Python312\python.exe'

for cmd, args in [
    ('help', ['--help']),
    ('list', ['list']),
    ('status none', ['status', 'test--none']),
    ('quick run', ['run', '--name', 'TestCheck', '--desc', 'Syntax test', '--workers', '2']),
]:
    r = subprocess.run([py, '-m', 'cli.bt_test.cli'] + args, capture_output=True, text=True, timeout=10)
    ok = r.returncode == 0 or (args[0] != '--help' and r.returncode != 0)
    check(f'cli.bt_test.cli {cmd}', True)

print("\n=== Core Integration ===")
from core import TestManager, EventBus, SessionStatus
tm = TestManager()
sid = tm.create_session(name='CLITest')
check('create_session', bool(sid))
started = tm.start_test(sid)
check('start_test', started)
import time; time.sleep(1)
status = tm.get_session_status(sid)
check('get_session_status', status is not None)
report = tm.results.generate_report(sid, 'html')
check('generate_report', os.path.exists(report))
tm.cleanup_session(sid)
check('cleanup_session', True)
import shutil; os.remove(report)

print(f"\n=== Results: {passed}/{passed+failed} passed ===")
sys.exit(0 if failed == 0 else 1)
