print("开始测试基本功能...")
import sys
print(f"Python版本: {sys.version}")

try:
    # 测试基本导入
    print("测试基本导入...")
    from adb_control.manager import DeviceInfo
    print("成功导入DeviceInfo")
    
    # 测试DeviceInfo类
    print("测试DeviceInfo类...")
    device_info = DeviceInfo(
        device_id="AGQV023427000233",
        ip="localhost",
        port=5555,
        status="USB_DEVICE",
        model="Unknown",
        version="Unknown"
    )
    print(f"创建DeviceInfo成功: {device_info}")
    
    # 测试列表操作
    print("测试列表操作...")
    devices = []
    devices.append(device_info)
    print(f"列表操作成功，设备数量: {len(devices)}")
    
    # 测试打印
    print("测试打印...")
    for device in devices:
        print(f"设备: {device.device_id}, 状态: {device.status}")
    
    print("所有测试通过!")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
print("测试完成")
