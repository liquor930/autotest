"""资源管理器 — 设备注册、分配、释放"""

import threading
import logging
from datetime import datetime
from typing import List, Optional, Dict

from core.models import CoreDeviceInfo, DeviceType, DeviceStatus, EventType
from core.event_bus import EventBus, Event

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    资源管理器
    
    管理测试设备（手机、蓝牙设备）的注册、分配和释放。
    支持设备健康检查和资源竞争处理。
    """

    def __init__(self):
        self._devices: Dict[str, CoreDeviceInfo] = {}
        self._lock = threading.Lock()
        self._event_bus = EventBus()

    # ==================== 设备注册 / 注销 ====================

    def register_device(self, device: CoreDeviceInfo) -> bool:
        """注册设备"""
        with self._lock:
            if device.device_id in self._devices:
                logger.warning(f"设备 {device.device_id} 已注册，将覆盖")
            self._devices[device.device_id] = device
            self._event_bus.publish(Event(
                EventType.DEVICE_REGISTERED,
                {"device_id": device.device_id, "device_type": device.device_type.value}
            ))
            logger.info(f"设备已注册: {device.device_id} ({device.device_type.value})")
        return True

    def unregister_device(self, device_id: str) -> bool:
        """注销设备"""
        with self._lock:
            if device_id not in self._devices:
                logger.warning(f"设备 {device_id} 未注册")
                return False
            device = self._devices.pop(device_id)
            self._event_bus.publish(Event(
                EventType.DEVICE_UNREGISTERED,
                {"device_id": device_id}
            ))
            logger.info(f"设备已注销: {device_id}")
        return True

    # ==================== 设备分配 / 释放 ====================

    def allocate_device(self, device_type: str = None) -> Optional[CoreDeviceInfo]:
        """
        分配一个可用设备。
        返回设备并设置为 BUSY 状态；无可用时返回 None。
        """
        with self._lock:
            for device in self._devices.values():
                if device.status != DeviceStatus.AVAILABLE:
                    continue
                if device_type and device.device_type.value != device_type:
                    continue
                device.status = DeviceStatus.BUSY
                device.last_used = datetime.now()
                self._event_bus.publish(Event(
                    EventType.DEVICE_ALLOCATED,
                    {"device_id": device.device_id}
                ))
                logger.info(f"设备已分配: {device.device_id}")
                return device
        return None

    def allocate_specific_device(self, device_id: str) -> Optional[CoreDeviceInfo]:
        """分配指定设备"""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                logger.warning(f"设备 {device_id} 不存在")
                return None
            if device.status != DeviceStatus.AVAILABLE:
                logger.warning(f"设备 {device_id} 不可用，当前状态: {device.status.value}")
                return None
            device.status = DeviceStatus.BUSY
            device.last_used = datetime.now()
            self._event_bus.publish(Event(
                EventType.DEVICE_ALLOCATED,
                {"device_id": device_id}
            ))
            return device

    def release_device(self, device_id: str) -> bool:
        """释放设备"""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return False
            device.status = DeviceStatus.AVAILABLE
            self._event_bus.publish(Event(
                EventType.DEVICE_RELEASED,
                {"device_id": device_id}
            ))
            logger.info(f"设备已释放: {device_id}")
        return True

    # ==================== 查询 ====================

    def get_available_devices(self, device_type: str = None) -> List[CoreDeviceInfo]:
        """获取可用设备列表"""
        with self._lock:
            result = []
            for device in self._devices.values():
                if device.status != DeviceStatus.AVAILABLE:
                    continue
                if device_type and device.device_type.value != device_type:
                    continue
                result.append(device)
            return result

    def get_all_devices(self) -> List[CoreDeviceInfo]:
        """获取所有注册设备"""
        with self._lock:
            return list(self._devices.values())

    def get_device_status(self, device_id: str) -> Optional[DeviceStatus]:
        """获取设备状态"""
        with self._lock:
            device = self._devices.get(device_id)
            return device.status if device else None

    def get_device(self, device_id: str) -> Optional[CoreDeviceInfo]:
        """获取设备信息"""
        with self._lock:
            return self._devices.get(device_id)

    def device_count(self) -> Dict[str, int]:
        """获取各类设备数量统计"""
        with self._lock:
            total = len(self._devices)
            available = sum(1 for d in self._devices.values() if d.status == DeviceStatus.AVAILABLE)
            busy = sum(1 for d in self._devices.values() if d.status == DeviceStatus.BUSY)
            error = sum(1 for d in self._devices.values() if d.status == DeviceStatus.ERROR)
            return {"total": total, "available": available, "busy": busy, "error": error}

    # ==================== 健康检查 ====================

    def check_device_health(self, device_id: str) -> bool:
        """
        检查设备是否健康。
        子类可扩展此方法实现具体检测逻辑。
        """
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return False
            # 这里可添加 ping / ADB status 检查
            return device.status != DeviceStatus.ERROR

    def mark_device_error(self, device_id: str, error_message: str):
        """标记设备为错误状态"""
        with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.status = DeviceStatus.ERROR
                device.error_message = error_message
                self._event_bus.publish(Event(
                    EventType.DEVICE_ERROR,
                    {"device_id": device_id, "error": error_message}
                ))

    # ==================== 从 ADB / 串口注册设备 ====================

    def register_from_adb(self, device_id: str, ip: str = "", port: int = 5555,
                          model: str = "", version: str = ""):
        """从 ADB 设备信息注册手机设备"""
        device = CoreDeviceInfo(
            device_id=device_id,
            device_type=DeviceType.PHONE,
            connection_info={"ip": ip, "port": port},
            properties={"model": model, "android_version": version},
            name=model or device_id,
        )
        self.register_device(device)

    def register_serial_device(self, device_id: str, port: str, baud_rate: int = 115200,
                               name: str = ""):
        """注册串口连接的蓝牙设备"""
        device = CoreDeviceInfo(
            device_id=device_id,
            device_type=DeviceType.BLE_DEVICE,
            connection_info={"port": port, "baud_rate": baud_rate},
            name=name or device_id,
        )
        self.register_device(device)
