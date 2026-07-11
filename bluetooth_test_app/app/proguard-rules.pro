# 蓝牙自动化测试 APP - ProGuard 混淆规则

# ==================== 保持类 ====================

# 保持数据模型类（用于 Gson 序列化）
-keep class com.bttest.model.** { *; }

# 保持命令相关类
-keep class com.bttest.handler.** { *; }
-keep class com.bttest.receiver.** { *; }

# 保持服务类
-keep class com.bttest.service.** { *; }

# ==================== Gson ====================
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer

# 防止 Gson 混淆字段名
-keepclassmembers class com.bttest.model.** {
    <fields>;
}

# ==================== 蓝牙相关 ====================
-keep class android.bluetooth.** { *; }

# ==================== Kotlin ====================
-keep class kotlinx.coroutines.** { *; }
-keepclassmembers class kotlinx.parcelize.Parcelize { *; }

# ==================== 通用 ====================
-keepattributes SourceFile,LineNumberTable
-keepattributes EnclosingMethod
-keepattributes InnerClasses
