package com.bttest.model

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName

/**
 * 命令执行结果
 */
data class CommandResult(
    /** 命令是否执行成功 */
    @SerializedName("success")
    val success: Boolean,

    /** 结果消息 */
    @SerializedName("message")
    val message: String,

    /** 附加数据（JSON 格式） */
    @SerializedName("data")
    val data: String? = null,

    /** 错误码（成功时为 0） */
    @SerializedName("error_code")
    val errorCode: Int = if (success) 0 else -1,

    /** 命令类型 */
    @SerializedName("command")
    val command: String? = null
) {
    companion object {
        private val gson = Gson()

        /**
         * 创建成功结果
         */
        fun success(
            message: String,
            data: String? = null,
            command: String? = null
        ): CommandResult {
            return CommandResult(
                success = true,
                message = message,
                data = data,
                errorCode = 0,
                command = command
            )
        }

        /**
         * 创建失败结果
         */
        fun failure(
            message: String,
            errorCode: Int = -1,
            command: String? = null
        ): CommandResult {
            return CommandResult(
                success = false,
                message = message,
                data = null,
                errorCode = errorCode,
                command = command
            )
        }

        /**
         * 序列化为 JSON 字符串
         */
        fun toJson(result: CommandResult): String {
            return gson.toJson(result)
        }

        /**
         * 从 JSON 字符串反序列化
         */
        fun fromJson(json: String): CommandResult {
            return gson.fromJson(json, CommandResult::class.java)
        }
    }

    /**
     * 转换为 JSON 字符串
     */
    fun toJson(): String = Companion.toJson(this)
}
