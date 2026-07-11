package com.bttest.util

import android.util.Log
import com.bttest.model.CommandResult

/**
 * 日志工具类
 * 统一管理 logcat 输出格式，便于 PC 端解析
 */
object LogUtil {

    /** 日志 TAG，用于 logcat 过滤 */
    const val TAG = "BT_TEST"

    /** 日志级别 */
    private const val LEVEL_DEBUG = 3
    private const val LEVEL_INFO = 4
    private const val LEVEL_WARN = 5
    private const val LEVEL_ERROR = 6

    /** 默认日志级别 */
    private var logLevel = LEVEL_DEBUG

    /**
     * 设置日志级别
     */
    fun setLogLevel(level: Int) {
        logLevel = level
    }

    /**
     * Debug 日志
     */
    fun debug(message: String) {
        if (logLevel <= LEVEL_DEBUG) {
            Log.d(TAG, message)
        }
    }

    /**
     * Info 日志
     */
    fun info(message: String) {
        if (logLevel <= LEVEL_INFO) {
            Log.i(TAG, message)
        }
    }

    /**
     * Warning 日志
     */
    fun warn(message: String) {
        if (logLevel <= LEVEL_WARN) {
            Log.w(TAG, message)
        }
    }

    /**
     * Error 日志
     */
    fun error(message: String, throwable: Throwable? = null) {
        if (logLevel <= LEVEL_ERROR) {
            if (throwable != null) {
                Log.e(TAG, message, throwable)
            } else {
                Log.e(TAG, message)
            }
        }
    }

    /**
     * 输出命令执行结果到 logcat
     * PC 端可通过 `adb logcat -s BT_TEST` 捕获
     */
    fun outputResult(result: CommandResult) {
        val json = result.toJson()
        Log.i(TAG, json)
    }

    /**
     * 输出设备列表到 logcat
     */
    fun outputDeviceList(devices: List<com.bttest.model.BluetoothDeviceInfo>) {
        val json = com.google.gson.Gson().toJson(devices)
        Log.i(TAG, "DEVICE_LIST: $json")
    }

    /**
     * 输出状态信息到 logcat
     */
    fun outputStatus(status: String, details: String? = null) {
        val message = if (details != null) {
            "STATUS: $status - $details"
        } else {
            "STATUS: $status"
        }
        Log.i(TAG, message)
    }
}
