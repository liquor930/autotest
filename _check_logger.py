"""bt-logger 模块快速验证（无 emoji 版）"""
import ast, os, sys

print("=== Syntax Check ===")
files = [
    'modules/logger/__init__.py', 'modules/logger/logger_manager.py',
    'modules/logger/hci_parser.py', 'modules/logger/btsnoop.py',
    'cli/bt_logger/__init__.py', 'cli/bt_logger/cli.py',
]
ok = fail = 0
for f in files:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        ok += 1
        print(f'  PASS: {f}')
    except SyntaxError as e:
        fail += 1
        print(f'  FAIL: {f} line {e.lineno}: {e.msg}')
print(f'\nSyntax: {ok}/{ok+fail} passed')

if fail:
    sys.exit(1)

print("\n=== Functional Tests ===")
from modules.logger import HciLogParser, LoggerManager
from modules.logger.btsnoop import BtsnoopParser
from core import LogEntry, LogLevel
import subprocess

parser = HciLogParser()
r = parser.parse('_nonexistent_.log', 'text')
assert r.error_count == 1, "Missing file should error"
print('PASS: HciLogParser handles missing file')

b = BtsnoopParser()
r2 = b.parse('_nonexistent_.btsnoop')
assert r2.error_count == 1, "Missing btsnoop should error"
print('PASS: BtsnoopParser handles missing file')

mgr = LoggerManager()
try:
    mgr.start_hci_log('test')
    assert False, "Should raise"
except RuntimeError:
    print('PASS: LoggerManager raises without ADB')

files = mgr.list_log_files()
assert isinstance(files, list)
print(f'PASS: list_log_files returns {len(files)} files')

analysis = parser.analyze(r)
path = mgr.export_analysis(analysis)
assert path and os.path.exists(path), "Export should create file"
print(f'PASS: export_analysis creates {path}')
mgr.delete_log_file(os.path.basename(path))

py = r'C:\Users\36272\AppData\Local\Programs\Python\Python312\python.exe'
result = subprocess.run([py, '-m', 'cli.bt_logger.cli', 'list'], capture_output=True, text=True)
assert result.returncode == 0, f"CLI failed: {result.stderr}"
print('PASS: bt-logger list runs')

result2 = subprocess.run([py, '-m', 'cli.bt_logger.cli', '--help'], capture_output=True, text=True)
assert result2.returncode == 0, "CLI --help failed"
print('PASS: bt-logger --help shows usage')

print("\n=== ALL TESTS PASSED ===")
