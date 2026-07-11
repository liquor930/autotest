print("开始测试ADBManager初始化...")
import sys
import os

# 添加adb_control目录到Python搜索路径
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), 'adb_control'))

print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.path}")

try:
    print("导入ADBManager...")
    from adb_control.manager import ADBManager
    print("成功导入ADBManager")
    
    # 创建ADB管理器实例
    print("创建ADB管理器实例...")
    adb_manager = ADBManager()
    print("ADB管理器实例创建成功")
    
    # 调用list_devices方法
    print("调用list_devices方法...")
    import time
    start_time = time.time()
    devices = adb_manager.list_devices()
    end_time = time.time()
    print(f"list_devices方法执行时间: {end_time - start_time}秒")
    print(f"list_devices方法返回: {devices}")
    print(f"返回设备数量: {len(devices)}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
print("测试完成")
