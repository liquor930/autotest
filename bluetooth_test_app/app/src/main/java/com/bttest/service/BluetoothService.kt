package com.bttest.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothSocket
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Binder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.bttest.model.BluetoothDeviceInfo
import com.bttest.model.CommandResult
import com.bttest.util.LogUtil
import com.google.gson.Gson
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * 蓝牙操作服务
 * 在后台运行，负责蓝牙扫描、配对、连接、数据传输等操作
 */
class BluetoothService : Service() {

    /** Binder 用于 Activity 与服务通信 */
    private val binder = BluetoothBinder()

    /** 蓝牙适配器 */
    private var bluetoothAdapter: BluetoothAdapter? = null

    /** 蓝牙管理器 */
    private var bluetoothManager: BluetoothManager? = null

    /** 已发现的设备缓存 */
    private val discoveredDevices = ConcurrentHashMap<String, BluetoothDeviceInfo>()

    /** 已连接的 GATT 连接 */
    private val gattConnections = ConcurrentHashMap<String, BluetoothGatt>()

    /** 已连接的经典蓝牙 Socket */
    private val socketConnections = ConcurrentHashMap<String, BluetoothSocket>()

    /** 是否正在扫描 */
    @Volatile
    private var isScanning = false

    /** Gson 实例 */
    private val gson = Gson()

    /** SPP UUID（标准串口协议） */
    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        const val CHANNEL_ID = "bluetooth_service_channel"
        const val NOTIFICATION_ID = 1001
        const val ACTION_STOP_SERVICE = "com.bttest.STOP_SERVICE"
        const val ACTION_START_SCAN = "com.bttest.START_SCAN"
        const val ACTION_STOP_SCAN = "com.bttest.STOP_SCAN"
    }

    // ==================== 发现接收器 ====================

    /** 蓝牙设备发现广播接收器 */
    private val discoveryReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                BluetoothDevice.ACTION_FOUND -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    val rssi = intent.getShortExtra(BluetoothDevice.EXTRA_RSSI, Short.MIN_VALUE).toInt()
                    device?.let { onDeviceDiscovered(it, rssi) }
                }
                BluetoothAdapter.ACTION_DISCOVERY_STARTED -> {
                    LogUtil.info("Discovery started")
                }
                BluetoothAdapter.ACTION_DISCOVERY_FINISHED -> {
                    LogUtil.info("Discovery finished")
                    onDiscoveryFinished()
                }
            }
        }
    }

    /** 蓝牙配对状态广播接收器 */
    private val bondStateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == BluetoothDevice.ACTION_BOND_STATE_CHANGED) {
                val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                }
                val bondState = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.BOND_NONE)
                val previousBondState = intent.getIntExtra(
                    BluetoothDevice.EXTRA_PREVIOUS_BOND_STATE,
                    BluetoothDevice.BOND_NONE
                )
                device?.let { onBondStateChanged(it, bondState, previousBondState) }
            }
        }
    }

    /** 蓝牙连接状态广播接收器 */
    private val connectionStateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                BluetoothDevice.ACTION_ACL_CONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    device?.let { onDeviceConnected(it) }
                }
                BluetoothDevice.ACTION_ACL_DISCONNECTED -> {
                    val device: BluetoothDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    }
                    device?.let { onDeviceDisconnected(it) }
                }
            }
        }
    }

    // ==================== 生命周期 ====================

    override fun onCreate() {
        super.onCreate()
        LogUtil.info("BluetoothService created")

        // 初始化蓝牙
        bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
        bluetoothAdapter = bluetoothManager?.adapter

        // 注册广播接收器
        val discoveryFilter = IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_FOUND)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_STARTED)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED)
        }
        registerReceiver(discoveryReceiver, discoveryFilter)

        val bondFilter = IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
        registerReceiver(bondStateReceiver, bondFilter)

        val connFilter = IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_ACL_CONNECTED)
            addAction(BluetoothDevice.ACTION_ACL_DISCONNECTED)
        }
        registerReceiver(connectionStateReceiver, connFilter)

        // 创建通知渠道并启动前台服务
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification())
    }

    override fun onDestroy() {
        // 取消注册所有广播接收器
        try {
            unregisterReceiver(discoveryReceiver)
            unregisterReceiver(bondStateReceiver)
            unregisterReceiver(connectionStateReceiver)
        } catch (e: IllegalArgumentException) {
            // 可能已经取消注册
        }

        // 停止扫描
        stopScan()

        // 关闭所有连接
        gattConnections.values.forEach { gatt ->
            try { gatt.close() } catch (e: Exception) { /* ignore */ }
        }
        gattConnections.clear()

        socketConnections.values.forEach { socket ->
            try { socket.close() } catch (e: Exception) { /* ignore */ }
        }
        socketConnections.clear()

        LogUtil.info("BluetoothService destroyed")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }

    inner class BluetoothBinder : Binder() {
        fun getService(): BluetoothService = this@BluetoothService
    }

    // ==================== 蓝牙扫描 ====================

    /**
     * 开始扫描蓝牙设备
     */
    fun startScan(): CommandResult {
        if (bluetoothAdapter == null) {
            return CommandResult.failure("Bluetooth is not supported on this device", command = "SCAN")
        }

        if (!bluetoothAdapter!!.isEnabled) {
            return CommandResult.failure("Bluetooth is not enabled", errorCode = -2, command = "SCAN")
        }

        if (isScanning) {
            return CommandResult.failure("Scan is already in progress", errorCode = -3, command = "SCAN")
        }

        // 检查位置权限（蓝牙扫描需要）
        if (!com.bttest.util.PermissionUtil.checkLocationPermissions(this)) {
            return CommandResult.failure(
                "Location permission not granted, cannot perform Bluetooth scan",
                errorCode = -4,
                command = "SCAN"
            )
        }

        discoveredDevices.clear()
        val started = bluetoothAdapter!!.startDiscovery()
        if (started) {
            isScanning = true
            LogUtil.info("Bluetooth scan started")
            return CommandResult.success("Scan started successfully", command = "SCAN")
        } else {
            return CommandResult.failure("Failed to start scan", command = "SCAN")
        }
    }

    /**
     * 停止扫描
     */
    fun stopScan(): CommandResult {
        if (!isScanning) {
            return CommandResult.failure("No scan in progress", command = "SCAN")
        }

        bluetoothAdapter?.cancelDiscovery()
        isScanning = false
        LogUtil.info("Bluetooth scan stopped")

        val deviceList = discoveredDevices.values.toList()
        val result = CommandResult.success(
            "Scan stopped. Found ${deviceList.size} devices",
            data = gson.toJson(deviceList),
            command = "SCAN"
        )
        return result
    }

    /**
     * 获取已发现的设备列表
     */
    fun getDiscoveredDevices(): List<BluetoothDeviceInfo> {
        return discoveredDevices.values.toList()
    }

    // ==================== 配对管理 ====================

    /**
     * 与指定设备配对
     */
    fun pairDevice(address: String): CommandResult {
        val device = findDevice(address)
            ?: return CommandResult.failure("Device not found: $address", command = "PAIR")

        if (device.bondState == BluetoothDevice.BOND_BONDED) {
            return CommandResult.success("Device already paired", command = "PAIR")
        }

        return try {
            val success = device.createBond()
            if (success) {
                CommandResult.success("Pairing initiated for $address", command = "PAIR")
            } else {
                CommandResult.failure("Failed to initiate pairing for $address", command = "PAIR")
            }
        } catch (e: SecurityException) {
            CommandResult.failure(
                "Security exception: ${e.message}",
                errorCode = -4,
                command = "PAIR"
            )
        } catch (e: Exception) {
            CommandResult.failure("Pairing error: ${e.message}", command = "PAIR")
        }
    }

    /**
     * 取消配对
     */
    fun unpairDevice(address: String): CommandResult {
        val device = findDevice(address)
            ?: return CommandResult.failure("Device not found: $address", command = "UNPAIR")

        return try {
            val method = device.javaClass.getMethod("removeBond")
            val result = method.invoke(device) as? Boolean ?: false
            if (result) {
                CommandResult.success("Unpaired successfully: $address", command = "UNPAIR")
            } else {
                CommandResult.failure("Failed to unpair: $address", command = "UNPAIR")
            }
        } catch (e: Exception) {
            CommandResult.failure("Unpair error: ${e.message}", command = "UNPAIR")
        }
    }

    /**
     * 获取已配对的设备列表
     */
    fun getPairedDevices(): List<BluetoothDeviceInfo> {
        val devices = mutableListOf<BluetoothDeviceInfo>()
        try {
            bluetoothAdapter?.bondedDevices?.forEach { device ->
                devices.add(BluetoothDeviceInfo.fromBluetoothDevice(device))
            }
        } catch (e: SecurityException) {
            LogUtil.error("Failed to get paired devices", e)
        }
        return devices
    }

    // ==================== 连接管理 ====================

    /**
     * 连接蓝牙设备（GATT - BLE）
     */
    fun connectDevice(address: String): CommandResult {
        val device = findDevice(address)
            ?: return CommandResult.failure("Device not found: $address", command = "CONNECT")

        // 检查是否已连接
        if (gattConnections.containsKey(address)) {
            return CommandResult.success("Already connected to $address", command = "CONNECT")
        }

        return try {
            val gatt = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                device.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
            } else {
                @Suppress("DEPRECATION")
                device.connectGatt(this, false, gattCallback)
            }

            if (gatt != null) {
                gattConnections[address] = gatt
                CommandResult.success("Connecting to $address...", command = "CONNECT")
            } else {
                CommandResult.failure("Failed to initiate connection to $address", command = "CONNECT")
            }
        } catch (e: SecurityException) {
            CommandResult.failure(
                "Security exception: ${e.message}", errorCode = -4, command = "CONNECT"
            )
        } catch (e: Exception) {
            CommandResult.failure("Connection error: ${e.message}", command = "CONNECT")
        }
    }

    /**
     * 连接蓝牙设备（SPP - 经典蓝牙）
     */
    fun connectClassicDevice(address: String): CommandResult {
        val device = findDevice(address)
            ?: return CommandResult.failure("Device not found: $address", command = "CONNECT")

        if (socketConnections.containsKey(address)) {
            return CommandResult.success("Already connected to $address", command = "CONNECT")
        }

        return try {
            val socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            socket.connect()
            socketConnections[address] = socket
            LogUtil.info("Classic Bluetooth connected to $address")
            CommandResult.success("Connected to $address", command = "CONNECT")
        } catch (e: IOException) {
            CommandResult.failure("SPP connection failed: ${e.message}", command = "CONNECT")
        } catch (e: SecurityException) {
            CommandResult.failure(
                "Security exception: ${e.message}", errorCode = -4, command = "CONNECT"
            )
        }
    }

    /**
     * 断开蓝牙设备连接
     */
    fun disconnectDevice(address: String): CommandResult {
        var disconnected = false

        // 断开 GATT 连接
        gattConnections[address]?.let { gatt ->
            try {
                gatt.disconnect()
                gatt.close()
                disconnected = true
            } catch (e: SecurityException) {
                LogUtil.warn("Security exception during GATT disconnect: ${e.message}")
            }
            gattConnections.remove(address)
        }

        // 断开 SPP 连接
        socketConnections[address]?.let { socket ->
            try {
                socket.close()
                disconnected = true
            } catch (e: IOException) {
                LogUtil.warn("IOException during socket close: ${e.message}")
            }
            socketConnections.remove(address)
        }

        return if (disconnected) {
            LogUtil.info("Disconnected from $address")
            CommandResult.success("Disconnected from $address", command = "DISCONNECT")
        } else {
            CommandResult.failure(
                "No active connection to $address",
                errorCode = -1,
                command = "DISCONNECT"
            )
        }
    }

    /**
     * 获取已连接的设备列表
     */
    fun getConnectedDevices(): List<BluetoothDeviceInfo> {
        val connected = mutableListOf<BluetoothDeviceInfo>()
        try {
            // 通过 getConnectedDevices 获取已连接的 GATT 设备
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                bluetoothManager?.getConnectedDevices(BluetoothProfile.GATT)?.forEach { device ->
                    val info = BluetoothDeviceInfo.fromBluetoothDevice(device, isConnected = true)
                    connected.add(info)
                }
            }
        } catch (e: SecurityException) {
            LogUtil.warn("Security exception when getting connected devices: ${e.message}")
        }

        // 添加通过服务连接的设备
        gattConnections.keys.forEach { address ->
            if (connected.none { it.address == address }) {
                val device = findDevice(address)
                if (device != null) {
                    connected.add(BluetoothDeviceInfo.fromBluetoothDevice(device, isConnected = true))
                }
            }
        }
        socketConnections.keys.forEach { address ->
            if (connected.none { it.address == address }) {
                val device = findDevice(address)
                if (device != null) {
                    connected.add(BluetoothDeviceInfo.fromBluetoothDevice(device, isConnected = true))
                }
            }
        }

        return connected
    }

    // ==================== 数据传输 ====================

    /**
     * 发送数据到已连接的 BLE 设备
     */
    fun sendData(address: String, data: ByteArray): CommandResult {
        val gatt = gattConnections[address]
            ?: return CommandResult.failure("Device not connected: $address", command = "SEND_DATA")

        return try {
            // 查找可写的 characteristic 并写入数据
            val services = gatt.services ?: return CommandResult.failure(
                "No services discovered yet", command = "SEND_DATA"
            )

            var written = false
            for (service in services) {
                for (characteristic in service.characteristics) {
                    if (characteristic.properties and
                        (BluetoothGattCharacteristic.PROPERTY_WRITE or
                                BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) > 0
                    ) {
                        characteristic.value = data
                        val writeType = if (characteristic.properties and
                            BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE > 0
                        ) {
                            BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                        } else {
                            BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                        }
                        characteristic.writeType = writeType
                        gatt.writeCharacteristic(characteristic)
                        written = true
                        break
                    }
                }
                if (written) break
            }

            if (written) {
                CommandResult.success(
                    "Data sent (${data.size} bytes) to $address",
                    command = "SEND_DATA"
                )
            } else {
                CommandResult.failure(
                    "No writable characteristic found for $address",
                    command = "SEND_DATA"
                )
            }
        } catch (e: SecurityException) {
            CommandResult.failure(
                "Security exception: ${e.message}", errorCode = -4, command = "SEND_DATA"
            )
        }
    }

    /**
     * 通过经典蓝牙 SPP 发送数据
     */
    fun sendDataClassic(address: String, data: ByteArray): CommandResult {
        val socket = socketConnections[address]
            ?: return CommandResult.failure("Device not connected via SPP: $address", command = "SEND_DATA")

        return try {
            val outputStream: OutputStream = socket.outputStream
            outputStream.write(data)
            outputStream.flush()
            CommandResult.success(
                "Data sent (${data.size} bytes) to $address via SPP",
                command = "SEND_DATA"
            )
        } catch (e: IOException) {
            CommandResult.failure("SPP send failed: ${e.message}", command = "SEND_DATA")
        }
    }

    // ==================== 蓝牙状态 ====================

    /**
     * 获取蓝牙适配器状态
     */
    fun getBluetoothStatus(): CommandResult {
        val adapter = bluetoothAdapter ?: return CommandResult.failure(
            "Bluetooth not supported", command = "GET_BT_STATUS"
        )

        val status = mapOf(
            "enabled" to adapter.isEnabled,
            "state" to getStateName(adapter.state),
            "name" to (adapter.name ?: "Unknown"),
            "address" to (adapter.address ?: "Unknown"),
            "is_scanning" to isScanning,
            "connected_devices_count" to gattConnections.size + socketConnections.size,
            "paired_devices_count" to (adapter.bondedDevices?.size ?: 0)
        )

        return CommandResult.success(
            "Bluetooth status retrieved",
            data = gson.toJson(status),
            command = "GET_BT_STATUS"
        )
    }

    /**
     * 获取设备详细信息
     */
    fun getDeviceInfo(address: String): CommandResult {
        val device = findDevice(address)
            ?: return CommandResult.failure("Device not found: $address", command = "GET_DEVICE_INFO")

        val info = BluetoothDeviceInfo.fromBluetoothDevice(
            device,
            isConnected = gattConnections.containsKey(address) || socketConnections.containsKey(address)
        )

        return CommandResult.success(
            "Device info retrieved",
            data = gson.toJson(info),
            command = "GET_DEVICE_INFO"
        )
    }

    // ==================== 内部方法 ====================

    private fun findDevice(address: String): BluetoothDevice? {
        // 先从 adapter 查找
        return try {
            bluetoothAdapter?.getRemoteDevice(address)
        } catch (e: IllegalArgumentException) {
            null
        }
    }

    private fun onDeviceDiscovered(device: BluetoothDevice, rssi: Int) {
        val deviceInfo = BluetoothDeviceInfo.fromBluetoothDevice(device, rssi)
        discoveredDevices[device.address] = deviceInfo
        LogUtil.info("Device found: ${device.name} (${device.address}) RSSI: $rssi dBm")
    }

    private fun onDiscoveryFinished() {
        isScanning = false
        LogUtil.info("Discovery finished. Total devices: ${discoveredDevices.size}")
        LogUtil.outputDeviceList(discoveredDevices.values.toList())
    }

    private fun onBondStateChanged(device: BluetoothDevice, newState: Int, previousState: Int) {
        val stateName = BluetoothDeviceInfo.getBondStateName(newState)
        LogUtil.info("Bond state changed for ${device.address}: $stateName (was: ${BluetoothDeviceInfo.getBondStateName(previousState)})")

        val result = if (newState == BluetoothDevice.BOND_BONDED) {
            CommandResult.success("Device paired: ${device.address} - ${device.name}", command = "PAIR")
        } else if (newState == BluetoothDevice.BOND_NONE && previousState == BluetoothDevice.BOND_BONDED) {
            CommandResult.success("Device unpaired: ${device.address}", command = "UNPAIR")
        } else if (newState == BluetoothDevice.BOND_NONE && previousState == BluetoothDevice.BOND_BONDING) {
            CommandResult.failure("Pairing failed for ${device.address}", command = "PAIR")
        } else {
            null
        }

        result?.let { LogUtil.outputResult(it) }
    }

    private fun onDeviceConnected(device: BluetoothDevice) {
        LogUtil.info("Device connected: ${device.address}")
        LogUtil.outputResult(
            CommandResult.success("Device connected: ${device.address}", command = "CONNECT")
        )
    }

    private fun onDeviceDisconnected(device: BluetoothDevice) {
        LogUtil.info("Device disconnected: ${device.address}")
        gattConnections.remove(device.address)
        socketConnections.remove(device.address)
        LogUtil.outputResult(
            CommandResult.success("Device disconnected: ${device.address}", command = "DISCONNECT")
        )
    }

    // ==================== GATT 回调 ====================

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
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val hexData = characteristic.value.joinToString(" ") { "%02x".format(it) }
                LogUtil.info("Read characteristic: ${characteristic.uuid} = $hexData")
                LogUtil.outputResult(
                    CommandResult.success(
                        "Data received from ${gatt.device.address}",
                        data = hexData,
                        command = "RECEIVE_DATA"
                    )
                )
            }
        }

        override fun onCharacteristicWrite(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                LogUtil.info("Write to characteristic ${characteristic.uuid} succeeded")
                LogUtil.outputResult(
                    CommandResult.success(
                        "Data written to ${gatt.device.address}",
                        command = "SEND_DATA"
                    )
                )
            } else {
                LogUtil.warn("Write to characteristic ${characteristic.uuid} failed: status=$status")
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            val hexData = characteristic.value.joinToString(" ") { "%02x".format(it) }
            LogUtil.info("Characteristic changed: ${characteristic.uuid} = $hexData")
            LogUtil.outputResult(
                CommandResult.success(
                    "Notification from ${gatt.device.address}",
                    data = hexData,
                    command = "RECEIVE_DATA"
                )
            )
        }
    }

    // ==================== 通知 ====================

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Bluetooth Test Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Notification for Bluetooth Test Service"
                setShowBadge(false)
            }
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getBroadcast(
            this,
            0,
            Intent(ACTION_STOP_SERVICE),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE
            else 0
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Bluetooth Test Service")
            .setContentText("Running Bluetooth operations...")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(android.R.drawable.ic_media_pause, "Stop", pendingIntent)
            .build()
    }

    private fun getStateName(state: Int): String {
        return when (state) {
            BluetoothAdapter.STATE_OFF -> "OFF"
            BluetoothAdapter.STATE_TURNING_ON -> "TURNING_ON"
            BluetoothAdapter.STATE_ON -> "ON"
            BluetoothAdapter.STATE_TURNING_OFF -> "TURNING_OFF"
            else -> "UNKNOWN"
        }
    }
}
