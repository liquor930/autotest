"""事件总线 — 模块间松耦合通信"""

import logging
import threading
from typing import Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

from core.models import EventType

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件对象"""
    event_type: EventType
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


EventHandler = Callable[[Event], None]


class EventBus:
    """
    事件总线（观察者模式）
    
    用法:
        bus = EventBus()
        bus.subscribe(EventType.SESSION_STARTED, my_handler)
        bus.publish(Event(EventType.SESSION_STARTED, {"session_id": "abc"}))
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._handlers: Dict[EventType, List[EventHandler]] = {}
                cls._instance._handler_lock = threading.Lock()
            return cls._instance
    
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """订阅事件"""
        with self._handler_lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug(f"Handler subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """取消订阅"""
        with self._handler_lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h is not handler
                ]
    
    def publish(self, event: Event):
        """发布事件（同步调用所有订阅者）"""
        with self._handler_lock:
            handlers = list(self._handlers.get(event.event_type, []))
        
        logger.debug(f"Event published: {event.event_type.value}")
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type.value}: {e}")
    
    def publish_async(self, event: Event):
        """异步发布事件"""
        thread = threading.Thread(target=self.publish, args=(event,), daemon=True)
        thread.start()
    
    def clear(self):
        """清除所有订阅"""
        with self._handler_lock:
            self._handlers.clear()
