package com.bttest.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.bttest.handler.CommandHandler
import com.bttest.model.CommandResult
import com.bttest.util.LogUtil

/**
 * 命令广播接收器
 * 接收来自 ADB 的广播命令，并转发给 CommandHandler 处理
 *
 * ADB 命令格式：
 *   adb shell am broadcast -a com.bttest.COMMAND \
 *       --es command <COMMAND_TYPE> \
 *       --es address <DEVICE_ADDRESS> \
 *       --es data <PAYLOAD_DATA> \
 *       --ei duration_ms <SCAN_DURATION> \
 *       --es action <ACTION> \
 *       --es type <CONNECTION_TYPE> \
 *       --ez is_hex <true|false>
 *
 * 结果通过 logcat 输出，格式：BT_TEST: <JSON_RESULT>
 * 使用 `adb logcat -s BT_TEST` 捕获结果
 */
class CommandReceiver : BroadcastReceiver() {

    companion object {
        /** 广播 Action */
        const val ACTION_COMMAND = "com.bttest.COMMAND"

        /** 结果输出 TAG */
        const val RESULT_TAG = "BT_TEST"
    }

    /**
     * 命令处理器（外部注入）
     */
    private var commandHandler: CommandHandler? = null

    /**
     * 设置命令处理器
     * 在创建 Receiver 实例后调用
     */
    fun setCommandHandler(handler: CommandHandler) {
        this.commandHandler = handler
    }

    override fun onReceive(context: Context, intent: Intent) {
        // 处理服务停止请求
        if (intent.action == com.bttest.service.BluetoothService.ACTION_STOP_SERVICE ||
            intent.action == com.bttest.service.HciLogService.ACTION_STOP_SERVICE) {
            LogUtil.info("Received stop service request")
            return
        }

        // 处理命令广播
        if (intent.action == ACTION_COMMAND) {
            handleCommandIntent(context, intent)
        } else if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            // 开机自启
            LogUtil.info("Boot completed - starting services")
            startServices(context)
        }
    }

    /**
     * 处理命令 Intent
     */
    private fun handleCommandIntent(context: Context, intent: Intent) {
        val commandType = intent.getStringExtra("command")
        val params = intent.extras

        LogUtil.info("Received command: $commandType")
        LogUtil.debug("Command intent extras: ${params?.keySet()?.joinToString(", ") { key -> "$key=${params.get(key)}" }}")

        if (commandType == null) {
            LogUtil.outputResult(
                CommandResult.failure(
                    "Missing 'command' extra in intent",
                    errorCode = -1,
                    command = null
                )
            )
            return
        }

        // 确保 CommandHandler 已初始化
        val handler = commandHandler ?: synchronized(this) {
            commandHandler ?: CommandHandler(context).also { commandHandler = it }
        }

        // 执行命令
        try {
            val result: CommandResult = handler.handleCommand(commandType, params)
            LogUtil.info("Command result: success=${result.success}, message=${result.message}")
        } catch (e: Exception) {
            LogUtil.error("Unhandled exception in command receiver", e)
            LogUtil.outputResult(
                CommandResult.failure(
                    "Unhandled exception: ${e.message}",
                    errorCode = -999,
                    command = commandType
                )
            )
        }
    }

    /**
     * 启动后台服务
     */
    private fun startServices(context: Context) {
        try {
            // 启动蓝牙服务
            val btIntent = Intent(context, com.bttest.service.BluetoothService::class.java)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                context.startForegroundService(btIntent)
            } else {
                context.startService(btIntent)
            }

            // 启动 HCI 日志服务
            val hciIntent = Intent(context, com.bttest.service.HciLogService::class.java)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                context.startForegroundService(hciIntent)
            } else {
                context.startService(hciIntent)
            }

            LogUtil.info("Services started on boot")
        } catch (e: Exception) {
            LogUtil.error("Failed to start services on boot", e)
        }
    }
}
