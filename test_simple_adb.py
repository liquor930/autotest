import subprocess

# 直接运行adb devices命令
print("运行adb devices命令...")
result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
print(f"返回码: {result.returncode}")
print(f"输出: {result.stdout}")
print(f"错误: {result.stderr}")

# 解析输出
print("\n解析输出...")
if result.returncode == 0:
    lines = result.stdout.strip().split('\n')
    print(f"解析到的行: {lines}")
    if len(lines) > 1:
        for line in lines[1:]:
            if line.strip():
                parts = line.split('\t')
                print(f"设备信息: {parts}")
                if len(parts) >= 2 and parts[1] == 'device':
                    print(f"找到设备: {parts[0]}")
    else:
        print("没有找到设备")
else:
    print("命令执行失败")
