package com.bttest.handler

import android.os.Handler
import android.os.Looper

import android.content.Context
import android.os.Bundle
import com.bttest.model.CommandResult
import com.bttest.model.CommandType
import com.bttest.service.BluetoothService
import com.bttest.service.HciLogService
import com.bttest.util.LogUtil
import com.google.gson.Gson

/**
 * 命令处理器
 * 根据命令类型分发到对应的服务进行处理
 * 使用命令工厂模式处理不同类型的命令
 */
class CommandHandler(private val context: Context) {

    private val gson = Gson()

    /** 蓝牙服务绑定器引用 */
    private var bluetoothService: BluetoothService? = null

    /** HCI 日志服务绑定器引用 */
    private var hciLogService: HciLogService? = null

    /** 重试次数 */
    private var maxRetries = 3

    /**
     * 设置蓝牙服务引用
     */
    fun setBluetoothService(service: BluetoothService?) {
        this.bluetoothService = service
    }

    /**
     * 设置 HCI 日志服务引用
     */
    fun setHciLogService(service: HciLogService?) {
        this.hciLogService = service
    }

    /**
     * 设置最大重试次数
     */
    fun setMaxRetries(retries: Int) {
        this.maxRetries = retries
    }

    /**
     * 处理命令（主入口）
     */
    fun handleCommand(commandType: String?, params: Bundle?): CommandResult {
        val command = CommandType.fromString(commandType)
        if (command == null) {
            val result = CommandResult.failure(
                "Unknown command: $commandType",
                errorCode = -100,
                command = commandType
            )
            LogUtil.outputResult(result)
            return result
        }

        LogUtil.info("Handling command: ${command.name}")
        params?.let {
            LogUtil.debug("Command params: ${it.keySet().joinToString(", ") { key -> "$key=${it.get(key)}" }}")
        }

        return try {
            executeWithRetry(command, params)
        } catch (e: Exception) {
            LogUtil.error("Command execution failed: ${command.name}", e)
            val result = CommandResult.failure(
                "Execution error: ${e.message}",
                errorCode = -500,
                command = command.name
            )
            LogUtil.outputResult(result)
            result
        }
    }

    /**
     * 带重试机制的命令执行
     */
    private fun executeWithRetry(command: CommandType, params: Bundle?): CommandResult {
        var lastResult: CommandResult? = null
        var attempt = 0

        while (attempt < maxRetries) {
            attempt++
            val result = executeCommand(command, params)

            if (result.success) {
                LogUtil.outputResult(result)
                return result
            }

            lastResult = result
            LogUtil.warn("Command ${command.name} failed on attempt $attempt/$maxRetries: ${result.message}")

            if (attempt < maxRetries) {
                // 短暂延迟后重试
                Thread.sleep(500 * attempt.toLong())
            }
        }

        val finalResult = lastResult ?: CommandResult.failure(
            "Max retries exceeded",
            command = command.name
        )
        LogUtil.outputResult(finalResult)
        return finalResult
    }

    /**
     * 执行具体命令
     */
    private fun executeCommand(command: CommandType, params: Bundle?): CommandResult {
        return when (command) {
            CommandType.SCAN -> handleScan(params)
            CommandType.PAIR -> handlePair(params)
            CommandType.CONNECT -> handleConnect(params)
            CommandType.DISCONNECT -> handleDisconnect(params)
            CommandType.SEND_DATA -> handleSendData(params)
            CommandType.RECEIVE_DATA -> handleReceiveData(params)
            CommandType.ENABLE_HCI_LOG -> handleEnableHciLog()
            CommandType.DISABLE_HCI_LOG -> handleDisableHciLog()
            CommandType.GET_PAIRED_DEVICES -> handleGetPairedDevices()
            CommandType.GET_CONNECTED_DEVICES -> handleGetConnectedDevices()
            CommandType.GET_DEVICE_INFO -> handleGetDeviceInfo(params)
            CommandType.UNPAIR -> handleUnpair(params)
            CommandType.GET_BT_STATUS -> handleGetBtStatus()
        }
    }

    // ==================== 蓝牙命令处理 ====================

    private fun handleScan(params: Bundle?): CommandResult {
        val action = params?.getString("action", "start") ?: "start"
        val durationMs = params?.getInt("duration_ms", 10000) ?: 10000

        return when (action.lowercase()) {
            "start" -> {
                val result = requireBluetoothService()
                    ?: return CommandResult.failure("BluetoothService not available", command = "SCAN")
                val scanResult = result.startScan()

                // 如果指定了扫描持续时间，自动在指定时间后停止扫描 (Fix 3: 改用Handler)
                if (scanResult.success && durationMs > 0) {
                    val btService = result
                    Handler(Looper.getMainLooper()).postDelayed({
                        try {
                            btService.stopScan()
                        } catch (e: Exception) {
                            LogUtil.error("Auto stop scan failed", e)
                        }
                    }, durationMs.toLong())
                }

                scanResult
            }
            "stop" -> {
                requireBluetoothService()?.stopScan()
                    ?: CommandResult.failure("BluetoothService not available", command = "SCAN")
            }
            "list" -> {
                val devices = requireBluetoothService()?.getDiscoveredDevices() ?: emptyList()
                CommandResult.success(
                    "Found ${devices.size} discovered devices",
                    data = gson.toJson(devices),
                    command = "SCAN"
                )
            }
            else -> CommandResult.failure("Unknown scan action: $action", command = "SCAN")
        }
    }

    private fun handlePair(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "PAIR")

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "PAIR")

        return btService.pairDevice(address)
    }

    private fun handleUnpair(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "UNPAIR")

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "UNPAIR")

        return btService.unpairDevice(address)
    }

    private fun handleConnect(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "CONNECT")
        val connectionType = params?.getString("type", "gatt") ?: "gatt"

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "CONNECT")

        return when (connectionType.lowercase()) {
            "gatt", "ble" -> btService.connectDevice(address)
            "spp", "classic" -> btService.connectClassicDevice(address)
            else -> CommandResult.failure(
                "Unknown connection type: $connectionType. Use 'gatt' or 'spp'",
                command = "CONNECT"
            )
        }
    }

    private fun handleDisconnect(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "DISCONNECT")

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "DISCONNECT")

        return btService.disconnectDevice(address)
    }

    private fun handleSendData(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "SEND_DATA")
        val dataStr = params?.getString("data")
            ?: return CommandResult.failure("Missing parameter: data", command = "SEND_DATA")
        val connectionType = params?.getString("type", "gatt") ?: "gatt"

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "SEND_DATA")

        // 支持 Hex 和 UTF-8 两种数据格式
        val data = if (params.getBoolean("is_hex", false)) {
            // Hex 格式: "AA BB CC"
            dataStr.split(" ", "\n", "\t")
                .filter { it.isNotBlank() }
                .map { it.toInt(16).toByte() }
                .toByteArray()
        } else {
            dataStr.toByteArray(Charsets.UTF_8)
        }

        return when (connectionType.lowercase()) {
            "gatt", "ble" -> btService.sendData(address, data)
            "spp", "classic" -> btService.sendDataClassic(address, data)
            else -> CommandResult.failure(
                "Unknown connection type: $connectionType",
                command = "SEND_DATA"
            )
        }
    }

    private fun handleReceiveData(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "RECEIVE_DATA")

        // 接收数据主要通过 BLE 通知/指示回调实现
        // 这里主要用于标记设备以接收数据
        return CommandResult.success(
            "Listening for data from $address. Data will be output via logcat notifications.",
            data = "{\"device\": \"$address\", \"status\": \"listening\"}",
            command = "RECEIVE_DATA"
        )
    }

    private fun handleGetPairedDevices(): CommandResult {
        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "GET_PAIRED_DEVICES")

        val devices = btService.getPairedDevices()
        return CommandResult.success(
            "Found ${devices.size} paired devices",
            data = gson.toJson(devices),
            command = "GET_PAIRED_DEVICES"
        )
    }

    private fun handleGetConnectedDevices(): CommandResult {
        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "GET_CONNECTED_DEVICES")

        val devices = btService.getConnectedDevices()
        return CommandResult.success(
            "Found ${devices.size} connected devices",
            data = gson.toJson(devices),
            command = "GET_CONNECTED_DEVICES"
        )
    }

    private fun handleGetDeviceInfo(params: Bundle?): CommandResult {
        val address = params?.getString("address")
            ?: return CommandResult.failure("Missing parameter: address", command = "GET_DEVICE_INFO")

        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "GET_DEVICE_INFO")

        return btService.getDeviceInfo(address)
    }

    private fun handleGetBtStatus(): CommandResult {
        val btService = requireBluetoothService()
            ?: return CommandResult.failure("BluetoothService not available", command = "GET_BT_STATUS")

        return btService.getBluetoothStatus()
    }

    // ==================== HCI 日志命令处理 ====================

    private fun handleEnableHciLog(): CommandResult {
        val hciService = requireHciLogService()
            ?: return CommandResult.failure("HciLogService not available", command = "ENABLE_HCI_LOG")

        return hciService.enableHciLog()
    }

    private fun handleDisableHciLog(): CommandResult {
        val hciService = requireHciLogService()
            ?: return CommandResult.failure("HciLogService not available", command = "DISABLE_HCI_LOG")

        return hciService.disableHciLog()
    }

    // ==================== 辅助方法 ====================

    private fun requireBluetoothService(): BluetoothService? {
        return bluetoothService
    }

    private fun requireHciLogService(): HciLogService? {
        return hciLogService
    }
}
