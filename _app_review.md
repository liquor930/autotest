# 手机端APP代码审查报告

## 一、文件清单

| 文件 | 说明 | 规模 |
|------|------|------|
| AndroidManifest.xml | 权限声明 + 组件注册 | 完整 |
| MainActivity.kt | UI界面 + 服务绑定 | 完整 |
| service/BluetoothService.kt | 蓝牙操作核心服务 | ~600行 |
| service/HciLogService.kt | HCI日志管理服务 | ~300行 |
| handler/CommandHandler.kt | 命令分发处理 | ~300行 |
| receiver/CommandReceiver.kt | 广播接收器 | ~200行 |
| model/BluetoothDeviceInfo.kt | 蓝牙设备数据模型 | ~80行 |
| model/CommandResult.kt | 命令结果模型 | ~50行 |
| model/CommandType.kt | 命令类型枚举 | ~40行 |
| util/LogUtil.kt | 日志工具 | ~80行 |
| util/PermissionUtil.kt | 权限工具 | ~120行 |
| activity_main.xml | 布局文件 | 完整 |
| build.gradle.kts | 构建配置(根+App) | 完整 |

## 二、功能完整度评估

### 已实现功能 (18项)

| 功能 | 位置 | 状态 |
|------|------|------|
| 蓝牙扫描 (startDiscovery) | BluetoothService | 完整 |
| 扫描结果获取 | BluetoothService | 完整 |
| 配对 (createBond) | BluetoothService | 完整 |
| 取消配对 (removeBond via reflection) | BluetoothService | 完整 |
| 已配对设备列表 | BluetoothService | 完整 |
| BLE连接 (GATT) | BluetoothService | 完整 |
| 经典蓝牙连接 (SPP/RFCOMM) | BluetoothService | 完整 |
| 断开连接 (GATT+SPP) | BluetoothService | 完整 |
| BLE数据发送 (writeCharacteristic) | BluetoothService | 完整 |
| 经典蓝牙数据发送 (SPP OutputStream) | BluetoothService | 完整 |
| GATT服务发现 | BluetoothService | 完整 |
| 蓝牙状态查询 | BluetoothService | 完整 |
| 设备信息查询 | BluetoothService | 完整 |
| btsnoop日志启停 | HciLogService | 完整 |
| 日志复制/压缩/打包/导出 | HciLogService | 完整 |
| ADB广播命令接收 | CommandReceiver | 完整 |
| 命令分发+重试 | CommandHandler | 完整 |
| 权限请求 | MainActivity+PermissionUtil | 完整 |

### 缺失功能 (8项)

| 功能 | 设计文档要求 | 重要性 |
|------|-------------|--------|
| **BLE通知接收** | 注册Notification/Indication | 高 — 只能发不能收 |
| **CCCD描述符写入** | 使能通知需写描述符 | 高 — 否则收不到数据 |
| **MTU协商** | requestMtu协商MTU | 中 — 长包传输需要 |
| **RSSI读取** | readRemoteRssi | 中 — 信号质量监测 |
| **A2DP/HFP支持** | 经典蓝牙音频配置 | 低 — 当前聚焦SPP/BLE |
| **配置持久化** | SharedPreferences保存设置 | 中 — 重启丢失配置 |
| **主动结果推送** | 结果通过广播主动推送给PC | 中 — 目前只写logcat |
| **开机自启** | BOOT_COMPLETED已有代码 | 中 — 需要用户授权 |

## 三、代码质量问题 (7条)

### 1. 关键Bug: BLE通知未使能 — 永远收不到数据

文件: `BluetoothService.kt`

`onServicesDiscovered` 回调中发现了服务，但没有对 `onCharacteristicChanged` 需要依赖的 characteristic 使能 notification。

```kotlin
// 需要补充: 找到支持 NOTIFY的 characteristic，写CCCD描述符
val cccdUuid = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
val descriptor = characteristic.getDescriptor(cccdUuid)
descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
gatt.writeDescriptor(descriptor)
```

否则 `onCharacteristicChanged` 永远不会被触发，`RECEIVE_DATA` 命令形同虚设。

### 2. SPP接收线程缺失

文件: `BluetoothService.kt` - `connectClassicDevice()`

SPP连接后没有启动后台读取线程，服务端发来的数据不会被接收。

```kotlin
// 需要补充: socket连接后启动InputSteam读取线程
Thread {
    val input = socket.inputStream
    val buffer = ByteArray(1024)
    while (socket.isConnected) {
        val bytes = input.read(buffer)
        if (bytes > 0) {
            // handle received data
        }
    }
}.start()
```

### 3. 命令回调线程安全

文件: `CommandHandler.kt` - `handleScan()`

```kotlin
Thread {
    Thread.sleep(durationMs.toLong())
    result.stopScan()
}.start()
```

创建匿名线程调用了 `result.stopScan()`，但 `result` 是 `BluetoothService`。如果用户在停止前已断开服务或APP进入后台，可能空指针。建议用 `Handler` 或 `Coroutine`。

### 4. 异常处理过于宽泛

多处代码使用 `catch (Exception: e)` 吞掉异常：
- `BluetoothService.kt` disconnect 处
- `HciLogService.kt` 多处
- `CommandHandler.kt` 重试逻辑
- `MainActivity.kt` onDestroy 处

建议至少打印 log 或区分业务异常和系统异常。

### 5. Layout中Button硬编码

`activity_main.xml` 中的按钮通过 `findViewById` 手动绑定，代码冗长。建议迁移到 ViewBinding 或 DataBinding。

### 6. 权限请求没有细化

`PermissionUtil.checkAllPermissions` 一次性请求所有权限，没有区分Android 12+的行为变更。Android 12 以上的 `BLUETOOTH_SCAN` 不需要位置权限，但代码仍然请求。

### 7. 缺少Gradle插件版本锁定

`build.gradle.kts` 中 `kotlin-android` 插件版本未锁定到具体版本号（使用 `project` 变量方式），可能导致构建版本不一致。

## 四、修改计划

### 高优先级（不改功能不完整）

1. **CCCD描述符写入** — 在 `onServicesDiscovered` 中遍历characteristic，对支持NOTIFY的写 `ENABLE_NOTIFICATION_VALUE`
2. **SPP接收线程** — `connectClassicDevice` 成功后启动InputSteam读取线程

### 中优先级

3. **主动结果推送** — 实现一个 `ResultBroadcastReceiver` 或增加 logcat 输出的JSON格式，让PC可以通过 `adb logcat -s BT_TEST:V` 实时获取结果
4. **配置持久化** — 使用 SharedPreferences 保存设备配置、默认参数
5. **线程安全改造** — `handleScan` 改为 Handler/Coroutine

### 低优先级

6. **ViewBinding迁移** — `MainActivity` 改用 ViewBinding
7. **MTU协商** — GATT连接成功后调 `requestMtu(512)`
8. **权限逻辑升级** — 区分 Android 12+ / 12- 权限请求
