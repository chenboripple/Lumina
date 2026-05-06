"""
Lumina 日志系统
统一的日志配置，支持不同输出级别，性能监控
"""

import logging
import time
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, cast

# 类型变量，用于装饰器类型注解
F = TypeVar('F', bound=Callable[..., Any])

# 全局日志实例
_logger: Optional[logging.Logger] = None

# 性能统计
_performance_stats: dict[str, list[float]] = {}


def get_logger(name: str = "lumina") -> logging.Logger:
    """
    获取配置好的 logger 实例

    Args:
        name: logger 名称

    Returns:
        配置好的 logger
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if logger.handlers:
        _logger = logger
        return logger

    # 控制台输出格式
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 尝试添加文件 handler（如果配置目录存在）
    try:
        log_dir = Path.home() / ".lumina" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 按日期命名日志文件
        log_file = log_dir / f"{time.strftime('%Y-%m-%d')}.log"
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        logger.debug(f"Logging to file: {log_file}")
    except Exception:
        # 如果文件日志创建失败，仍然可以用控制台
        pass

    _logger = logger
    return logger


def set_log_level(level: str) -> None:
    """
    设置日志级别

    Args:
        level: 日志级别 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    logger = get_logger()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    logger.setLevel(level_map.get(level.upper(), logging.INFO))


def timed(func: F) -> F:
    """
    性能监控装饰器，记录函数执行时间

    Args:
        func: 要装饰的函数

    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = get_logger()
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start_time

            # 记录性能统计
            func_name = f"{func.__module__}.{func.__qualname__}"
            if func_name not in _performance_stats:
                _performance_stats[func_name] = []
            _performance_stats[func_name].append(duration)

            # 仅记录慢操作或 DEBUG 级别时记录所有
            if duration > 1.0:
                logger.warning(f"{func_name} took {duration:.2f}s (slow)")
            elif logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"{func_name} took {duration:.2f}s")

            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"{func.__qualname__} failed after {duration:.2f}s: {e}")
            raise

    return cast(F, wrapper)


def get_performance_stats() -> dict[str, dict[str, float]]:
    """
    获取性能统计信息

    Returns:
        包含平均耗时、调用次数、总耗时的统计信息
    """
    stats = {}
    for func_name, durations in _performance_stats.items():
        stats[func_name] = {
            "count": len(durations),
            "total": sum(durations),
            "avg": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
        }
    return stats


def reset_performance_stats() -> None:
    """重置性能统计"""
    global _performance_stats
    _performance_stats = {}


# 便捷函数，兼容旧的 _log_llm 函数
def log_info(message: str, **kwargs: Any) -> None:
    """记录 INFO 级别日志"""
    get_logger().info(message, **kwargs)


def log_warning(message: str, **kwargs: Any) -> None:
    """记录 WARNING 级别日志"""
    get_logger().warning(message, **kwargs)


def log_error(message: str, **kwargs: Any) -> None:
    """记录 ERROR 级别日志"""
    get_logger().error(message, **kwargs)


def log_debug(message: str, **kwargs: Any) -> None:
    """记录 DEBUG 级别日志"""
    get_logger().debug(message, **kwargs)


# 友好的错误提示和恢复建议
_ERROR_RECOVERY = {
    "chromadb": {
        "missing": {
            "message": "ChromaDB 向量库未安装",
            "recovery": "运行: pip install 'lumina[vector]'",
        },
        "old_version": {
            "message": "ChromaDB 版本可能不兼容",
            "recovery": "更新到新版本: pip install --upgrade 'chromadb>=1.0.0'",
        },
    },
    "openai": {
        "missing": {
            "message": "OpenAI 包未安装",
            "recovery": "运行: pip install openai",
        },
        "invalid_api_key": {
            "message": "API Key 无效或未设置",
            "recovery": "设置环境变量或在 ~/.lumina/lumina.yaml 中配置",
        },
        "network_error": {
            "message": "网络连接失败",
            "recovery": "检查网络连接或配置代理",
        },
    },
    "ollama": {
        "not_running": {
            "message": "Ollama 服务未运行",
            "recovery": "运行: ollama serve 或检查 http://localhost:11434",
        },
        "model_not_found": {
            "message": "Ollama 模型不存在",
            "recovery": "运行: ollama pull <model-name>",
        },
    },
    "config": {
        "missing": {
            "message": "配置文件不存在",
            "recovery": "运行: lumina init 创建配置",
        },
        "invalid": {
            "message": "配置文件格式错误",
            "recovery": "检查 ~/.lumina/lumina.yaml 的 YAML 格式",
        },
    },
    "file": {
        "permission": {
            "message": "文件权限不足",
            "recovery": "检查文件/目录权限",
        },
        "not_found": {
            "message": "文件不存在",
            "recovery": "检查路径是否正确",
        },
    },
}


def get_error_recovery(error_type: str, error_subtype: str) -> dict[str, str]:
    """
    获取错误提示和恢复建议

    Args:
        error_type: 错误类型（如 "chromadb", "openai"）
        error_subtype: 错误子类型（如 "missing", "not_running"）

    Returns:
        包含 message 和 recovery 的字典
    """
    return _ERROR_RECOVERY.get(error_type, {}).get(error_subtype, {
        "message": f"未知错误: {error_type}/{error_subtype}",
        "recovery": "请查看日志了解详细信息",
    })


def log_with_recovery(
    error_type: str,
    error_subtype: str,
    details: Optional[str] = None,
    level: str = "ERROR",
) -> None:
    """
    记录错误并显示恢复建议

    Args:
        error_type: 错误类型
        error_subtype: 错误子类型
        details: 详细错误信息
        level: 日志级别
    """
    logger = get_logger()
    recovery = get_error_recovery(error_type, error_subtype)

    message = recovery["message"]
    if details:
        message = f"{message}: {details}"

    log_func = {
        "ERROR": logger.error,
        "WARNING": logger.warning,
        "INFO": logger.info,
        "DEBUG": logger.debug,
    }.get(level, logger.error)

    log_func(message)
    log_func(f"💡 恢复建议: {recovery['recovery']}")
