# 手机端APP详细设计

## 1. 模块概述

手机端APP负责接收ADB命令，执行蓝牙操作，启用HCI日志，并通过logcat输出执行结果。

## 2. 功能需求

- 蓝牙扫描：扫描周围蓝牙设备
- 配对管理：配对/取消配对蓝牙设备
- 连接管理：连接/断开蓝牙设备
- 数据传输：发送/接收蓝牙数据
- HCI日志：启用/禁用btsnoop日志
- 命令接收：通过BroadcastReceiver接收ADB命令
- 结果输出：通过logcat输出执行结果

## 3. 设计方案

- 使用Java开发Android应用
- 实现BroadcastReceiver接收ADB广播命令
- 实现蓝牙操作服务，处理蓝牙相关功能
- 实现HCI日志管理服务，控制btsnoop日志
- 提供命令解析器，处理不同类型的命令

## 4. 接口设计

```kotlin
// 广播接收器
class CommandReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // 处理接收到的命令
        val commandType = intent.getStringExtra("command")
        val params = intent.getBundleExtra("params")
        val commandHandler = CommandHandler(context)
        val result = commandHandler.handleCommand(commandType, params)
        // 输出结果到logcat
        Log.d("BT_TEST", "Command result: ${result.success} - ${result.message}")
    }
}

// 命令处理器
class CommandHandler(private val context: Context) {
    fun handleCommand(commandType: String?, params: Bundle?): CommandResult {
        return when (commandType) {
            CommandType.SCAN.name -> handleScan()
            CommandType.PAIR.name -> handlePair(params)
            CommandType.CONNECT.name -> handleConnect(params)
            CommandType.DISCONNECT.name -> handleDisconnect(params)
            CommandType.SEND_DATA.name -> handleSendData(params)
            CommandType.RECEIVE_DATA.name -> handleReceiveData()
            CommandType.ENABLE_HCI_LOG.name -> handleEnableHciLog()
            CommandType.DISABLE_HCI_LOG.name -> handleDisableHciLog()
            else -> CommandResult(false, "Unknown command")
        }
    }
    
    private fun handleScan(): CommandResult {
        // 处理扫描命令
    }
    
    private fun handlePair(params: Bundle?): CommandResult {
        // 处理配对命令
    }
    
    private fun handleConnect(params: Bundle?): CommandResult {
        // 处理连接命令
    }
    
    private fun handleDisconnect(params: Bundle?): CommandResult {
        // 处理断开连接命令
    }
    
    private fun handleSendData(params: Bundle?): CommandResult {
        // 处理发送数据命令
    }
    
    private fun handleReceiveData(): CommandResult {
        // 处理接收数据命令
    }
    
    private fun handleEnableHciLog(): CommandResult {
        // 处理启用HCI日志命令
    }
    
    private fun handleDisableHciLog(): CommandResult {
        // 处理禁用HCI日志命令
    }
}

// 蓝牙操作服务
class BluetoothService : Service() {
    fun scanDevices(): List<BluetoothDevice> {
        // 扫描蓝牙设备
    }
    
    fun pairDevice(device: BluetoothDevice): Boolean {
        // 配对蓝牙设备
    }
    
    fun connectDevice(device: BluetoothDevice): Boolean {
        // 连接蓝牙设备
    }
    
    fun disconnectDevice(device: BluetoothDevice): Boolean {
        // 断开连接
    }
    
    fun sendData(device: BluetoothDevice, data: ByteArray): Boolean {
        // 发送蓝牙数据
    }
    
    fun receiveData(): ByteArray {
        // 接收蓝牙数据
    }
}

// HCI日志管理服务
class HciLogService : Service() {
    fun enableHciLog(): Boolean {
        // 启用HCI日志
    }
    
    fun disableHciLog(): Boolean {
        // 禁用HCI日志
    }
    
    fun getLogPath(): String {
        // 获取日志文件路径
    }
}
```

## 5. 数据结构

```kotlin
// 命令类型
enum class CommandType {
    SCAN,
    PAIR,
    CONNECT,
    DISCONNECT,
    SEND_DATA,
    RECEIVE_DATA,
    ENABLE_HCI_LOG,
    DISABLE_HCI_LOG
}

// 命令结果
data class CommandResult(
    val success: Boolean,
    val message: String,
    val data: String? = null
)

// 蓝牙设备信息
data class BluetoothDeviceInfo(
    val address: String,
    val name: String,
    val rssi: Int,
    val bondState: Int
)
```

## 6. 实现细节

- **蓝牙操作**：
  - 使用Android Bluetooth API实现蓝牙扫描、配对、连接和数据传输
  - 支持蓝牙低功耗（BLE）和传统蓝牙操作
  - 实现蓝牙设备的发现和管理
  - 支持蓝牙设备的状态监控和通知
- **命令处理**：
  - 使用BroadcastReceiver接收ADB广播命令
  - 实现命令解析和分发机制
  - 使用命令工厂模式处理不同类型的命令
  - 提供命令执行的错误处理和重试机制
- **HCI日志管理**：
  - 实现HCI日志的启动、停止和管理
  - 支持日志文件的存储和访问
  - 提供日志的压缩和清理
  - 实现日志的实时监控和分析
- **后台服务**：
  - 使用Service后台运行蓝牙操作和日志管理
  - 使用前台服务确保稳定性，避免被系统杀死
  - 实现服务的绑定和解绑机制
  - 提供服务状态监听接口
- **权限管理**：
  - 详细列出需要申请的Android权限：
    - BLUETOOTH：蓝牙基本操作
    - BLUETOOTH_ADMIN：蓝牙管理操作
    - ACCESS_FINE_LOCATION：蓝牙扫描需要位置权限
    - ACCESS_COARSE_LOCATION：蓝牙扫描需要位置权限
    - WRITE_EXTERNAL_STORAGE：存储HCI日志
    - READ_EXTERNAL_STORAGE：读取HCI日志
  - 处理Android 6.0+的运行时权限申请
  - 适配Android 10+的后台位置权限限制
  - 提供权限申请的用户友好提示
- **ADB通信**：
  - 明确ADB通信接口格式：
    - 命令格式：`adb shell am broadcast -a com.bt.test.<COMMAND> --es <param> <value>`
    - 结果格式：通过logcat输出，格式为`BT_TEST: <json_result>`
    - 错误处理：返回标准化的错误码和错误信息
- **设备管理**：
  - 实现多设备同时连接和管理功能
  - 提供设备管理界面，显示已连接设备
  - 实现设备状态监控和通知
  - 支持设备的分组和标签管理
- **版本兼容性**：
  - 适配不同Android版本的蓝牙API差异
  - 处理不同Android版本的权限申请差异
  - 支持Android 4.4+的设备
- **设备信息缓存**：
  - 缓存已发现的蓝牙设备信息
  - 减少重复扫描，提高扫描速度
  - 支持缓存过期和更新机制
- **快速配对和连接**：
  - 支持快速配对模式
  - 实现连接参数优化，提高连接速度
  - 提供连接状态的实时反馈
- **设备状态监控**：
  - 监控设备的连接状态、信号强度等
  - 提供设备状态变化的通知
  - 实现设备异常的自动检测和告警
- **离线模式**：
  - 支持无网络环境下的基本操作
  - 缓存必要的数据，确保离线时的功能可用性
  - 网络恢复后自动同步数据
- **设备模拟**：
  - 支持模拟蓝牙设备，用于测试APP功能
  - 提供模拟设备的配置和管理
  - 支持模拟不同类型的蓝牙设备
- **自动化测试**：
  - 支持通过脚本控制APP功能
  - 提供脚本API，便于编写自动化测试
  - 支持脚本的录制和回放
  - 实现自动化测试框架，便于扩展测试功能
- **数据备份和恢复**：
  - 支持APP配置和测试数据的备份
  - 提供备份数据的恢复功能
  - 支持备份数据的加密存储
- **蓝牙协议分析**：
  - 支持蓝牙协议数据包的捕获和分析
  - 提供协议分析工具，便于调试和问题定位
  - 支持协议数据的导出和分享
- **设备诊断**：
  - 支持设备状态的诊断和分析
  - 提供诊断报告，包含设备健康状态
  - 实现自动诊断和故障排除建议
- **用户体验测试**：
  - 支持设备的用户体验测试
  - 提供用户体验测试工具，如延迟测试、响应速度测试等
  - 支持测试结果的分析和报告
- **性能测试**：
  - 支持设备性能的测试和分析
  - 提供性能测试工具，如CPU、内存、网络等
  - 支持性能测试结果的分析和报告
- **安全测试**：
  - 支持设备安全性的测试和分析
  - 提供安全测试工具，如漏洞扫描、权限分析等
  - 支持安全测试结果的分析和报告
- **与PC端的集成**：
  - 与PC端ADB控制模块集成，接收ADB命令
  - 与PC端日志收集模块集成，提供HCI日志
  - 实现与PC端的实时通信
  - 提供标准化的通信接口

## 7. 测试计划

- 测试蓝牙扫描功能
- 测试配对管理功能
- 测试连接管理功能
- 测试数据传输功能
- 测试HCI日志控制功能
- 测试命令接收和处理功能

## 8. 部署与集成

### 8.1 依赖管理

- **核心依赖**：
  - AndroidX：提供基础UI组件和兼容性支持
  - Kotlin Coroutines：用于异步操作
  - Gson：用于JSON解析
  - Log4j：用于日志管理
- **可选依赖**：
  - Room：用于本地数据存储
  - Retrofit：用于网络请求
  - Espresso：用于UI测试

### 8.2 安装与配置

- **安装方式**：
  - 通过APK文件安装：`adb install app-debug.apk`
  - 通过Android Studio直接安装到设备
- **配置文件**：
  - 支持XML格式的配置文件
  - 默认配置文件路径：`res/values/config.xml`
  - 支持通过SharedPreferences存储用户配置

### 8.3 集成接口

- **ADB接口**：通过ADB广播命令与PC端通信
- **Intent接口**：支持通过Intent与其他APP集成
- **Content Provider**：提供数据共享接口
- **与其他模块的集成**：
  - 与PC端ADB控制模块集成，接收ADB命令
  - 与PC端日志收集模块集成，提供HCI日志

### 8.4 部署场景

- **本地部署**：直接安装到Android设备
- **远程部署**：通过ADB远程安装到设备
- **批量部署**：支持通过MDM系统批量部署到多台设备

