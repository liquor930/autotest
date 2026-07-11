// ============================================================
// 蓝牙自动化测试 APP - 项目级 Gradle 构建配置
// ============================================================

plugins {
    id("com.android.application") version "8.2.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.20" apply false
    id("org.jetbrains.kotlin.plugin.parcelize") version "1.9.20" apply false
}

// 注意：repositories 统一在 settings.gradle.kts 的
// dependencyResolutionManagement 中管理，此处不再声明 allprojects {}
// 否则会与 FAIL_ON_PROJECT_REPOS 模式冲突

tasks.register("clean", Delete::class) {
    delete(rootProject.layout.buildDirectory)
}
