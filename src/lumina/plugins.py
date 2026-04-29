"""
Plugin system for Lumina output formats
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
import re


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

    SCENE_CALLOUT_MAP = {
        "meeting_notes": "info",
        "requirements": "question",
        "prd": "question",
        "design_doc": "example",
        "technical_doc": "abstract",
        "code_explanation": "abstract",
        "test_report": "warning",
        "ops_doc": "danger",
        "academic_paper": "quote",
        "book_notes": "quote",
        "task_list": "todo",
        "email": "tip",
        "chat_log": "note",
        "diary": "note",
        "knowledge_essay": "note",
        "generic_notes": "note",
    }
    
    def format(self, note: NoteData) -> str:
        scene = str(note.metadata.get("scene", "generic_notes"))
        related = self._clean_related(note.links)
        para = self._infer_para(note.metadata)
        hierarchical_tags = self._build_hierarchical_tags(note.tags, scene, para)

        lines = []

        # Frontmatter
        metadata = {
            "title": note.title,
            "status": self._derive_status(note.metadata),
            "para": para,
            "aliases": self._build_aliases(note),
            "up": self._build_up_links(note, para),
            "related": related,
            "tags": hierarchical_tags,
            "source": note.source,
            "lumina_score": note.metadata.get("score", 0),
            "lumina_scene": scene,
        }
        lines.append(self.frontmatter(metadata))

        callout_type = self.SCENE_CALLOUT_MAP.get(scene, "note")
        lines.append(self._build_callout(callout_type, "Context", f"status: {metadata['status']} | para: {para}"))

        # 内容
        lines.append(note.content)

        if note.metadata.get("summary"):
            lines.append(self._build_callout("abstract", "Summary", str(note.metadata.get("summary"))))

        # 关联主题
        if related:
            related_lines = [f"- {self.link_syntax(link)}" for link in related]
            lines.append(self._build_callout("tip", "Related", "\n".join(related_lines)))

        if hierarchical_tags:
            lines.append("\n## Tags\n")
            lines.append(self.tag_syntax(hierarchical_tags))

        return "\n".join(lines)
    
    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        import yaml
        return f"---\n{yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)}---\n"
    
    def link_syntax(self, target: str) -> str:
        return f"[[{target}]]"
    
    def tag_syntax(self, tags: List[str]) -> str:
        return " ".join(f"#{self._normalize_tag(tag)}" for tag in tags if tag)

    def _derive_status(self, metadata: Dict[str, Any]) -> str:
        score = float(metadata.get("score", 0) or 0)
        if score >= 0.85:
            return "stable"
        if score >= 0.65:
            return "draft"
        return "review"

    def _infer_para(self, metadata: Dict[str, Any]) -> str:
        para = str(metadata.get("para", "")).strip()
        if para:
            return para

        subdir = str(metadata.get("note_subdir", "")).strip("/")
        if not subdir:
            return "Resources"

        parts = [p for p in subdir.split("/") if p]
        for part in parts:
            lowered = part.lower()
            if lowered in {"projects", "areas", "resources", "archive", "archives"}:
                if lowered == "archives":
                    return "Archive"
                return part

        return parts[-1] if parts else "Resources"

    def _build_aliases(self, note: NoteData) -> List[str]:
        source_name = note.source.rsplit("/", 1)[-1].rsplit(".", 1)[0] if note.source else ""
        candidates = [note.title, source_name, str(note.metadata.get("alias", ""))]
        aliases = []
        seen = set()
        for item in candidates:
            value = str(item).strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                aliases.append(value)
        return aliases[:6]

    def _build_up_links(self, note: NoteData, para: str) -> List[str]:
        scene = str(note.metadata.get("scene", "")).strip()
        up = [f"{para}/Index"] if para else []
        if scene:
            up.append(f"Scene/{scene}")
        return up

    def _clean_related(self, links: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for link in links or []:
            value = str(link).strip().strip("[]")
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        return cleaned[:20]

    def _build_hierarchical_tags(self, tags: List[str], scene: str, para: str) -> List[str]:
        normalized = []
        seen = set()

        base_tags = [f"lumina/scene/{self._normalize_tag(scene)}", f"lumina/para/{self._normalize_tag(para)}"]
        for tag in base_tags + (tags or []):
            value = self._to_hierarchical_tag(tag)
            if value and value not in seen:
                seen.add(value)
                normalized.append(value)

        return normalized

    def _to_hierarchical_tag(self, tag: str) -> str:
        raw = self._normalize_tag(tag)
        if not raw:
            return ""
        if "/" in raw:
            return raw

        parts = [p for p in re.split(r"[_\-:\s]+", raw) if p]
        if len(parts) >= 2:
            return "/".join(parts[:3])

        return raw

    def _normalize_tag(self, tag: str) -> str:
        value = str(tag or "").strip().strip("#")
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"[^\w\-/\u4e00-\u9fff]", "", value)
        value = re.sub(r"/+", "/", value)
        return value.strip("/_")

    def _build_callout(self, callout_type: str, title: str, body: str) -> str:
        lines = [f"> [!{callout_type}] {title}"]
        for line in (body or "").splitlines() or [""]:
            lines.append(f"> {line}")
        return "\n".join(lines) + "\n"


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