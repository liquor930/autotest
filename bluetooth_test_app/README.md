# Bluetooth Test App - README

## 项目简介

蓝牙自动化测试 APP，运行在 Android 设备上。**打开 APP 后**，通过 ADB 广播命令执行蓝牙操作（扫描、配对、连接、数据传输），管理 HCI 日志，并通过 logcat 输出结构化 JSON 结果。

> ⚠️ **使用前提**：APP 必须保持在前台运行（`MainActivity` 可见），ADB 广播命令才能被接收。如果 APP 被切到后台或关闭，命令将无法送达。

## 项目结构

```
bluetooth_test_app/
├── .gitignore                     # Git 忽略规则
├── build.gradle.kts               # 项目级构建配置
├── settings.gradle.kts            # 项目设置
├── gradle.properties              # Gradle 属性
├── gradle/wrapper/
│   └── gradle-wrapper.properties  # Gradle Wrapper 配置
├── app/
│   ├── build.gradle.kts           # 模块级构建配置
│   ├── proguard-rules.pro         # 混淆规则
│   └── src/main/
│       ├── AndroidManifest.xml    # 应用清单
│       ├── java/com/bttest/
│       │   ├── MainActivity.kt            # 主 Activity
│       │   ├── model/
│       │   │   ├── CommandType.kt         # 命令类型枚举
│       │   │   ├── CommandResult.kt       # 命令结果数据类
│       │   │   └── BluetoothDeviceInfo.kt # 蓝牙设备信息
│       │   ├── handler/
│       │   │   └── CommandHandler.kt      # 命令处理器
│       │   ├── receiver/
│       │   │   └── CommandReceiver.kt     # ADB 广播接收器
│       │   ├── service/
│       │   │   ├── BluetoothService.kt    # 蓝牙操作服务
│       │   │   └── HciLogService.kt       # HCI 日志管理服务
│       │   └── util/
│       │       ├── LogUtil.kt             # 日志工具类
│       │       └── PermissionUtil.kt      # 权限管理工具
│       └── res/
│           ├── drawable/
│           │   └── ic_launcher_foreground.xml  # 启动图标前景
│           ├── mipmap-anydpi-v26/
│           │   └── ic_launcher.xml              # 自适应图标
│           ├── layout/
│           │   └── activity_main.xml     # 主界面布局
│           └── values/
│               ├── strings.xml           # 字符串资源
│               ├── colors.xml            # 颜色资源
│               └── styles.xml            # 主题样式
```

## ADB 命令格式

### 基本命令格式

```bash
adb shell am broadcast -a com.bttest.COMMAND --es command <COMMAND> [--es <key> <value> ...]
```

### 命令列表

| 命令 | 说明 | 参数 |
|------|------|------|
| SCAN | 蓝牙扫描 | --es action start/stop --ei duration_ms 10000 |
| PAIR | 配对设备 | --es address AA:BB:CC:DD:EE:FF |
| UNPAIR | 取消配对 | --es address AA:BB:CC:DD:EE:FF |
| CONNECT | 连接设备 | --es address AA:BB:CC:DD:EE:FF --es type gatt/spp |
| DISCONNECT | 断开连接 | --es address AA:BB:CC:DD:EE:FF |
| SEND_DATA | 发送数据 | --es address AA:BB:CC:DD:EE:FF --es data "Hello" [--ez is_hex true] |
| RECEIVE_DATA | 接收数据 | --es address AA:BB:CC:DD:EE:FF |
| GET_PAIRED_DEVICES | 获取已配对设备 | 无 |
| GET_CONNECTED_DEVICES | 获取已连接设备 | 无 |
| GET_DEVICE_INFO | 获取设备信息 | --es address AA:BB:CC:DD:EE:FF |
| GET_BT_STATUS | 获取蓝牙状态 | 无 |
| ENABLE_HCI_LOG | 启用 HCI 日志 | 无 |
| DISABLE_HCI_LOG | 禁用 HCI 日志 | 无 |

### 示例

```bash
# 开始扫描 10 秒
adb shell am broadcast -a com.bttest.COMMAND --es command SCAN --es action start --ei duration_ms 10000

# 停止扫描
adb shell am broadcast -a com.bttest.COMMAND --es command SCAN --es action stop

# 获取已配对设备列表
adb shell am broadcast -a com.bttest.COMMAND --es command GET_PAIRED_DEVICES

# 配对设备
adb shell am broadcast -a com.bttest.COMMAND --es command PAIR --es address "00:11:22:33:44:55"

# 连接 BLE 设备
adb shell am broadcast -a com.bttest.COMMAND --es command CONNECT --es address "00:11:22:33:44:55" --es type gatt

# 发送数据
adb shell am broadcast -a com.bttest.COMMAND --es command SEND_DATA --es address "00:11:22:33:44:55" --es data "Hello World"

# 发送 Hex 数据
adb shell am broadcast -a com.bttest.COMMAND --es command SEND_DATA --es address "00:11:22:33:44:55" --es data "AA BB CC DD" --ez is_hex true

# 获取蓝牙状态
adb shell am broadcast -a com.bttest.COMMAND --es command GET_BT_STATUS

# 启用 HCI 日志
adb shell am broadcast -a com.bttest.COMMAND --es command ENABLE_HCI_LOG
```

### 查看结果

```bash
# 实时查看结果
adb logcat -s BT_TEST

# 过滤命令结果 JSON
adb logcat -s BT_TEST | grep "success"
```

## 构建与安装

### 前提条件

- Android Studio Hedgehog (2023.1) 或更新版本
- Android SDK 34
- JDK 17
- Kotlin 1.9.20

### 构建

```bash
# 编译 Debug 版本
./gradlew assembleDebug

# 编译 Release 版本
./gradlew assembleRelease
```

### 安装

```bash
# 安装到设备
adb install app/build/outputs/apk/debug/BluetoothTest-debug-v1.0.0.apk

# 或直接从 Android Studio 安装
```

## 测试

### 单元测试

```bash
./gradlew test
```

### 仪器化测试

```bash
./gradlew connectedAndroidTest
```

## 已知限制

- **前台运行要求**：ADB 广播命令仅在 APP 处于前台时才能被接收（`CommandReceiver` 由 `MainActivity` 动态注册，离开前台即取消注册）
- **HCI 日志**：`ENABLE_HCI_LOG` / `DISABLE_HCI_LOG` 通过 `settings` 和 `su -c setprop` 命令控制系统属性，普通无 root 设备上可能无法生效，建议手动在「开发者选项」→「启用蓝牙 HCI 信息收集日志」中开启
- **取消配对**：Android 无公开 `unpair` API，实现使用反射调用 `removeBond()`，不同 ROM 可能存在兼容性差异
- **API 31+ 蓝牙权限**：Android 12 及以上访问蓝牙设备地址/名称需要 `BLUETOOTH_CONNECT` 权限，首次启动时会弹窗申请
- **开机自启**：`BOOT_COMPLETED` 广播仅启动后台服务；命令接收仍需手动打开 APP

## 技术栈

- **语言**: Kotlin
- **最低 SDK**: Android 5.0 (API 21)
- **目标 SDK**: Android 14 (API 34)
- **蓝牙**: Android Bluetooth API (CLASSIC + BLE/GATT)
- **序列化**: Gson
- **异步**: Kotlin Coroutines
- **广播通信**: Android BroadcastReceiver
- **日志输出**: Android Logcat (TAG: BT_TEST)
