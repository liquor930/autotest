"""
Apply all APP fixes:
1. CCCD descriptor write in onServicesDiscovered
2. SPP receive thread in connectClassicDevice
3. Thread safety in CommandHandler.handleScan (use Handler)
4. Better exception logging in catch blocks
"""
import os, re

BT_SERVICE = r'D:\code\AutoTest\bluetooth_test_app\app\src\main\java\com\bttest\service\BluetoothService.kt'
CMD_HANDLER = r'D:\code\AutoTest\bluetooth_test_app\app\src\main\java\com\bttest\handler\CommandHandler.kt'

changes = []

# ============ Fix 1: CCCD in onServicesDiscovered ============
with open(BT_SERVICE, encoding='utf-8') as f:
    bt = f.read()

# Add CCCD UUID constant and notification handling
old_gatt_callback = '''    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            val deviceAddress = gatt.device.address
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                LogUtil.info("GATT connected to $deviceAddress")
                LogUtil.outputResult(
                    CommandResult.success("GATT connected: $deviceAddress", command = "CONNECT")
                )
                // 连接成功后自动发现服务
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                LogUtil.info("GATT disconnected from $deviceAddress")
                gattConnections.remove(deviceAddress)
                try { gatt.close() } catch (e: Exception) { /* ignore */ }
                LogUtil.outputResult(
                    CommandResult.success("GATT disconnected: $deviceAddress", command = "DISCONNECT")
                )
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                LogUtil.info("Services discovered for ${gatt.device.address}")
                val services = gatt.services.map { service ->
                    mapOf(
                        "uuid" to service.uuid.toString(),
                        "type" to (if (service.type == BluetoothGattService.SERVICE_TYPE_PRIMARY) "PRIMARY" else "SECONDARY"),
                        "characteristics" to service.characteristics.map { char ->
                            mapOf(
                                "uuid" to char.uuid.toString(),
                                "properties" to char.properties,
                                "permissions" to char.permissions
                            )
                        }
                    )
                }
                LogUtil.outputResult(
                    CommandResult.success(
                        "Services discovered for ${gatt.device.address}",
                        data = gson.toJson(services),
                        command = "CONNECT"
                    )
                )
            } else {
                LogUtil.warn("Service discovery failed for ${gatt.device.address}: status=$status")
            }
        }'''

new_gatt_callback = '''    /** CCCD UUID — 客户端特性配置描述符 */
    private val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            val deviceAddress = gatt.device.address
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                LogUtil.info("GATT connected to $deviceAddress")
                LogUtil.outputResult(
                    CommandResult.success("GATT connected: $deviceAddress", command = "CONNECT")
                )
                // 连接成功后自动发现服务
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                LogUtil.info("GATT disconnected from $deviceAddress")
                gattConnections.remove(deviceAddress)
                try { gatt.close() } catch (e: Exception) { LogUtil.warn("GATT close: ${e.message}") }
                LogUtil.outputResult(
                    CommandResult.success("GATT disconnected: $deviceAddress", command = "DISCONNECT")
                )
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                LogUtil.info("Services discovered for ${gatt.device.address}")
                val services = gatt.services.map { service ->
                    mapOf(
                        "uuid" to service.uuid.toString(),
                        "type" to (if (service.type == BluetoothGattService.SERVICE_TYPE_PRIMARY) "PRIMARY" else "SECONDARY"),
                        "characteristics" to service.characteristics.map { char ->
                            mapOf(
                                "uuid" to char.uuid.toString(),
                                "properties" to char.properties,
                                "permissions" to char.permissions
                            )
                        }
                    )
                }
                LogUtil.outputResult(
                    CommandResult.success(
                        "Services discovered for ${gatt.device.address}",
                        data = gson.toJson(services),
                        command = "CONNECT"
                    )
                )

                // === Fix 1: Enable BLE notifications/indications ===
                enableGattNotifications(gatt)
            } else {
                LogUtil.warn("Service discovery failed for ${gatt.device.address}: status=$status")
            }
        }

        /**
         * 遍历服务中的 characteristic，对支持 NOTIFY/INDICATE 的注册通知
         */
        private fun enableGattNotifications(gatt: BluetoothGatt) {
            try {
                for (service in gatt.services) {
                    for (characteristic in service.characteristics) {
                        val properties = characteristic.properties
                        val canNotify = (properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY) > 0
                        val canIndicate = (properties and BluetoothGattCharacteristic.PROPERTY_INDICATE) > 0

                        if (!canNotify && !canIndicate) continue

                        val descriptor = characteristic.getDescriptor(CCCD_UUID) ?: continue
                        descriptor.value = if (canIndicate)
                            BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
                        else
                            BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE

                        gatt.setCharacteristicNotification(characteristic, true)
                        gatt.writeDescriptor(descriptor)

                        LogUtil.info("Notification enabled for ${characteristic.uuid} on ${gatt.device.address}")
                    }
                }
            } catch (e: SecurityException) {
                LogUtil.warn("Security exception enabling notifications: ${e.message}")
            }
        }'''

if old_gatt_callback in bt:
    bt = bt.replace(old_gatt_callback, new_gatt_callback)
    changes.append("Fix 1: CCCD notification enable in onServicesDiscovered")
else:
    changes.append("Fix 1: SKIPPED - gattCallback pattern not found")

# ============ Fix 2: SPP receive thread in connectClassicDevice ============
old_connect_classic = '''            val socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            socket.connect()
            socketConnections[address] = socket
            LogUtil.info("Classic Bluetooth connected to $address")
            CommandResult.success("Connected to $address", command = "CONNECT")'''

new_connect_classic = '''            val socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            socket.connect()
            socketConnections[address] = socket
            LogUtil.info("Classic Bluetooth connected to $address")

            // === Fix 2: Start SPP receive thread ===
            startSppReceiveThread(address, socket)

            CommandResult.success("Connected to $address", command = "CONNECT")'''

if old_connect_classic in bt:
    bt = bt.replace(old_connect_classic, new_connect_classic)
    changes.append("Fix 2: SPP receive thread started")
else:
    changes.append("Fix 2: SKIPPED - connectClassic pattern not found")

# Add the SPP receive thread method before the companion object
old_companion = '''    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")'''

spp_receive_method = '''    // === Fix 2: SPP data receive thread ===
    private fun startSppReceiveThread(address: String, socket: BluetoothSocket) {
        Thread({
            try {
                val input: InputStream = socket.inputStream
                val buffer = ByteArray(4096)
                val deviceAddress = address
                while (socket.isConnected) {
                    val bytes = input.read(buffer)
                    if (bytes > 0) {
                        val data = buffer.copyOf(bytes)
                        val hex = data.joinToString(" ") { "%02x".format(it) }
                        LogUtil.info("SPP data received from $deviceAddress: $hex")
                        LogUtil.outputResult(
                            CommandResult.success(
                                "SPP data received ($bytes bytes) from $deviceAddress",
                                data = hex,
                                command = "RECEIVE_DATA"
                            )
                        )
                    }
                }
            } catch (e: IOException) {
                LogUtil.warn("SPP receive thread ended for $address: ${e.message}")
            } catch (e: Exception) {
                LogUtil.warn("SPP receive thread error for $address: ${e.message}")
            }
        }, "spp-recv-$address").apply { isDaemon = true; start() }
    }

    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")'''

if old_companion in bt:
    bt = bt.replace(old_companion, spp_receive_method)
    changes.append("Fix 2: SPP receive thread method added")
else:
    changes.append("Fix 2: SKIPPED - companion object not found")

# Add import for InputStream
bt = bt.replace(
    "import java.io.IOException\nimport java.io.InputStream\nimport java.io.OutputStream",
    "import java.io.IOException\nimport java.io.InputStream\nimport java.io.OutputStream"
)
if not 'import java.io.InputStream' in bt:
    bt = bt.replace(
        "import java.io.IOException",
        "import java.io.IOException\nimport java.io.InputStream"
    )
    changes.append("Fix 2: Added InputStream import")

# Fix broad catch blocks - add logging
# Replace catch blocks that only have comments
bt = bt.replace(
    "try { gatt.close() } catch (e: Exception) { /* ignore */ }",
    "try { gatt.close() } catch (e: Exception) { LogUtil.warn(\"GATT close: ${e.message}\") }"
)

# Same for socket close in destroy
bt = bt.replace(
    "try { socket.close() } catch (e: Exception) { /* ignore */ }",
    "try { socket.close() } catch (e: Exception) { LogUtil.warn(\"Socket close: ${e.message}\") }"
)

changes.append("Fix 4: Added logging to broad catch blocks")

# Unregister receiver catch blocks
bt = bt.replace(
    '} catch (e: IllegalArgumentException) {\n            // 可能已经取消注册\n        }',
    '} catch (e: IllegalArgumentException) { LogUtil.warn("Unregister receiver: ${e.message}") }'
)

with open(BT_SERVICE, 'w', encoding='utf-8') as f:
    f.write(bt)

print("BluetoothService.kt updated")

# ============ Fix 3: CommandHandler thread safety ============
with open(CMD_HANDLER, encoding='utf-8') as f:
    ch = f.read()

# Add import for Handler and Looper
ch = ch.replace(
    "package com.bttest.handler",
    "package com.bttest.handler\n\nimport android.os.Handler\nimport android.os.Looper"
)
changes.append("Fix 3: Added Handler import")

old_scan_thread = '''                // 如果指定了扫描持续时间，自动在指定时间后停止扫描
                if (scanResult.success && durationMs > 0) {
                    Thread {
                        Thread.sleep(durationMs.toLong())
                        result.stopScan()
                    }.start()
                }'''

new_scan_handler = '''                // 如果指定了扫描持续时间，自动在指定时间后停止扫描 (Fix 3: 改用Handler)
                if (scanResult.success && durationMs > 0) {
                    val btService = result
                    Handler(Looper.getMainLooper()).postDelayed({
                        try {
                            btService.stopScan()
                        } catch (e: Exception) {
                            LogUtil.error("Auto stop scan failed", e)
                        }
                    }, durationMs.toLong())
                }'''

if old_scan_thread in ch:
    ch = ch.replace(old_scan_thread, new_scan_handler)
    changes.append("Fix 3: handleScan uses Handler instead of raw Thread")
else:
    changes.append("Fix 3: SKIPPED - scan thread pattern not found")

with open(CMD_HANDLER, 'w', encoding='utf-8') as f:
    f.write(ch)

print("CommandHandler.kt updated")

# ============ Write report ============
report = "APP Fixes Applied\n" + "="*40 + "\n"
for c in changes:
    report += f"  {c}\n"
report += "\nDone."
with open(r'D:\code\AutoTest\_fix_result.txt', 'w', encoding='utf-8') as f:
    f.write(report)

print("Report written")
