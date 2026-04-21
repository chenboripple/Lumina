"""
Plugin system for Lumina output formats
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class NoteData:
    """标准化笔记数据"""
    title: str
    content: str
    tags: List[str]
    links: List[str]
    source: str
    metadata: Dict[str, Any]


class BasePlugin(ABC):
    """
    输出插件基类
    
    所有笔记工具插件必须继承此类
    """
    
    # 插件标识
    name: str = "base"
    display_name: str = "Base Plugin"
    
    @abstractmethod
    def format(self, note: NoteData) -> str:
        """
        格式化笔记为特定工具的格式
        
        Args:
            note: 标准化笔记数据
            
        Returns:
            格式化后的字符串
        """
        pass
    
    @abstractmethod
    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        """
        生成前置元数据
        
        Args:
            metadata: 元数据字典
            
        Returns:
            前置元数据字符串
        """
        pass
    
    @abstractmethod
    def link_syntax(self, target: str) -> str:
        """
        转换链接语法
        
        Args:
            target: 链接目标
            
        Returns:
            特定格式的链接字符串
        """
        pass
    
    @abstractmethod
    def tag_syntax(self, tags: List[str]) -> str:
        """
        转换标签语法
        
        Args:
            tags: 标签列表
            
        Returns:
            特定格式的标签字符串
        """
        pass
    
    def post_process(self, content: str) -> str:
        """
        后处理钩子（可选）
        
        Args:
            content: 格式化后的内容
            
        Returns:
            处理后的内容
        """
        return content


class ObsidianPlugin(BasePlugin):
    """
    Obsidian 格式插件
    
    支持：
    - YAML Frontmatter
    - [[双向链接]]
    - #标签 语法
    """
    
    name = "obsidian"
    display_name = "Obsidian"
    
    def format(self, note: NoteData) -> str:
        lines = []
        
        # Frontmatter
        metadata = {
            "title": note.title,
            "tags": note.tags,
            "source": note.source,
            "lumina_score": note.metadata.get("score", 0),
        }
        lines.append(self.frontmatter(metadata))
        
        # 内容
        lines.append(note.content)
        
        # 关联主题
        if note.links:
            lines.append("\n## Related\n")
            for link in note.links:
                lines.append(f"- {self.link_syntax(link)}")
        
        return "\n".join(lines)
    
    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        import yaml
        return f"---\n{yaml.dump(metadata, allow_unicode=True)}---\n"
    
    def link_syntax(self, target: str) -> str:
        return f"[[{target}]]"
    
    def tag_syntax(self, tags: List[str]) -> str:
        return " ".join(f"#{tag}" for tag in tags)


class PlainMarkdownPlugin(BasePlugin):
    """
    纯 Markdown 插件
    
    标准 Markdown，无特殊语法
    """
    
    name = "plain"
    display_name = "Plain Markdown"
    
    def format(self, note: NoteData) -> str:
        lines = [
            f"# {note.title}",
            "",
            f"*Source: {note.source}*",
            "",
            note.content,
        ]
        
        if note.tags:
            lines.append(f"\nTags: {self.tag_syntax(note.tags)}")
        
        if note.links:
            lines.append("\n## Links\n")
            for link in note.links:
                lines.append(f"- {self.link_syntax(link)}")
        
        return "\n".join(lines)
    
    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        return ""
    
    def link_syntax(self, target: str) -> str:
        return f"[{target}]({target})"
    
    def tag_syntax(self, tags: List[str]) -> str:
        return ", ".join(tags)


class NotionPlugin(BasePlugin):
    """
    Notion 格式插件（计划中）
    
    目标：生成 Notion API 兼容的格式
    """
    
    name = "notion"
    display_name = "Notion"
    
    def format(self, note: NoteData) -> str:
        # TODO: 实现 Notion API 格式
        raise NotImplementedError("Notion plugin is planned but not implemented yet")
    
    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        return ""
    
    def link_syntax(self, target: str) -> str:
        return f"[{target}]({target})"
    
    def tag_syntax(self, tags: List[str]) -> str:
        return ", ".join(tags)


# 插件注册表
PLUGIN_REGISTRY = {
    "obsidian": ObsidianPlugin,
    "plain": PlainMarkdownPlugin,
    "notion": NotionPlugin,
}


def get_plugin(name: str) -> BasePlugin:
    """
    获取插件实例
    
    Args:
        name: 插件名称
        
    Returns:
        插件实例
        
    Raises:
        ValueError: 插件不存在
    """
    if name not in PLUGIN_REGISTRY:
        available = ", ".join(PLUGIN_REGISTRY.keys())
        raise ValueError(f"Unknown plugin: {name}. Available: {available}")
    
    return PLUGIN_REGISTRY[name]()


def list_plugins() -> Dict[str, str]:
    """
    列出所有可用插件
    
    Returns:
        插件名称到显示名称的映射
    """
    return {
        name: plugin.display_name 
        for name, plugin in PLUGIN_REGISTRY.items()
    }