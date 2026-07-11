package com.bttest.model

import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothDevice
import android.os.Parcelable
import com.google.gson.annotations.SerializedName
import kotlinx.parcelize.Parcelize

/**
 * 蓝牙设备信息数据类
 * 封装蓝牙设备的关键属性，便于序列化和传输
 */
@Parcelize
data class BluetoothDeviceInfo(
    /** 设备 MAC 地址 */
    @SerializedName("address")
    val address: String,

    /** 设备名称 */
    @SerializedName("name")
    val name: String,

    /** 信号强度 (dBm) */
    @SerializedName("rssi")
    val rssi: Int,

    /** 绑定状态 */
    @SerializedName("bond_state")
    val bondState: Int,

    /** 设备类型（如手机、耳机等） */
    @SerializedName("device_class")
    val deviceClass: Int = BluetoothClass.Device.Major.MISC,

    /** 设备类型名称 */
    @SerializedName("device_type")
    val deviceType: String = "Unknown",

    /** 是否已连接 */
    @SerializedName("is_connected")
    val isConnected: Boolean = false,

    /** 蓝牙类型（CLASSIC / BLE / DUAL） */
    @SerializedName("bluetooth_type")
    val bluetoothType: String = "CLASSIC",

    /** 最后发现时间戳 */
    @SerializedName("last_seen")
    val lastSeen: Long = System.currentTimeMillis()
) : Parcelable {
    companion object {
        /**
         * 绑定状态常量
         */
        const val BOND_NONE = BluetoothDevice.BOND_NONE
        const val BOND_BONDING = BluetoothDevice.BOND_BONDING
        const val BOND_BONDED = BluetoothDevice.BOND_BONDED

        /**
         * 从 Android BluetoothDevice 创建
         * 注意：API 31+ 访问 address/name 需要 BLUETOOTH_CONNECT 权限
         */
        fun fromBluetoothDevice(
            device: BluetoothDevice,
            rssi: Int = 0,
            isConnected: Boolean = false
        ): BluetoothDeviceInfo {
            // 安全获取设备地址和名称（处理 API 31+ 权限要求）
            val address = try {
                device.address ?: "00:00:00:00:00:00"
            } catch (e: SecurityException) {
                "00:00:00:00:00:00"
            }
            val name = try {
                device.name ?: "Unknown Device"
            } catch (e: SecurityException) {
                "Unknown Device"
            }
            val bondState = try {
                device.bondState
            } catch (e: SecurityException) {
                BluetoothDevice.BOND_NONE
            }
            val deviceType = try {
                getDeviceTypeName(device.bluetoothClass?.majorDeviceClass)
            } catch (e: SecurityException) {
                "Unknown"
            }
            val btType = try {
                when (device.type) {
                    BluetoothDevice.DEVICE_TYPE_CLASSIC -> "CLASSIC"
                    BluetoothDevice.DEVICE_TYPE_LE -> "BLE"
                    BluetoothDevice.DEVICE_TYPE_DUAL -> "DUAL"
                    else -> "UNKNOWN"
                }
            } catch (e: SecurityException) {
                "UNKNOWN"
            }

            return BluetoothDeviceInfo(
                address = address,
                name = name,
                rssi = rssi,
                bondState = bondState,
                deviceClass = try {
                    device.bluetoothClass?.majorDeviceClass ?: BluetoothClass.Device.Major.MISC
                } catch (e: SecurityException) {
                    BluetoothClass.Device.Major.MISC
                },
                deviceType = deviceType,
                isConnected = isConnected,
                bluetoothType = btType
            )
        }

        /**
         * 获取设备类型名称
         */
        fun getDeviceTypeName(majorDeviceClass: Int?): String {
            return when (majorDeviceClass) {
                BluetoothClass.Device.Major.AUDIO_VIDEO -> "Audio/Video"
                BluetoothClass.Device.Major.COMPUTER -> "Computer"
                BluetoothClass.Device.Major.HEALTH -> "Health"
                BluetoothClass.Device.Major.IMAGING -> "Imaging"
                BluetoothClass.Device.Major.MISC -> "Miscellaneous"
                BluetoothClass.Device.Major.NETWORKING -> "Networking"
                BluetoothClass.Device.Major.PERIPHERAL -> "Peripheral"
                BluetoothClass.Device.Major.PHONE -> "Phone"
                BluetoothClass.Device.Major.TOY -> "Toy"
                BluetoothClass.Device.Major.UNCATEGORIZED -> "Uncategorized"
                BluetoothClass.Device.Major.WEARABLE -> "Wearable"
                else -> "Unknown"
            }
        }

        /**
         * 获取绑定状态名称
         */
        fun getBondStateName(bondState: Int): String {
            return when (bondState) {
                BOND_NONE -> "Not Bonded"
                BOND_BONDING -> "Bonding"
                BOND_BONDED -> "Bonded"
                else -> "Unknown"
            }
        }
    }
}
