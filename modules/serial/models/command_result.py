from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CommandResult(BaseModel):
    """AT指令执行结果"""
    command: str
    response: str
    success: bool
    timestamp: datetime = datetime.now()
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def __str__(self) -> str:
        status = "成功" if self.success else "失败"
        return f"[{status}] {self.command} -> {self.response[:50] if self.response else '无响应'}"

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "response": self.response,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message
        }
