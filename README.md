# 蓝牙自动化测试平台

> Bluetooth Automation Test Platform — PC端测试工具 + Android端蓝牙操作APP

## 架构

```
cli/          CLI工具链 (bt-adb / bt-serial / bt-logger / bt-test)
modules/      业务逻辑模块 (adb / serial / logger)
core/         核心引擎 (TestManager + ExecutionEngine + ...)
android-app/  手机端蓝牙操作APP
```

## 快速开始

```bash
# 安装
pip install -e .

# ADB 设备控制
bt-adb list
bt-adb connect 192.168.1.100:5555
bt-adb command <device> "getprop ro.product.model"

# 串口控制（需要 PySerial）
pip install pyserial
bt-serial list
bt-serial connect COM3
bt-serial send "AT"

# 日志采集分析
bt-logger start <device>     # 开启btsnoop
bt-logger stop <device>      # 停止
bt-logger pull <device>      # 拉取日志
bt-logger analyze <file>     # 分析HCI日志

# 测试执行
bt-test run config.yaml       # 按配置运行测试
bt-test run --name "快速测试"  # 快速测试
bt-test list                  # 查看会话
bt-test report <session>      # 生成HTML报告
```

## 项目结构

```
.
├── cli/              CLI入口
│   ├── bt_adb/       bt-adb 命令
│   ├── bt_serial/    bt-serial 命令
│   ├── bt_logger/    bt-logger 命令
│   └── bt_test/      bt-test 命令
├── modules/          业务逻辑
│   ├── adb/          ADB设备管理 (adb-shell)
│   ├── serial/       串口通信 (PySerial)
│   └── logger/       日志解析 (btsnoop/logcat)
├── core/             核心引擎
│   ├── models.py     数据模型
│   ├── database.py   数据库 (SQLite)
│   ├── event_bus.py  事件总线
│   ├── test_manager.py   测试管理器
│   ├── execution_engine.py  执行引擎
│   ├── result_manager.py    结果管理器
│   └── resource_manager.py  资源管理器
├── gui/              GUI界面 (PySide6, 开发中)
├── android-app/      手机端蓝牙APP
├── docs/             设计文档
├── tests/            测试脚本
└── setup.py          安装配置
```

## 依赖

| 包 | 用途 | 必装 |
|----|------|------|
| typer | CLI框架 | 是 |
| adb-shell | ADB通信 | 是 |
| PySerial | 串口通信 | 仅bt-serial |
| PySide6 | GUI界面 | 仅GUI |

## 手机端APP

`android-app/` 是一个Android蓝牙测试APP，支持：
- 蓝牙扫描/配对/连接/数据传输
- BLE GATT + 经典蓝牙 SPP
- btsnoop HCI日志控制
- ADB广播命令接收
- 前台服务保活

```bash
cd android-app
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```
