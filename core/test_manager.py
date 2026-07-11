"""测试管理器 — 测试会话的创建、控制与生命周期管理"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.models import (
    TestSession, TestCase, TestStep, TestConfig,
    SessionStatus, EventType, SessionInfo,
)
from core.database import DatabaseManager
from core.event_bus import EventBus, Event
from core.execution_engine import ExecutionEngine
from core.result_manager import ResultManager

logger = logging.getLogger(__name__)


class TestManager:
    """
    测试管理器

    核心引擎的顶层入口，负责：
    - 测试会话的创建、启动、停止、暂停、恢复
    - 测试配置的加载与解析
    - 协调 ExecutionEngine 和 ResultManager
    - 会话状态追踪与事件通知
    """

    def __init__(self, db_manager: DatabaseManager = None,
                 execution_engine: ExecutionEngine = None,
                 result_manager: ResultManager = None):
        self.db = db_manager or DatabaseManager()
        self.engine = execution_engine or ExecutionEngine()
        self.results = result_manager or ResultManager(self.db)

        self._sessions: Dict[str, TestSession] = {}         # 活跃会话缓存
        self._session_threads: Dict[str, threading.Thread] = {}
        self._session_events: Dict[str, threading.Event] = {}  # pause/resume/stop
        self._lock = threading.Lock()
        self._event_bus = EventBus()

    # ==================== 创建会话 ====================

    def create_session(self, config_file: str = None,
                       config: TestConfig = None,
                       name: str = "", description: str = "") -> str:
        """
        创建测试会话。
        可从配置文件或直接传入 TestConfig 创建。
        """
        resolved_config = config
        if config_file and os.path.exists(config_file):
            resolved_config = self._load_config(config_file)

        session = TestSession(
            name=name or (resolved_config.name if resolved_config else ""),
            description=description or (resolved_config.description if resolved_config else ""),
            config_file=config_file or "",
            config=resolved_config,
            status=SessionStatus.PENDING,
        )

        # 加载测试用例
        if resolved_config:
            session.devices = resolved_config.devices
            # 从配置中的 case_id 加载用例（此处简化为空列表，由子模块填充）
            session.test_cases = []

        # 持久化
        self.db.save_session(session)
        self.db.log_audit("SESSION_CREATED", "test_session", session.session_id, {
            "name": session.name, "config": config_file
        })

        with self._lock:
            self._sessions[session.session_id] = session

        self._event_bus.publish(Event(
            EventType.SESSION_CREATED,
            {"session_id": session.session_id, "name": session.name}
        ))

        logger.info(f"测试会话已创建: {session.session_id} ({session.name})")
        return session.session_id

    # ==================== 启动测试 ====================

    def start_test(self, session_id: str) -> bool:
        """启动测试会话（后台线程执行）"""
        session = self._get_session(session_id)
        if not session:
            return False

        if session.status not in (SessionStatus.PENDING, SessionStatus.PAUSED):
            logger.warning(f"会话 {session_id} 状态不允许启动: {session.status.value}")
            return False

        session.status = SessionStatus.RUNNING
        session.start_time = datetime.now()
        self.db.save_session(session)

        # 创建控制事件
        control_event = threading.Event()
        self._session_events[session_id] = control_event

        # 后台线程执行
        thread = threading.Thread(
            target=self._run_session,
            args=(session_id,),
            daemon=True,
            name=f"session-{session_id[:8]}"
        )
        self._session_threads[session_id] = thread
        thread.start()

        self._event_bus.publish(Event(
            EventType.SESSION_STARTED,
            {"session_id": session_id, "name": session.name}
        ))
        logger.info(f"测试已启动: {session_id}")
        return True

    def _run_session(self, session_id: str):
        """后台执行测试会话"""
        session = self._get_session(session_id)
        control_event = self._session_events.get(session_id)

        try:
            # 准备测试用例
            test_cases = self._prepare_test_cases(session)

            if not test_cases:
                session.status = SessionStatus.FAILED
                session.error_message = "No test cases to execute"
                self.db.save_session(session)
                self._event_bus.publish(Event(
                    EventType.SESSION_FAILED,
                    {"session_id": session_id, "error": session.error_message}
                ))
                return

            # 逐用例执行
            total = len(test_cases)
            for i, test_case in enumerate(test_cases):
                # 检查暂停/停止
                if control_event and control_event.is_set():
                    session.status = SessionStatus.STOPPED
                    break

                session.current_case_id = test_case.case_id
                session.progress = (i / total) * 100
                self.db.save_session(session)

                # 分配设备
                device = None
                if hasattr(self.engine, 'resource_manager'):
                    device = self.engine.resource_manager.allocate_specific_device(
                        session.devices[i % len(session.devices)]
                    ) if session.devices else None

                # 执行
                result = self.engine.execute_test_case(test_case, device)
                result.session_id = session_id

                # 释放设备
                if device:
                    self.engine.resource_manager.release_device(device.device_id)

                # 保存结果
                self.results.save_test_result(result)

            # 最终状态
            if session.status != SessionStatus.STOPPED:
                session.status = SessionStatus.COMPLETED

            session.progress = 100.0
            session.end_time = datetime.now()
            self.db.save_session(session)

            # 生成报告
            try:
                report_path = self.results.generate_report(session_id, "html")
                logger.info(f"测试报告: {report_path}")
            except Exception as e:
                logger.warning(f"报告生成失败: {e}")

            event_type = EventType.SESSION_COMPLETED if session.status == SessionStatus.COMPLETED else EventType.SESSION_STOPPED
            self._event_bus.publish(Event(event_type, {"session_id": session_id}))

        except Exception as e:
            session.status = SessionStatus.FAILED
            session.error_message = str(e)
            session.end_time = datetime.now()
            self.db.save_session(session)
            self._event_bus.publish(Event(
                EventType.SESSION_FAILED,
                {"session_id": session_id, "error": str(e)}
            ))
            logger.error(f"会话执行异常: {e}")

    def _prepare_test_cases(self, session: TestSession) -> List[TestCase]:
        """
        准备测试用例。
        从配置加载 case_id 列表，返回 TestCase 对象列表。
        实际项目中应通过配置的 case_id 从用例库加载。
        """
        # 如果会话已有用例，直接返回
        if session.test_cases:
            return session.test_cases

        # 从配置文件中的 test_cases 列表加载
        if session.config and session.config.test_cases:
            # 此处简化：根据 case_id 构造占位用例
            cases = []
            for cid in session.config.test_cases:
                case = TestCase(
                    case_id=cid,
                    name=f"Test Case {cid}",
                    steps=[
                        TestStep(name=f"Step 1 of {cid}", action=f"echo 'Executing {cid}'",
                                 action_type="shell", order_index=0),
                    ]
                )
                cases.append(case)
            return cases

        # 默认用例
        return [
            TestCase(
                name="Default Test",
                steps=[
                    TestStep(name="Check device", action="echo 'Device check OK'",
                             action_type="shell", order_index=0),
                ]
            )
        ]

    # ==================== 暂停 / 恢复 / 停止 ====================

    def pause_test(self, session_id: str) -> bool:
        """暂停测试"""
        session = self._get_session(session_id)
        if not session or session.status != SessionStatus.RUNNING:
            return False

        session.status = SessionStatus.PAUSED
        self.db.save_session(session)
        self._event_bus.publish(Event(
            EventType.SESSION_PAUSED, {"session_id": session_id}
        ))
        logger.info(f"测试已暂停: {session_id}")
        return True

    def resume_test(self, session_id: str) -> bool:
        """恢复测试"""
        session = self._get_session(session_id)
        if not session or session.status != SessionStatus.PAUSED:
            return False

        session.status = SessionStatus.RUNNING
        self.db.save_session(session)
        self._event_bus.publish(Event(
            EventType.SESSION_RESUMED, {"session_id": session_id}
        ))
        logger.info(f"测试已恢复: {session_id}")
        return True

    def stop_test(self, session_id: str) -> bool:
        """停止测试"""
        # 设置控制事件
        control_event = self._session_events.get(session_id)
        if control_event:
            control_event.set()

        # 取消执行引擎中的任务
        for eid in list(self.engine._cancel_flags.keys()):
            self.engine.cancel_execution(eid)

        session = self._get_session(session_id)
        if session:
            session.status = SessionStatus.STOPPED
            session.end_time = datetime.now()
            self.db.save_session(session)
            self._event_bus.publish(Event(
                EventType.SESSION_STOPPED, {"session_id": session_id}
            ))

        logger.info(f"测试已停止: {session_id}")
        return True

    # ==================== 状态查询 ====================

    def get_session_status(self, session_id: str):
        """获取会话实时状态"""
        session = self._get_session(session_id)
        if not session:
            return None

        elapsed = 0
        if session.start_time:
            end = session.end_time or datetime.now()
            elapsed = int((end - session.start_time).total_seconds())

        from core.models import TestSessionStatus
        return TestSessionStatus(
            session_id=session_id,
            status=session.status,
            progress=session.progress,
            current_case=session.current_case_id,
            current_step=session.current_step_id,
            elapsed_time=elapsed,
            remaining_time=max(0, int(elapsed * (100 - session.progress) / max(session.progress, 1))),
        )

    def list_sessions(self) -> List[SessionInfo]:
        """列出所有会话"""
        rows = self.db.list_sessions(50)
        infos = []
        for row in rows:
            total = self.db.execute_query(
                "SELECT COUNT(*) as cnt FROM test_results WHERE session_id = ?",
                (row["session_id"],)
            )
            passed = self.db.execute_query(
                "SELECT COUNT(*) as cnt FROM test_results WHERE session_id = ? AND status='PASSED'",
                (row["session_id"],)
            )
            failed = self.db.execute_query(
                "SELECT COUNT(*) as cnt FROM test_results WHERE session_id = ? AND status IN ('FAILED','ERROR')",
                (row["session_id"],)
            )
            infos.append(SessionInfo(
                session_id=row["session_id"],
                name=row["name"],
                status=SessionStatus(row["status"]),
                start_time=datetime.fromisoformat(row["start_time"]) if row.get("start_time") else None,
                end_time=datetime.fromisoformat(row["end_time"]) if row.get("end_time") else None,
                total_cases=total[0]["cnt"] if total else 0,
                passed=passed[0]["cnt"] if passed else 0,
                failed=failed[0]["cnt"] if failed else 0,
                progress=row["progress"],
            ))
        return infos

    def cleanup_session(self, session_id: str) -> bool:
        """清理会话数据"""
        try:
            self.stop_test(session_id)
            self.db.delete_session(session_id)
            with self._lock:
                self._sessions.pop(session_id, None)
                self._session_threads.pop(session_id, None)
                self._session_events.pop(session_id, None)
            logger.info(f"会话已清理: {session_id}")
            return True
        except Exception as e:
            logger.error(f"清理会话失败: {e}")
            return False

    # ==================== 配置加载 ====================

    def _load_config(self, config_file: str) -> Optional[TestConfig]:
        """从 YAML/JSON 文件加载测试配置"""
        if not os.path.exists(config_file):
            logger.error(f"配置文件不存在: {config_file}")
            return None

        ext = os.path.splitext(config_file)[1].lower()
        try:
            if ext in ('.yaml', '.yml'):
                try:
                    import yaml
                    with open(config_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                except ImportError:
                    logger.warning("PyYAML 未安装，尝试 JSON 解析 YAML")
                    with open(config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
            elif ext == '.json':
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                logger.error(f"不支持的配置文件格式: {ext}")
                return None

            return TestConfig(
                config_id=data.get("config_id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                test_cases=data.get("test_cases", []),
                devices=data.get("devices", []),
                serial_ports=data.get("serial_ports", []),
                prep_script=data.get("prep_script"),
                max_workers=data.get("max_workers", 4),
                report_format=data.get("report_format", "html"),
                output_dir=data.get("output_dir", "reports"),
            )
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return None

    # ==================== 内部 ====================

    def _get_session(self, session_id: str) -> Optional[TestSession]:
        """获取会话（缓存优先）"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session
        return self.db.load_session(session_id)
