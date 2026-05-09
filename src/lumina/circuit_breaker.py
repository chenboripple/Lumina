"""
Circuit Breaker - 熔断器模式实现
防止 LLM API 故障时持续请求，提供降级策略
"""
import time
import threading
from enum import Enum
from typing import Dict, Any, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from functools import wraps
from collections import deque

from .exceptions import (
    LuminaError,
    CircuitBreakerError,
    CircuitOpenError,
    CircuitHalfOpenError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMAPIError,
    ErrorContext,
)
from .utils.logging import get_logger

logger = get_logger("lumina.circuit_breaker")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态，请求通过
    OPEN = "open"          # 打开状态，请求快速失败
    HALF_OPEN = "half_open"  # 半开状态，尝试少量请求


@dataclass
class CircuitMetrics:
    """熔断器统计指标"""
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    total_recovery_attempts: int = 0
    
    def reset(self) -> None:
        """重置统计"""
        self.total_requests = 0
        self.success_count = 0
        self.failure_count = 0
        self.timeout_count = 0
        self.rate_limit_count = 0
        self.consecutive_failures = 0
    
    def record_success(self) -> None:
        """记录成功"""
        self.total_requests += 1
        self.success_count += 1
        self.last_success_time = time.time()
        self.consecutive_failures = 0
    
    def record_failure(self, error_type: Optional[str] = None) -> None:
        """记录失败"""
        self.total_requests += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.consecutive_failures += 1
        
        if error_type == "timeout":
            self.timeout_count += 1
        elif error_type == "rate_limit":
            self.rate_limit_count += 1
    
    def record_recovery_attempt(self) -> None:
        """记录恢复尝试"""
        self.total_recovery_attempts += 1
    
    def failure_rate(self, window_seconds: int = 60) -> float:
        """计算最近一段时间的失败率"""
        if self.total_requests == 0:
            return 0.0
        # 简化实现，真实场景可以用滑动窗口
        return self.failure_count / max(self.total_requests, 1)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "rate_limit_count": self.rate_limit_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "consecutive_failures": self.consecutive_failures,
            "total_recovery_attempts": self.total_recovery_attempts,
            "failure_rate": self.failure_rate(),
        }


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    # 阈值配置
    failure_threshold: int = 5  # 连续失败次数阈值
    timeout_threshold: int = 3  # 连续超时次数阈值
    rate_limit_threshold: int = 2  # 连续限流次数阈值
    
    # 时间配置
    open_timeout_seconds: float = 30.0  # 打开状态持续时间
    half_open_timeout_seconds: float = 10.0  # 半开状态超时时间
    metrics_window_seconds: int = 60  # 指标统计窗口
    
    # 半开状态配置
    half_open_max_requests: int = 1  # 半开状态最多允许的请求数
    half_open_min_successes: int = 1  # 半开状态需要的成功次数
    
    # 降级配置
    enable_fallback: bool = True  # 是否启用降级策略
    fallback_timeout_seconds: float = 5.0  # 降级策略超时时间
    
    # 需要触发熔断的异常类型
    failure_exceptions: tuple = field(default_factory=lambda: (
        LLMAPIError,
        LLMTimeoutError,
        LLMRateLimitError,
        ConnectionError,
        TimeoutError,
    ))
    
    # 需要立即熔断的异常类型
    critical_exceptions: tuple = field(default_factory=lambda: (
        LLMAuthenticationError,
    ))


class CircuitBreaker:
    """熔断器实现"""
    
    # 全局熔断器注册表
    _registry: Dict[str, "CircuitBreaker"] = {}
    _registry_lock = threading.Lock()
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        
        # 状态管理
        self._state = CircuitState.CLOSED
        self._state_lock = threading.RLock()
        self._open_time: Optional[float] = None
        self._half_open_requests: int = 0
        self._half_open_successes: int = 0
        
        # 指标统计
        self.metrics = CircuitMetrics()
        
        # 降级策略缓存
        self._fallback_cache: Dict[str, Any] = {}
        self._fallback_cache_lock = threading.Lock()
        
        # 注册全局熔断器
        with self._registry_lock:
            self._registry[name] = self
        
        logger.info(f"🔌 CircuitBreaker '{name}' initialized in {self._state.value} state")
    
    @classmethod
    def get(cls, name: str) -> Optional["CircuitBreaker"]:
        """获取已注册的熔断器"""
        with cls._registry_lock:
            return cls._registry.get(name)
    
    @classmethod
    def get_or_create(cls, name: str, config: Optional[CircuitBreakerConfig] = None) -> "CircuitBreaker":
        """获取或创建熔断器"""
        with cls._registry_lock:
            if name in cls._registry:
                return cls._registry[name]
            cb = cls(name, config=config)
            return cb
    
    @classmethod
    def list_all(cls) -> Dict[str, Dict[str, Any]]:
        """列出所有熔断器状态"""
        with cls._registry_lock:
            return {
                name: {
                    "state": cb._state.value,
                    "metrics": cb.metrics.to_dict(),
                    "config": {
                        "failure_threshold": cb.config.failure_threshold,
                        "open_timeout": cb.config.open_timeout_seconds,
                    }
                }
                for name, cb in cls._registry.items()
            }
    
    @property
    def state(self) -> CircuitState:
        """当前状态"""
        with self._state_lock:
            return self._state
    
    def _transition_to_open(self) -> None:
        """转换到打开状态"""
        with self._state_lock:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                self._open_time = time.time()
                logger.warning(f"🔌 CircuitBreaker '{self.name}' transitioned to OPEN state after {self.metrics.consecutive_failures} failures")
    
    def _transition_to_half_open(self) -> None:
        """转换到半开状态"""
        with self._state_lock:
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN
                self._half_open_requests = 0
                self._half_open_successes = 0
                self.metrics.record_recovery_attempt()
                logger.info(f"🔌 CircuitBreaker '{self.name}' transitioned to HALF_OPEN state")
    
    def _transition_to_closed(self) -> None:
        """转换到关闭状态"""
        with self._state_lock:
            if self._state != CircuitState.CLOSED:
                self._state = CircuitState.CLOSED
                self._open_time = None
                self.metrics.reset()
                logger.info(f"🔌 CircuitBreaker '{self.name}' transitioned to CLOSED state")
    
    def _should_open(self) -> bool:
        """判断是否应该打开熔断器"""
        # 检查连续失败次数
        if self.metrics.consecutive_failures >= self.config.failure_threshold:
            return True
        
        # 检查是否有严重异常
        # (通过 record_failure 时的异常类型判断)
        
        return False
    
    def _should_try_close(self) -> bool:
        """判断是否应该尝试关闭熔断器（进入半开状态）"""
        if self._state != CircuitState.OPEN:
            return False
        
        if self._open_time is None:
            return False
        
        elapsed = time.time() - self._open_time
        return elapsed >= self.config.open_timeout_seconds
    
    def _check_state(self) -> None:
        """检查并更新状态"""
        with self._state_lock:
            if self._state == CircuitState.OPEN:
                if self._should_try_close():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_requests = 0
                    self._half_open_successes = 0
                    self.metrics.record_recovery_attempt()
                    logger.info(f"🔌 CircuitBreaker '{self.name}' transitioned to HALF_OPEN state")
    
    def _execute_fallback(self, func: Callable, *args, **kwargs) -> Any:
        """执行降级策略"""
        if not self.config.enable_fallback or not self.fallback:
            return None
        
        # 尝试使用缓存的降级结果（可选）
        cache_key = self._get_fallback_cache_key(func, args, kwargs)
        if cache_key in self._fallback_cache:
            cached = self._fallback_cache[cache_key]
            if time.time() - cached.get("time", 0) < self.config.fallback_timeout_seconds:
                logger.debug(f"🔌 CircuitBreaker '{self.name}' using cached fallback result")
                return cached.get("value")
        
        try:
            result = self.fallback(*args, **kwargs)
            with self._fallback_cache_lock:
                self._fallback_cache[cache_key] = {
                    "value": result,
                    "time": time.time(),
                }
            logger.info(f"🔌 CircuitBreaker '{self.name}' fallback executed successfully")
            return result
        except Exception as e:
            logger.error(f"🔌 CircuitBreaker '{self.name}' fallback failed: {e}")
            return None
    
    def _get_fallback_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """生成降级策略缓存 key"""
        import hashlib
        import json
        key_parts = [
            getattr(func, "__name__", str(func)),
            str(args),
            json.dumps(kwargs, sort_keys=True, default=str),
        ]
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()
    
    def _is_failure_exception(self, exc: Exception) -> bool:
        """判断是否是需要计数的失败异常"""
        return isinstance(exc, self.config.failure_exceptions)
    
    def _is_critical_exception(self, exc: Exception) -> bool:
        """判断是否是需要立即熔断的严重异常"""
        return isinstance(exc, self.config.critical_exceptions)
    
    def _get_error_type(self, exc: Exception) -> Optional[str]:
        """获取异常类型"""
        if isinstance(exc, LLMTimeoutError):
            return "timeout"
        if isinstance(exc, LLMRateLimitError):
            return "rate_limit"
        return None
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数，应用熔断逻辑
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitOpenError: 当熔断器打开时
            Exception: 执行过程中的异常
        """
        # 检查并更新状态
        self._check_state()
        
        with self._state_lock:
            current_state = self._state
            
            # 打开状态：快速失败或使用降级
            if current_state == CircuitState.OPEN:
                if self.fallback and self.config.enable_fallback:
                    logger.warning(f"🔌 CircuitBreaker '{self.name}' is OPEN, using fallback")
                    return self._execute_fallback(func, *args, **kwargs)
                remaining = max(0, self.config.open_timeout_seconds - (time.time() - self._open_time))
                raise circuit_open_error(
                    f"Circuit breaker '{self.name}' is OPEN. Try again in {remaining:.1f}s",
                    remaining_seconds=remaining,
                    operation=getattr(func, "__name__", str(func)),
                )
            
            # 半开状态：限制请求数
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_requests >= self.config.half_open_max_requests:
                    raise CircuitHalfOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN, max requests reached"
                    )
                self._half_open_requests += 1
        
        # 执行函数
        try:
            result = func(*args, **kwargs)
            
            # 成功
            with self._state_lock:
                self.metrics.record_success()
                
                if self._state == CircuitState.HALF_OPEN:
                    self._half_open_successes += 1
                    if self._half_open_successes >= self.config.half_open_min_successes:
                        self._transition_to_closed()
            
            return result
            
        except Exception as e:
            # 失败
            with self._state_lock:
                error_type = self._get_error_type(e)
                self.metrics.record_failure(error_type)
                
                # 严重异常立即熔断
                if self._is_critical_exception(e):
                    self._transition_to_open()
                
                # 普通异常计数
                elif self._is_failure_exception(e):
                    if self._state == CircuitState.HALF_OPEN:
                        # 半开状态失败，立即回到打开状态
                        self._transition_to_open()
                    elif self._should_open():
                        self._transition_to_open()
            
            # 尝试使用降级策略
            if self.fallback and self.config.enable_fallback:
                logger.warning(f"🔌 CircuitBreaker '{self.name}' caught {type(e).__name__}, using fallback")
                return self._execute_fallback(func, *args, **kwargs)
            
            # 重新抛出异常
            raise
    
    def __call__(self, func: Callable) -> Callable:
        """装饰器用法"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.execute(func, *args, **kwargs)
        return wrapper
    
    def reset(self) -> None:
        """重置熔断器"""
        with self._state_lock:
            self._state = CircuitState.CLOSED
            self._open_time = None
            self._half_open_requests = 0
            self._half_open_successes = 0
            self.metrics.reset()
            self._fallback_cache.clear()
        logger.info(f"🔌 CircuitBreaker '{self.name}' reset to CLOSED state")
    
    def force_open(self) -> None:
        """强制打开熔断器（用于测试）"""
        self._transition_to_open()
    
    def force_close(self) -> None:
        """强制关闭熔断器（用于测试）"""
        self._transition_to_closed()
    
    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        with self._state_lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "open_time": self._open_time,
                "metrics": self.metrics.to_dict(),
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "timeout_threshold": self.config.timeout_threshold,
                    "rate_limit_threshold": self.config.rate_limit_threshold,
                    "open_timeout_seconds": self.config.open_timeout_seconds,
                    "half_open_max_requests": self.config.half_open_max_requests,
                },
            }


# ==================== 便捷装饰器函数 ====================

def circuit_break(
    name: Optional[str] = None,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable] = None,
) -> Callable:
    """
    熔断器装饰器
    
    Args:
        name: 熔断器名称（默认使用函数名）
        config: 熔断器配置
        fallback: 降级策略函数
        
    Returns:
        装饰器
    """
    def decorator(func: Callable) -> Callable:
        cb_name = name or f"{func.__module__}.{func.__name__}"
        cb = CircuitBreaker.get_or_create(cb_name, config=config)
        if fallback:
            cb.fallback = fallback
        return cb(func)
    return decorator


def llm_circuit_break(
    provider: str = "default",
    model: Optional[str] = None,
    fallback: Optional[Callable] = None,
) -> Callable:
    """
    LLM 专用熔断器装饰器
    
    Args:
        provider: LLM 提供商名称
        model: 模型名称
        fallback: 降级策略函数
        
    Returns:
        装饰器
    """
    cb_name = f"llm.{provider}"
    if model:
        cb_name += f".{model}"
    
    config = CircuitBreakerConfig(
        failure_threshold=5,
        timeout_threshold=3,
        rate_limit_threshold=2,
        open_timeout_seconds=60.0,
        half_open_timeout_seconds=30.0,
        enable_fallback=True,
    )
    
    return circuit_break(name=cb_name, config=config, fallback=fallback)

