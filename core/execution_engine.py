"""执行引擎 — 测试任务调度与执行"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import List, Optional, Dict, Callable

from core.models import (
    TestCase, TestStep, TestResult, StepResult,
    CoreDeviceInfo, ResultStatus, ExecutionStatus, EventType,
)
from core.event_bus import EventBus, Event
from core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class StepExecutor:
    """
    步骤执行器
    根据步骤的 action_type 执行具体操作。
    子类可扩展以支持自定义 action_type。
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, action_type: str, handler: Callable):
        """注册自定义步骤处理器"""
        self._handlers[action_type] = handler

    def execute(self, step: TestStep, device: CoreDeviceInfo = None) -> StepResult:
        """执行单个测试步骤"""
        result = StepResult(
            step_id=step.step_id,
            step_name=step.name,
            status=ResultStatus.RUNNING,
            start_time=datetime.now(),
        )

        logger.info(f"执行步骤 [{step.step_id}] {step.name} (action={step.action_type})")

        try:
            handler = self._handlers.get(step.action_type)
            if handler:
                output = handler(step, device)
            else:
                output = self._default_execute(step)

            result.actual_result = str(output)
            result.status = ResultStatus.PASSED
            result.log_output = str(output)

        except Exception as e:
            result.status = ResultStatus.FAILED
            result.error_message = str(e)
            result.log_output = str(e)
            logger.error(f"步骤 [{step.step_id}] 执行失败: {e}")

        finally:
            result.end_time = datetime.now()

        return result

    def _default_execute(self, step: TestStep) -> str:
        """默认执行：返回步骤 action 作为模拟输出"""
        import subprocess
        try:
            proc = subprocess.run(
                step.action, shell=True, capture_output=True, text=True,
                timeout=step.timeout,
            )
            output = proc.stdout
            if proc.returncode != 0:
                output += f"\nSTDERR: {proc.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return f"[TIMEOUT] 超过 {step.timeout}s"
        except Exception as e:
            raise RuntimeError(f"命令执行失败: {e}")


class ExecutionEngine:
    """
    执行引擎

    调度测试用例的执行，支持串行/并发模式。
    通过 StepExecutor 执行具体步骤。
    """

    def __init__(self, resource_manager: ResourceManager = None):
        self.resource_manager = resource_manager or ResourceManager()
        self.step_executor = StepExecutor()
        self._executions: Dict[str, Dict] = {}               # execution_id -> execution state
        self._futures: Dict[str, List[Future]] = {}          # execution_id -> futures
        self._cancel_flags: Dict[str, threading.Event] = {}  # execution_id -> cancel event
        self._lock = threading.Lock()
        self._event_bus = EventBus()

    # ==================== 用例执行 ====================

    def execute_test_case(self, test_case: TestCase,
                          device: CoreDeviceInfo = None,
                          execution_id: str = None) -> TestResult:
        """
        串行执行单个测试用例的所有步骤。
        返回 TestResult，包含每一步的 StepResult。
        """
        execution_id = execution_id or f"exec_{test_case.case_id}"

        result = TestResult(
            case_id=test_case.case_id,
            case_name=test_case.name,
            status=ResultStatus.RUNNING,
            start_time=datetime.now(),
            device_id=device.device_id if device else None,
        )

        self._event_bus.publish(Event(
            EventType.CASE_STARTED,
            {"case_id": test_case.case_id, "case_name": test_case.name}
        ))

        # 按顺序执行每一步
        for step in sorted(test_case.steps, key=lambda s: s.order_index):
            # 检查是否被取消
            cancel_event = self._cancel_flags.get(execution_id)
            if cancel_event and cancel_event.is_set():
                result.status = ResultStatus.SKIPPED
                result.error_message = "Execution cancelled"
                break

            self._event_bus.publish(Event(
                EventType.STEP_STARTED,
                {"step_id": step.step_id, "step_name": step.name}
            ))

            # 执行步骤（支持重试）
            step_result = self._execute_step_with_retry(step, device)

            result.step_results.append(step_result)
            self._event_bus.publish(Event(
                EventType.STEP_COMPLETED,
                {"step_id": step.step_id, "status": step_result.status.value}
            ))

            # 步骤失败 → 用例失败（除非非关键步骤）
            if step_result.status in (ResultStatus.FAILED, ResultStatus.ERROR):
                result.status = ResultStatus.FAILED
                result.error_message = f"Step '{step.name}' failed: {step_result.error_message}"
                break

        # 所有步骤通过
        if result.status == ResultStatus.RUNNING:
            result.status = ResultStatus.PASSED

        result.end_time = datetime.now()
        result.actual_result = f"Passed: {sum(1 for s in result.step_results if s.status == ResultStatus.PASSED)}/{len(result.step_results)}"

        self._event_bus.publish(Event(
            EventType.CASE_COMPLETED if result.status == ResultStatus.PASSED else EventType.CASE_FAILED,
            {"case_id": test_case.case_id, "status": result.status.value}
        ))

        return result

    def execute_test_cases(self, test_cases: List[TestCase],
                           devices: List[CoreDeviceInfo],
                           max_workers: int = 4) -> List[TestResult]:
        """
        并发执行多个测试用例。
        每个用例分配到设备执行。
        """
        execution_id = f"batch_{datetime.now().strftime('%H%M%S')}"
        cancel_event = threading.Event()
        self._cancel_flags[execution_id] = cancel_event

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = []
            for i, test_case in enumerate(test_cases):
                device = devices[i % len(devices)] if devices else None
                future = pool.submit(self.execute_test_case, test_case, device, execution_id)
                futures.append(future)

            self._futures[execution_id] = futures

            for future in futures:
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"并发执行失败: {e}")
                    results.append(TestResult(
                        case_id="unknown",
                        status=ResultStatus.ERROR,
                        error_message=str(e),
                    ))

        self._cleanup_execution(execution_id)
        return results

    def _execute_step_with_retry(self, step: TestStep, device: CoreDeviceInfo = None) -> StepResult:
        """执行步骤（自动重试）"""
        last_result = None
        for attempt in range(1 + step.retry_count):
            if attempt > 0:
                logger.info(f"步骤 [{step.name}] 第 {attempt} 次重试...")
                time.sleep(step.retry_delay)

            step_result = self.step_executor.execute(step, device)
            step_result.retry_attempts = attempt

            if step_result.status == ResultStatus.PASSED:
                return step_result
            last_result = step_result

        return last_result

    # ==================== 执行状态 ====================

    def get_execution_status(self, execution_id: str = None) -> ExecutionStatus:
        """获取执行状态"""
        status = ExecutionStatus()
        with self._lock:
            futures = []
            if execution_id:
                futs = self._futures.get(execution_id, [])
                futures = [(execution_id, f) for f in futs]
            else:
                for eid, futs in self._futures.items():
                    futures.extend((eid, f) for f in futs)

        status.total_tasks = len(futures)
        for eid, future in futures:
            if future.done():
                if future.exception():
                    status.failed_tasks += 1
                else:
                    status.completed_tasks += 1
            else:
                status.running_tasks += 1

        status.pending_tasks = status.total_tasks - status.running_tasks - status.completed_tasks - status.failed_tasks
        return status

    def cancel_execution(self, execution_id: str) -> bool:
        """取消正在执行的测试"""
        cancel_event = self._cancel_flags.get(execution_id)
        if cancel_event:
            cancel_event.set()
            logger.info(f"已取消执行: {execution_id}")
            return True
        return False

    # ==================== 清理 ====================

    def _cleanup_execution(self, execution_id: str):
        """清理执行状态"""
        with self._lock:
            self._futures.pop(execution_id, None)
            self._cancel_flags.pop(execution_id, None)
