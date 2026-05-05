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
        status = self._derive_status(note.metadata)
        location_summary = self._build_location_summary(note.metadata, scene, para)

        lines = []

        # Frontmatter
        metadata = {
            "title": note.title,
            "status": status,
            "para": para,
            "aliases": self._build_aliases(note),
            "up": self._build_up_links(note, para),
            "related": related,
            "tags": hierarchical_tags,
            "source": note.source,
            "lumina_score": note.metadata.get("score", 0),
            "lumina_scene": scene,
            "lumina_note_subdir": str(note.metadata.get("note_subdir", "") or ""),
        }
        lines.append(self.frontmatter(metadata))

        callout_type = self.SCENE_CALLOUT_MAP.get(scene, "note")
        lines.append(self._build_callout(callout_type, "Context", f"status: {status} | scene: {scene} | para: {para}"))
        lines.append(self._build_callout("tip", "Organization", location_summary))

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

    def _build_location_summary(self, metadata: Dict[str, Any], scene: str, para: str) -> str:
        note_subdir = str(metadata.get("note_subdir", "") or "").strip("/")
        lines = []
        if note_subdir:
            lines.append(f"path: {note_subdir}")
        if scene:
            lines.append(f"scene: {scene}")
        if para:
            lines.append(f"para: {para}")

        parts = [part for part in note_subdir.split("/") if part]
        if parts:
            lines.append(f"levels: {' -> '.join(parts)}")

        confidence = metadata.get("confidence")
        if confidence not in (None, ""):
            lines.append(f"confidence: {confidence}")

        return "\n".join(lines) or "path: root"

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
        scene = str(note.metadata.get("scene", "")).strip()
        para = str(note.metadata.get("para", "")).strip()
        note_subdir = str(note.metadata.get("note_subdir", "") or "").strip("/")

        lines = [
            f"# {note.title}",
            "",
            f"*Source: {note.source}*",
            "",
        ]

        if note_subdir or scene or para:
            lines.extend([
                "## Organization",
                f"- Path: {note_subdir or 'root'}",
                f"- Scene: {scene or 'n/a'}",
                f"- PARA: {para or 'n/a'}",
                "",
            ])

        lines.append(note.content)
        
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
    Notion 格式插件

    生成 Notion 导入友好的 Markdown：
    - 使用 properties 表格替代 YAML Frontmatter
    - 使用标准 Markdown 链接
    - 适合直接导入 Notion
    """

    name = "notion"
    display_name = "Notion"

    def format(self, note: NoteData) -> str:
        scene = str(note.metadata.get("scene", "generic_notes"))
        related = self._clean_related(note.links)
        para = self._infer_para(note.metadata)
        hierarchical_tags = self._build_hierarchical_tags(note.tags, scene, para)
        status = self._derive_status(note.metadata)
        note_subdir = str(note.metadata.get("note_subdir", "") or "").strip("/")

        lines = []

        # 标题
        lines.append(f"# {note.title}")
        lines.append("")

        # Notion 风格的 Properties 表格
        prop_table = [
            "| Property | Value |",
            "|----------|-------|",
        ]
        prop_table.append(f"| Status | {status} |")
        prop_table.append(f"| PARA | {para} |")
        prop_table.append(f"| Scene | {scene} |")
        if note_subdir:
            prop_table.append(f"| Path | {note_subdir} |")
        prop_table.append(f"| Source | {note.source} |")
        prop_table.append(f"| Lumina Score | {note.metadata.get('score', 0) or 0} |")
        lines.extend(prop_table)
        lines.append("")

        # 上下文区块
        if scene or para or note_subdir:
            lines.append("## Context")
            lines.append("")
            if note_subdir:
                lines.append(f"- **Path**: {note_subdir}")
            if scene:
                lines.append(f"- **Scene**: {scene}")
            if para:
                lines.append(f"- **PARA**: {para}")
            if scene and para:
                lines.append(f"- **Type**: {scene} ({para})")
            lines.append("")

        # 内容
        lines.append(note.content)
        lines.append("")

        # 摘要
        if note.metadata.get("summary"):
            lines.append("## Summary")
            lines.append("")
            lines.append(f"> {note.metadata.get('summary')}")
            lines.append("")

        # 标签
        if hierarchical_tags:
            lines.append("## Tags")
            lines.append("")
            lines.append(self.tag_syntax(hierarchical_tags))
            lines.append("")

        # 关联
        if related:
            lines.append("## Related")
            lines.append("")
            for link in related:
                lines.append(f"- {self.link_syntax(link)}")
            lines.append("")

        return "\n".join(lines)

    def frontmatter(self, metadata: Dict[str, Any]) -> str:
        # Notion 不使用 YAML frontmatter
        return ""

    def link_syntax(self, target: str) -> str:
        # Notion 使用标准 Markdown 链接
        cleaned = target.strip("[]")
        return f"[{cleaned}]({cleaned})"

    def tag_syntax(self, tags: List[str]) -> str:
        # Notion 标签在 Markdown 中用逗号分隔
        return ", ".join(f"`{tag}`" for tag in tags if tag)

    def _derive_status(self, metadata: Dict[str, Any]) -> str:
        score = float(metadata.get("score", 0) or 0)
        if score >= 0.85:
            return "🟢 Stable"
        if score >= 0.65:
            return "🟡 Draft"
        return "🔴 Review"

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

        base_tags = [f"lumina/scene/{scene}", f"lumina/para/{para}"]
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