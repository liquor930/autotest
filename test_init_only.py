print("开始测试ADBManager初始化...")

# 导入ADBManager
from adb_control.adb_control.manager import ADBManager

# 创建ADBManager实例
print("创建ADBManager实例...")
try:
    adb_manager = ADBManager()
    print("ADBManager实例创建成功")
except Exception as e:
    print(f"创建ADBManager实例失败: {e}")
    import traceback
    traceback.print_exc()

print("测试完成")
