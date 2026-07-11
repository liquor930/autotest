"""
核心引擎

蓝牙自动化测试平台的核心组件，负责测试流程控制、任务调度、
结果管理和资源协调。

模块组成:
    - models:           数据模型定义（dataclasses + enums）
    - database:         数据库管理器（SQLite 持久化）
    - event_bus:        事件总线（观察者模式，模块间松耦合通信）
    - resource_manager: 资源管理器（设备注册、分配、释放）
    - execution_engine: 执行引擎（测试任务调度、步骤执行）
    - result_manager:   结果管理器（结果收集、存储、报告生成）
    - test_manager:     测试管理器（会话创建、启动/停止/暂停/恢复）
"""

from core.models import (
    TestSession, TestCase, TestStep, TestConfig,
    TestResult, StepResult, SessionInfo,
    SessionStatus, ResultStatus, DeviceType, DeviceStatus,
    CoreDeviceInfo, TestSessionStatus, ExecutionStatus,
    LogEntry, LogStatistics, KeyEvent, LogParserResult, LogAnalysisResult,
    EventType, LogLevel,
)

from core.event_bus import EventBus, Event
from core.database import DatabaseManager
from core.resource_manager import ResourceManager
from core.execution_engine import ExecutionEngine, StepExecutor
from core.result_manager import ResultManager
from core.test_manager import TestManager

__all__ = [
    # Models
    "TestSession", "TestCase", "TestStep", "TestConfig",
    "TestResult", "StepResult", "SessionInfo",
    "SessionStatus", "ResultStatus", "DeviceType", "DeviceStatus",
    "CoreDeviceInfo", "TestSessionStatus", "ExecutionStatus",
    "LogEntry", "LogStatistics", "KeyEvent", "LogParserResult", "LogAnalysisResult",
    "EventType", "LogLevel",

    # Event
    "EventBus", "Event",

    # Database
    "DatabaseManager",

    # Resource
    "ResourceManager",

    # Execution
    "ExecutionEngine", "StepExecutor",

    # Results
    "ResultManager",

    # Test Manager
    "TestManager",
]
