"""
bt-logger CLI — 日志收集、解析、分析命令行工具

用法:
    bt-logger start <device_id>              # 开启 HCI 日志
    bt-logger stop <device_id>               # 停止 HCI 日志
    bt-logger pull <device_id> [output]      # 拉取 HCI 日志
    bt-logger parse <file>                   # 解析日志文件
    bt-logger analyze <file>                 # 分析日志文件
    bt-logger quick <device_id> <秒数>        # 一键采集+分析
    bt-logger list                           # 列出本地日志文件
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    import typer
    TYPER_AVAILABLE = True
    from typing import Optional

    from modules.logger import LoggerManager
    from core.models import LogLevel

    app = typer.Typer()
    logger_mgr = LoggerManager()

except ImportError as e:
    TYPER_AVAILABLE = False
    print(f"警告: 导入依赖项失败: {e}")


@app.command()
def start(device_id: str):
    """开启设备 HCI 日志采集"""
    try:
        from modules.adb.manager import ADBManager
        adb = ADBManager()
        logger_mgr.set_adb_manager(adb)

        if logger_mgr.start_hci_log(device_id):
            typer.echo(f"✅ HCI 日志已开启: {device_id}")
        else:
            typer.echo(f"❌ 开启失败: {device_id}")
    except Exception as e:
        typer.echo(f"❌ 错误: {e}")


@app.command()
def stop(device_id: Optional[str] = None):
    """停止设备 HCI 日志采集"""
    try:
        from modules.adb.manager import ADBManager
        adb = ADBManager()
        logger_mgr.set_adb_manager(adb)

        if logger_mgr.stop_hci_log(device_id):
            typer.echo(f"✅ HCI 日志已停止")
        else:
            typer.echo(f"❌ 停止失败")
    except Exception as e:
        typer.echo(f"❌ 错误: {e}")


@app.command()
def pull(device_id: str, output: Optional[str] = None):
    """拉取设备 HCI 日志到本地"""
    try:
        from modules.adb.manager import ADBManager
        adb = ADBManager()
        logger_mgr.set_adb_manager(adb)

        path = logger_mgr.pull_hci_log(device_id, output)
        if path:
            size = os.path.getsize(path)
            typer.echo(f"✅ 日志已拉取: {path} ({size} bytes)")
        else:
            typer.echo(f"❌ 拉取失败")
    except Exception as e:
        typer.echo(f"❌ 错误: {e}")


@app.command()
def parse(file: str):
    """解析日志文件并输出摘要"""
    if not os.path.exists(file):
        typer.echo(f"❌ 文件不存在: {file}")
        raise typer.Exit(1)

    typer.echo(f"解析日志: {file}")
    typer.echo("-" * 50)

    result = logger_mgr.parse_hci_log(file) \
        if open(file, 'rb').read(8) == b'btsnoop\x00' \
        else logger_mgr.parse_module_log(file)

    typer.echo(f"日志类型: {result.log_type}")
    typer.echo(f"总条目数: {len(result.entries)}")
    typer.echo(f"错误数:   {result.error_count}")
    typer.echo(f"关键事件: {len(result.key_events)}")
    typer.echo("")

    if result.key_events:
        typer.echo("关键事件:")
        for evt in result.key_events[:20]:
            ts = evt.timestamp.strftime('%H:%M:%S') if evt.timestamp else '--:--:--'
            typer.echo(f"  [{ts}] {evt.event_type}: {evt.details}")
        if len(result.key_events) > 20:
            typer.echo(f"  ... 还有 {len(result.key_events)-20} 条")

    if result.entries and result.error_count > 0:
        typer.echo(f"\n前 10 条错误:")
        count = 0
        for entry in result.entries:
            if count >= 10:
                break
            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                typer.echo(f"  [{entry.level.value}] {entry.message[:120]}")
                count += 1


@app.command()
def analyze(file: str):
    """分析日志并生成分析报告"""
    if not os.path.exists(file):
        typer.echo(f"❌ 文件不存在: {file}")
        raise typer.Exit(1)

    typer.echo(f"分析日志: {file}")
    typer.echo("-" * 50)

    analysis = logger_mgr.analyze_log('btsnoop' if open(file, 'rb').read(8) == b'btsnoop\x00' else 'text', file)

    stats = analysis.statistics
    typer.echo(f"总条目:   {stats.total_entries}")
    typer.echo(f"错误:     {stats.error_count}")
    typer.echo(f"警告:     {stats.warning_count}")
    typer.echo(f"信息:     {stats.info_count}")
    typer.echo(f"调试:     {stats.debug_count}")

    if analysis.key_events:
        typer.echo(f"\n关键事件 ({len(analysis.key_events)} 条):")
        for evt in analysis.key_events[:15]:
            ts = evt.timestamp.strftime('%H:%M:%S') if evt.timestamp else '--:--:--'
            typer.echo(f"  [{ts}] {evt.event_type}: {evt.details}")

    if analysis.errors:
        typer.echo(f"\n错误 ({len(analysis.errors)} 条, 前 20):")
        for err in analysis.errors[:20]:
            typer.echo(f"  [{err.level.value}] {err.message[:120]}")

    # 导出报告
    report_path = logger_mgr.export_analysis(analysis)
    if report_path:
        typer.echo(f"\n分析报告已导出: {report_path}")


@app.command()
def quick(device_id: str, duration: int = 10):
    """一键采集+分析：开启日志 → 等待 → 停止 → 拉取 → 分析"""
    try:
        from modules.adb.manager import ADBManager
        adb = ADBManager()
        logger_mgr.set_adb_manager(adb)

        typer.echo(f"一键采集分析: {device_id}, {duration}秒")
        report = logger_mgr.collect_and_analyze(device_id, duration)

        if report:
            typer.echo(f"✅ 分析报告: {report}")
            with open(report, 'r', encoding='utf-8') as f:
                typer.echo(f.read())
        else:
            typer.echo("❌ 采集分析失败")
    except Exception as e:
        typer.echo(f"❌ 错误: {e}")


@app.command()
def list():
    """列出本地日志文件"""
    files = logger_mgr.list_log_files()
    if not files:
        typer.echo("没有本地日志文件")
        return

    typer.echo(f"{'文件名':<40} {'大小':>8} {'修改时间'}")
    typer.echo("-" * 68)
    for f in files:
        mod = f['modified'].strftime('%m-%d %H:%M')
        typer.echo(f"{f['name']:<40} {f['size_str']:>8} {mod}")
    typer.echo(f"\n共 {len(files)} 个文件")


@app.command()
def delete(file_name: str):
    """删除日志文件"""
    if logger_mgr.delete_log_file(file_name):
        typer.echo(f"✅ 已删除: {file_name}")
    else:
        typer.echo(f"❌ 删除失败: {file_name}")


if __name__ == "__main__":
    if TYPER_AVAILABLE:
        app()
