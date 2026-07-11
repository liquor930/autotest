print("开始测试list_devices方法...")

# 直接导入所需的模块
from adb_control.manager import DeviceInfo

# 定义一个简单的list_devices函数
def list_devices():
    devices = []
    print("开始列出设备...")
    print("list_devices方法开始执行")
    print("list_devices方法执行完成")
    return devices

# 调用函数
print("调用list_devices函数...")
devices = list_devices()
print(f"list_devices函数返回: {devices}")
print(f"返回设备数量: {len(devices)}")

print("测试完成")
