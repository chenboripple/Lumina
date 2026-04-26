
"""
工具系统入口
初始化并注册所有工具
"""

from .base_tool import BaseTool, ToolResult, ToolContext
from .file_edit_tool import FileEditTool
from .tool_registry import (
    register_tool, get_tool, list_tools,
    execute_tool, get_all_tool_descriptions, cleanup_all_tools
)


def init_tools(config: dict = None) -> None:
    """
    初始化所有工具
    在系统启动时调用
    """
    # 注册文件编辑工具
    register_tool(FileEditTool, config)
    
    # 后续可以在这里注册更多工具
    # register_tool(OtherTool, config)
    
    print(f"🛠️  Tool system initialized with {len(list_tools())} tools")


__all__ = [
    # 基础类
    "BaseTool",
    "ToolResult", 
    "ToolContext",
    # 工具实现
    "FileEditTool",
    # 注册表
    "register_tool",
    "get_tool",
    "list_tools",
    "execute_tool",
    "get_all_tool_descriptions",
    "cleanup_all_tools",
    # 初始化
    "init_tools",
]
