package com.bttest

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.widget.Button
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.bttest.handler.CommandHandler
import com.bttest.model.CommandResult
import com.bttest.receiver.CommandReceiver
import com.bttest.service.BluetoothService
import com.bttest.service.HciLogService
import com.bttest.util.LogUtil
import com.bttest.util.PermissionUtil
import com.google.gson.Gson
import com.google.gson.GsonBuilder

/**
 * 主 Activity
 * 提供简单的 UI 用于监控服务状态和执行测试命令
 * 实际主要功能通过 ADB 广播命令驱动
 */
class MainActivity : AppCompatActivity() {

    // 服务引用
    private var bluetoothService: BluetoothService? = null
    private var hciLogService: HciLogService? = null
    private var commandHandler: CommandHandler? = null
    private var commandReceiver: CommandReceiver? = null

    // UI 组件
    private lateinit var statusTextView: TextView
    private lateinit var logTextView: TextView
    private lateinit var scrollView: ScrollView

    // 日志缓冲区
    private val logBuffer = StringBuilder()
    private val gson = GsonBuilder().setPrettyPrinting().create()

    // 权限请求码
    companion object {
        private const val REQUEST_ALL_PERMISSIONS = 1001
    }

    // ==================== 服务连接 ====================

    private val bluetoothServiceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as? BluetoothService.BluetoothBinder
            bluetoothService = binder?.getService()
            commandHandler?.setBluetoothService(bluetoothService)
            appendLog("BluetoothService connected")
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            bluetoothService = null
            commandHandler?.setBluetoothService(null)
            appendLog("BluetoothService disconnected")
        }
    }

    private val hciLogServiceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as? HciLogService.HciLogBinder
            hciLogService = binder?.getService()
            commandHandler?.setHciLogService(hciLogService)
            appendLog("HciLogService connected")
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            hciLogService = null
            commandHandler?.setHciLogService(null)
            appendLog("HciLogService disconnected")
        }
    }

    // ==================== 生命周期 ====================

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // 初始化 UI
        statusTextView = findViewById(R.id.statusTextView)
        logTextView = findViewById(R.id.logTextView)
        scrollView = findViewById(R.id.scrollView)

        // 初始化命令处理器
        commandHandler = CommandHandler(this)

        // 初始化广播接收器
        commandReceiver = CommandReceiver()
        commandReceiver?.setCommandHandler(commandHandler!!)

        // 注册广播接收器
        registerCommandReceiver()

        // 设置按钮事件
        setupButtons()

        // 请求权限
        requestPermissionsIfNeeded()

        // 启动并绑定服务
        startAndBindServices()

        appendLog("Bluetooth Test App started")
        appendLog("Waiting for ADB commands via broadcast...")
    }

    override fun onDestroy() {
        // 取消注册广播接收器
        try {
            commandReceiver?.let { unregisterReceiver(it) }
        } catch (e: IllegalArgumentException) {
            // 可能已经取消注册
        }

        // 解绑服务
        try {
            unbindService(bluetoothServiceConnection)
        } catch (e: IllegalArgumentException) {
            // 可能已经解绑
        }
        try {
            unbindService(hciLogServiceConnection)
        } catch (e: IllegalArgumentException) {
            // 可能已经解绑
        }

        super.onDestroy()
    }

    // ==================== 权限处理 ====================

    private fun requestPermissionsIfNeeded() {
        val missingPermissions = PermissionUtil.checkAllPermissions(this)
        if (missingPermissions.isNotEmpty()) {
            appendLog("Requesting permissions: ${missingPermissions.joinToString(", ")}")
            ActivityCompat.requestPermissions(
                this,
                missingPermissions.toTypedArray(),
                REQUEST_ALL_PERMISSIONS
            )
        } else {
            appendLog("All permissions granted")
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_ALL_PERMISSIONS) {
            val denied = permissions.filterIndexed { index, _ ->
                grantResults[index] != PackageManager.PERMISSION_GRANTED
            }
            if (denied.isNotEmpty()) {
                appendLog("WARNING: Permissions denied: ${denied.joinToString(", ")}")
                appendLog("Some features may not work properly")
            } else {
                appendLog("All permissions granted")
            }
            updateStatusDisplay()
        }
    }

    // ==================== 服务管理 ====================

    private fun startAndBindServices() {
        // 启动蓝牙服务
        val btIntent = Intent(this, BluetoothService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(btIntent)
        } else {
            startService(btIntent)
        }
        bindService(btIntent, bluetoothServiceConnection, Context.BIND_AUTO_CREATE)

        // 启动 HCI 日志服务
        val hciIntent = Intent(this, HciLogService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(hciIntent)
        } else {
            startService(hciIntent)
        }
        bindService(hciIntent, hciLogServiceConnection, Context.BIND_AUTO_CREATE)
    }

    // ==================== 广播接收器注册 ====================

    private fun registerCommandReceiver() {
        val filter = IntentFilter().apply {
            addAction(CommandReceiver.ACTION_COMMAND)
            addAction(BluetoothService.ACTION_STOP_SERVICE)
            addAction(HciLogService.ACTION_STOP_SERVICE)
        }
        registerReceiver(commandReceiver, filter)
    }

    // ==================== UI 设置 ====================

    private fun setupButtons() {
        findViewById<Button>(R.id.btnScan).setOnClickListener {
            executeTestCommand("SCAN")
        }

        findViewById<Button>(R.id.btnGetPaired).setOnClickListener {
            executeTestCommand("GET_PAIRED_DEVICES")
        }

        findViewById<Button>(R.id.btnGetStatus).setOnClickListener {
            executeTestCommand("GET_BT_STATUS")
        }

        findViewById<Button>(R.id.btnEnableHci).setOnClickListener {
            executeTestCommand("ENABLE_HCI_LOG")
        }

        findViewById<Button>(R.id.btnDisableHci).setOnClickListener {
            executeTestCommand("DISABLE_HCI_LOG")
        }

        findViewById<Button>(R.id.btnClearLog).setOnClickListener {
            logBuffer.clear()
            logTextView.text = ""
        }

        findViewById<Button>(R.id.btnRefreshStatus).setOnClickListener {
            updateStatusDisplay()
        }
    }

    /**
     * 执行测试命令
     */
    private fun executeTestCommand(commandType: String) {
        appendLog(">>> Executing: $commandType")

        val result = commandHandler?.handleCommand(commandType, null)
            ?: CommandResult.failure("Command handler not initialized", command = commandType)

        appendLog("<<< Result: ${if (result.success) "SUCCESS" else "FAILED"} - ${result.message}")
        if (result.data != null) {
            try {
                val prettyJson = gson.toJson(gson.fromJson(result.data, Map::class.java))
                appendLog("    Data: $prettyJson")
            } catch (e: Exception) {
                appendLog("    Data: ${result.data}")
            }
        }
    }

    // ==================== UI 更新 ====================

    private fun updateStatusDisplay() {
        val status = buildString {
            appendLine("=== Bluetooth Test App Status ===")
            appendLine()

            // 权限状态
            appendLine("--- Permissions ---")
            appendLine(PermissionUtil.getPermissionStatus(this@MainActivity))
            appendLine()

            // 蓝牙状态
            appendLine("--- Bluetooth ---")
            val btStatus = bluetoothService?.getBluetoothStatus()
            if (btStatus?.data != null) {
                try {
                    val statusMap = gson.fromJson(btStatus.data, Map::class.java)
                    statusMap.forEach { (key, value) ->
                        appendLine("  $key: $value")
                    }
                } catch (e: Exception) {
                    appendLine("  ${btStatus.message}")
                }
            } else {
                appendLine("  BluetoothService not connected")
            }
            appendLine()

            // HCI 日志状态
            appendLine("--- HCI Log ---")
            val hciStatus = hciLogService?.getHciLogStatus()
            if (hciStatus?.data != null) {
                try {
                    val statusMap = gson.fromJson(hciStatus.data, Map::class.java)
                    statusMap.forEach { (key, value) ->
                        appendLine("  $key: $value")
                    }
                } catch (e: Exception) {
                    appendLine("  ${hciStatus.message}")
                }
            } else {
                appendLine("  HciLogService not connected")
            }
        }

        statusTextView.text = status
    }

    private fun appendLog(message: String) {
        logBuffer.appendLine(message)
        logTextView.text = logBuffer.toString()
        // 自动滚动到底部
        scrollView.post {
            scrollView.fullScroll(ScrollView.FOCUS_DOWN)
        }
        // 同时输出到 logcat
        LogUtil.info("[UI] $message")
    }
}
