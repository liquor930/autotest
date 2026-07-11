# ADB控制模块详细设计

## 1. 模块概述

ADB控制模块负责通过WiFi ADB与Android手机设备进行通信，实现设备的发现、连接、命令执行等操作。

## 2. 功能需求

- 设备发现：发现可连接的Android设备
- 设备连接：连接指定的Android设备
- 设备断开：断开与指定设备的连接 
- 状态查询：获取设备的连接状态
- 命令执行：在设备上执行ADB命令
- 日志采集：采集设备的HCI日志

## 3. 设计方案

- 使用`adb-shell`库实现ADB通信
- 采用Click/Typer框架构建CLI界面
- 实现ADB管理类，维护设备连接状态
- 提供设备发现和连接管理机制

## 4. 接口设计

```python
# 核心类
class ADBManager:
    def list_devices(self) -> List[DeviceInfo]:
        """列出所有可连接的设备"""
        pass
    
    def connect(self, ip: str, port: int) -> bool:
        """连接指定设备"""
        pass
    
    def disconnect(self, device_id: str) -> bool:
        """断开与指定设备的连接"""
        pass
    
    def get_status(self, device_id: str) -> DeviceStatus:
        """获取设备状态"""
        pass
    
    def execute_command(self, device_id: str, command: str) -> str:
        """在指定设备上执行命令"""
        pass
    
    def start_hci_log(self, device_id: str) -> bool:
        """开始采集HCI日志"""
        pass
    
    def stop_hci_log(self, device_id: str) -> bool:
        """停止采集HCI日志"""
        pass
    
    def pull_hci_log(self, device_id: str, output_file: str) -> bool:
        """拉取HCI日志文件"""
        pass
```

## 5. 数据结构

```python
# 设备信息
class DeviceInfo:
    device_id: str
    ip: str
    port: int
    status: str  # CONNECTED, DISCONNECTED, ERROR
    model: str
    version: str

# 设备状态
class DeviceStatus:
    device_id: str
    status: str
    error_message: str
    last_connected: datetime

# 命令结果
class CommandResult:
    success: bool
    output: str
    error: str
```

## 6. 实现细节

- **设备发现**：
  - 实现网络扫描，发现局域网内的Android设备
  - 支持通过IP地址和端口手动添加设备
  - 实现设备的自动发现和注册
  - 提供设备发现的定时扫描和手动触发
- **连接管理**：
  - 使用`adb-shell`库的`AdbDeviceTcp`类建立与设备的TCP连接
  - 实现连接的建立、维护和断开
  - 支持连接的重试和超时处理
  - 实现连接状态的实时监控和通知
- **命令执行**：
  - 实现ADB命令的执行和结果获取
  - 支持命令的超时设置和错误处理
  - 提供命令执行的异步处理
  - 实现命令的批处理和队列管理
- **HCI日志管理**：
  - 实现HCI日志的启动和停止
  - 支持日志文件的拉取和存储
  - 实现日志的清理和归档
  - 提供日志的实时监控和分析
- **设备管理**：
  - 实现设备的分组和标签管理
  - 支持设备的属性和状态管理
  - 提供设备的健康检查和诊断
  - 实现设备的认证和授权
- **错误处理**：
  - 定义具体的错误码和错误类型
  - 实现错误的捕获和处理
  - 提供错误的重试和恢复策略
  - 实现错误的日志记录和报告
- **性能优化**：
  - 实现连接池，减少连接开销
  - 支持命令的缓存和批处理
  - 优化网络传输，减少延迟
  - 实现资源的动态管理和回收

## 7. 测试计划

- 测试设备发现功能
- 测试设备连接和断开功能
- 测试命令执行功能
- 测试HCI日志采集功能
- 测试异常处理

## 8. 部署与集成

### 8.1 依赖管理

- **核心依赖**：
  - adb-shell：用于ADB通信
  - Click/Typer：用于命令行界面
  - pyyaml：用于配置文件解析
  - loguru：用于日志管理
- **可选依赖**：
  - pytest：用于单元测试

### 8.2 安装与配置

- **安装方式**：
  - 通过pip安装：`pip install bt-adb`
  - 从源码安装：`pip install -e .`
- **配置文件**：
  - 支持JSON、YAML格式的配置文件
  - 默认配置文件路径：`~/.config/bt-adb/config.yaml`
  - 支持通过环境变量覆盖配置

### 8.3 集成接口

- **CLI接口**：提供命令行接口，支持各种ADB操作
- **Python API**：提供Python API，便于其他Python应用集成
- **与其他模块的集成**：
  - 与核心引擎集成，提供手机设备的管理
  - 与测试执行模块集成，支持测试前准备和测试执行过程中的设备操作
  - 与日志收集模块集成，提供HCI日志的采集接口

### 8.4 部署场景

- **本地部署**：直接在本地机器上安装和运行
- **容器化部署**：支持Docker容器化部署
- **远程部署**：支持在远程服务器上部署，通过网络控制设备

