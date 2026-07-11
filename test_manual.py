import subprocess
from adb_control.manager import DeviceInfo

# 直接运行adb devices命令
print("运行adb devices命令...")
result = subprocess.run('adb devices', shell=True, capture_output=True, text=True)
print(f"返回码: {result.returncode}")
print(f"输出: {result.stdout}")
print(f"错误: {result.stderr}")

# 手动解析输出
devices = []
if result.returncode == 0:
    lines = result.stdout.strip().split('\n')
    print(f"解析到的行: {lines}")
    if len(lines) > 1:
        for line in lines[1:]:
            if line.strip():
                parts = line.split('\t')
                print(f"设备信息: {parts}")
                if len(parts) >= 2 and parts[1] == 'device':
                    device_id = parts[0]
                    print(f"找到设备: {device_id}")
                    
                    # 为所有设备创建基本信息
                    if ':' in device_id:
                        # WiFi设备
                        ip, port_str = device_id.split(':')
                        port = int(port_str)
                        device_info = DeviceInfo(
                            device_id=device_id,
                            ip=ip,
                            port=port,
                            status="FOUND",
                            model="Unknown",
                            version="Unknown"
                        )
                    else:
                        # USB设备
                        device_info = DeviceInfo(
                            device_id=device_id,
                            ip="localhost",
                            port=5555,
                            status="USB_DEVICE",
                            model="Unknown",
                            version="Unknown"
                        )
                    
                    # 添加设备到列表
                    devices.append(device_info)
                    print(f"已添加设备: {device_id}")

# 打印结果
print(f"最终找到的设备数量: {len(devices)}")
for device in devices:
    print(f"设备: {device.device_id}, 状态: {device.status}")
