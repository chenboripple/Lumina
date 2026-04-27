"""
Error Handler - 错误处理增强模块
支持优雅降级、重试机制、错误分类
"""

import logging
import traceback
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
from dataclasses import dataclass, field
from functools import wraps


class ErrorSeverity(Enum):
    """错误严重程度"""
    INFO = "info"           # 信息性，无需处理
    WARNING = "warning"     # 警告，可继续
    ERROR = "error"         # 错误，需要处理
    CRITICAL = "critical"    # 严重错误，终止流程


@dataclass
class ErrorRecord:
    """错误记录"""
    exception: Exception
    severity: ErrorSeverity
    context: str = ""
    fallback_value: Any = None
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    traceback_str: str = ""
    
    def __post_init__(self):
        if not self.traceback_str:
            self.traceback_str = traceback.format_exc()


class ErrorHandler:
    """
    错误处理器
    
    支持：
    1. 错误分类和严重程度判断
    2. 优雅降级（fallback）
    3. 自动重试
    4. 错误日志记录
    5. 错误统计
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("lumina")
        self.errors: List[ErrorRecord] = []
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # 错误处理策略映射
        self._fallbacks: Dict[type, Callable] = {}
        self._severity_map: Dict[type, ErrorSeverity] = {
            FileNotFoundError: ErrorSeverity.WARNING,
            PermissionError: ErrorSeverity.ERROR,
            ConnectionError: ErrorSeverity.ERROR,
            TimeoutError: ErrorSeverity.WARNING,
            ValueError: ErrorSeverity.ERROR,
            KeyError: ErrorSeverity.ERROR,
            ImportError: ErrorSeverity.CRITICAL,
        }
    
    def register_fallback(self, exception_type: type, fallback: Callable):
        """注册错误降级策略"""
        self._fallbacks[exception_type] = fallback
    
    def set_severity(self, exception_type: type, severity: ErrorSeverity):
        """设置错误严重程度"""
        self._severity_map[exception_type] = severity
    
    def handle_error(
        self,
        exception: Exception,
        severity: Optional[ErrorSeverity] = None,
        context: str = "",
        fallback: Any = None,
        raise_on_critical: bool = True
    ) -> Any:
        """
        处理错误
        
        Args:
            exception: 异常对象
            severity: 严重程度（自动检测如果未提供）
            context: 错误上下文
            fallback: 降级值
            raise_on_critical: 严重错误是否抛出
            
        Returns:
            fallback 值或 None
        """
        # 自动检测严重程度
        if severity is None:
            severity = self._detect_severity(exception)
        
        # 记录错误
        record = ErrorRecord(
            exception=exception,
            severity=severity,
            context=context,
            fallback_value=fallback
        )
        self.errors.append(record)
        
        # 记录日志
        log_message = f"[{severity.value.upper()}] {context}: {str(exception)}"
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # 严重错误抛出
        if severity == ErrorSeverity.CRITICAL and raise_on_critical:
            raise exception
        
        # 尝试使用注册的降级策略
        fallback_type = type(exception)
        if fallback_type in self._fallbacks:
            try:
                return self._fallbacks[fallback_type](exception)
            except Exception as e:
                self.logger.error(f"Fallback failed: {e}")
        
        return fallback
    
    def with_retry(
        self,
        operation: Callable,
        max_retries: Optional[int] = None,
        delay: Optional[float] = None,
        fallback: Any = None,
        retryable_exceptions: tuple = (ConnectionError, TimeoutError)
    ) -> Any:
        """
        带重试的操作执行
        
        Args:
            operation: 要执行的操作
            max_retries: 最大重试次数
            delay: 重试延迟（秒）
            fallback: 最终失败时的降级值
            retryable_exceptions: 可重试的异常类型
            
        Returns:
            操作结果或 fallback 值
        """
        max_retries = max_retries or self.max_retries
        delay = delay or self.retry_delay
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return operation()
            except retryable_exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    self.logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    import time
                    time.sleep(delay)
                else:
                    self.logger.error(f"Operation failed after {max_retries + 1} attempts: {e}")
        
        # 所有重试失败
        return self.handle_error(
            last_exception,
            severity=ErrorSeverity.ERROR,
            fallback=fallback
        )
    
    def _detect_severity(self, exception: Exception) -> ErrorSeverity:
        """自动检测错误严重程度"""
        exception_type = type(exception)
        
        # 精确匹配
        if exception_type in self._severity_map:
            return self._severity_map[exception_type]
        
        # 继承链匹配
        for exc_type, severity in self._severity_map.items():
            if isinstance(exception, exc_type):
                return severity
        
        # 默认
        return ErrorSeverity.ERROR
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        severity_counts = {}
        for record in self.errors:
            severity = record.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_errors": len(self.errors),
            "severity_counts": severity_counts,
            "has_critical": any(
                r.severity == ErrorSeverity.CRITICAL for r in self.errors
            ),
            "recent_errors": [
                {
                    "type": type(r.exception).__name__,
                    "message": str(r.exception),
                    "severity": r.severity.value,
                    "context": r.context
                }
                for r in self.errors[-5:]  # 最近5个
            ]
        }
    
    def clear_errors(self):
        """清除错误记录"""
        self.errors.clear()


def safe_execute(
    fallback: Any = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    context: str = ""
):
    """
    装饰器：安全执行函数
    
    用法：
        @safe_execute(fallback=[])
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return handler.handle_error(
                    e,
                    severity=severity,
                    context=context or f"Function {func.__name__}",
                    fallback=fallback
                )
        return wrapper
    return decorator


class GracefulDegradation:
    """
    优雅降级上下文管理器
    
    用法：
        with GracefulDegradation(fallback=[]) as gd:
            result = risky_operation()
    """
    
    def __init__(
        self,
        fallback: Any = None,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        context: str = "",
        handler: Optional[ErrorHandler] = None
    ):
        self.fallback = fallback
        self.severity = severity
        self.context = context
        self.handler = handler or ErrorHandler()
        self.result = fallback
        self.error = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.error = exc_val
            self.result = self.handler.handle_error(
                exc_val,
                severity=self.severity,
                context=self.context,
                fallback=self.fallback,
                raise_on_critical=False
            )
            return True  # 抑制异常
        return False
