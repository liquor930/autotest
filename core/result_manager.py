"""结果管理器 — 测试结果收集、存储、报告生成"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.models import (
    TestResult, StepResult, ResultStatus, EventType,
)
from core.database import DatabaseManager
from core.event_bus import EventBus, Event

logger = logging.getLogger(__name__)

# 默认报告输出目录
DEFAULT_REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


class ResultManager:
    """
    结果管理器

    收集测试结果并持久化到数据库，提供查询和报告生成功能。
    """

    def __init__(self, db_manager: DatabaseManager = None,
                 report_dir: str = DEFAULT_REPORT_DIR):
        self.db_manager = db_manager or DatabaseManager()
        self.report_dir = report_dir
        self._event_bus = EventBus()
        os.makedirs(self.report_dir, exist_ok=True)

    # ==================== 保存结果 ====================

    def save_test_result(self, result: TestResult) -> bool:
        """保存测试结果到数据库"""
        try:
            result.session_id = result.session_id or ""
            self.db_manager.save_test_result(result)
            for step_result in result.step_results:
                step_result.result_id = result.result_id
                self.db_manager.save_step_result(step_result)
            return True
        except Exception as e:
            logger.error(f"保存测试结果失败: {e}")
            return False

    def save_step_result(self, step_result: StepResult) -> bool:
        """保存步骤结果"""
        try:
            self.db_manager.save_step_result(step_result)
            return True
        except Exception as e:
            logger.error(f"保存步骤结果失败: {e}")
            return False

    # ==================== 查询结果 ====================

    def get_test_result(self, case_id: str, session_id: str) -> Optional[TestResult]:
        """获取指定测试结果"""
        result = self.db_manager.get_test_result(case_id, session_id)
        if result:
            result.step_results = self.db_manager.get_step_results(result.result_id)
        return result

    def get_session_results(self, session_id: str) -> List[TestResult]:
        """获取会话的所有测试结果"""
        results = self.db_manager.get_session_results(session_id)
        for r in results:
            r.step_results = self.db_manager.get_step_results(r.result_id)
        return results

    # ==================== 报告生成 ====================

    def generate_report(self, session_id: str, report_format: str = "html") -> str:
        """
        生成测试报告。
        返回报告文件路径。
        """
        results = self.get_session_results(session_id)
        session = self.db_manager.load_session(session_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_slug = (session.name or "test").replace(" ", "_")[:30] if session else "test"

        if report_format == "html":
            path = os.path.join(self.report_dir, f"{name_slug}_{timestamp}.html")
            self._generate_html_report(results, session, path)
        elif report_format == "csv":
            path = os.path.join(self.report_dir, f"{name_slug}_{timestamp}.csv")
            self._generate_csv_report(results, path)
        else:
            path = os.path.join(self.report_dir, f"{name_slug}_{timestamp}.html")
            self._generate_html_report(results, session, path)

        self._event_bus.publish(Event(
            EventType.REPORT_GENERATED,
            {"session_id": session_id, "path": path, "format": report_format}
        ))
        logger.info(f"报告已生成: {path}")
        return path

    def _generate_html_report(self, results: List[TestResult],
                              session_data: Any = None,
                              output_path: str = "report.html"):
        """生成 HTML 报告"""
        total = len(results)
        passed = sum(1 for r in results if r.status == ResultStatus.PASSED)
        failed = sum(1 for r in results if r.status in (ResultStatus.FAILED, ResultStatus.ERROR))
        skipped = sum(1 for r in results if r.status == ResultStatus.SKIPPED)
        pass_rate = (passed / total * 100) if total > 0 else 0

        # 构建用例行
        case_rows = ""
        for r in results:
            status_badge = {
                ResultStatus.PASSED: '<span class="badge badge-pass">PASS</span>',
                ResultStatus.FAILED: '<span class="badge badge-fail">FAIL</span>',
                ResultStatus.ERROR: '<span class="badge badge-fail">ERROR</span>',
                ResultStatus.SKIPPED: '<span class="badge badge-skip">SKIP</span>',
                ResultStatus.TIMEOUT: '<span class="badge badge-fail">TIMEOUT</span>',
                ResultStatus.RUNNING: '<span class="badge badge-warn">RUNNING</span>',
                ResultStatus.PENDING: '<span class="badge badge-warn">PENDING</span>',
            }.get(r.status, '<span class="badge badge-warn">UNKNOWN</span>')

            steps_html = ""
            for s in r.step_results:
                s_status = {
                    ResultStatus.PASSED: "✅",
                    ResultStatus.FAILED: "❌",
                    ResultStatus.ERROR: "⚠️",
                    ResultStatus.SKIPPED: "⏭️",
                }.get(s.status, "⏳")
                steps_html += f"<tr><td>{s.step_name}</td><td>{s_status}</td>"
                steps_html += f"<td>{s.actual_result[:100]}</td>"
                steps_html += f"<td>{s.error_message[:100] if s.error_message else '-'}</td></tr>"

            duration = ""
            if r.start_time and r.end_time:
                delta = (r.end_time - r.start_time).total_seconds()
                duration = f"{delta:.1f}s"

            case_rows += f"""
            <tr>
                <td>{r.case_name or r.case_id[:12]}</td>
                <td>{status_badge}</td>
                <td>{duration}</td>
                <td>{r.error_message[:80] if r.error_message else '-'}</td>
            </tr>
            """

        session_name = session_data.name if session_data else "Test Report"
        session_desc = session_data.description if session_data else ""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{session_name} - 测试报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f7fa; color: #333; padding: 20px; }}
.header {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px;
           box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
.header h1 {{ font-size: 22px; margin-bottom: 8px; }}
.header p {{ color: #666; font-size: 14px; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
.stat-card {{ background: #fff; border-radius: 10px; padding: 20px; min-width: 140px;
              flex: 1; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
.stat-card .num {{ font-size: 32px; font-weight: 700; }}
.stat-card .label {{ color: #888; font-size: 13px; margin-top: 4px; }}
.stat-card.pass .num {{ color: #22c55e; }}
.stat-card.fail .num {{ color: #ef4444; }}
.stat-card.skip .num {{ color: #f59e0b; }}
.stat-card.total .num {{ color: #3b82f6; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px;
         overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }}
th {{ background: #f8fafc; font-weight: 600; color: #555; }}
tr:hover {{ background: #f8fafc; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px;
          font-size: 12px; font-weight: 600; }}
.badge-pass {{ background: #dcfce7; color: #16a34a; }}
.badge-fail {{ background: #fef2f2; color: #dc2626; }}
.badge-skip {{ background: #fef3c7; color: #d97706; }}
.badge-warn {{ background: #eff6ff; color: #2563eb; }}
.details-btn {{ color: #3b82f6; cursor: pointer; text-decoration: underline; font-size: 13px; }}
@media (max-width: 640px) {{ .stat-card {{ min-width: 100px; }} }}
</style>
</head>
<body>
<div class="header">
    <h1>📊 {session_name}</h1>
    <p>{session_desc}</p>
    <p style="margin-top:6px;color:#999;font-size:13px">
        生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
        会话ID: {session_data.session_id if session_data else '-'}
    </p>
</div>

<div class="summary">
    <div class="stat-card total"><div class="num">{total}</div><div class="label">总用例</div></div>
    <div class="stat-card pass"><div class="num">{passed}</div><div class="label">通过</div></div>
    <div class="stat-card fail"><div class="num">{failed}</div><div class="label">失败</div></div>
    <div class="stat-card skip"><div class="num">{skipped}</div><div class="label">跳过</div></div>
    <div class="stat-card total"><div class="num">{pass_rate:.1f}%</div><div class="label">通过率</div></div>
</div>

<table>
<thead><tr><th>用例名称</th><th>状态</th><th>耗时</th><th>错误信息</th></tr></thead>
<tbody>{case_rows}</tbody>
</table>

<p style="text-align:center;color:#999;font-size:12px;margin-top:20px">
    Bluetooth Auto Test Platform · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</p>
</body>
</html>"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def _generate_csv_report(self, results: List[TestResult], output_path: str):
        """生成 CSV 报告"""
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["Case ID", "Case Name", "Status", "Error Message",
                             "Start Time", "End Time", "Steps"])
            for r in results:
                steps_summary = "; ".join(
                    f"{s.step_name}:{s.status.value}" for s in r.step_results
                )
                writer.writerow([
                    r.case_id[:12], r.case_name, r.status.value,
                    r.error_message,
                    r.start_time.isoformat() if r.start_time else "",
                    r.end_time.isoformat() if r.end_time else "",
                    steps_summary,
                ])

    # ==================== 导出 ====================

    def export_results(self, session_id: str, export_format: str,
                       output_file: str) -> bool:
        """导出测试结果到指定文件"""
        try:
            path = self.generate_report(session_id, export_format)
            if output_file and path != output_file:
                import shutil
                shutil.copy2(path, output_file)
                logger.info(f"结果已导出到: {output_file}")
            return True
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return False

    # ==================== 统计 ====================

    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """获取会话的测试统计"""
        results = self.get_session_results(session_id)
        total_steps = sum(len(r.step_results) for r in results)
        passed_steps = sum(
            sum(1 for s in r.step_results if s.status == ResultStatus.PASSED)
            for r in results
        )

        return {
            "total_cases": len(results),
            "passed": sum(1 for r in results if r.status == ResultStatus.PASSED),
            "failed": sum(1 for r in results if r.status in (ResultStatus.FAILED, ResultStatus.ERROR)),
            "skipped": sum(1 for r in results if r.status == ResultStatus.SKIPPED),
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "pass_rate": (sum(1 for r in results if r.status == ResultStatus.PASSED) / len(results) * 100)
                         if results else 0,
        }
