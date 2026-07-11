import sys

# 重定向输出到文件
with open('test_output.txt', 'w', encoding='utf-8') as f:
    # 保存标准输出
    original_stdout = sys.stdout
    sys.stdout = f
    
    try:
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
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复标准输出
        sys.stdout = original_stdout

# 打印完成信息
print("测试完成，输出已保存到 test_output.txt 文件")
