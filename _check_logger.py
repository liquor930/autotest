"""bt-logger 模块语法检查 + 功能验证"""
import ast, os, sys

print("=" * 50)
print("bt-logger 语法检查 + 功能验证")
print("=" * 50)

# 1. 语法检查
files = [
    'modules/logger/__init__.py',
    'modules/logger/logger_manager.py',
    'modules/logger/hci_parser.py',
    'modules/logger/btsnoop.py',
    'cli/bt_logger/__init__.py',
    'cli/bt_logger/cli.py',
]
ok = fail = 0
for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        ok += 1
        print(f'  ✅ {f}')
    except SyntaxError as e:
        fail += 1
        print(f'  ❌ {f} line {e.lineno}: {e.msg}')

print(f'\n语法: {ok}/{ok+fail} 通过')

if fail > 0:
    sys.exit(1)

# 2. 功能验证
print('\n--- 功能验证 ---\n')

# HciLogParser: 无文件时优雅降级
from modules.logger import HciLogParser
parser = HciLogParser()
result = parser.parse('nonexistent.log', 'text')
assert result.error_count == 1, 'Missing file should have error_count=1'
print('✅ HciLogParser.parse(nonexistent): 错误计数正确')

# Quick analyze nonexistent btsnoop
from modules.logger.btsnoop import BtsnoopParser
btsnoop = BtsnoopParser()
r = btsnoop.parse('nonexistent.btsnoop')
assert r.error_count == 1
print('✅ BtsnoopParser.parse(nonexistent): 错误计数正确')

# LoggerManager: no ADB manager
from modules.logger import LoggerManager
mgr = LoggerManager()
try:
    mgr.start_hci_log('test')
    print('❌ start_hci_log without adb should raise')
except RuntimeError as e:
    print(f'✅ LoggerManager.start_hci_log(no adb): {e}')

try:
    mgr.stop_hci_log('test')
    print('❌ stop_hci_log without adb should raise')
except RuntimeError as e:
    print(f'✅ LoggerManager.stop_hci_log(no adb): {e}')

# LoggerManager list files (empty dir)
files = mgr.list_log_files()
assert isinstance(files, list)
print(f'✅ LoggerManager.list_log_files(): {len(files)} files')

# Log export
analysis = parser.analyze(result)
path = mgr.export_analysis(analysis)
assert path is not None and os.path.exists(path)
print(f'✅ LoggerManager.export_analysis() → {path}')

# Log management
assert mgr.delete_log_file(os.path.basename(path)) == True
print('✅ LoggerManager.delete_log_file()')

# 3. Imports from core (should be compatible)
from core import (
    LogEntry, LogLevel, LogStatistics, KeyEvent,
    LogParserResult, LogAnalysisResult,
)
entry = LogEntry(level=LogLevel.INFO, message='test')
assert entry.level == LogLevel.INFO
print('✅ core models import compatible')

print('\n' + '=' * 50)
print('🎉 全部通过!')
print('=' * 50)
