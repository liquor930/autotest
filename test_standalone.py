print("开始测试独立脚本...")

# 定义DeviceInfo类
from dataclasses import dataclass

@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    ip: str
    port: int
    status: str  # CONNECTED, DISCONNECTED, ERROR
    model: str = ""
    version: str = ""

# 定义list_devices函数
def list_devices():
    """列出所有可连接的设备"""
    devices = []
    
    print("开始列出设备...")
    print("list_devices方法开始执行")
    
    # 直接返回一个测试设备
    device_info = DeviceInfo(
        device_id="AGQV023427000233",
        ip="localhost",
        port=5555,
        status="USB_DEVICE",
        model="Unknown",
        version="Unknown"
    )
    devices.append(device_info)
    
    print("list_devices方法执行完成")
    print(f"最终找到的设备数量: {len(devices)}")
    for device in devices:
        print(f"设备: {device.device_id}, 状态: {device.status}")
    
    return devices

# 调用函数
print("调用list_devices函数...")
devices = list_devices()
print(f"list_devices函数返回: {devices}")
print(f"返回设备数量: {len(devices)}")

print("测试完成")
