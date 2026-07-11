from adb_control.manager import ADBManager

# 创建ADB管理器实例
print("创建ADB管理器实例...")
adb_manager = ADBManager()

# 调用list_devices方法
print("\n调用list_devices方法...")
devices = adb_manager.list_devices()

# 打印结果
print("\n结果:")
print(f"找到的设备数量: {len(devices)}")
for device in devices:
    print(f"设备: {device.device_id}, 状态: {device.status}")
