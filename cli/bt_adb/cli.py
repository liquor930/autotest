"""ADB控制模块CLI接口"""

import sys
import os

# 添加项目根目录到Python搜索路径，确保在开发模式下也能找到模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    import typer
    TYPER_AVAILABLE = True
    from typing import Optional
    
    from modules.adb.manager import ADBManager
    
    app = typer.Typer()
    adb_manager = ADBManager()
except ImportError as e:
    TYPER_AVAILABLE = False
    print(f"警告: 导入依赖项失败: {e}")
    print("请运行: pip install typer")


@app.command()
def list():
    """列出所有可连接的设备"""
    devices = adb_manager.list_devices()
    if not devices:
        typer.echo("没有找到可连接的设备")
        return
    
    typer.echo("可连接的设备:")
    for device in devices:
        if device.status == "PERMISSION_ERROR":
            typer.echo(f"- {device.device_id} (状态: {device.status} - 请以管理员权限运行命令，或检查USB驱动程序)")
        else:
            typer.echo(f"- {device.device_id} ({device.model}, Android {device.version}, 状态: {device.status})")


@app.command(context_settings={"allow_extra_args": True})
def pair(ctx: typer.Context):
    """使用配对码配对设备（Android 11+），支持 IP:端口 格式"""
    import re
    import subprocess
    
    args = ctx.args
    
    if len(args) < 1:
        typer.echo("用法: bt-adb pair <IP:端口> [配对码]")
        return
    
    address = args[0]
    code = args[1] if len(args) > 1 else None
    
    ip = address
    port = 30025
    
    if ':' in address:
        match = re.match(r'^([\d\.]+):(\d+)$', address)
        if match:
            ip = match.group(1)
            port = int(match.group(2))
    
    try:
        cmd = ['adb', 'pair', f'{ip}:{port}']
        if code:
            cmd.append(code)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30
        )
        
        try:
            stdout = result.stdout.decode('utf-8', errors='ignore')
        except:
            try:
                stdout = result.stdout.decode('gbk', errors='ignore')
            except:
                stdout = str(result.stdout)
        
        try:
            stderr = result.stderr.decode('utf-8', errors='ignore')
        except:
            try:
                stderr = result.stderr.decode('gbk', errors='ignore')
            except:
                stderr = str(result.stderr)
        
        print(f"adb pair 命令返回码: {result.returncode}")
        print(f"adb pair 输出: {stdout}")
        if stderr:
            print(f"adb pair 错误: {stderr}")
        
        if result.returncode == 0:
            typer.echo(f"成功配对设备 {ip}:{port}")
        else:
            if "Enter pairing code" in stdout or "Enter pairing code" in stderr:
                typer.echo(f"需要配对码，请使用: bt-adb pair {ip}:{port} <配对码>")
            else:
                typer.echo(f"配对设备 {ip}:{port} 失败")
                
    except subprocess.TimeoutExpired:
        typer.echo("配对超时")
    except Exception as e:
        typer.echo(f"配对失败: {e}")


@app.command()
def connect(address: str, port: Optional[int] = None):
    """连接指定设备，支持 IP:端口 格式或单独的 IP 和端口参数"""
    import re
    
    ip = address
    specified_port = port
    
    if ':' in address:
        match = re.match(r'^([\d\.]+):(\d+)$', address)
        if match:
            ip = match.group(1)
            specified_port = int(match.group(2))
    
    final_port = specified_port if specified_port is not None else 5555
    
    if adb_manager.connect(ip, final_port):
        typer.echo(f"成功连接到设备 {ip}:{final_port}")
    else:
        typer.echo(f"连接设备 {ip}:{final_port} 失败")


@app.command()
def disconnect(device_id: str):
    """断开与指定设备的连接"""
    if adb_manager.disconnect(device_id):
        typer.echo(f"成功断开与设备 {device_id} 的连接")
    else:
        typer.echo(f"断开与设备 {device_id} 的连接失败")


@app.command()
def status(device_id: str):
    """获取设备状态"""
    status = adb_manager.get_status(device_id)
    typer.echo(f"设备 {device_id} 的状态: {status.status}")
    if status.error_message:
        typer.echo(f"错误信息: {status.error_message}")
    if status.last_connected:
        import datetime
        last_connected = datetime.datetime.fromtimestamp(status.last_connected)
        typer.echo(f"最后连接时间: {last_connected}")


@app.command()
def command(device_id: str, command: str):
    """在指定设备上执行命令"""
    result = adb_manager.execute_command(device_id, command)
    typer.echo(result)


@app.command()
def start_hci_log(device_id: str):
    """开始采集HCI日志"""
    if adb_manager.start_hci_log(device_id):
        typer.echo(f"成功开始在设备 {device_id} 上采集HCI日志")
    else:
        typer.echo(f"在设备 {device_id} 上开始采集HCI日志失败")


@app.command()
def stop_hci_log(device_id: str):
    """停止采集HCI日志"""
    if adb_manager.stop_hci_log(device_id):
        typer.echo(f"成功停止在设备 {device_id} 上采集HCI日志")
    else:
        typer.echo(f"在设备 {device_id} 上停止采集HCI日志失败")


@app.command()
def pull_hci_log(device_id: str, output_file: str):
    """拉取HCI日志文件"""
    if adb_manager.pull_hci_log(device_id, output_file):
        typer.echo(f"成功拉取设备 {device_id} 的HCI日志到 {output_file}")
    else:
        typer.echo(f"拉取设备 {device_id} 的HCI日志失败")


@app.command()
def add_to_group(device_id: str, group_name: str):
    """添加设备到分组"""
    if adb_manager.add_device_to_group(device_id, group_name):
        typer.echo(f"成功将设备 {device_id} 添加到分组 {group_name}")
    else:
        typer.echo(f"添加设备 {device_id} 到分组 {group_name} 失败")


@app.command()
def remove_from_group(device_id: str, group_name: str):
    """从分组中移除设备"""
    if adb_manager.remove_device_from_group(device_id, group_name):
        typer.echo(f"成功从分组 {group_name} 中移除设备 {device_id}")
    else:
        typer.echo(f"从分组 {group_name} 中移除设备 {device_id} 失败")


@app.command()
def list_group(group_name: str):
    """获取分组中的设备"""
    devices = adb_manager.get_devices_in_group(group_name)
    if not devices:
        typer.echo(f"分组 {group_name} 中没有设备")
        return
    
    typer.echo(f"分组 {group_name} 中的设备:")
    for device in devices:
        typer.echo(f"- {device}")


@app.command()
def add_tag(device_id: str, tag: str):
    """添加标签到设备"""
    if adb_manager.add_tag_to_device(device_id, tag):
        typer.echo(f"成功为设备 {device_id} 添加标签 {tag}")
    else:
        typer.echo(f"为设备 {device_id} 添加标签 {tag} 失败")


@app.command()
def remove_tag(device_id: str, tag: str):
    """从设备中移除标签"""
    if adb_manager.remove_tag_from_device(device_id, tag):
        typer.echo(f"成功从设备 {device_id} 中移除标签 {tag}")
    else:
        typer.echo(f"从设备 {device_id} 中移除标签 {tag} 失败")


@app.command()
def list_tags(device_id: str):
    """获取设备的标签"""
    tags = adb_manager.get_device_tags(device_id)
    if not tags:
        typer.echo(f"设备 {device_id} 没有标签")
        return
    
    typer.echo(f"设备 {device_id} 的标签:")
    for tag in tags:
        typer.echo(f"- {tag}")


@app.command(context_settings={"allow_extra_args": True})
def connect_all(ctx: typer.Context):
    """批量连接多个设备，格式: bt-adb connect-all <IP1:端口1> <IP2:端口2> ..."""
    args = ctx.args
    
    if len(args) < 1:
        typer.echo("用法: bt-adb connect-all <IP1:端口1> <IP2:端口2> ...")
        return
    
    success_count = 0
    fail_count = 0
    
    typer.echo(f"开始连接 {len(args)} 个设备...")
    
    for address in args:
        import re
        
        ip = address
        port = 5555
        
        if ':' in address:
            match = re.match(r'^([\d\.]+):(\d+)$', address)
            if match:
                ip = match.group(1)
                port = int(match.group(2))
        
        typer.echo(f"正在连接 {ip}:{port}...")
        
        if adb_manager.connect(ip, port):
            typer.echo(f"✓ 成功连接到设备 {ip}:{port}")
            success_count += 1
        else:
            typer.echo(f"✗ 连接设备 {ip}:{port} 失败")
            fail_count += 1
    
    typer.echo(f"\n连接完成: 成功 {success_count} 个, 失败 {fail_count} 个")


@app.command(context_settings={"allow_extra_args": True})
def disconnect_all(ctx: typer.Context):
    """断开所有已连接的设备"""
    devices = adb_manager.list_devices()
    
    if not devices:
        typer.echo("没有已连接的设备")
        return
    
    success_count = 0
    fail_count = 0
    
    typer.echo(f"开始断开 {len(devices)} 个设备...")
    
    for device in devices:
        if device.status == "CONNECTED":
            typer.echo(f"正在断开 {device.device_id}...")
            
            if adb_manager.disconnect(device.device_id):
                typer.echo(f"✓ 成功断开设备 {device.device_id}")
                success_count += 1
            else:
                typer.echo(f"✗ 断开设备 {device.device_id} 失败")
                fail_count += 1
    
    typer.echo(f"\n断开完成: 成功 {success_count} 个, 失败 {fail_count} 个")


@app.command(context_settings={"allow_extra_args": True})
def command_all(ctx: typer.Context):
    """向所有已连接的设备执行命令，格式: bt-adb command-all <命令>"""
    args = ctx.args
    
    if len(args) < 1:
        typer.echo("用法: bt-adb command-all <命令>")
        return
    
    command = " ".join(args)
    devices = adb_manager.list_devices()
    
    connected_devices = [d for d in devices if d.status == "CONNECTED"]
    
    if not connected_devices:
        typer.echo("没有已连接的设备")
        return
    
    typer.echo(f"向 {len(connected_devices)} 个设备执行命令: {command}")
    typer.echo("-" * 60)
    
    for device in connected_devices:
        typer.echo(f"\n[{device.device_id}]")
        result = adb_manager.execute_command(device.device_id, command)
        typer.echo(result)
        typer.echo("-" * 60)


@app.command(context_settings={"allow_extra_args": True})
def group_command(ctx: typer.Context):
    """向分组中的所有设备执行命令，格式: bt-adb group-command <分组名> <命令>"""
    args = ctx.args
    
    if len(args) < 2:
        typer.echo("用法: bt-adb group-command <分组名> <命令>")
        return
    
    group_name = args[0]
    command = " ".join(args[1:])
    
    devices = adb_manager.get_devices_in_group(group_name)
    
    if not devices:
        typer.echo(f"分组 {group_name} 中没有设备")
        return
    
    connected_devices = []
    for device_id in devices:
        device_info = adb_manager.get_device_info(device_id)
        if device_info and device_info.status == "CONNECTED":
            connected_devices.append(device_id)
    
    if not connected_devices:
        typer.echo(f"分组 {group_name} 中没有已连接的设备")
        return
    
    typer.echo(f"向分组 {group_name} 中的 {len(connected_devices)} 个设备执行命令: {command}")
    typer.echo("-" * 60)
    
    for device_id in connected_devices:
        typer.echo(f"\n[{device_id}]")
        result = adb_manager.execute_command(device_id, command)
        typer.echo(result)
        typer.echo("-" * 60)


@app.command()
def list_groups():
    """列出所有分组"""
    groups = adb_manager.get_all_groups()
    
    if not groups:
        typer.echo("没有定义任何分组")
        return
    
    typer.echo("可用分组:")
    for group_name, devices in groups.items():
        typer.echo(f"- {group_name} ({len(devices)} 个设备)")


@app.command()
def start_hci_log_all():
    """在所有已连接的设备上开始采集HCI日志"""
    devices = adb_manager.list_devices()
    connected_devices = [d for d in devices if d.status == "CONNECTED"]
    
    if not connected_devices:
        typer.echo("没有已连接的设备")
        return
    
    success_count = 0
    fail_count = 0
    
    typer.echo(f"开始在 {len(connected_devices)} 个设备上采集HCI日志...")
    
    for device in connected_devices:
        typer.echo(f"正在设备 {device.device_id} 上启动日志采集...")
        
        if adb_manager.start_hci_log(device.device_id):
            typer.echo(f"✓ 成功启动设备 {device.device_id} 的日志采集")
            success_count += 1
        else:
            typer.echo(f"✗ 启动设备 {device.device_id} 的日志采集失败")
            fail_count += 1
    
    typer.echo(f"\n操作完成: 成功 {success_count} 个, 失败 {fail_count} 个")


@app.command()
def stop_hci_log_all():
    """在所有已连接的设备上停止采集HCI日志"""
    devices = adb_manager.list_devices()
    connected_devices = [d for d in devices if d.status == "CONNECTED"]
    
    if not connected_devices:
        typer.echo("没有已连接的设备")
        return
    
    success_count = 0
    fail_count = 0
    
    typer.echo(f"停止在 {len(connected_devices)} 个设备上采集HCI日志...")
    
    for device in connected_devices:
        typer.echo(f"正在设备 {device.device_id} 上停止日志采集...")
        
        if adb_manager.stop_hci_log(device.device_id):
            typer.echo(f"✓ 成功停止设备 {device.device_id} 的日志采集")
            success_count += 1
        else:
            typer.echo(f"✗ 停止设备 {device.device_id} 的日志采集失败")
            fail_count += 1
    
    typer.echo(f"\n操作完成: 成功 {success_count} 个, 失败 {fail_count} 个")


@app.command()
def auto_connect():
    """自动发现并连接设备"""
    devices = adb_manager.auto_connect()
    if not devices:
        typer.echo("没有发现可连接的设备")
        return
    
    typer.echo("自动连接成功的设备:")
    for device in devices:
        typer.echo(f"- {device}")


@app.command()
def device_health(device_id: str):
    """检查设备健康状态"""
    health_info = adb_manager.check_device_health(device_id)
    if not health_info:
        typer.echo(f"无法获取设备 {device_id} 的健康状态")
        return
    
    typer.echo(f"设备 {device_id} 的健康状态:")
    if 'battery' in health_info:
        typer.echo("\n电池状态:")
        typer.echo(health_info['battery'])
    if 'storage' in health_info:
        typer.echo("\n存储空间:")
        typer.echo(health_info['storage'])
    if 'memory' in health_info:
        typer.echo("\n内存使用:")
        typer.echo(health_info['memory'])
    if 'cpu' in health_info:
        typer.echo("\nCPU使用:")
        typer.echo(health_info['cpu'])
    if 'error' in health_info:
        typer.echo("\n错误:")
        typer.echo(health_info['error'])


@app.command(context_settings={"allow_extra_args": True})
def app_send(ctx: typer.Context):
    """发送命令给指定APP，格式: bt-adb app-send <设备ID> <包名> <命令> [参数]"""
    args = ctx.args
    
    if len(args) < 3:
        typer.echo("用法: bt-adb app-send <设备ID> <包名> <命令> [参数]")
        return
    
    device_id = args[0]
    package_name = args[1]
    command = args[2]
    args_str = " ".join(args[3:]) if len(args) > 3 else ""
    
    result = adb_manager.send_app_command(device_id, package_name, command, args_str)
    typer.echo(result)


@app.command()
def app_result(device_id: str, result_file: str = "/sdcard/myapp_command_result.txt", local_file: str = None):
    """获取APP执行结果"""
    result = adb_manager.get_app_result(device_id, result_file, local_file)
    typer.echo(result)


@app.command(context_settings={"allow_extra_args": True})
def app_command(ctx: typer.Context):
    """发送命令给APP并获取结果（完整流程），格式: bt-adb app-command <设备ID> <包名> <命令> [参数]"""
    args = ctx.args
    
    if len(args) < 3:
        typer.echo("用法: bt-adb app-command <设备ID> <包名> <命令> [参数]")
        return
    
    device_id = args[0]
    package_name = args[1]
    command = args[2]
    args_str = " ".join(args[3:]) if len(args) > 3 else ""
    
    typer.echo(f"发送命令到设备 {device_id} 的APP {package_name}...")
    result = adb_manager.app_command_with_result(device_id, package_name, command, args_str)
    typer.echo("\n执行结果:")
    typer.echo(result)


@app.command()
def install_app(device_id: str, apk_path: str, reinstall: bool = False):
    """安装APP"""
    result = adb_manager.install_app(device_id, apk_path, reinstall)
    typer.echo(result)


@app.command()
def uninstall_app(device_id: str, package_name: str, keep_data: bool = False):
    """卸载APP"""
    result = adb_manager.uninstall_app(device_id, package_name, keep_data)
    typer.echo(result)


@app.command()
def list_apps(device_id: str, system: bool = False, third_party: bool = False):
    """列出已安装的APP"""
    result = adb_manager.list_apps(device_id, system, third_party)
    typer.echo(result)


@app.command()
def start_app(device_id: str, package_name: str, activity: str = None):
    """启动APP"""
    result = adb_manager.start_app(device_id, package_name, activity)
    typer.echo(result)


@app.command()
def stop_app(device_id: str, package_name: str):
    """停止APP"""
    result = adb_manager.stop_app(device_id, package_name)
    typer.echo(result)


if __name__ == "__main__":
    if TYPER_AVAILABLE:
        app()
    else:
        print("错误: typer 依赖项未安装，CLI接口无法使用")
        print("请运行: pip install typer")
