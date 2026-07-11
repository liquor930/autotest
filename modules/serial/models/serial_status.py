from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SerialStatus(BaseModel):
    """串口连接状态"""
    connected: bool
    port: Optional[str] = None
    baud_rate: Optional[int] = None
    error: Optional[str] = None
    last_activity: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    def __str__(self) -> str:
        if self.connected:
            return f"已连接 - {self.port} @ {self.baud_rate}bps"
        else:
            return f"未连接" + (f" (错误: {self.error})" if self.error else "")

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "error": self.error,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received
        }
