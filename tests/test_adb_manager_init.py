print("开始测试ADBManager初始化...")
import sys
print(f"Python版本: {sys.version}")

try:
    # 测试导入ADBManager
    print("导入ADBManager...")
    from adb_control.manager import ADBManager
    print("成功导入ADBManager")
    
    # 测试ADBManager初始化
    print("初始化ADBManager...")
    adb_manager = ADBManager()
    print("ADBManager初始化成功")
    
    print("所有测试通过!")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
print("测试完成")
