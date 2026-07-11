# ADB控制模块

ADB控制模块是一个用于通过WiFi ADB与Android手机设备进行通信的工具，支持设备发现、连接、命令执行、HCI日志收集、多设备管理和APP通信等功能。

## 功能特性

- 设备发现：自动扫描局域网内的Android设备
- 设备连接：连接指定的Android设备（支持无线调试端口和配对码）
- 设备断开：断开与指定设备的连接
- 状态查询：获取设备的连接状态
- 命令执行：在设备上执行ADB命令
- HCI日志管理：启动、停止和拉取HCI日志
- 设备分组：将设备添加到分组，便于管理多设备
- 设备标签：为设备添加标签，便于分类和识别
- 自动连接：自动发现并连接设备
- 设备健康检查：检查设备的电池、存储、内存和CPU使用情况
- 错误处理：提供详细的错误码和错误信息
- USB设备支持：支持通过USB连接的设备
- 多设备管理：批量连接、断开、执行命令
- APP通信：与自制APP进行命令交互
- APP管理：安装、卸载、启动、停止APP

## 目录结构

```
adb_control/
├── adb_control/
│   ├── __init__.py
│   ├── cli.py
│   └── manager.py
├── README.md
├── setup.py
└── pyproject.toml
```

## 安装

### 从源码安装

```bash
# 进入adb_control目录
cd adb_control

# 安装模块
pip install .
```

### 打包分发

```bash
# 构建wheel包
python setup.py bdist_wheel

# 在目标机器上安装
pip install adb_control-1.0.0-py3-none-any.whl
```

### 依赖项

- Python 3.8+
- adb-shell>=0.4.3
- typer>=0.7.0

## 使用方法

### 命令行接口

#### 设备管理

```bash
# 列出所有可连接的设备
bt-adb list

# 连接指定设备（支持多种格式）
bt-adb connect 192.168.1.100:34427      # IP:端口格式
bt-adb connect 192.168.1.100 34427      # 分开的IP和端口参数
bt-adb connect 192.168.1.100             # 仅IP，使用默认端口5555

# 使用配对码配对设备（Android 11+无线调试）
bt-adb pair 192.168.1.100:30025 123456   # IP:配对端口 配对码

# 断开与指定设备的连接
bt-adb disconnect 192.168.1.100:34427

# 获取设备状态
bt-adb status 192.168.1.100:34427

# 自动发现并连接设备
bt-adb auto-connect

# 检查设备健康状态
bt-adb device-health 192.168.1.100:34427
```

#### 多设备管理

```bash
# 批量连接多个设备
bt-adb connect-all 192.168.1.100:5555 192.168.1.101:5555 192.168.1.102:5555

# 断开所有已连接的设备
bt-adb disconnect-all

# 向所有已连接设备执行命令
bt-adb command-all "ls /sdcard"

# 查看所有分组
bt-adb list-groups

# 向分组中的所有设备执行命令
bt-adb group-command test-group "getprop ro.product.model"
```

#### 设备分组与标签

```bash
# 设备分组管理
bt-adb add-to-group 192.168.1.100:34427 test-group
bt-adb remove-from-group 192.168.1.100:34427 test-group
bt-adb list-group test-group

# 设备标签管理
bt-adb add-tag 192.168.1.100:34427 production
bt-adb remove-tag 192.168.1.100:34427 production
bt-adb list-tags 192.168.1.100:34427
```

#### 命令执行

```bash
# 在指定设备上执行命令
bt-adb command 192.168.1.100:34427 "ls -la"
```

#### HCI日志管理

```bash
# 开始采集HCI日志
bt-adb start-hci-log 192.168.1.100:34427

# 停止采集HCI日志
bt-adb stop-hci-log 192.168.1.100:34427

# 拉取HCI日志文件
bt-adb pull-hci-log 192.168.1.100:34427 hci.log

# 在所有设备上启动/停止HCI日志采集
bt-adb start-hci-log-all
bt-adb stop-hci-log-all
```

#### APP通信

```bash
# 发送命令给指定APP
bt-adb app-send 192.168.1.100:5555 com.example.myapp get_status

# 获取APP执行结果
bt-adb app-result 192.168.1.100:5555

# 发送命令并获取结果（完整流程）
bt-adb app-command 192.168.1.100:5555 com.example.myapp set_config "server=http://192.168.1.100:8080"
```

#### APP管理

```bash
# 安装APP
bt-adb install-app 192.168.1.100:5555 ./my_app.apk

# 覆盖安装（保留数据）
bt-adb install-app 192.168.1.100:5555 ./my_app.apk --reinstall

# 卸载APP
bt-adb uninstall-app 192.168.1.100:5555 com.example.myapp

# 卸载APP（保留数据）
bt-adb uninstall-app 192.168.1.100:5555 com.example.myapp --keep-data

# 列出已安装的APP
bt-adb list-apps 192.168.1.100:5555
bt-adb list-apps 192.168.1.100:5555 --third-party
bt-adb list-apps 192.168.1.100:5555 --system

# 启动APP
bt-adb start-app 192.168.1.100:5555 com.example.myapp

# 启动指定Activity
bt-adb start-app 192.168.1.100:5555 com.example.myapp .MainActivity

# 停止APP
bt-adb stop-app 192.168.1.100:5555 com.example.myapp
```

### Python API

```python
from adb_control.manager import ADBManager

# 创建ADB管理器实例
adb_manager = ADBManager()

# 列出所有可连接的设备
devices = adb_manager.list_devices()
print("可连接的设备:")
for device in devices:
    print(f"- {device.device_id} ({device.model}, Android {device.version})")

# 自动发现并连接设备
connected_devices = adb_manager.auto_connect()
print("自动连接成功的设备:")
for device in connected_devices:
    print(f"- {device}")

# 连接指定设备
if adb_manager.connect("192.168.1.100", 34427):
    print("成功连接到设备")
else:
    print("连接设备失败")

# 在设备上执行命令
result = adb_manager.execute_command("192.168.1.100:34427", "ls -la")
print(result)

# 检查设备健康状态
health_info = adb_manager.check_device_health("192.168.1.100:34427")
print("设备健康状态:")
print(health_info)

# 添加设备到分组
if adb_manager.add_device_to_group("192.168.1.100:34427", "test-group"):
    print("成功将设备添加到分组")
else:
    print("添加设备到分组失败")

# 获取分组中的设备
group_devices = adb_manager.get_devices_in_group("test-group")
print("分组中的设备:")
for device in group_devices:
    print(f"- {device}")

# 添加标签到设备
if adb_manager.add_tag_to_device("192.168.1.100:34427", "production"):
    print("成功为设备添加标签")
else:
    print("为设备添加标签失败")

# 获取设备的标签
tags = adb_manager.get_device_tags("192.168.1.100:34427")
print("设备的标签:")
for tag in tags:
    print(f"- {tag}")

# 开始采集HCI日志
if adb_manager.start_hci_log("192.168.1.100:34427"):
    print("成功开始采集HCI日志")
else:
    print("开始采集HCI日志失败")

# 停止采集HCI日志
if adb_manager.stop_hci_log("192.168.1.100:34427"):
    print("成功停止采集HCI日志")
else:
    print("停止采集HCI日志失败")

# 拉取HCI日志文件
if adb_manager.pull_hci_log("192.168.1.100:34427", "hci.log"):
    print("成功拉取HCI日志")
else:
    print("拉取HCI日志失败")

# 发送命令给APP
result = adb_manager.send_app_command("192.168.1.100:5555", "com.example.myapp", "get_status")
print(result)

# 获取APP执行结果
result = adb_manager.get_app_result("192.168.1.100:5555")
print(result)

# 发送命令并获取结果（完整流程）
result = adb_manager.app_command_with_result("192.168.1.100:5555", "com.example.myapp", "set_config", "server=http://192.168.1.100:8080")
print(result)

# 安装APP
result = adb_manager.install_app("192.168.1.100:5555", "./my_app.apk")
print(result)

# 启动APP
result = adb_manager.start_app("192.168.1.100:5555", "com.example.myapp")
print(result)

# 停止APP
result = adb_manager.stop_app("192.168.1.100:5555", "com.example.myapp")
print(result)

# 从设备中移除标签
if adb_manager.remove_tag_from_device("192.168.1.100:34427", "production"):
    print("成功从设备中移除标签")
else:
    print("从设备中移除标签失败")

# 从分组中移除设备
if adb_manager.remove_device_from_group("192.168.1.100:34427", "test-group"):
    print("成功从分组中移除设备")
else:
    print("从分组中移除设备失败")

# 断开与设备的连接
if adb_manager.disconnect("192.168.1.100:34427"):
    print("成功断开与设备的连接")
else:
    print("断开与设备的连接失败")
```

## 与自制APP通信

### APP端实现

1. 在 `AndroidManifest.xml` 中注册 Intent Filter：

```xml
<activity
    android:name=".CommandReceiverActivity"
    android:exported="true">
    <intent-filter>
        <action android:name="com.example.myapp.ACTION_EXECUTE_COMMAND" />
        <category android:name="android.intent.category.DEFAULT" />
    </intent-filter>
</activity>
```

2. 创建 `CommandReceiverActivity` 处理命令：

```java
public class CommandReceiverActivity extends Activity {
    private static final String RESULT_FILE = "/sdcard/myapp_command_result.txt";
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        String command = getIntent().getStringExtra("command");
        String args = getIntent().getStringExtra("args");
        String callbackId = getIntent().getStringExtra("callback_id");
        
        String result = executeCommand(command, args);
        String response = buildResponse(callbackId, true, result, null);
        
        writeResultToFile(response);
        finish();
    }
    
    private String executeCommand(String command, String args) {
        switch (command) {
            case "get_status":
                return "{\"status\":\"running\",\"version\":\"1.0.0\"}";
            case "set_config":
                // 解析并设置配置
                return "Configuration updated";
            default:
                throw new IllegalArgumentException("Unknown command: " + command);
        }
    }
    
    private String buildResponse(String callbackId, boolean success, String data, String error) {
        JSONObject json = new JSONObject();
        try {
            if (callbackId != null) json.put("callback_id", callbackId);
            json.put("success", success);
            if (data != null) json.put("data", data);
            if (error != null) json.put("error", error);
        } catch (JSONException e) {
            return "{\"success\":false,\"error\":\"JSON error\"}";
        }
        return json.toString();
    }
    
    private void writeResultToFile(String content) {
        try {
            FileWriter writer = new FileWriter(RESULT_FILE, false);
            writer.write(content);
            writer.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
```

### PC端调用

```bash
# 发送命令并获取结果
bt-adb app-command 192.168.1.100:5555 com.example.myapp get_status

# 发送带参数的命令
bt-adb app-command 192.168.1.100:5555 com.example.myapp set_config "server=http://192.168.1.100:8080"
```

## 注意事项

1. 使用前请确保Android设备已启用开发者选项和无线调试
2. 使用WiFi ADB前，需要在手机上启用"无线调试"功能并获取配对码或端口号
3. 确保设备和电脑在同一局域网内
4. 首次连接设备时，需要在设备上授权ADB连接
5. 首次运行时，系统会自动生成ADB密钥文件（~/.android/adbkey）
6. 确保已安装ADB工具并添加到系统路径
7. 无线调试端口通常在手机的开发者选项中显示（格式如：192.168.1.100:34427）
8. APP通信需要APP端实现相应的Intent接收逻辑
9. 配对码有效期较短，获取后请立即使用

## 故障排除

### 常见错误

1. **ModuleNotFoundError: No module named 'adb_control'**
   - 确保模块已正确安装：`pip install -e .`
   - 检查目录结构是否正确（adb_control/adb_control/）

2. **adb-shell 依赖项未安装**
   - 安装依赖项：`pip install adb-shell>=0.4.3 typer>=0.7.0`

3. **'adb' 不是内部或外部命令**
   - 安装Android SDK Platform Tools
   - 将ADB工具添加到系统环境变量PATH

4. **连接失败**
   - 检查设备是否已启用开发者选项和无线调试
   - 确保设备和电脑在同一WiFi网络下
   - 验证端口号是否正确（在手机无线调试设置中查看）
   - 尝试重启ADB服务：`adb kill-server && adb start-server`

5. **配对失败（protocol fault）**
   - 配对码已过期，重新获取配对码
   - 确保设备和电脑在同一网络
   - 重启ADB服务后重试

6. **授权问题**
   - 首次连接时，设备会弹出授权提示，请点击允许
   - 如果没有弹出提示，检查设备是否处于锁定状态

7. **命令执行失败**
   - 检查设备是否已正确连接
   - 确认命令在设备上可用

8. **HCI日志拉取失败**
   - 检查设备是否支持HCI日志
   - 确保已启动日志采集

9. **ADB密钥错误**
   - 执行`adb devices`命令生成ADB密钥文件
   - 检查密钥文件路径：~/.android/adbkey

10. **APP通信失败**
    - 确保APP已安装并启动
    - 检查APP的Intent Filter配置是否正确
    - 验证APP是否有写入外部存储的权限

### 移植到其他电脑

1. 打包wheel文件：`python setup.py bdist_wheel`
2. 复制dist目录下的.whl文件到目标电脑
3. 在目标电脑上安装：`pip install adb_control-1.0.0-py3-none-any.whl`
4. 安装依赖项：`pip install adb-shell>=0.4.3 typer>=0.7.0`
5. 安装ADB工具并配置环境变量

## 许可证

MIT License
