"""数据库管理器 — SQLite 持久化"""

import json
import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.models import (
    TestSession, TestCase, TestStep, TestResult, StepResult,
    SessionStatus, ResultStatus,
)

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "test_results.db")


class DatabaseManager:
    """
    数据库管理器
    
    基于 SQLite，提供线程安全的查询/更新操作，管理测试相关数据的持久化。
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._local = threading.local()  # 每个线程独立连接
        self._init_db()

    # ==================== 连接管理 ====================

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def close(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ==================== 初始化 ====================

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                session_id      TEXT PRIMARY KEY,
                name            TEXT NOT NULL DEFAULT '',
                description     TEXT DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'PENDING',
                config_file     TEXT DEFAULT '',
                config_json     TEXT DEFAULT '{}',
                start_time      TEXT,
                end_time        TEXT,
                progress        REAL DEFAULT 0.0,
                current_case_id TEXT,
                current_step_id TEXT,
                error_message   TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS test_cases (
                case_id      TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                name         TEXT NOT NULL DEFAULT '',
                description  TEXT DEFAULT '',
                priority     TEXT DEFAULT 'P2',
                timeout      INTEGER DEFAULT 300,
                tags         TEXT DEFAULT '[]',
                steps_json   TEXT DEFAULT '[]',
                order_index  INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS test_results (
                result_id      TEXT PRIMARY KEY,
                session_id     TEXT NOT NULL,
                case_id        TEXT NOT NULL,
                case_name      TEXT DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'PENDING',
                start_time     TEXT,
                end_time       TEXT,
                actual_result  TEXT DEFAULT '',
                error_message  TEXT DEFAULT '',
                log_path       TEXT DEFAULT '',
                device_id      TEXT DEFAULT '',
                created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS step_results (
                step_result_id TEXT PRIMARY KEY,
                result_id      TEXT NOT NULL,
                step_id        TEXT NOT NULL,
                step_name      TEXT DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'PENDING',
                start_time     TEXT,
                end_time       TEXT,
                actual_result  TEXT DEFAULT '',
                error_message  TEXT DEFAULT '',
                log_output     TEXT DEFAULT '',
                retry_attempts INTEGER DEFAULT 0,
                FOREIGN KEY (result_id) REFERENCES test_results(result_id)
            );

            CREATE TABLE IF NOT EXISTS devices (
                device_id      TEXT PRIMARY KEY,
                device_type    TEXT DEFAULT 'PHONE',
                name           TEXT DEFAULT '',
                status         TEXT DEFAULT 'AVAILABLE',
                connection_info TEXT DEFAULT '{}',
                properties     TEXT DEFAULT '{}',
                last_used      TEXT,
                error_message  TEXT DEFAULT '',
                created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS test_configs (
                config_id    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT DEFAULT '',
                config_data  TEXT NOT NULL DEFAULT '{}',
                file_path    TEXT DEFAULT '',
                created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key   TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                description   TEXT DEFAULT '',
                updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id        TEXT PRIMARY KEY,
                action        TEXT NOT NULL,
                resource_type TEXT DEFAULT '',
                resource_id   TEXT DEFAULT '',
                details       TEXT DEFAULT '{}',
                timestamp     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_results_session ON test_results(session_id);
            CREATE INDEX IF NOT EXISTS idx_step_results_result ON step_results(result_id);
            CREATE INDEX IF NOT EXISTS idx_cases_session ON test_cases(session_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
        """)
        conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    # ==================== 查询 / 更新 ====================

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行 SELECT 查询，返回字典列表"""
        conn = self._get_conn()
        try:
            cur = conn.execute(query, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {query[:80]}... {e}")
            raise

    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        conn = self._get_conn()
        try:
            cur = conn.execute(query, params or ())
            conn.commit()
            return cur.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"Update failed: {query[:80]}... {e}")
            raise

    def execute_many(self, query: str, params_list: List[tuple]):
        """批量执行"""
        conn = self._get_conn()
        try:
            conn.executemany(query, params_list)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Batch update failed: {query[:80]}... {e}")
            raise

    # ==================== 事务 ====================

    def begin_transaction(self):
        """开始事务"""
        self._get_conn().execute("BEGIN")

    def commit_transaction(self):
        """提交事务"""
        conn = self._get_conn()
        conn.commit()

    def rollback_transaction(self):
        """回滚事务"""
        conn = self._get_conn()
        conn.rollback()

    # ==================== 测试会话 CRUD ====================

    def save_session(self, session: TestSession):
        """保存或更新测试会话"""
        self.execute_update("""
            INSERT INTO test_sessions
                (session_id, name, description, status, config_file, config_json,
                 start_time, end_time, progress, current_case_id, current_step_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                status=excluded.status, progress=excluded.progress,
                end_time=excluded.end_time, error_message=excluded.error_message,
                current_case_id=excluded.current_case_id,
                current_step_id=excluded.current_step_id,
                updated_at=datetime('now','localtime')
        """, (
            session.session_id, session.name, session.description,
            session.status.value, session.config_file,
            json.dumps(session.config.__dict__ if session.config else {}, default=str),
            session.start_time.isoformat() if session.start_time else None,
            session.end_time.isoformat() if session.end_time else None,
            session.progress, session.current_case_id, session.current_step_id,
            session.error_message,
        ))

    def load_session(self, session_id: str) -> Optional[TestSession]:
        """加载测试会话"""
        rows = self.execute_query(
            "SELECT * FROM test_sessions WHERE session_id = ?", (session_id,)
        )
        if not rows:
            return None
        row = rows[0]
        session = TestSession(
            session_id=row["session_id"],
            name=row["name"],
            description=row["description"],
            status=SessionStatus(row["status"]),
            config_file=row["config_file"],
            progress=row["progress"],
            current_case_id=row["current_case_id"],
            current_step_id=row["current_step_id"],
            error_message=row["error_message"],
        )
        if row.get("start_time"):
            session.start_time = datetime.fromisoformat(row["start_time"])
        if row.get("end_time"):
            session.end_time = datetime.fromisoformat(row["end_time"])
        return session

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出最近会话"""
        return self.execute_query("""
            SELECT * FROM test_sessions
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))

    def delete_session(self, session_id: str):
        """删除会话及关联数据"""
        self.execute_update("DELETE FROM step_results WHERE result_id IN (SELECT result_id FROM test_results WHERE session_id = ?)", (session_id,))
        self.execute_update("DELETE FROM test_results WHERE session_id = ?", (session_id,))
        self.execute_update("DELETE FROM test_cases WHERE session_id = ?", (session_id,))
        self.execute_update("DELETE FROM test_sessions WHERE session_id = ?", (session_id,))

    # ==================== 测试结果 CRUD ====================

    def save_test_result(self, result: TestResult):
        """保存测试结果"""
        self.execute_update("""
            INSERT INTO test_results
                (result_id, session_id, case_id, case_name, status,
                 start_time, end_time, actual_result, error_message, log_path, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(result_id) DO UPDATE SET
                status=excluded.status, end_time=excluded.end_time,
                actual_result=excluded.actual_result, error_message=excluded.error_message,
                log_path=excluded.log_path
        """, (
            result.result_id, result.session_id, result.case_id, result.case_name,
            result.status.value,
            result.start_time.isoformat() if result.start_time else None,
            result.end_time.isoformat() if result.end_time else None,
            result.actual_result, result.error_message,
            result.log_path, result.device_id,
        ))

    def save_step_result(self, step_result: StepResult):
        """保存步骤结果"""
        self.execute_update("""
            INSERT INTO step_results
                (step_result_id, result_id, step_id, step_name, status,
                 start_time, end_time, actual_result, error_message, log_output, retry_attempts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(step_result_id) DO UPDATE SET
                status=excluded.status, end_time=excluded.end_time,
                actual_result=excluded.actual_result, error_message=excluded.error_message,
                log_output=excluded.log_output, retry_attempts=excluded.retry_attempts
        """, (
            step_result.step_result_id, step_result.result_id,
            step_result.step_id, step_result.step_name, step_result.status.value,
            step_result.start_time.isoformat() if step_result.start_time else None,
            step_result.end_time.isoformat() if step_result.end_time else None,
            step_result.actual_result, step_result.error_message,
            step_result.log_output, step_result.retry_attempts,
        ))

    def get_test_result(self, case_id: str, session_id: str) -> Optional[TestResult]:
        """获取指定用例的测试结果"""
        rows = self.execute_query(
            "SELECT * FROM test_results WHERE case_id = ? AND session_id = ?",
            (case_id, session_id)
        )
        if not rows:
            return None
        return self._row_to_test_result(rows[0])

    def get_session_results(self, session_id: str) -> List[TestResult]:
        """获取会话的所有测试结果"""
        rows = self.execute_query(
            "SELECT * FROM test_results WHERE session_id = ? ORDER BY start_time",
            (session_id,)
        )
        return [self._row_to_test_result(r) for r in rows]

    def get_step_results(self, result_id: str) -> List[StepResult]:
        """获取测试结果的所有步骤结果"""
        rows = self.execute_query(
            "SELECT * FROM step_results WHERE result_id = ? ORDER BY start_time",
            (result_id,)
        )
        return [self._row_to_step_result(r) for r in rows]

    def _row_to_test_result(self, row: dict) -> TestResult:
        tr = TestResult(
            result_id=row["result_id"],
            session_id=row["session_id"],
            case_id=row["case_id"],
            case_name=row["case_name"],
            status=ResultStatus(row["status"]),
            actual_result=row["actual_result"],
            error_message=row["error_message"],
            log_path=row["log_path"],
            device_id=row["device_id"],
        )
        if row.get("start_time"):
            tr.start_time = datetime.fromisoformat(row["start_time"])
        if row.get("end_time"):
            tr.end_time = datetime.fromisoformat(row["end_time"])
        return tr

    def _row_to_step_result(self, row: dict) -> StepResult:
        sr = StepResult(
            step_result_id=row["step_result_id"],
            result_id=row["result_id"],
            step_id=row["step_id"],
            step_name=row["step_name"],
            status=ResultStatus(row["status"]),
            actual_result=row["actual_result"],
            error_message=row["error_message"],
            log_output=row["log_output"],
            retry_attempts=row["retry_attempts"],
        )
        if row.get("start_time"):
            sr.start_time = datetime.fromisoformat(row["start_time"])
        if row.get("end_time"):
            sr.end_time = datetime.fromisoformat(row["end_time"])
        return sr

    # ==================== 设备 CRUD ====================

    def save_device(self, device_id: str, device_type: str = "PHONE",
                    name: str = "", status: str = "AVAILABLE",
                    connection_info: dict = None, properties: dict = None):
        self.execute_update("""
            INSERT INTO devices (device_id, device_type, name, status, connection_info, properties)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                status=excluded.status, connection_info=excluded.connection_info,
                properties=excluded.properties, last_used=datetime('now','localtime')
        """, (
            device_id, device_type, name, status,
            json.dumps(connection_info or {}),
            json.dumps(properties or {}),
        ))

    def list_devices(self, status: str = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM devices"
        params = None
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY device_id"
        return self.execute_query(query, params)

    # ==================== 系统设置 ====================

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        rows = self.execute_query(
            "SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,)
        )
        return rows[0]["setting_value"] if rows else default

    def set_setting(self, key: str, value: str, description: str = ""):
        self.execute_update("""
            INSERT INTO system_settings (setting_key, setting_value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value=excluded.setting_value, updated_at=datetime('now','localtime')
        """, (key, value, description))

    # ==================== 审计日志 ====================

    def log_audit(self, action: str, resource_type: str = "",
                  resource_id: str = "", details: dict = None):
        import uuid
        self.execute_update(
            "INSERT INTO audit_logs (log_id, action, resource_type, resource_id, details) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex[:16], action, resource_type, resource_id, json.dumps(details or {}))
        )

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.execute_query(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
