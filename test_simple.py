import subprocess

# 直接运行adb devices命令
result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
print('ADB Devices Output:')
print(result.stdout)
print('Return Code:', result.returncode)
