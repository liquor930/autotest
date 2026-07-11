"""
bt-test CLI — 测试执行命令工具

通过核心引擎的 TestManager 实现测试会话的全生命周期管理。

用法:
    bt-test run <config>              # 运行测试（从配置文件）
    bt-test run --name <name>         # 快速运行（默认用例）
    bt-test stop <session_id>         # 停止会话
    bt-test pause <session_id>        # 暂停会话
    bt-test resume <session_id>       # 恢复会话
    bt-test status [session_id]       # 查看状态
    bt-test list                      # 列出所有会话
    bt-test report <session_id>       # 生成报告
    bt-test config <file>             # 验证配置文件
    bt-test cleanup <session_id>      # 清理会话
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    import typer
    from typing import Optional
    from datetime import datetime

    from core import TestManager, SessionStatus, EventBus
    from core.test_manager import TestManager as TM

    app = typer.Typer()
    tm = TM()

except ImportError as e:
    print(f"Error: {e}")
    print("Run: pip install typer")
    sys.exit(1)


@app.command()
def run(
    config: Optional[str] = typer.Argument(None, help="配置文件路径 (.yaml/.json)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="测试名称"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="测试描述"),
    device: Optional[str] = typer.Option(None, "--device", help="指定设备ID"),
    max_workers: int = typer.Option(4, "--workers", "-w", help="最大并发数"),
):
    """运行测试"""
    from core import TestConfig

    session_id = None

    if config:
        if not os.path.exists(config):
            typer.echo(f"Error: 配置文件不存在: {config}")
            raise typer.Exit(1)
        session_id = tm.create_session(config_file=config)
        typer.echo(f"Loaded config: {config}")
    else:
        # 创建默认测试
        test_config = TestConfig(
            name=name or f"QuickTest_{datetime.now().strftime('%H%M%S')}",
            description=description or "",
            max_workers=max_workers,
        )
        if device:
            test_config.devices = [device]
        session_id = tm.create_session(config=test_config,
                                       name=test_config.name,
                                       description=test_config.description)

    if not session_id:
        typer.echo("Error: 创建会话失败")
        raise typer.Exit(1)

    typer.echo(f"Session created: {session_id}")
    typer.echo(f"Starting test: {tm._get_session(session_id).name}")

    if tm.start_test(session_id):
        typer.echo("Test started.")
        typer.echo(f"Use: bt-test status {session_id}")
        typer.echo(f"Use: bt-test report {session_id}")
    else:
        typer.echo("Error: 启动测试失败")
        raise typer.Exit(1)


@app.command()
def stop(session_id: str):
    """停止测试会话"""
    if tm.stop_test(session_id):
        typer.echo(f"Session {session_id} stopped.")
    else:
        typer.echo(f"Error: 停止会话 {session_id} 失败")


@app.command()
def pause(session_id: str):
    """暂停测试"""
    if tm.pause_test(session_id):
        typer.echo(f"Session {session_id} paused.")
    else:
        typer.echo(f"Error: 暂停会话 {session_id} 失败")


@app.command()
def resume(session_id: str):
    """恢复暂停的测试"""
    if tm.resume_test(session_id):
        typer.echo(f"Session {session_id} resumed.")
    else:
        typer.echo(f"Error: 恢复会话 {session_id} 失败")


@app.command()
def status(session_id: Optional[str] = typer.Argument(None, help="会话ID，不指定则显示所有")):
    """查看测试状态"""
    if session_id:
        s = tm.get_session_status(session_id)
        if not s:
            typer.echo(f"Session {session_id} not found.")
            raise typer.Exit(1)

        session = tm._get_session(session_id)
        typer.echo(f"Session:   {session_id[:16]}...")
        typer.echo(f"Name:      {session.name if session else '-'}")
        typer.echo(f"Status:    {s.status.value}")
        typer.echo(f"Progress:  {s.progress:.1f}%")
        typer.echo(f"Elapsed:   {s.elapsed_time}s")
        typer.echo(f"Remaining: {s.remaining_time}s")
        if s.current_case:
            typer.echo(f"Current:   {s.current_case}")
    else:
        sessions = tm.list_sessions()
        if not sessions:
            typer.echo("No sessions found.")
            return
        typer.echo(f"{'Session ID':<20} {'Name':<20} {'Status':<12} {'Progress':<10} {'Cases':<8}")
        typer.echo("-" * 70)
        for s in sessions:
            sid = s.session_id[:16]
            name = s.name[:18] if s.name else "-"
            typer.echo(f"{sid:<20} {name:<20} {s.status.value:<12} {s.progress:<10.1f} {s.total_cases:<8}")


@app.command()
def list():
    """列出所有测试会话"""
    sessions = tm.list_sessions()
    if not sessions:
        typer.echo("No sessions found.")
        return

    typer.echo(f"{'Session ID':<20} {'Name':<25} {'Status':<12} {'Progress':<10} {'Pass/Fail'}")
    typer.echo("-" * 80)
    for s in sessions:
        sid = s.session_id[:16]
        name = (s.name or "-")[:23]
        pf = f"{s.passed}/{s.failed}"
        typer.echo(f"{sid:<20} {name:<25} {s.status.value:<12} {s.progress:<10.1f} {pf}")


@app.command()
def report(session_id: str, output: Optional[str] = typer.Option(None, "--output", "-o", help="输出路径")):
    """生成测试报告"""
    from core.result_manager import ResultManager
    rm = ResultManager()

    path = rm.generate_report(session_id, "html")
    if output and path != output:
        import shutil
        shutil.copy2(path, output)
        typer.echo(f"Report saved: {output}")
    else:
        typer.echo(f"Report generated: {path}")


@app.command()
def config(file: str):
    """验证测试配置文件"""
    if not os.path.exists(file):
        typer.echo(f"Error: 文件不存在: {file}")
        raise typer.Exit(1)

    cfg = tm._load_config(file)
    if cfg is None:
        typer.echo(f"Error: 配置文件解析失败: {file}")
        raise typer.Exit(1)

    typer.echo(f"Config:     {cfg.name}")
    typer.echo(f"Description: {cfg.description}")
    typer.echo(f"Test cases: {len(cfg.test_cases)}")
    typer.echo(f"Devices:    {len(cfg.devices)}")
    typer.echo(f"Max workers: {cfg.max_workers}")
    typer.echo(f"Report fmt: {cfg.report_format}")
    typer.echo("Config is valid.")


@app.command()
def cleanup(session_id: str):
    """清理会话数据"""
    if tm.cleanup_session(session_id):
        typer.echo(f"Session {session_id} cleaned up.")
    else:
        typer.echo(f"Error: 清理会话 {session_id} 失败")


if __name__ == "__main__":
    app()
