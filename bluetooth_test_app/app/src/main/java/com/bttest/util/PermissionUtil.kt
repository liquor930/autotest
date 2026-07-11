package com.bttest.util

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

/**
 * 权限管理工具类
 * 处理 Android 运行时权限申请和检查
 */
object PermissionUtil {

    /**
     * 蓝牙测试所需的全部权限
     */
    val REQUIRED_PERMISSIONS: List<String> = buildList {
        // 蓝牙权限
        add(Manifest.permission.BLUETOOTH)
        add(Manifest.permission.BLUETOOTH_ADMIN)

        // Android 12+ 新增蓝牙权限
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(Manifest.permission.BLUETOOTH_SCAN)
            add(Manifest.permission.BLUETOOTH_CONNECT)
            add(Manifest.permission.BLUETOOTH_ADVERTISE)
        }

        // 位置权限（蓝牙扫描需要）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
        } else {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            add(Manifest.permission.ACCESS_COARSE_LOCATION)
        }

        // 存储权限（HCI 日志存储）
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.Q) {
            add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
            add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

        // Android 13+ 通知权限（前台服务需要）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    /**
     * 检查所有必需权限是否已授予
     * @return 未授予的权限列表
     */
    fun checkAllPermissions(context: Context): List<String> {
        return REQUIRED_PERMISSIONS.filter { permission ->
            ContextCompat.checkSelfPermission(context, permission)
                != PackageManager.PERMISSION_GRANTED
        }
    }

    /**
     * 检查蓝牙相关权限是否已授予
     */
    fun checkBluetoothPermissions(context: Context): Boolean {
        val btPermissions = listOf(
            Manifest.permission.BLUETOOTH,
            Manifest.permission.BLUETOOTH_ADMIN
        )
        return btPermissions.all { permission ->
            ContextCompat.checkSelfPermission(context, permission)
                == PackageManager.PERMISSION_GRANTED
        }
    }

    /**
     * 检查位置权限是否已授予
     */
    fun checkLocationPermissions(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * 检查存储权限是否已授予
     */
    fun checkStoragePermissions(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            return true // Android 10+ 不需要存储权限
        }
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.WRITE_EXTERNAL_STORAGE
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * 获取权限状态描述
     */
    fun getPermissionStatus(context: Context): String {
        val missing = checkAllPermissions(context)
        return if (missing.isEmpty()) {
            "All permissions granted"
        } else {
            "Missing permissions: ${missing.joinToString(", ")}"
        }
    }
}
