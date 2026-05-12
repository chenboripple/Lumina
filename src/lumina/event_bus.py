"""
Event Bus - 事件总线
解耦模块间通信，支持发布/订阅模式
"""
import threading
import time
import weakref
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Set, Union
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps
import logging
import uuid

from .utils.logging import get_logger

logger = get_logger("lumina.event_bus")


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0   # 关键，立即处理
    HIGH = 1       # 高优先级
    NORMAL = 2     # 正常优先级（默认）
    LOW = 3        # 低优先级
    BACKGROUND = 4 # 后台处理，不影响主流程


@dataclass
class Event:
    """事件基类"""
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if "event_id" not in self.metadata:
            self.metadata["event_id"] = self.event_id
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建事件"""
        priority = EventPriority(data.get("priority", 2))
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", "unknown"),
            source=data.get("source"),
            priority=priority,
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


# ==================== 预定义事件类型 ====================

class EventTypes:
    """预定义事件类型常量"""
    # 文件处理事件
    FILE_SCANNED = "file.scanned"
    FILE_PROCESSED = "file.processed"
    FILE_SKIPPED = "file.skipped"
    FILE_FAILED = "file.failed"
    
    # 笔记生成事件
    NOTE_CREATED = "note.created"
    NOTE_UPDATED = "note.updated"
    NOTE_DELETED = "note.deleted"
    NOTE_APPENDED = "note.appended"
    
    # LLM 调用事件
    LLM_REQUEST_START = "llm.request.start"
    LLM_REQUEST_SUCCESS = "llm.request.success"
    LLM_REQUEST_ERROR = "llm.request.error"
    LLM_TOKEN_USAGE = "llm.token.usage"
    
    # 缓存事件
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"
    CACHE_SET = "cache.set"
    CACHE_INVALIDATED = "cache.invalidated"
    
    # 向量存储事件
    VECTOR_INDEXED = "vector.indexed"
    VECTOR_SEARCHED = "vector.searched"
    VECTOR_RELATED_FOUND = "vector.related.found"
    
    # 任务处理事件
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # 批处理事件
    BATCH_STARTED = "batch.started"
    BATCH_PROGRESS = "batch.progress"
    BATCH_COMPLETED = "batch.completed"
    BATCH_FAILED = "batch.failed"
    
    # 错误事件
    ERROR_OCCURRED = "error.occurred"
    ERROR_HANDLED = "error.handled"
    
    # 系统事件
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    CONFIG_CHANGED = "config.changed"
    
    # 健康检查事件
    HEALTH_CHECK_OK = "health.check.ok"
    HEALTH_CHECK_WARNING = "health.check.warning"
    HEALTH_CHECK_ERROR = "health.check.error"
    
    # 知识图谱事件
    ENTITY_EXTRACTED = "entity.extracted"
    RELATION_EXTRACTED = "relation.extracted"


# ==================== 便捷事件创建函数 ====================

def file_scanned_event(file_path: str, file_type: str, source: Optional[str] = None) -> Event:
    """创建文件扫描事件"""
    return Event(
        event_type=EventTypes.FILE_SCANNED,
        payload={"file_path": file_path, "file_type": file_type},
        source=source,
        priority=EventPriority.LOW,
    )


def file_processed_event(
    file_path: str,
    note_path: str,
    score: float,
    success: bool = True,
    source: Optional[str] = None,
) -> Event:
    """创建文件处理完成事件"""
    return Event(
        event_type=EventTypes.FILE_PROCESSED,
        payload={
            "file_path": file_path,
            "note_path": note_path,
            "score": score,
            "success": success,
        },
        source=source,
        priority=EventPriority.NORMAL,
    )


def file_failed_event(
    file_path: str,
    error: str,
    error_type: Optional[str] = None,
    source: Optional[str] = None,
) -> Event:
    """创建文件处理失败事件"""
    return Event(
        event_type=EventTypes.FILE_FAILED,
        payload={
            "file_path": file_path,
            "error": error,
            "error_type": error_type,
        },
        source=source,
        priority=EventPriority.HIGH,
    )


def note_created_event(
    note_path: str,
    title: str,
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
) -> Event:
    """创建笔记创建事件"""
    return Event(
        event_type=EventTypes.NOTE_CREATED,
        payload={
            "note_path": note_path,
            "title": title,
            "tags": tags or [],
        },
        source=source,
        priority=EventPriority.NORMAL,
    )


def llm_success_event(
    provider: str,
    model: str,
    tokens_used: int,
    duration: float,
    source: Optional[str] = None,
) -> Event:
    """创建 LLM 调用成功事件"""
    return Event(
        event_type=EventTypes.LLM_REQUEST_SUCCESS,
        payload={
            "provider": provider,
            "model": model,
            "tokens_used": tokens_used,
            "duration": duration,
        },
        source=source,
        priority=EventPriority.LOW,
    )


def llm_error_event(
    provider: str,
    model: str,
    error: str,
    error_type: Optional[str] = None,
    source: Optional[str] = None,
) -> Event:
    """创建 LLM 调用失败事件"""
    return Event(
        event_type=EventTypes.LLM_REQUEST_ERROR,
        payload={
            "provider": provider,
            "model": model,
            "error": error,
            "error_type": error_type,
        },
        source=source,
        priority=EventPriority.HIGH,
    )


def error_occurred_event(
    error_type: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> Event:
    """创建错误发生事件"""
    return Event(
        event_type=EventTypes.ERROR_OCCURRED,
        payload={
            "error_type": error_type,
            "message": message,
            "context": context or {},
        },
        source=source,
        priority=EventPriority.HIGH,
    )


def batch_progress_event(
    batch_id: str,
    current: int,
    total: int,
    percentage: float,
    source: Optional[str] = None,
) -> Event:
    """创建批处理进度事件"""
    return Event(
        event_type=EventTypes.BATCH_PROGRESS,
        payload={
            "batch_id": batch_id,
            "current": current,
            "total": total,
            "percentage": percentage,
        },
        source=source,
        priority=EventPriority.BACKGROUND,
    )


# ==================== 事件总线实现 ====================

class EventBus:
    """事件总线实现"""
    
    # 全局单例
    _instance: Optional["EventBus"] = None
    _instance_lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        # 订阅者管理
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._wildcard_subscribers: List[Callable] = []
        self._priority_subscribers: Dict[EventPriority, Dict[str, List[Callable]]] = defaultdict(lambda: defaultdict(list))
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 事件历史（用于调试）
        self._event_history: List[Event] = []
        self._max_history_size: int = 1000
        
        # 异步处理
        self._async_enabled: bool = True
        self._event_queue: List[Event] = []
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False
        
        # 弱引用支持（避免内存泄漏）
        self._weak_refs: Set[weakref.ref] = set()
        
        self._initialized = True
        logger.info("📡 EventBus initialized")
    
    @classmethod
    def get(cls) -> "EventBus":
        """获取全局单例"""
        return cls()
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], None],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型（或 "*" 订阅所有事件）
            handler: 事件处理函数
            priority: 优先级
        """
        with self._lock:
            if event_type == "*":
                if handler not in self._wildcard_subscribers:
                    self._wildcard_subscribers.append(handler)
                    logger.debug(f"📡 Subscribed to wildcard event")
            else:
                if handler not in self._subscribers[event_type]:
                    self._subscribers[event_type].append(handler)
                    logger.debug(f"📡 Subscribed to event: {event_type}")
            
            # 按优先级注册
            self._priority_subscribers[priority][event_type].append(handler)
    
    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[Event], None],
    ) -> None:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if event_type == "*":
                if handler in self._wildcard_subscribers:
                    self._wildcard_subscribers.remove(handler)
            else:
                if handler in self._subscribers.get(event_type, []):
                    self._subscribers[event_type].remove(handler)
            
            # 移除优先级订阅
            for priority in EventPriority:
                if handler in self._priority_subscribers[priority].get(event_type, []):
                    self._priority_subscribers[priority][event_type].remove(handler)
    
    def unsubscribe_all(self, handler: Callable) -> None:
        """取消某个 handler 的所有订阅"""
        with self._lock:
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
            
            for event_type in self._subscribers:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
            
            for priority in EventPriority:
                for event_type in self._priority_subscribers[priority]:
                    if handler in self._priority_subscribers[priority][event_type]:
                        self._priority_subscribers[priority][event_type].remove(handler)
    
    def publish(self, event: Event) -> None:
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        # 记录历史
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)
        
        logger.debug(f"📡 Publishing event: {event.event_type} (id={event.event_id})")
        
        # 获取所有订阅者
        handlers: List[Callable] = []
        
        # 通配符订阅者
        with self._lock:
            handlers.extend(self._wildcard_subscribers)
        
        # 特定事件订阅者
        with self._lock:
            handlers.extend(self._subscribers.get(event.event_type, []))
        
        # 按优先级订阅者
        for priority in EventPriority:
            if priority.value <= event.priority.value:
                with self._lock:
                    handlers.extend(self._priority_subscribers[priority].get(event.event_type, []))
        
        # 去重
        handlers = list(dict.fromkeys(handlers))
        
        # 调用处理函数
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"📡 Error in event handler for {event.event_type}: {e}", exc_info=True)
    
    def publish_async(self, event: Event) -> None:
        """
        异步发布事件（后台处理）
        
        Args:
            event: 事件对象
        """
        if not self._async_enabled:
            self.publish(event)
            return
        
        with self._lock:
            self._event_queue.append(event)
    
    def start_worker(self) -> None:
        """启动后台工作线程"""
        if self._running:
            return
        
        self._running = True
        
        def worker():
            logger.info("📡 EventBus worker started")
            while self._running:
                event_to_process: Optional[Event] = None
                
                # 获取事件
                with self._lock:
                    if self._event_queue:
                        # 按优先级排序
                        self._event_queue.sort(key=lambda e: e.priority.value)
                        event_to_process = self._event_queue.pop(0)
                
                if event_to_process:
                    self.publish(event_to_process)
                else:
                    time.sleep(0.01)
        
        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
    
    def stop_worker(self) -> None:
        """停止后台工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
    
    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """
        获取事件历史
        
        Args:
            event_type: 事件类型过滤
            limit: 返回数量限制
            
        Returns:
            事件列表
        """
        with self._lock:
            history = list(self._event_history)
        
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        return history[-limit:]
    
    def clear_history(self) -> None:
        """清除事件历史"""
        with self._lock:
            self._event_history.clear()
    
    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """
        获取订阅者数量
        
        Args:
            event_type: 事件类型（None 返回所有订阅者）
            
        Returns:
            订阅者数量
        """
        with self._lock:
            if event_type is None:
                total = len(self._wildcard_subscribers)
                for et in self._subscribers:
                    total += len(self._subscribers[et])
                return total
            else:
                return len(self._subscribers.get(event_type, []))
    
    def reset(self) -> None:
        """重置事件总线（用于测试）"""
        with self._lock:
            self._subscribers.clear()
            self._wildcard_subscribers.clear()
            self._priority_subscribers.clear()
            self._event_history.clear()
            self._event_queue.clear()
            logger.info("📡 EventBus reset")
    
    def get_status(self) -> Dict[str, Any]:
        """获取事件总线状态"""
        with self._lock:
            return {
                "subscribers": {
                    "wildcard": len(self._wildcard_subscribers),
                    "by_event_type": {
                        et: len(handlers)
                        for et, handlers in self._subscribers.items()
                    },
                },
                "history_size": len(self._event_history),
                "queue_size": len(self._event_queue),
                "running": self._running,
            }


# ==================== 便捷装饰器 ====================

def on(event_type: str, priority: EventPriority = EventPriority.NORMAL) -> Callable:
    """
    事件订阅装饰器
    
    Args:
        event_type: 事件类型
        priority: 优先级
        
    Returns:
        装饰器
    """
    def decorator(func: Callable) -> Callable:
        bus = EventBus.get()
        bus.subscribe(event_type, func, priority=priority)
        return func
    return decorator


def emit(event_type: str, priority: EventPriority = EventPriority.NORMAL) -> Callable:
    """
    事件发射装饰器：函数调用后自动发射事件
    
    Args:
        event_type: 事件类型
        priority: 优先级
        
    Returns:
        装饰器
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            bus = EventBus.get()
            try:
                result = func(*args, **kwargs)
                event = Event(
                    event_type=event_type,
                    payload={
                        "result": result,
                        "args": args,
                        "kwargs": kwargs,
                    },
                    priority=priority,
                )
                bus.publish(event)
                return result
            except Exception as e:
                error_event = Event(
                    event_type=EventTypes.ERROR_OCCURRED,
                    payload={
                        "error": str(e),
                        "function": func.__name__,
                        "args": args,
                        "kwargs": kwargs,
                    },
                    priority=EventPriority.HIGH,
                )
                bus.publish(error_event)
                raise
        return wrapper
    return decorator


# ==================== 便捷函数 ====================

def publish(event: Event) -> None:
    """发布事件（便捷函数）"""
    EventBus.get().publish(event)


def publish_async(event: Event) -> None:
    """异步发布事件（便捷函数）"""
    EventBus.get().publish_async(event)


def subscribe(event_type: str, handler: Callable[[Event], None], priority: EventPriority = EventPriority.NORMAL) -> None:
    """订阅事件（便捷函数）"""
    EventBus.get().subscribe(event_type, handler, priority)


def unsubscribe(event_type: str, handler: Callable[[Event], None]) -> None:
    """取消订阅（便捷函数）"""
    EventBus.get().unsubscribe(event_type, handler)


def start_worker() -> None:
    """启动后台工作线程（便捷函数）"""
    EventBus.get().start_worker()


def stop_worker() -> None:
    """停止后台工作线程（便捷函数）"""
    EventBus.get().stop_worker()


# ==================== 全局单例 ====================

_global_event_bus: Optional[EventBus] = None
_global_lock = threading.Lock()


def get_global_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        with _global_lock:
            if _global_event_bus is None:
                _global_event_bus = EventBus()
    return _global_event_bus


