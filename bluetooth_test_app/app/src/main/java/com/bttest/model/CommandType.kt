package com.bttest.model

/**
 * 命令类型枚举
 * 定义所有支持的蓝牙测试命令
 */
enum class CommandType {
    /** 蓝牙扫描 */
    SCAN,
    /** 配对设备 */
    PAIR,
    /** 连接设备 */
    CONNECT,
    /** 断开连接 */
    DISCONNECT,
    /** 发送数据 */
    SEND_DATA,
    /** 接收数据 */
    RECEIVE_DATA,
    /** 启用 HCI 日志 */
    ENABLE_HCI_LOG,
    /** 禁用 HCI 日志 */
    DISABLE_HCI_LOG,
    /** 获取已配对设备列表 */
    GET_PAIRED_DEVICES,
    /** 获取已连接设备列表 */
    GET_CONNECTED_DEVICES,
    /** 获取设备详细信息 */
    GET_DEVICE_INFO,
    /** 取消配对 */
    UNPAIR,
    /** 获取蓝牙适配器状态 */
    GET_BT_STATUS;

    companion object {
        /**
         * 安全地从字符串解析命令类型
         */
        fun fromString(value: String?): CommandType? {
            return try {
                value?.let { valueOf(it.uppercase()) }
            } catch (e: IllegalArgumentException) {
                null
            }
        }
    }
}
