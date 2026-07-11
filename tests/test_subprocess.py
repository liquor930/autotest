print("测试subprocess模块...")
try:
    import subprocess
    print("成功导入subprocess模块")
    
    # 执行adb devices命令
    print("执行adb devices命令...")
    result = subprocess.run('adb devices', shell=True, capture_output=True, text=True, timeout=5)
    print(f"返回码: {result.returncode}")
    print(f"输出: {result.stdout}")
    print(f"错误: {result.stderr}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
print("测试完成")
