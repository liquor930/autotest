"""
HCI 日志解析器

支持解析:
1. Android btsnoop_hci.log (btsnoop 格式) — 通过 BtsnoopParser
2. HCI snoop log (文本格式) — 直接文本解析
3. Android logcat 蓝牙相关日志
"""

import re
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

from core.models import (
    LogEntry, LogLevel, KeyEvent, LogStatistics,
    LogParserResult, LogAnalysisResult,
)
from modules.logger.btsnoop import BtsnoopParser


class HciLogParser:
    """
    HCI 日志解析器

    集成多种日志格式解析，提供统一的分析接口。

    用法:
        parser = HciLogParser()
        result = parser.parse('btsnoop_hci.log')
        analysis = parser.analyze(result)
        print(analysis.statistics)
    """

    # Android logcat 蓝牙相关关键字
    BT_KEYWORDS = [
        'Bluetooth', 'bluetooth', 'bt_', 'BT_',
        'hci', 'HCI', 'acl', 'ACL', 'sco', 'SCO',
        'l2cap', 'L2CAP', 'rfcomm', 'RFCOMM',
        'gatt', 'GATT', 'sdp', 'SDP',
    ]

    # 日志级别模式
    PATTERN_LOG_LEVEL = re.compile(
        r'\b(VERBOSE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL)\b'
    )

    # logcat 标准格式: 日期 时间  PID  TID  LEVEL  TAG: message
    PATTERN_LOGCAT = re.compile(
        r'^(\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d+)\s+'
        r'(\d+)\s+(\d+)\s+([VDFIWE])\s+(\S+):\s*(.*)'
    )

    LOG_LEVEL_MAP = {
        'V': LogLevel.DEBUG,
        'D': LogLevel.DEBUG,
        'I': LogLevel.INFO,
        'W': LogLevel.WARNING,
        'E': LogLevel.ERROR,
        'F': LogLevel.CRITICAL,
    }

    # HCI snoop 文本格式行匹配
    PATTERN_HCI_SNOOP = re.compile(
        r'^[<\->]\s+HCI\s+(Command|Event|ACL|SCO|ISO)'
    )

    def __init__(self):
        self._btsnoop_parser = BtsnoopParser()

    # ==================== 解析入口 ====================

    def parse(self, file_path: str, log_type: str = None) -> LogParserResult:
        """
        解析日志文件，自动检测格式。

        Args:
            file_path: 日志文件路径
            log_type: 强制指定类型: 'btsnoop', 'logcat', 'hci_snoop', 'auto'

        Returns:
            LogParserResult
        """
        if log_type == 'btsnoop' or (log_type is None and self._is_btsnoop(file_path)):
            return self._btsnoop_parser.parse(file_path)

        if log_type == 'logcat' or (log_type is None and self._is_logcat(file_path)):
            return self._parse_logcat(file_path)

        # 默认: 按行解析文本日志
        return self._parse_text_log(file_path)

    def _is_btsnoop(self, file_path: str) -> bool:
        """检测是否为 btsnoop 二进制格式"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
            return header == b'btsnoop\x00'
        except Exception:
            return False

    def _is_logcat(self, file_path: str) -> bool:
        """检测是否为 logcat 文本格式"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for _ in range(20):
                    line = f.readline()
                    if self.PATTERN_LOGCAT.match(line):
                        return True
            return False
        except Exception:
            return False

    # ==================== logcat 解析 ====================

    def _parse_logcat(self, file_path: str) -> LogParserResult:
        """解析 logcat 格式日志"""
        result = LogParserResult(log_type="logcat", error_count=0)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                current_year = datetime.now().year
                for line in f:
                    line = line.rstrip('\n\r')
                    entry = self._parse_logcat_line(line, current_year)
                    if entry:
                        # 只保留蓝牙相关日志
                        if any(kw in entry.message for kw in self.BT_KEYWORDS):
                            result.entries.append(entry)
                            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                                result.error_count += 1
        except FileNotFoundError:
            result.error_count += 1

        return result

    def _parse_logcat_line(self, line: str, year: int) -> Optional[LogEntry]:
        """解析单行 logcat"""
        m = self.PATTERN_LOGCAT.match(line)
        if not m:
            return None

        date_str = m.group(1)      # MM-DD
        time_str = m.group(2)      # HH:MM:SS.mmm
        # pid = m.group(3)
        # tid = m.group(4)
        level_char = m.group(5)    # V/D/I/W/E/F
        tag = m.group(6)
        message = m.group(7)

        level = self.LOG_LEVEL_MAP.get(level_char, LogLevel.INFO)

        try:
            ts = datetime.strptime(
                f"{year}-{date_str} {time_str}",
                "%Y-%m-%d %H:%M:%S.%f"
            )
        except ValueError:
            ts = datetime.now()

        return LogEntry(
            timestamp=ts,
            level=level,
            message=f"[{tag}] {message}",
        )

    # ==================== 通用文本日志解析 ====================

    def _parse_text_log(self, file_path: str) -> LogParserResult:
        """解析通用文本日志"""
        result = LogParserResult(log_type="text")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.rstrip('\n\r')
                    if not line:
                        continue
                    entry = self._parse_text_line(line)
                    if entry:
                        result.entries.append(entry)
                        if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                            result.error_count += 1
        except FileNotFoundError:
            result.error_count += 1

        return result

    def _parse_text_line(self, line: str) -> Optional[LogEntry]:
        """解析单行文本日志"""
        level = LogLevel.INFO

        # 检测级别
        m = self.PATTERN_LOG_LEVEL.search(line.upper())
        if m:
            lvl = m.group(1)
            if lvl in ('ERROR', 'FATAL'):
                level = LogLevel.ERROR
            elif lvl == 'WARN' or lvl == 'WARNING':
                level = LogLevel.WARNING
            elif lvl == 'DEBUG':
                level = LogLevel.DEBUG
            elif lvl == 'VERBOSE':
                level = LogLevel.DEBUG

        return LogEntry(level=level, message=line)

    # ==================== 日志分析 ====================

    def analyze(self, parse_result: LogParserResult) -> LogAnalysisResult:
        """分析解析后的日志，提取关键事件和统计"""
        analysis = LogAnalysisResult()

        # 基本统计
        for entry in parse_result.entries:
            if entry.level == LogLevel.ERROR or entry.level == LogLevel.CRITICAL:
                analysis.statistics.error_count += 1
                analysis.errors.append(entry)
            elif entry.level == LogLevel.WARNING:
                analysis.statistics.warning_count += 1
            elif entry.level == LogLevel.INFO:
                analysis.statistics.info_count += 1
            elif entry.level == LogLevel.DEBUG:
                analysis.statistics.debug_count += 1

        analysis.statistics.total_entries = len(parse_result.entries)

        # 提取关键事件
        analysis.key_events = parse_result.key_events or []

        # 错误聚类
        if analysis.errors:
            # 按错误消息模式聚类
            error_patterns: Dict[str, int] = {}
            for err in analysis.errors:
                # 取前60字符作为模式
                pattern = err.message[:60]
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1

        return analysis

    def quick_analyze_btsnoop(self, file_path: str) -> dict:
        """快速分析 btsnoop 日志"""
        return self._btsnoop_parser.quick_analyze(file_path)

    # ==================== 模块日志解析 ====================

    def parse_module_log(self, log_file: str) -> LogParserResult:
        """解析模块日志（蓝牙模块串口输出）"""
        return self._parse_text_log(log_file)

    def parse_hci_log(self, log_file: str) -> LogParserResult:
        """解析 HCI 日志（自动检测格式）"""
        return self.parse(log_file)

    def analyze_log(self, log_type: str, log_file: str) -> LogAnalysisResult:
        """一站式: 解析 + 分析"""
        parse_result = self.parse(log_file, log_type)
        return self.analyze(parse_result)

    def export_analysis(self, analysis_result: LogAnalysisResult,
                        output_file: str, export_format: str = "txt") -> bool:
        """导出分析结果到文件"""
        try:
            lines = []
            lines.append("=" * 60)
            lines.append("蓝牙自动化测试平台 - 日志分析报告")
            lines.append("=" * 60)
            lines.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"总条目数: {analysis_result.statistics.total_entries}")
            lines.append(f"错误数: {analysis_result.statistics.error_count}")
            lines.append(f"警告数: {analysis_result.statistics.warning_count}")
            lines.append(f"信息数: {analysis_result.statistics.info_count}")
            lines.append(f"关键事件数: {len(analysis_result.key_events)}")
            lines.append(f"错误条目数: {len(analysis_result.errors)}")
            lines.append("")

            if analysis_result.key_events:
                lines.append("--- 关键事件 ---")
                for evt in analysis_result.key_events:
                    lines.append(
                        f"  [{evt.timestamp.strftime('%H:%M:%S')}] "
                        f"{evt.event_type}: {evt.details}"
                    )

            if analysis_result.errors:
                lines.append("")
                lines.append(f"--- 错误列表 ({len(analysis_result.errors)} 条) ---")
                for err in analysis_result.errors[:50]:
                    lines.append(f"  [{err.level.value}] {err.message}")

            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True

        except Exception as e:
            print(f"导出分析结果失败: {e}")
            return False
