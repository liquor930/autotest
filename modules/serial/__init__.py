"""串口控制模块 - 用于通过USB串口与蓝牙设备通信"""

from .serial_manager import SerialManager
from .models.command_result import CommandResult
from .models.serial_status import SerialStatus

__version__ = "1.0.0"
__all__ = ["SerialManager", "CommandResult", "SerialStatus"]
