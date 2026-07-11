import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from queue import Queue


class LogCollector:
    """日志收集器 - 用于实时收集和存储串口通信日志"""

    def __init__(self, log_file: str, max_buffer_size: int = 10000):
        """初始化日志收集器

        Args:
            log_file: 日志文件路径
            max_buffer_size: 最大缓冲区大小
        """
        self._log_file = Path(log_file)
        self._max_buffer_size = max_buffer_size
        self._buffer: List[str] = []
        self._queue: Queue = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 确保日志目录存在
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """启动日志收集"""
        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        """停止日志收集"""
        if not self._running:
            return True

        self._running = False
        self._queue.put(None)  # 发送停止信号

        if self._thread:
            self._thread.join(timeout=2.0)

        # 刷新剩余日志
        self._flush_buffer()
        return True

    def log(self, message: str) -> bool:
        """添加日志条目

        Args:
            message: 日志消息

        Returns:
            bool: 是否成功添加
        """
        if not self._running:
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self._queue.put(log_entry)
        return True

    def _worker(self):
        """后台工作线程"""
        while self._running:
            try:
                log_entry = self._queue.get(timeout=0.1)
                if log_entry is None:  # 停止信号
                    break

                with self._lock:
                    self._buffer.append(log_entry)

                    # 缓冲区满时刷新到文件
                    if len(self._buffer) >= self._max_buffer_size:
                        self._flush_buffer()

            except Exception:
                continue

    def _flush_buffer(self):
        """将缓冲区内容刷新到文件"""
        if not self._buffer:
            return

        try:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                for entry in self._buffer:
                    f.write(entry + '\n')
            self._buffer.clear()
        except Exception as e:
            print(f"写入日志文件失败: {e}")

    def export(self, output_file: str) -> bool:
        """导出日志到指定文件

        Args:
            output_file: 输出文件路径

        Returns:
            bool: 导出是否成功
        """
        try:
            # 先刷新缓冲区
            self._flush_buffer()

            # 复制日志文件
            import shutil
            shutil.copy2(self._log_file, output_file)
            return True
        except Exception as e:
            print(f"导出日志失败: {e}")
            return False

    def get_logs(self, count: int = 100) -> List[str]:
        """获取最近的日志条目

        Args:
            count: 获取的条目数量

        Returns:
            List[str]: 日志条目列表
        """
        with self._lock:
            return self._buffer[-count:] if self._buffer else []

    def clear(self) -> bool:
        """清空日志缓冲区和文件"""
        with self._lock:
            self._buffer.clear()
            try:
                if self._log_file.exists():
                    self._log_file.write_text('')
                return True
            except Exception as e:
                print(f"清空日志失败: {e}")
                return False
