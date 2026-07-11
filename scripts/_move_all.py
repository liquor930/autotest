"""Robust move: serial_control -> modules/serial + create CLI + update setup.py"""

import os, shutil, re

BASE = r'D:\code\AutoTest'

# 1. Create target dirs
os.makedirs(os.path.join(BASE, 'modules', 'serial', 'models'), exist_ok=True)
os.makedirs(os.path.join(BASE, 'modules', 'serial', 'utils'), exist_ok=True)
os.makedirs(os.path.join(BASE, 'cli', 'bt_serial'), exist_ok=True)

# 2. Copy files from serial_control to modules/serial
src_base = os.path.join(BASE, 'serial_control')
files_to_copy = [
    ('serial_manager.py', 'modules/serial/serial_manager.py'),
    ('models/command_result.py', 'modules/serial/models/command_result.py'),
    ('models/serial_status.py', 'modules/serial/models/serial_status.py'),
    ('models/__init__.py', 'modules/serial/models/__init__.py'),
    ('utils/logger.py', 'modules/serial/utils/logger.py'),
    ('utils/__init__.py', 'modules/serial/utils/__init__.py'),
    ('__init__.py', 'modules/serial/__init__.py'),
]

for rel_src, rel_dst in files_to_copy:
    src = os.path.join(src_base, rel_src)
    dst = os.path.join(BASE, rel_dst)
    if os.path.exists(src):
        content = open(src, encoding='utf-8').read()
        # Fix imports: from .models.xxx -> from modules.serial.models.xxx
        content = content.replace('from .models', 'from modules.serial.models')
        content = content.replace('from .utils', 'from modules.serial.utils')
        # Fix relative imports in __init__
        content = content.replace('from .serial_manager', 'from modules.serial.serial_manager')
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'COPY+IMPORT_FIX: {rel_dst}')
    else:
        print(f'MISSING: {rel_src}')

# 3. Create __init__.py for cli/bt_serial
with open(os.path.join(BASE, 'cli', 'bt_serial', '__init__.py'), 'w') as f:
    f.write('"""bt-serial CLI package"""\n')
print('CREATED: cli/bt_serial/__init__.py')

# 4. Create cli/bt_serial/cli.py
CLI_CODE = '''"""
bt-serial CLI - 串口设备控制命令工具

Commands:
  list                   列出可用串口
  connect <port> [baud]  连接串口
  disconnect             断开串口
  send <command>         发送AT指令
  sequence <file>        执行指令序列
  status                 获取串口状态
  interactive            进入交互模式
  log start|stop|export  日志管理
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import typer
from typing import Optional
from modules.serial.serial_manager import SerialManager

app = typer.Typer()
_mgr = SerialManager()


@app.command()
def list():
    """列出可用串口"""
    ports = SerialManager.list_ports()
    if not ports:
        typer.echo("No serial ports found")
        return
    typer.echo("Available serial ports:")
    for p in ports:
        typer.echo(f"  {p['port']:<20} {p['description']}")


@app.command()
def connect(port: str, baud: int = 115200):
    """连接串口设备"""
    try:
        if _mgr.connect(port, baud):
            typer.echo(f"Connected to {port} @ {baud} baud")
        else:
            typer.echo("Connection failed")
    except Exception as e:
        typer.echo(f"Error: {e}")


@app.command()
def disconnect():
    """断开串口连接"""
    _mgr.disconnect()
    typer.echo("Disconnected")


@app.command()
def send(command: str, timeout: float = 2.0):
    """发送AT指令并显示响应"""
    result = _mgr.send_command(command, timeout)
    typer.echo(f"TX: {result.command}")
    typer.echo(f"RX: {result.response}")
    typer.echo(f"Status: {'OK' if result.success else 'FAIL'} ({result.execution_time_ms:.0f}ms)")
    if result.error_message:
        typer.echo(f"Error: {result.error_message}")


@app.command()
def sequence(file: str):
    """执行AT指令序列文件"""
    if not os.path.exists(file):
        typer.echo(f"File not found: {file}")
        raise typer.Exit(1)
    def cb(step, total, r):
        s = 'OK' if r.success else 'FAIL'
        typer.echo(f"  [{step}/{total}] {r.command}: {s} ({r.execution_time_ms:.0f}ms)")
    try:
        results = _mgr.execute_sequence(file, cb)
        passed = sum(1 for r in results if r.success)
        typer.echo(f"\\nDone: {passed}/{len(results)} passed")
    except Exception as e:
        typer.echo(f"Error: {e}")


@app.command()
def status():
    """获取串口状态"""
    s = _mgr.get_status()
    typer.echo(f"Connected: {s.connected}")
    typer.echo(f"Port:      {s.port or '-'}")
    typer.echo(f"Baud rate: {s.baud_rate}")
    typer.echo(f"Bytes TX:  {s.bytes_sent}")
    typer.echo(f"Bytes RX:  {s.bytes_received}")
    if s.error_message:
        typer.echo(f"Error:     {s.error_message}")


@app.command()
def interactive():
    """进入交互命令模式"""
    typer.echo("Interactive mode. Type AT commands, 'exit' to quit.\\n---")
    try:
        while True:
            cmd = typer.prompt(">>>", prompt_suffix=" ")
            if cmd.lower() in ('exit', 'quit', 'q'):
                break
            if not cmd.strip():
                continue
            result = _mgr.send_command(cmd)
            resp = result.response if result.response else '(no response)'
            typer.echo(f"  {resp}")
    except (KeyboardInterrupt, EOFError):
        pass
    typer.echo("\\n---\\nExited")


@app.command()
def log(action: str, file: Optional[str] = None):
    """日志管理: start <file>, stop, export <file>"""
    if action == 'start':
        if not file:
            typer.echo("Usage: bt-serial log start <file>")
            return
        _mgr.start_logging(file)
        typer.echo(f"Logging started: {file}")
    elif action == 'stop':
        _mgr.stop_logging()
        typer.echo("Logging stopped")
    elif action == 'export':
        if not file:
            typer.echo("Usage: bt-serial log export <file>")
            return
        _mgr.export_log(file)
        typer.echo(f"Log exported: {file}")
    else:
        typer.echo("Action must be: start, stop, or export")


if __name__ == '__main__':
    app()
'''

with open(os.path.join(BASE, 'cli', 'bt_serial', 'cli.py'), 'w', encoding='utf-8') as f:
    f.write(CLI_CODE)
print('CREATED: cli/bt_serial/cli.py')

# 5. Update setup.py
sp = os.path.join(BASE, 'setup.py')
content = open(sp, encoding='utf-8').read()
if 'bt-serial' not in content:
    content = content.replace(
        '"bt-test=cli.bt_test.cli:app",',
        '"bt-serial=cli.bt_serial.cli:app",\n            "bt-test=cli.bt_test.cli:app",'
    )
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('UPDATED: setup.py (added bt-serial entry point)')
else:
    print('SKIPPED: setup.py (bt-serial already present)')

# 6. Clean up old serial_control dir
old_dir = os.path.join(BASE, 'serial_control')
if os.path.exists(old_dir):
    try:
        shutil.rmtree(old_dir, ignore_errors=True)
        print('REMOVED: serial_control/')
    except Exception as e:
        print(f'FAILED to remove serial_control/: {e}')

# 7. Clean up temp files
for f in ['_app_design.txt', '_app_files.txt', '_app_review.txt', '_apply_fixes.py',
          '_fix_result.txt', '_dump_serial.py', '_find_serial.py', '_git_done.txt',
          '_ser_find.txt', '_ser_list.txt', '_ser_list2.txt', '_ser_report.txt',
          '_serial_code.txt', '_check_result.txt', '_check_syntax.py', '_check_logger.py',
          '_check_test_cli.py', '_cli_result.txt', '_cli_test_help.txt', '_e.txt',
          '_git_commit.py', '_git_status_now.txt', '_log_result.txt', '_move_serial.py',
          '_result_logger.txt', '_result.txt']:
    fp = os.path.join(BASE, f)
    if os.path.exists(fp):
        os.remove(fp)
print('CLEANED: temp files')

print('\\nALL DONE')
