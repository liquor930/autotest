"""
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
        typer.echo(f"\nDone: {passed}/{len(results)} passed")
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
    typer.echo("Interactive mode. Type AT commands, 'exit' to quit.\n---")
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
    typer.echo("\n---\nExited")


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
