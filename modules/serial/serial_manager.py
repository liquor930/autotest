import serial
import serial.tools.list_ports
import time
import threading
from typing import List, Optional, Callable
from datetime import datetime
from pathlib import Path
import json

try:
    from .models.command_result import CommandResult
    from .models.serial_status import SerialStatus
    from .utils.logger import LogCollector
except ImportError:
    from models.command_result import CommandResult
    from models.serial_status import SerialStatus
    from utils.logger import LogCollector


class SerialManager:
    """串口管理器 - 负责串口通信的核心类"""

    DEFAULT_BAUD_RATE = 115200
    DEFAULT_TIMEOUT = 5.0
    DEFAULT_READ_TIMEOUT = 2.0

    def __init__(self):
        self._serial: Optional[serial.Serial] = None
        self._port: Optional[str] = None
        self._baud_rate: int = self.DEFAULT_BAUD_RATE
        self._connected: bool = False
        self._lock = threading.Lock()
        self._log_collector: Optional[LogCollector] = None
        self._bytes_sent: int = 0
        self._bytes_received: int = 0
        self._last_activity: Optional[datetime] = None

    def connect(self, port: str, baud_rate: int = DEFAULT_BAUD_RATE) -> bool:
        """连接指定串口设备

        Args:
            port: 串口名称 (如 'COM3' 或 '/dev/ttyUSB0')
            baud_rate: 波特率，默认115200

        Returns:
            bool: 连接是否成功
        """
        try:
            with self._lock:
                if self._serial and self._serial.is_open:
                    self._serial.close()

                self._serial = serial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.DEFAULT_TIMEOUT,
                    write_timeout=self.DEFAULT_TIMEOUT
                )

                self._port = port
                self._baud_rate = baud_rate
                self._connected = True
                self._bytes_sent = 0
                self._bytes_received = 0
                self._last_activity = datetime.now()

                return True

        except serial.SerialException as e:
            self._connected = False
            self._port = None
            raise ConnectionError(f"无法连接到串口 {port}: {str(e)}")
        except Exception as e:
            self._connected = False
            self._port = None
            raise RuntimeError(f"连接串口时发生错误: {str(e)}")

    def disconnect(self) -> bool:
        """断开串口连接

        Returns:
            bool: 断开是否成功
        """
        with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._connected = False
            self._port = None
            return True

    def send_command(self, command: str, timeout: float = DEFAULT_READ_TIMEOUT) -> CommandResult:
        """发送AT指令并返回响应

        Args:
            command: AT指令字符串
            timeout: 读取超时时间（秒）

        Returns:
            CommandResult: 命令执行结果
        """
        start_time = time.time()
        timestamp = datetime.now()

        if not self._connected or not self._serial or not self._serial.is_open:
            return CommandResult(
                command=command,
                response="",
                success=False,
                timestamp=timestamp,
                execution_time_ms=0,
                error_message="串口未连接"
            )

        try:
            with self._lock:
                # 确保命令以换行符结尾
                if not command.endswith('\r\n') and not command.endswith('\n'):
                    command += '\r\n'

                # 发送命令
                bytes_written = self._serial.write(command.encode('utf-8'))
                self._serial.flush()
                self._bytes_sent += bytes_written

                # 收集日志
                if self._log_collector:
                    self._log_collector.log(f"TX: {command.strip()}")

                # 读取响应
                response = self._read_response(timeout)
                self._bytes_received += len(response.encode('utf-8'))
                self._last_activity = datetime.now()

                # 收集日志
                if self._log_collector:
                    self._log_collector.log(f"RX: {response.strip()}")

                execution_time = (time.time() - start_time) * 1000

                # 判断响应是否成功（通常OK表示成功，ERROR表示失败）
                success = "OK" in response or "ok" in response.lower()
                if "ERROR" in response or "error" in response.lower():
                    success = False

                return CommandResult(
                    command=command.strip(),
                    response=response.strip(),
                    success=success,
                    timestamp=timestamp,
                    execution_time_ms=execution_time
                )

        except serial.SerialTimeoutException:
            execution_time = (time.time() - start_time) * 1000
            return CommandResult(
                command=command.strip(),
                response="",
                success=False,
                timestamp=timestamp,
                execution_time_ms=execution_time,
                error_message="读取响应超时"
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return CommandResult(
                command=command.strip(),
                response="",
                success=False,
                timestamp=timestamp,
                execution_time_ms=execution_time,
                error_message=str(e)
            )

    def _read_response(self, timeout: float) -> str:
        """读取串口响应

        Args:
            timeout: 读取超时时间

        Returns:
            str: 响应字符串
        """
        self._serial.timeout = timeout
        response_lines = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._serial.in_waiting > 0:
                try:
                    line = self._serial.readline().decode('utf-8', errors='ignore')
                    response_lines.append(line)

                    # 如果收到OK或ERROR，通常表示响应结束
                    if line.strip() in ['OK', 'ERROR', 'FAIL']:
                        break
                except Exception:
                    pass
            else:
                time.sleep(0.01)

        return ''.join(response_lines)

    def execute_sequence(self, sequence_file: str, progress_callback: Optional[Callable] = None) -> List[CommandResult]:
        """执行预定义的AT指令序列

        Args:
            sequence_file: 指令序列JSON文件路径
            progress_callback: 进度回调函数，接收(当前步骤, 总步骤, CommandResult)

        Returns:
            List[CommandResult]: 所有命令的执行结果列表
        """
        results = []

        try:
            with open(sequence_file, 'r', encoding='utf-8') as f:
                sequence = json.load(f)

            commands = sequence.get('commands', [])
            total = len(commands)

            for i, cmd_item in enumerate(commands):
                if isinstance(cmd_item, str):
                    command = cmd_item
                    delay = 0
                else:
                    command = cmd_item.get('command', '')
                    delay = cmd_item.get('delay', 0)

                if not command:
                    continue

                result = self.send_command(command)
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, total, result)

                # 命令间延迟
                if delay > 0:
                    time.sleep(delay)

                # 如果命令失败且设置了stop_on_error，则停止执行
                if not result.success and sequence.get('stop_on_error', False):
                    break

        except FileNotFoundError:
            raise FileNotFoundError(f"找不到指令序列文件: {sequence_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"指令序列文件格式错误: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"执行指令序列时发生错误: {str(e)}")

        return results

    def start_logging(self, log_file: str) -> bool:
        """开始收集模块日志

        Args:
            log_file: 日志文件路径

        Returns:
            bool: 是否成功启动
        """
        try:
            self._log_collector = LogCollector(log_file)
            self._log_collector.start()
            return True
        except Exception as e:
            raise RuntimeError(f"启动日志收集失败: {str(e)}")

    def stop_logging(self) -> bool:
        """停止收集模块日志

        Returns:
            bool: 是否成功停止
        """
        if self._log_collector:
            self._log_collector.stop()
            self._log_collector = None
        return True

    def export_log(self, output_file: str) -> bool:
        """导出收集的日志

        Args:
            output_file: 输出文件路径

        Returns:
            bool: 导出是否成功
        """
        if self._log_collector:
            return self._log_collector.export(output_file)
        return False

    def get_status(self) -> SerialStatus:
        """获取串口连接状态

        Returns:
            SerialStatus: 当前串口状态
        """
        error = None
        if self._serial and not self._serial.is_open:
            error = "串口已关闭"

        return SerialStatus(
            connected=self._connected and self._serial is not None and self._serial.is_open,
            port=self._port,
            baud_rate=self._baud_rate,
            error=error,
            last_activity=self._last_activity,
            bytes_sent=self._bytes_sent,
            bytes_received=self._bytes_received
        )

    def list_available_ports(self) -> List[dict]:
        """列出可用的串口

        Returns:
            List[dict]: 可用串口信息列表
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
