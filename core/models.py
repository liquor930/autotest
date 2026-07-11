"""核心引擎数据模型"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


# ==================== 枚举 ====================

class SessionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class ResultStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


class DeviceType(str, Enum):
    PHONE = "PHONE"             # Android phone
    BLE_DEVICE = "BLE_DEVICE"   # Bluetooth device (earphone, speaker, etc.)


class DeviceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class EventType(str, Enum):
    # Test session events
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_PAUSED = "SESSION_PAUSED"
    SESSION_RESUMED = "SESSION_RESUMED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_FAILED = "SESSION_FAILED"
    SESSION_STOPPED = "SESSION_STOPPED"

    # Test execution events
    CASE_STARTED = "CASE_STARTED"
    CASE_COMPLETED = "CASE_COMPLETED"
    CASE_FAILED = "CASE_FAILED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"

    # Device events
    DEVICE_REGISTERED = "DEVICE_REGISTERED"
    DEVICE_UNREGISTERED = "DEVICE_UNREGISTERED"
    DEVICE_ALLOCATED = "DEVICE_ALLOCATED"
    DEVICE_RELEASED = "DEVICE_RELEASED"
    DEVICE_ERROR = "DEVICE_ERROR"

    # Report events
    REPORT_GENERATED = "REPORT_GENERATED"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ==================== 核心数据模型 ====================

@dataclass
class TestStep:
    """测试步骤"""
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    action: str = ""                     # 执行的操作：shell命令、adb命令、AT指令等
    action_type: str = "shell"           # shell, adb, at, bluetooth, script
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_result: str = ""
    timeout: int = 30                    # 超时秒数
    order_index: int = 0
    retry_count: int = 0
    retry_delay: int = 1                 # 重试间隔秒数


@dataclass
class TestCase:
    """测试用例"""
    case_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    priority: str = "P2"                 # P0, P1, P2, P3
    steps: List[TestStep] = field(default_factory=list)
    timeout: int = 300                   # 用例超时秒数
    tags: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)  # 前置条件描述


@dataclass
class TestConfig:
    """测试配置（对应配置文件）"""
    config_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    test_cases: List[str] = field(default_factory=list)      # case_id 列表
    devices: List[str] = field(default_factory=list)         # device_id 列表
    serial_ports: List[Dict[str, Any]] = field(default_factory=list)  # 串口配置
    prep_script: Optional[str] = None                        # 前置脚本
    max_workers: int = 4
    report_format: str = "html"
    output_dir: str = "reports"


@dataclass
class TestSession:
    """测试会话"""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    status: SessionStatus = SessionStatus.PENDING
    config_file: str = ""
    config: Optional[TestConfig] = None
    test_cases: List[TestCase] = field(default_factory=list)
    devices: List[str] = field(default_factory=list)         # device_id 列表
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    progress: float = 0.0                                    # 0.0 ~ 100.0
    current_case_id: Optional[str] = None
    current_step_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class StepResult:
    """步骤执行结果"""
    step_result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    result_id: str = ""                                      # 关联的测试结果ID
    step_id: str = ""
    step_name: str = ""
    status: ResultStatus = ResultStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actual_result: str = ""
    error_message: str = ""
    log_output: str = ""                                     # 执行日志
    retry_attempts: int = 0


@dataclass
class TestResult:
    """用例测试结果"""
    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    case_id: str = ""
    case_name: str = ""
    status: ResultStatus = ResultStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actual_result: str = ""
    error_message: str = ""
    log_path: str = ""
    step_results: List[StepResult] = field(default_factory=list)
    device_id: Optional[str] = None


@dataclass
class SessionInfo:
    """会话摘要信息（用于列表展示）"""
    session_id: str
    name: str
    status: SessionStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    total_cases: int
    passed: int = 0
    failed: int = 0
    progress: float = 0.0


# ==================== 状态数据结构 ====================

@dataclass
class TestSessionStatus:
    """测试会话实时状态"""
    session_id: str
    status: SessionStatus
    progress: float                                      # 0~100
    current_case: Optional[str] = None
    current_step: Optional[str] = None
    elapsed_time: int = 0                                # 秒
    remaining_time: int = 0                              # 秒（估算）


@dataclass
class ExecutionStatus:
    """执行引擎状态"""
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    total_tasks: int = 0
    resources_used: Dict[str, int] = field(default_factory=dict)


# ==================== ADB 层设备信息（与 modules.adb 互通） ====================

@dataclass
class CoreDeviceInfo:
    """核心引擎的设备信息"""
    device_id: str
    device_type: DeviceType = DeviceType.PHONE
    status: DeviceStatus = DeviceStatus.AVAILABLE
    connection_info: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    name: str = ""
    last_used: Optional[datetime] = None
    error_message: str = ""


# ==================== 日志数据结构 ====================

@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime = field(default_factory=datetime.now)
    level: LogLevel = LogLevel.INFO
    message: str = ""
    module: str = ""
    session_id: Optional[str] = None


@dataclass
class LogStatistics:
    """日志统计"""
    total_entries: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    debug_count: int = 0


@dataclass
class KeyEvent:
    """关键事件"""
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogParserResult:
    """日志解析结果"""
    log_type: str = ""
    entries: List[LogEntry] = field(default_factory=list)
    error_count: int = 0


@dataclass
class LogAnalysisResult:
    """日志分析结果"""
    key_events: List[KeyEvent] = field(default_factory=list)
    errors: List[LogEntry] = field(default_factory=list)
    statistics: LogStatistics = field(default_factory=LogStatistics)
