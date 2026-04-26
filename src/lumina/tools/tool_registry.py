
"""
工具注册表（参考 Claude Code 工具系统设计）
统一管理工具的注册、发现和调用
"""

from typing import Dict, Any, List, Optional, Type
from .base_tool import BaseTool, ToolResult, ToolContext


class ToolRegistry:
    """
    工具注册表
    统一管理所有工具的注册和发现
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
    
    def register(self, tool_class: Type[BaseTool], config: Optional[Dict[str, Any]] = None) -> None:
        """
        注册工具
        Args:
            tool_class: 工具类
            config: 工具配置（可选）
        """
        # 创建工具实例
        tool = tool_class(config)
        
        # 注册到注册表
        self._tools[tool.name] = tool
        self._tool_classes[tool.name] = tool_class
        
        print(f"✅ Registered tool: {tool.display_name} (v{tool.version})")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取工具实例
        Args:
            name: 工具名称
        Returns:
            工具实例，如果不存在返回 None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, str]]:
        """
        列出所有已注册的工具
        Returns:
            工具信息列表
        """
        return [
            {
                "name": tool.name,
                "display_name": tool.display_name,
                "description": tool.description,
                "version": tool.version,
            }
            for tool in self._tools.values()
        ]
    
    def execute(self, name: str, context: ToolContext, **kwargs) -> ToolResult:
        """
        执行工具
        Args:
            name: 工具名称
            context: 执行上下文
            **kwargs: 工具参数
        Returns:
            工具执行结果
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {name}"
            )
        
        return tool.execute(context, **kwargs)
    
    def get_tool_descriptions(self) -> str:
        """
        获取所有工具的详细描述（用于 LLM 调用）
        Returns:
            所有工具的详细描述字符串
        """
        descriptions = []
        for tool in self._tools.values():
            descriptions.append(tool.get_description())
        
        return "\n\n".join(descriptions)
    
    def cleanup_all(self) -> None:
        """清理所有工具资源"""
        for tool in self._tools.values():
            tool.cleanup()
        self._tools.clear()
        self._tool_classes.clear()


# 全局注册表实例
_registry = ToolRegistry()


def register_tool(tool_class: Type[BaseTool], config: Optional[Dict[str, Any]] = None) -> None:
    """注册工具到全局注册表"""
    _registry.register(tool_class, config)


def get_tool(name: str) -> Optional[BaseTool]:
    """从全局注册表获取工具"""
    return _registry.get_tool(name)


def list_tools() -> List[Dict[str, str]]:
    """列出全局注册表中的所有工具"""
    return _registry.list_tools()


def execute_tool(name: str, context: ToolContext, **kwargs) -> ToolResult:
    """在全局注册表中执行工具"""
    return _registry.execute(name, context, **kwargs)


def get_all_tool_descriptions() -> str:
    """获取全局注册表中所有工具的详细描述"""
    return _registry.get_tool_descriptions()


def cleanup_all_tools() -> None:
    """清理全局注册表中的所有工具"""
    _registry.cleanup_all()
