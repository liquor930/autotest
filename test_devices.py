from adb_control.manager import ADBManager
import subprocess
import sys

# 重定向输出到文件
with open('test_output.txt', 'w', encoding='utf-8') as f:
    # 保存标准输出
    original_stdout = sys.stdout
    sys.stdout = f
    
    try:
        # 先直接运行adb devices命令查看结果
        print("直接运行adb devices命令:")
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        print(f"返回码: {result.returncode}")
        print(f"输出: {result.stdout}")
        print(f"错误: {result.stderr}")
        
        # 创建ADB管理器实例
        print("\n创建ADB管理器实例:")
        adb_manager = ADBManager()
        
        # 列出所有可连接的设备
        print("\n调用list_devices方法:")
        devices = adb_manager.list_devices()
        
        # 打印找到的设备数量
        print('\n找到的设备数量:', len(devices))
        
        # 打印每个设备的信息
        for device in devices:
            print('设备:', device.device_id, '状态:', device.status, '型号:', device.model, '版本:', device.version)
    finally:
        # 恢复标准输出
        sys.stdout = original_stdout

# 打印完成信息
print("测试完成，输出已保存到 test_output.txt 文件")