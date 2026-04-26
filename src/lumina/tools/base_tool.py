
"""
工具基类（参考 Claude Code 工具系统设计）
实现统一的工具生命周期管理
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class ToolContext:
    """工具执行上下文"""
    session_id: str
    user_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


class BaseTool(ABC):
    """
    工具基类
    所有工具必须继承此类并实现抽象方法
    """
    
    # 工具元数据（子类必须重写）
    name: str = "base_tool"
    display_name: str = "Base Tool"
    description: str = "Base tool class"
    version: str = "1.0.0"
    author: str = "Lumina Team"
    
    # 工具配置（子类可以重写默认值）
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化工具
        Args:
            config: 工具配置，会覆盖 default_config
        """
        self.config = {**self.default_config, **(config or {})}
        self._validate_config()
        self._initialize()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """
        验证配置是否正确
        子类必须实现此方法，配置无效时抛出异常
        """
        pass
    
    def _initialize(self) -> None:
        """
        初始化工具（可选实现）
        子类可以在这里做一些初始化工作
        """
        pass
    
    @abstractmethod
    def execute(self, context: ToolContext, **kwargs) -> ToolResult:
        """
        执行工具
        Args:
            context: 执行上下文
            **kwargs: 工具参数
        Returns:
            工具执行结果
        """
        pass
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        获取工具参数的 JSON Schema
        Returns:
            参数的 JSON Schema 定义
        """
        pass
    
    def get_description(self) -> str:
        """
        获取工具描述（用于 LLM 调用）
        Returns:
            工具的详细描述
        """
        schema = self.get_parameters_schema()
        params_desc = "\n".join([
            f"- {name}: {prop.get('description', 'No description')}"
            for name, prop in schema.get('properties', {}).items()
        ])
        
        return f"""{self.display_name} (v{self.version})

{self.description}

Parameters:
{params_desc}
"""
    
    def cleanup(self) -> None:
        """
        清理资源（可选实现）
        工具不再使用时调用此方法
        """
        pass
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """with 语句退出时自动清理"""
        self.cleanup()
