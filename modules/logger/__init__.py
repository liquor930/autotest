"""日志收集解析模块

功能:
    - HCI 日志采集（通过 ADB 启停 btsnoop + 拉取）
    - HCI btsnoop 格式解析（Android btsnoop_hci.log）
    - logcat 蓝牙日志解析和过滤
    - 通用文本日志解析
    - 关键事件提取（配对/连接/断连/错误）
    - 日志分析报告导出（txt）
"""

from modules.logger.logger_manager import LoggerManager
from modules.logger.hci_parser import HciLogParser

__all__ = [
    "LoggerManager",
    "HciLogParser",
]
