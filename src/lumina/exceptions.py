"""
Lumina 自定义异常体系
定义统一的异常层次，便于错误处理和降级策略
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ErrorContext:
    """错误上下文信息"""
    file_path: Optional[str] = None
    operation: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    retries: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LuminaError(Exception):
    """Lumina 基础异常类"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, *args)
        self.message = message
        self.context = context or ErrorContext()
        self.timestamp: float = __import__('time').time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于序列化"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "timestamp": self.timestamp,
            "context": {
                "file_path": self.context.file_path,
                "operation": self.context.operation,
                "provider": self.context.provider,
                "model": self.context.model,
                "retries": self.context.retries,
                "metadata": self.context.metadata,
            }
        }


# ==================== LLM 相关异常 ====================

class LLMError(LuminaError):
    """LLM 相关异常基类"""
    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制异常"""
    
    def __init__(self, message: str, retry_after: int = 60, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """LLM 调用超时异常"""
    
    def __init__(self, message: str, timeout_seconds: int = 60, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.timeout_seconds = timeout_seconds


class LLMAuthenticationError(LLMError):
    """LLM 认证异常"""
    pass


class LLMAPIError(LLMError):
    """LLM API 返回错误"""
    
    def __init__(self, message: str, status_code: int = 500, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.status_code = status_code


class LLMResponseError(LLMError):
    """LLM 响应格式错误"""
    pass


class LLMCostLimitError(LLMError):
    """LLM 成本超出限制"""
    pass


# ==================== 文件处理相关异常 ====================

class FileProcessingError(LuminaError):
    """文件处理异常基类"""
    pass


class FileReadError(FileProcessingError):
    """文件读取错误"""
    pass


class FileWriteError(FileProcessingError):
    """文件写入错误"""
    pass


class FilePermissionError(FileProcessingError):
    """文件权限错误"""
    pass


class FileTooLargeError(FileProcessingError):
    """文件过大"""
    
    def __init__(self, message: str, file_size: int, max_size: int, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.file_size = file_size
        self.max_size = max_size


class UnsupportedFileTypeError(FileProcessingError):
    """不支持的文件类型"""
    
    def __init__(self, message: str, file_type: str, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.file_type = file_type


# ==================== 内容相关异常 ====================

class ContentFilterError(LuminaError):
    """内容过滤异常"""
    pass


class SensitiveContentError(ContentFilterError):
    """检测到敏感内容"""
    pass


class LowValueContentError(ContentFilterError):
    """低价值内容，不值得处理"""
    pass


# ==================== 配置相关异常 ====================

class ConfigError(LuminaError):
    """配置异常基类"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    pass


class ConfigMissingError(ConfigError):
    """配置缺失"""
    pass


# ==================== 缓存相关异常 ====================

class CacheError(LuminaError):
    """缓存异常基类"""
    pass


class CacheReadError(CacheError):
    """缓存读取错误"""
    pass


class CacheWriteError(CacheError):
    """缓存写入错误"""
    pass


# ==================== 向量存储相关异常 ====================

class VectorStoreError(LuminaError):
    """向量存储异常基类"""
    pass


class VectorIndexError(VectorStoreError):
    """向量索引错误"""
    pass


class VectorSearchError(VectorStoreError):
    """向量搜索错误"""
    pass


# ==================== 历史记录相关异常 ====================

class HistoryError(LuminaError):
    """历史记录异常基类"""
    pass


class HistoryReadError(HistoryError):
    """历史记录读取错误"""
    pass


class HistoryWriteError(HistoryError):
    """历史记录写入错误"""
    pass


# ==================== 任务相关异常 ====================

class TaskError(LuminaError):
    """任务异常基类"""
    pass


class TaskQueueError(TaskError):
    """任务队列错误"""
    pass


class TaskTimeoutError(TaskError):
    """任务超时"""
    pass


class TaskCancelledError(TaskError):
    """任务被取消"""
    pass


# ==================== Circuit Breaker 相关异常 ====================

class CircuitBreakerError(LuminaError):
    """熔断器异常基类"""
    pass


class CircuitOpenError(CircuitBreakerError):
    """熔断器打开状态"""
    
    def __init__(self, message: str, remaining_seconds: float = 60, context: Optional[ErrorContext] = None, *args):
        super().__init__(message, context, *args)
        self.remaining_seconds = remaining_seconds


class CircuitHalfOpenError(CircuitBreakerError):
    """熔断器半开状态"""
    pass


# ==================== 便捷工厂函数 ====================

def rate_limit_error(message: str, retry_after: int = 60, **kwargs) -> LLMRateLimitError:
    """快速创建速率限制异常"""
    return LLMRateLimitError(
        message=message,
        retry_after=retry_after,
        context=ErrorContext(**kwargs)
    )


def timeout_error(message: str, timeout_seconds: int = 60, **kwargs) -> LLMTimeoutError:
    """快速创建超时异常"""
    return LLMTimeoutError(
        message=message,
        timeout_seconds=timeout_seconds,
        context=ErrorContext(**kwargs)
    )


def auth_error(message: str, **kwargs) -> LLMAuthenticationError:
    """快速创建认证异常"""
    return LLMAuthenticationError(message, context=ErrorContext(**kwargs))


def api_error(message: str, status_code: int = 500, **kwargs) -> LLMAPIError:
    """快速创建 API 异常"""
    return LLMAPIError(message, status_code=status_code, context=ErrorContext(**kwargs))


def file_read_error(message: str, **kwargs) -> FileReadError:
    """快速创建文件读取异常"""
    return FileReadError(message, context=ErrorContext(**kwargs))


def file_write_error(message: str, **kwargs) -> FileWriteError:
    """快速创建文件写入异常"""
    return FileWriteError(message, context=ErrorContext(**kwargs))


def sensitive_content_error(message: str, **kwargs) -> SensitiveContentError:
    """快速创建敏感内容异常"""
    return SensitiveContentError(message, context=ErrorContext(**kwargs))


def config_error(message: str, **kwargs) -> ConfigValidationError:
    """快速创建配置验证异常"""
    return ConfigValidationError(message, context=ErrorContext(**kwargs))


def missing_config_error(message: str, **kwargs) -> ConfigMissingError:
    """快速创建配置缺失异常"""
    return ConfigMissingError(message, context=ErrorContext(**kwargs))


def circuit_open_error(message: str, remaining_seconds: float = 60, **kwargs) -> CircuitOpenError:
    """快速创建熔断器打开异常"""
    return CircuitOpenError(
        message=message,
        remaining_seconds=remaining_seconds,
        context=ErrorContext(**kwargs)
    )

