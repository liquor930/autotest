print("开始测试完全独立的脚本...")

# 完全独立实现，不依赖任何现有模块
from dataclasses import dataclass
import subprocess

@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    ip: str
    port: int
    status: str  # CONNECTED, DISCONNECTED, ERROR
    model: str = ""
    version: str = ""

class SimpleADBManager:
    """简单ADB管理器"""

    def __init__(self):
        """初始化ADB管理器"""
        print("开始初始化SimpleADBManager...")
        self.devices = {}
        print("SimpleADBManager初始化完成")

    def list_devices(self):
        """列出所有可连接的设备"""
        devices = []
        
        print("开始列出设备...")
        
        # 直接运行adb devices命令
        print("运行adb devices命令...")
        try:
            result = subprocess.run('adb devices', shell=True, capture_output=True, text=True, timeout=5)
            print(f"返回码: {result.returncode}")
            print(f"输出: {result.stdout}")
            
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
        except Exception as e:
            print(f"执行adb devices命令失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 打印结果
        print(f"最终找到的设备数量: {len(devices)}")
        for device in devices:
            print(f"设备: {device.device_id}, 状态: {device.status}")
        
        return devices

# 创建SimpleADBManager实例
print("创建SimpleADBManager实例...")
adb_manager = SimpleADBManager()
print("SimpleADBManager实例创建成功")

# 调用list_devices方法
print("调用list_devices方法...")
devices = adb_manager.list_devices()
print(f"list_devices方法返回: {devices}")
print(f"返回设备数量: {len(devices)}")

print("测试完成")
