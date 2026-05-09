"""
Health Check - 健康检查模块
支持系统健康状态监控、组件状态检查
"""
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import sys

from .utils.logging import get_logger

logger = get_logger("lumina.health")


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"    # 健康
    WARNING = "warning"    # 警告
    UNHEALTHY = "unhealthy"  # 不健康
    UNKNOWN = "unknown"    # 未知


@dataclass
class ComponentCheck:
    """组件检查结果"""
    name: str
    status: HealthStatus
    message: str = ""
    response_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_check_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "response_time": self.response_time,
            "metadata": self.metadata,
            "last_check_time": self.last_check_time,
        }


@dataclass
class HealthReport:
    """健康检查报告"""
    overall_status: HealthStatus
    components: List[ComponentCheck]
    timestamp: float = field(default_factory=time.time)
    uptime: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.overall_status.value,
            "timestamp": self.timestamp,
            "uptime": self.uptime,
            "components": [c.to_dict() for c in self.components],
            "metadata": self.metadata,
        }


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, ComponentCheck] = {}
        self._start_time: float = time.time()
        self._lock = threading.RLock()
        
        # 注册默认检查
        self._register_default_checks()
    
    def _register_default_checks(self):
        """注册默认检查"""
        # 系统检查
        self.register_check("system.disk", self._check_disk_space)
        self.register_check("system.memory", self._check_memory)
        self.register_check("system.time", self._check_system_time)
        
        # Python 环境检查
        self.register_check("python.version", self._check_python_version)
        self.register_check("python.dependencies", self._check_dependencies)
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """注册检查函数"""
        with self._lock:
            self._checks[name] = check_func
            logger.debug(f"🏥 Registered health check: {name}")
    
    def unregister_check(self, name: str) -> None:
        """取消注册检查函数"""
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                logger.debug(f"🏥 Unregistered health check: {name}")
    
    def check_all(self) -> HealthReport:
        """执行所有检查"""
        components = []
        
        with self._lock:
            checks = list(self._checks.items())
        
        for name, check_func in checks:
            try:
                start_time = time.time()
                result = check_func()
                response_time = time.time() - start_time
                
                if isinstance(result, ComponentCheck):
                    component = result
                else:
                    component = ComponentCheck(
                        name=name,
                        status=HealthStatus.HEALTHY,
                        message="OK",
                        response_time=response_time,
                    )
                
                component.response_time = response_time
                
            except Exception as e:
                component = ComponentCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(e)}",
                )
                logger.error(f"🏥 Health check {name} failed: {e}")
            
            self._last_results[name] = component
            components.append(component)
        
        # 计算整体状态
        overall_status = self._compute_overall_status(components)
        
        # 计算运行时间
        uptime = time.time() - self._start_time
        
        return HealthReport(
            overall_status=overall_status,
            components=components,
            uptime=uptime,
        )
    
    def check_single(self, name: str) -> Optional[ComponentCheck]:
        """执行单个检查"""
        with self._lock:
            check_func = self._checks.get(name)
        
        if check_func is None:
            return None
        
        try:
            start_time = time.time()
            result = check_func()
            response_time = time.time() - start_time
            
            if isinstance(result, ComponentCheck):
                component = result
            else:
                component = ComponentCheck(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    response_time=response_time,
                )
            
            self._last_results[name] = component
            return component
            
        except Exception as e:
            component = ComponentCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
            )
            self._last_results[name] = component
            return component
    
    def get_last_result(self, name: str) -> Optional[ComponentCheck]:
        """获取上次检查结果"""
        return self._last_results.get(name)
    
    def get_all_last_results(self) -> Dict[str, ComponentCheck]:
        """获取所有上次检查结果"""
        return dict(self._last_results)
    
    def _compute_overall_status(self, components: List[ComponentCheck]) -> HealthStatus:
        """计算整体健康状态"""
        statuses = [c.status for c in components]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    # ==================== 默认检查实现 ====================
    
    def _check_disk_space(self) -> ComponentCheck:
        """检查磁盘空间"""
        try:
            import shutil
            usage = shutil.disk_usage("/")
            total_gb = usage.total / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            used_percent = (usage.used / usage.total) * 100
            
            if free_gb < 1.0:
                return ComponentCheck(
                    name="system.disk",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low disk space: {free_gb:.1f}GB free",
                    metadata={
                        "total_gb": total_gb,
                        "free_gb": free_gb,
                        "used_percent": used_percent,
                    }
                )
            elif free_gb < 5.0:
                return ComponentCheck(
                    name="system.disk",
                    status=HealthStatus.WARNING,
                    message=f"Warning: {free_gb:.1f}GB free",
                    metadata={
                        "total_gb": total_gb,
                        "free_gb": free_gb,
                        "used_percent": used_percent,
                    }
                )
            
            return ComponentCheck(
                name="system.disk",
                status=HealthStatus.HEALTHY,
                message=f"{free_gb:.1f}GB free ({100 - used_percent:.1f}%)",
                metadata={
                    "total_gb": total_gb,
                    "free_gb": free_gb,
                    "used_percent": used_percent,
                }
            )
        except Exception as e:
            return ComponentCheck(
                name="system.disk",
                status=HealthStatus.WARNING,
                message=f"Could not check disk space: {e}",
            )
    
    def _check_memory(self) -> ComponentCheck:
        """检查内存"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024 ** 3)
            available_gb = memory.available / (1024 ** 3)
            used_percent = memory.percent
            
            if available_gb < 0.5:
                return ComponentCheck(
                    name="system.memory",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low memory: {available_gb:.1f}GB available",
                    metadata={
                        "total_gb": total_gb,
                        "available_gb": available_gb,
                        "used_percent": used_percent,
                    }
                )
            elif available_gb < 1.0:
                return ComponentCheck(
                    name="system.memory",
                    status=HealthStatus.WARNING,
                    message=f"Warning: {available_gb:.1f}GB available",
                    metadata={
                        "total_gb": total_gb,
                        "available_gb": available_gb,
                        "used_percent": used_percent,
                    }
                )
            
            return ComponentCheck(
                name="system.memory",
                status=HealthStatus.HEALTHY,
                message=f"{available_gb:.1f}GB available ({100 - used_percent:.1f}% free)",
                metadata={
                    "total_gb": total_gb,
                    "available_gb": available_gb,
                    "used_percent": used_percent,
                }
            )
        except ImportError:
            return ComponentCheck(
                name="system.memory",
                status=HealthStatus.WARNING,
                message="psutil not available, skipping memory check",
            )
        except Exception as e:
            return ComponentCheck(
                name="system.memory",
                status=HealthStatus.WARNING,
                message=f"Could not check memory: {e}",
            )
    
    def _check_system_time(self) -> ComponentCheck:
        """检查系统时间"""
        try:
            now = time.time()
            dt = datetime.fromtimestamp(now)
            
            return ComponentCheck(
                name="system.time",
                status=HealthStatus.HEALTHY,
                message=f"System time: {dt.isoformat()}",
                metadata={
                    "timestamp": now,
                    "datetime": dt.isoformat(),
                }
            )
        except Exception as e:
            return ComponentCheck(
                name="system.time",
                status=HealthStatus.WARNING,
                message=f"Could not check system time: {e}",
            )
    
    def _check_python_version(self) -> ComponentCheck:
        """检查 Python 版本"""
        try:
            version_info = sys.version_info
            version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
            
            if (version_info.major, version_info.minor) < (3, 8):
                return ComponentCheck(
                    name="python.version",
                    status=HealthStatus.WARNING,
                    message=f"Python version {version_str} is old, consider upgrading",
                    metadata={"version": version_str}
                )
            
            return ComponentCheck(
                name="python.version",
                status=HealthStatus.HEALTHY,
                message=f"Python {version_str}",
                metadata={"version": version_str}
            )
        except Exception as e:
            return ComponentCheck(
                name="python.version",
                status=HealthStatus.WARNING,
                message=f"Could not check Python version: {e}",
            )
    
    def _check_dependencies(self) -> ComponentCheck:
        """检查依赖"""
        try:
            # 检查关键依赖是否可用
            dependencies = {
                "openai": "OpenAI client",
                "aiohttp": "Async HTTP client",
                "yaml": "YAML parser",
                "chromadb": "Chroma vector DB",
            }
            
            missing = []
            available = []
            
            for module, name in dependencies.items():
                try:
                    __import__(module)
                    available.append(name)
                except ImportError:
                    missing.append(name)
            
            if missing:
                return ComponentCheck(
                    name="python.dependencies",
                    status=HealthStatus.WARNING,
                    message=f"Optional dependencies missing: {', '.join(missing)}",
                    metadata={
                        "available": available,
                        "missing": missing,
                    }
                )
            
            return ComponentCheck(
                name="python.dependencies",
                status=HealthStatus.HEALTHY,
                message=f"All dependencies available: {', '.join(available)}",
                metadata={"available": available}
            )
        except Exception as e:
            return ComponentCheck(
                name="python.dependencies",
                status=HealthStatus.WARNING,
                message=f"Could not check dependencies: {e}",
            )
    
    def register_llm_check(self, config: Dict[str, Any]) -> None:
        """注册 LLM 检查"""
        from .llm import get_llm_provider
        
        def _check_llm() -> ComponentCheck:
            try:
                provider = get_llm_provider(config)
                # 简单检查，不实际调用 API
                return ComponentCheck(
                    name=f"llm.{config.get('provider', 'unknown')}",
                    status=HealthStatus.HEALTHY,
                    message=f"LLM provider {config.get('provider', 'unknown')} configured",
                    metadata={"provider": config.get('provider')}
                )
            except Exception as e:
                return ComponentCheck(
                    name=f"llm.{config.get('provider', 'unknown')}",
                    status=HealthStatus.WARNING,
                    message=f"LLM check failed: {e}",
                )
        
        self.register_check(f"llm.{config.get('provider', 'unknown')}", _check_llm)
    
    def register_vector_store_check(self, vector_store) -> None:
        """注册向量存储检查"""
        def _check_vector_store() -> ComponentCheck:
            try:
                # 尝试进行简单搜索
                results = vector_store.search("test", n_results=1)
                return ComponentCheck(
                    name="vector_store",
                    status=HealthStatus.HEALTHY,
                    message=f"Vector store OK, collection: {vector_store._collection.name}",
                    metadata={"ok": True}
                )
            except Exception as e:
                return ComponentCheck(
                    name="vector_store",
                    status=HealthStatus.WARNING,
                    message=f"Vector store check failed: {e}",
                )
        
        self.register_check("vector_store", _check_vector_store)


# ==================== 便捷函数 ====================

_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def get_health_report() -> HealthReport:
    """获取健康报告"""
    return get_health_checker().check_all()


def get_health_status() -> Dict[str, Any]:
    """获取健康状态（字典格式）"""
    return get_health_report().to_dict()
