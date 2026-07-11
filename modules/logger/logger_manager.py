"""
日志管理器 — 日志收集、解析、分析和导出

功能:
    - 通过 ADB 控制 HCI 日志启停
    - 拉取 HCI 日志文件
    - 解析 btsnoop / logcat / 文本日志
    - 关键事件提取和错误分析
    - 导出分析报告
"""

import logging
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.models import (
    LogEntry, LogLevel, LogStatistics, KeyEvent,
    LogParserResult, LogAnalysisResult,
)
from modules.logger.hci_parser import HciLogParser

logger = logging.getLogger(__name__)

# 默认日志输出目录
DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs"
)


class LoggerManager:
    """
    日志管理器

    统一管理 HCI 日志和模块日志的采集、解析、分析和导出。
    通过 ADBManager 进行远程设备日志操作。
    """

    def __init__(self, adb_manager=None, log_dir: str = DEFAULT_LOG_DIR):
        self.adb = adb_manager
        self._parser = HciLogParser()
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        # 日志收集状态
        self._hci_enabled = False
        self._collection_start: Optional[datetime] = None
        self._active_device_id: Optional[str] = None

    def set_adb_manager(self, adb_manager):
        """设置 ADB 管理器引用"""
        self.adb = adb_manager

    # ==================== HCI 日志采集 ====================

    def start_hci_log(self, device_id: str) -> bool:
        """通过 ADB 启用 btsnoop HCI 日志"""
        if not self.adb or not hasattr(self.adb, 'start_hci_log'):
            raise RuntimeError("ADB manager not available or missing start_hci_log")

        result = self.adb.start_hci_log(device_id)
        if result:
            self._hci_enabled = True
            self._collection_start = datetime.now()
            self._active_device_id = device_id
            logger.info(f"HCI log started on {device_id}")
        return result

    def stop_hci_log(self, device_id: str = None) -> bool:
        """通过 ADB 禁用 btsnoop HCI 日志"""
        if not self.adb or not hasattr(self.adb, 'stop_hci_log'):
            raise RuntimeError("ADB manager not available or missing stop_hci_log")

        device_id = device_id or self._active_device_id
        if not device_id:
            logger.warning("No active device to stop HCI log")
            return False

        result = self.adb.stop_hci_log(device_id)
        if result:
            self._hci_enabled = False
            if self._collection_start:
                duration = (datetime.now() - self._collection_start).total_seconds()
                logger.info(f"HCI log stopped on {device_id}, duration={duration:.0f}s")
            self._collection_start = None
        return result

    def pull_hci_log(self, device_id: str, output_file: str = None) -> Optional[str]:
        """
        拉取 HCI 日志到本地

        Returns:
            保存的本地文件路径，失败返回 None
        """
        if not self.adb or not hasattr(self.adb, 'pull_file'):
            raise RuntimeError("ADB manager not available or missing pull_file")

        device_id = device_id or self._active_device_id
        if not device_id:
            logger.error("No device specified for HCI log pull")
            return None

        # 默认输出路径
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.log_dir, f"btsnoop_hci_{device_id.replace(':','_')}_{timestamp}.log")

        success = self.adb.pull_file(device_id, "/sdcard/btsnoop_hci.log", output_file)
        return output_file if success else None

    # ==================== 日志解析 ====================

    def parse_hci_log(self, log_file: str) -> LogParserResult:
        """解析 HCI 日志文件"""
        return self._parser.parse(log_file, 'btsnoop')

    def parse_module_log(self, log_file: str) -> LogParserResult:
        """解析蓝牙模块日志（串口 AT 输出等）"""
        return self._parser.parse(log_file, 'text')

    def parse_logcat(self, log_file: str) -> LogParserResult:
        """解析 Android logcat"""
        return self._parser.parse(log_file, 'logcat')

    # ==================== 日志分析 ====================

    def analyze_log(self, log_type: str, log_file: str) -> LogAnalysisResult:
        """解析 + 分析一站式"""
        return self._parser.analyze_log(log_type, log_file)

    def quick_analyze(self, log_file: str) -> Dict[str, Any]:
        """快速分析摘要"""
        if self._parser._is_btsnoop(log_file):
            return self._parser.quick_analyze_btsnoop(log_file)

        result = self._parser.parse(log_file)
        analysis = self._parser.analyze(result)
        return {
            "total_entries": analysis.statistics.total_entries,
            "errors": analysis.statistics.error_count,
            "warnings": analysis.statistics.warning_count,
            "key_events": len(analysis.key_events),
        }

    # ==================== 导出 ====================

    def export_analysis(self, analysis_result: LogAnalysisResult,
                        output_file: str = None) -> Optional[str]:
        """导出分析报告"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.log_dir, f"log_analysis_{timestamp}.txt")

        success = self._parser.export_analysis(analysis_result, output_file)
        return output_file if success else None

    # ==================== 日志文件管理 ====================

    def list_log_files(self, pattern: str = "*") -> List[Dict[str, Any]]:
        """列出本地日志文件"""
        import glob
        files = []
        for f in sorted(glob.glob(os.path.join(self.log_dir, pattern)), key=os.path.getmtime, reverse=True):
            if os.path.isfile(f):
                files.append({
                    "name": os.path.basename(f),
                    "path": f,
                    "size": os.path.getsize(f),
                    "size_str": self._format_size(os.path.getsize(f)),
                    "modified": datetime.fromtimestamp(os.path.getmtime(f)),
                })
        return files

    def delete_log_file(self, file_name: str) -> bool:
        """删除日志文件"""
        file_path = os.path.join(self.log_dir, file_name)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Delete log file failed: {e}")
        return False

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    # ==================== 一站式采集+分析 ====================

    def collect_and_analyze(self, device_id: str, duration_s: int = 10) -> Optional[str]:
        """
        一键采集 + 分析: 开启日志 → 等待 → 停止 → 拉取 → 分析 → 导出报告

        Returns:
            分析报告路径，失败返回 None
        """
        logger.info(f"开始一键采集分析: device={device_id}, duration={duration_s}s")

        if not self.start_hci_log(device_id):
            logger.error("启动 HCI 日志失败")
            return None

        logger.info(f"等待 {duration_s}s...")
        time.sleep(duration_s)

        self.stop_hci_log(device_id)

        log_file = self.pull_hci_log(device_id)
        if not log_file or not os.path.exists(log_file):
            logger.error("拉取 HCI 日志失败")
            return None

        logger.info(f"分析日志: {log_file}")
        analysis = self.analyze_log('btsnoop', log_file)
        report = self.export_analysis(analysis)
        return report
