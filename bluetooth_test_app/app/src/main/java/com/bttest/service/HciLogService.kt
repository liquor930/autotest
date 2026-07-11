package com.bttest.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.Environment
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.bttest.model.CommandResult
import com.bttest.util.LogUtil
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.GZIPOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * HCI 日志管理服务
 * 负责启用/禁用 btsnoop 日志、日志文件管理、日志压缩和导出
 */
class HciLogService : Service() {

    private val binder = HciLogBinder()

    /** 日志是否已启用 */
    @Volatile
    private var hciLogEnabled = false

    /** 日志文件目录 */
    private var logDirectory: File? = null

    /** 日志文件路径 */
    private var logFilePath: String? = null

    /** 日志收集开始时间 */
    private var logStartTime: Long = 0

    companion object {
        const val CHANNEL_ID = "hci_log_service_channel"
        const val NOTIFICATION_ID = 1002
        const val ACTION_STOP_SERVICE = "com.bttest.STOP_HCI_LOG_SERVICE"

        /** btsnoop 日志默认路径 */
        private const val BTSNOOP_LOG_PATH = "/sdcard/btsnoop_hci.log"

        /** 应用日志目录名 */
        private const val LOG_DIR_NAME = "BT_HCI_Logs"

        /** btsnoop 配置属性名 */
        private const val BTSNOOP_ENABLE_PROP = "persist.bluetooth.btsnoopenable"
    }

    // ==================== 生命周期 ====================

    override fun onCreate() {
        super.onCreate()
        LogUtil.info("HciLogService created")

        // 初始化日志目录
        logDirectory = File(getExternalFilesDir(null), LOG_DIR_NAME)
        if (logDirectory?.exists() != true) {
            logDirectory?.mkdirs()
        }

        // 创建通知渠道并启动前台服务
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification())
    }

    override fun onDestroy() {
        if (hciLogEnabled) {
            disableHciLog()
        }
        LogUtil.info("HciLogService destroyed")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }

    inner class HciLogBinder : Binder() {
        fun getService(): HciLogService = this@HciLogService
    }

    // ==================== HCI 日志控制 ====================

    /**
     * 启用 HCI 日志
     *
     * 注意：setprop 方法需要 root 权限，在普通设备上会失败。
     * 推荐通过开发者选项手动开启「启用蓝牙 HCI 信息收集日志」。
     * 本方法会尝试多种方式，部分成功即视为日志已启用。
     */
    fun enableHciLog(): CommandResult {
        if (hciLogEnabled) {
            return CommandResult.failure(
                "HCI log is already enabled",
                errorCode = -1,
                command = "ENABLE_HCI_LOG"
            )
        }

        return try {
            var anySuccess = false
            val messages = mutableListOf<String>()

            // 方法 1：通过 settings 命令（无需 root，但需要 WRITE_SETTINGS 权限）
            try {
                val process = Runtime.getRuntime().exec(
                    arrayOf("settings", "put", "global", "bluetooth_hci_log", "1")
                )
                // 消费 stdout/stderr 防止死锁
                process.inputStream.bufferedReader().use { it.readText() }
                process.errorStream.bufferedReader().use { it.readText() }
                val exitCode = process.waitFor()
                if (exitCode == 0) {
                    anySuccess = true
                    messages.add("settings command succeeded")
                } else {
                    messages.add("settings command failed (exit=$exitCode, may need WRITE_SETTINGS)")
                }
            } catch (e: Exception) {
                messages.add("settings command error: ${e.message}")
            }

            // 方法 2：通过 setprop（需要 root 权限，在普通设备上会失败）
            try {
                val process = Runtime.getRuntime().exec(
                    arrayOf("su", "-c", "setprop $BTSNOOP_ENABLE_PROP true")
                )
                process.inputStream.bufferedReader().use { it.readText() }
                process.errorStream.bufferedReader().use { it.readText() }
                val exitCode = process.waitFor()
                if (exitCode == 0) {
                    anySuccess = true
                    messages.add("setprop (root) succeeded")
                } else {
                    messages.add("setprop requires root (exit=$exitCode)")
                }
            } catch (e: Exception) {
                messages.add("setprop error (no root?): ${e.message}")
            }

            hciLogEnabled = true
            logStartTime = System.currentTimeMillis()

            // 记录当前 btsnoop 文件
            val snoopFile = File(BTSNOOP_LOG_PATH)
            if (snoopFile.exists()) {
                logFilePath = snoopFile.absolutePath
            }

            LogUtil.info("HCI log enabled. ${messages.joinToString("; ")}")

            CommandResult.success(
                if (anySuccess) "HCI log enabled"
                else "HCI log flag set (system commands may have failed, check Developer Options)",
                data = "{\"log_path\": \"${logFilePath ?: BTSNOOP_LOG_PATH}\", \"start_time\": $logStartTime, \"details\": \"${messages.joinToString("; ")}\"}",
                command = "ENABLE_HCI_LOG"
            )
        } catch (e: Exception) {
            LogUtil.error("Failed to enable HCI log", e)
            CommandResult.failure(
                "Failed to enable HCI log: ${e.message}",
                command = "ENABLE_HCI_LOG"
            )
        }
    }

    /**
     * 禁用 HCI 日志
     */
    fun disableHciLog(): CommandResult {
        if (!hciLogEnabled) {
            return CommandResult.failure(
                "HCI log is not enabled",
                errorCode = -1,
                command = "DISABLE_HCI_LOG"
            )
        }

        return try {
            // 方法 1：通过 settings 命令禁用
            try {
                val process = Runtime.getRuntime().exec(
                    arrayOf("settings", "put", "global", "bluetooth_hci_log", "0")
                )
                process.inputStream.bufferedReader().use { it.readText() }
                process.errorStream.bufferedReader().use { it.readText() }
                process.waitFor()
            } catch (e: Exception) {
                LogUtil.warn("settings disable error: ${e.message}")
            }

            // 方法 2：通过 setprop（需要 root）
            try {
                val process = Runtime.getRuntime().exec(
                    arrayOf("su", "-c", "setprop $BTSNOOP_ENABLE_PROP false")
                )
                process.inputStream.bufferedReader().use { it.readText() }
                process.errorStream.bufferedReader().use { it.readText() }
                process.waitFor()
            } catch (e: Exception) {
                LogUtil.warn("setprop disable error: ${e.message}")
            }

            hciLogEnabled = false
            val duration = System.currentTimeMillis() - logStartTime

            // 尝试将 btsnoop 日志复制到应用目录
            val copiedPath = copyBtsnoopLog()

            LogUtil.info("HCI log disabled. Duration: ${duration}ms")

            CommandResult.success(
                "HCI log disabled. Duration: ${duration}ms",
                data = "{\"duration_ms\": $duration, \"log_path\": \"${copiedPath ?: BTSNOOP_LOG_PATH}\"}",
                command = "DISABLE_HCI_LOG"
            )
        } catch (e: Exception) {
            LogUtil.error("Failed to disable HCI log", e)
            CommandResult.failure(
                "Failed to disable HCI log: ${e.message}",
                command = "DISABLE_HCI_LOG"
            )
        }
    }

    // ==================== 日志管理 ====================

    /**
     * 获取 HCI 日志状态
     */
    fun getHciLogStatus(): CommandResult {
        val status = mapOf(
            "enabled" to hciLogEnabled,
            "log_path" to (logFilePath ?: BTSNOOP_LOG_PATH),
            "start_time" to logStartTime,
            "duration_ms" to if (hciLogEnabled) System.currentTimeMillis() - logStartTime else 0,
            "log_directory" to (logDirectory?.absolutePath ?: ""),
            "available_space_mb" to (logDirectory?.usableSpace?.div(1024 * 1024) ?: 0)
        )

        return CommandResult.success(
            "HCI log status retrieved",
            data = com.google.gson.Gson().toJson(status),
            command = "GET_BT_STATUS"
        )
    }

    /**
     * 获取日志文件路径
     */
    fun getLogPath(): String {
        return logFilePath ?: BTSNOOP_LOG_PATH
    }

    /**
     * 获取日志目录下所有日志文件列表
     */
    fun listLogFiles(): CommandResult {
        val files = logDirectory?.listFiles()?.filter { it.isFile }?.map { file ->
            mapOf(
                "name" to file.name,
                "size_bytes" to file.length(),
                "last_modified" to file.lastModified(),
                "path" to file.absolutePath
            )
        } ?: emptyList()

        return CommandResult.success(
            "Found ${files.size} log files",
            data = com.google.gson.Gson().toJson(files),
            command = "GET_BT_STATUS"
        )
    }

    /**
     * 复制 btsnoop 日志到应用目录
     */
    private fun copyBtsnoopLog(): String? {
        return try {
            val sourceFile = File(BTSNOOP_LOG_PATH)
            if (!sourceFile.exists()) {
                LogUtil.warn("Btsnoop log file not found at $BTSNOOP_LOG_PATH")
                return null
            }

            val dateFormat = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault())
            val timestamp = dateFormat.format(Date())
            val destFile = File(logDirectory, "btsnoop_hci_$timestamp.log")

            sourceFile.copyTo(destFile, overwrite = true)
            LogUtil.info("Btsnoop log copied to ${destFile.absolutePath}")
            destFile.absolutePath
        } catch (e: IOException) {
            LogUtil.error("Failed to copy btsnoop log", e)
            null
        }
    }

    /**
     * 压缩指定的日志文件
     */
    fun compressLogFile(fileName: String): CommandResult {
        val sourceFile = File(logDirectory, fileName)
        if (!sourceFile.exists()) {
            return CommandResult.failure(
                "Log file not found: $fileName",
                command = "GET_BT_STATUS"
            )
        }

        return try {
            val compressedFile = File(logDirectory, "$fileName.gz")
            FileInputStream(sourceFile).use { input ->
                GZIPOutputStream(FileOutputStream(compressedFile)).use { output ->
                    input.copyTo(output)
                }
            }

            val originalSize = sourceFile.length()
            val compressedSize = compressedFile.length()
            val ratio = if (originalSize > 0) {
                "%.1f%%".format(100.0 * compressedSize / originalSize)
            } else {
                "N/A"
            }

            LogUtil.info("Log file compressed: $fileName (${originalSize} -> ${compressedSize} bytes, $ratio)")
            CommandResult.success(
                "Log file compressed successfully",
                data = "{\"original\": \"$fileName\", \"compressed\": \"${compressedFile.name}\", \"original_size\": $originalSize, \"compressed_size\": $compressedSize, \"ratio\": \"$ratio\"}",
                command = "GET_BT_STATUS"
            )
        } catch (e: IOException) {
            CommandResult.failure(
                "Compression failed: ${e.message}",
                command = "GET_BT_STATUS"
            )
        }
    }

    /**
     * 删除指定日志文件
     */
    fun deleteLogFile(fileName: String): CommandResult {
        val file = File(logDirectory, fileName)
        if (!file.exists()) {
            return CommandResult.failure(
                "Log file not found: $fileName",
                command = "GET_BT_STATUS"
            )
        }

        return if (file.delete()) {
            LogUtil.info("Log file deleted: $fileName")
            CommandResult.success(
                "Log file deleted: $fileName",
                command = "GET_BT_STATUS"
            )
        } else {
            CommandResult.failure(
                "Failed to delete log file: $fileName",
                command = "GET_BT_STATUS"
            )
        }
    }

    /**
     * 清除所有日志文件
     */
    fun clearAllLogs(): CommandResult {
        val files = logDirectory?.listFiles() ?: emptyArray()
        var deletedCount = 0
        var failedCount = 0

        files.forEach { file ->
            if (file.isFile) {
                if (file.delete()) {
                    deletedCount++
                } else {
                    failedCount++
                }
            }
        }

        LogUtil.info("Cleared $deletedCount log files, $failedCount failed")
        return CommandResult.success(
            "Cleared $deletedCount log files, $failedCount failed",
            data = "{\"deleted\": $deletedCount, \"failed\": $failedCount}",
            command = "GET_BT_STATUS"
        )
    }

    /**
     * 导出日志文件到指定位置
     */
    fun exportLogFile(fileName: String, exportPath: String): CommandResult {
        val sourceFile = File(logDirectory, fileName)
        if (!sourceFile.exists()) {
            return CommandResult.failure(
                "Log file not found: $fileName",
                command = "GET_BT_STATUS"
            )
        }

        return try {
            val destFile = File(exportPath)
            destFile.parentFile?.mkdirs()
            sourceFile.copyTo(destFile, overwrite = true)
            LogUtil.info("Log file exported to $exportPath")
            CommandResult.success(
                "Log file exported to $exportPath",
                command = "GET_BT_STATUS"
            )
        } catch (e: IOException) {
            CommandResult.failure(
                "Export failed: ${e.message}",
                command = "GET_BT_STATUS"
            )
        }
    }

    /**
     * 打包所有日志文件为 ZIP
     */
    fun packageLogsAsZip(): CommandResult {
        val files = logDirectory?.listFiles()?.filter { it.isFile && !it.name.endsWith(".zip") }
            ?: emptyList()

        if (files.isEmpty()) {
            return CommandResult.failure(
                "No log files to package",
                command = "GET_BT_STATUS"
            )
        }

        return try {
            val dateFormat = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault())
            val zipFileName = "bt_hci_logs_${dateFormat.format(Date())}.zip"
            val zipFile = File(logDirectory, zipFileName)

            ZipOutputStream(FileOutputStream(zipFile)).use { zipOutput ->
                files.forEach { file ->
                    zipOutput.putNextEntry(ZipEntry(file.name))
                    FileInputStream(file).use { input ->
                        input.copyTo(zipOutput)
                    }
                    zipOutput.closeEntry()
                }
            }

            LogUtil.info("Logs packaged as $zipFileName (${zipFile.length()} bytes)")
            CommandResult.success(
                "Logs packaged successfully",
                data = "{\"zip_file\": \"$zipFileName\", \"size_bytes\": ${zipFile.length()}, \"path\": \"${zipFile.absolutePath}\"}",
                command = "GET_BT_STATUS"
            )
        } catch (e: IOException) {
            CommandResult.failure(
                "Package failed: ${e.message}",
                command = "GET_BT_STATUS"
            )
        }
    }

    // ==================== 通知 ====================

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "HCI Log Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Notification for HCI Log Service"
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
            .setContentTitle("HCI Log Service")
            .setContentText(if (hciLogEnabled) "Collecting HCI logs..." else "HCI log service running")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(android.R.drawable.ic_media_pause, "Stop", pendingIntent)
            .build()
    }
}
