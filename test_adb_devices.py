import subprocess

# 执行adb devices命令
result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)

# 打印命令返回码
print('adb devices命令返回码:', result.returncode)

# 打印命令输出
print('adb devices命令输出:', result.stdout)

# 打印命令错误
print('adb devices命令错误:', result.stderr)

# 解析设备列表
if result.returncode == 0:
    lines = result.stdout.strip().split('\n')
    print('解析到的设备行:', lines)
    for line in lines[1:]:  # 跳过第一行标题
        if line.strip():
            parts = line.split('\t')
            print('设备信息:', parts)