"""
Plugins 模块单元测试
测试 Obsidian、Notion、Plain Markdown 输出格式
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestNoteData:
    """NoteData 数据类测试"""

    def test_basic_creation(self):
        """测试基本创建"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Test Note",
            content="Test content",
            tags=[],
            links=[],
            source="test.md",
            metadata={"source": "test.md"}
        )

        assert note.title == "Test Note"
        assert note.content == "Test content"
        assert note.metadata["source"] == "test.md"

    def test_default_values(self):
        """测试必填字段"""
        from lumina.plugins import NoteData
        with pytest.raises(TypeError):
            NoteData(title="Test")


class TestObsidianPlugin:
    """Obsidian 格式插件测试"""

    @pytest.fixture
    def plugin(self):
        from lumina.plugins import ObsidianPlugin
        return ObsidianPlugin()

    def test_format_basic(self, plugin):
        """测试基本格式化"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Meeting Notes",
            content="## Agenda\n\n1. Review\n2. Plan",
            tags=["meeting", "team"],
            links=[],
            source="meeting.md",
            metadata={
                "source": "meeting.md",
                "date": "2026-05-05",
                "status": "completed",
            }
        )

        result = plugin.format(note)

        assert "---" in result  # YAML frontmatter
        assert "Meeting Notes" in result
        assert "## Agenda" in result
        assert "meeting" in result
        assert "team" in result

    def test_format_with_frontmatter(self, plugin):
        """测试包含 YAML frontmatter 的输出"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Test",
            content="Body",
            tags=[],
            links=[],
            source="test.md",
            metadata={
                "status": "draft",
                "para": "Projects",
                "tags": ["test"],
                "source": "test.md",
            }
        )

        result = plugin.format(note)

        # 检查 frontmatter
        assert "status: review" in result
        assert "para: Projects" in result
        assert "source: test.md" in result

    def test_format_with_links(self, plugin):
        """测试双向链接"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Main Note",
            content="See also [[Related Note]]",
            tags=[],
            links=["Related Note", "Another Note"],
            source="main.md",
            metadata={}
        )

        result = plugin.format(note)

        # 应该包含双向链接
        assert "[[Related Note]]" in result
        assert "[[Another Note]]" in result

    def test_plugin_name(self, plugin):
        """测试插件名称"""
        assert plugin.name == "obsidian"
        assert plugin.display_name == "Obsidian"

    def test_format_empty_metadata(self, plugin):
        """测试空元数据处理"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Simple",
            content="Content",
            tags=[],
            links=[],
            source="simple.md",
            metadata={}
        )

        result = plugin.format(note)
        assert "---" in result
        assert "Content" in result


class TestNotionPlugin:
    """Notion 格式插件测试"""

    @pytest.fixture
    def plugin(self):
        from lumina.plugins import NotionPlugin
        return NotionPlugin()

    def test_format_basic(self, plugin):
        """测试基本格式化"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Meeting Notes",
            content="## Agenda\n\n1. Review\n2. Plan",
            tags=["meeting", "team"],
            links=[],
            source="meeting.md",
            metadata={
                "source": "meeting.md",
                "status": "completed",
            }
        )

        result = plugin.format(note)

        assert "Meeting Notes" in result
        assert "## Agenda" in result

    def test_format_properties_table(self, plugin):
        """测试 Properties 表格格式"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Test",
            content="Body",
            tags=[],
            links=[],
            source="test.md",
            metadata={
                "status": "draft",
                "date": "2026-05-05",
                "source": "test.md",
            }
        )

        result = plugin.format(note)

        # Notion 使用 Properties 表格，不是 YAML
        assert "| Property | Value |" in result
        assert "Status" in result
        assert "Review" in result

    def test_format_standard_links(self, plugin):
        """测试标准 Markdown 链接"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Main Note",
            content="See also [Related Note](Related Note)",
            tags=[],
            links=["Related Note"],
            source="main.md",
            metadata={}
        )

        result = plugin.format(note)

        # 使用标准 Markdown 链接
        assert "[Related Note](" in result

    def test_plugin_name(self, plugin):
        """测试插件名称"""
        assert plugin.name == "notion"
        assert plugin.display_name == "Notion"

    def test_no_yaml_frontmatter(self, plugin):
        """确认没有 YAML frontmatter"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Test",
            content="Body",
            tags=[],
            links=[],
            source="test.md",
            metadata={"key": "value"}
        )

        result = plugin.format(note)

        # Notion 格式不使用 --- 分隔符
        lines = result.split('\n')
        assert "---" not in lines[:3]  # 开头不是 YAML


class TestPlainMarkdownPlugin:
    """Plain Markdown 格式插件测试"""

    @pytest.fixture
    def plugin(self):
        from lumina.plugins import PlainMarkdownPlugin
        return PlainMarkdownPlugin()

    def test_format_basic(self, plugin):
        """测试基本格式化"""
        from lumina.plugins import NoteData
        note = NoteData(
            title="Test Note",
            content="Simple content",
            tags=[],
            links=[],
            source="test.md",
            metadata={}
        )

        result = plugin.format(note)

        assert "# Test Note" in result
        assert "Simple content" in result

    def test_plugin_name(self, plugin):
        """测试插件名称"""
        assert plugin.name == "plain"
        assert plugin.display_name == "Plain Markdown"


class TestPluginRegistry:
    """插件注册表测试"""

    def test_get_plugin_obsidian(self):
        """测试获取 Obsidian 插件"""
        from lumina.plugins import get_plugin
        plugin = get_plugin("obsidian")
        assert plugin.name == "obsidian"

    def test_get_plugin_notion(self):
        """测试获取 Notion 插件"""
        from lumina.plugins import get_plugin
        plugin = get_plugin("notion")
        assert plugin.name == "notion"

    def test_get_plugin_plain(self):
        """测试获取 Plain 插件"""
        from lumina.plugins import get_plugin
        plugin = get_plugin("plain")
        assert plugin.name == "plain"

    def test_get_plugin_default(self):
        """测试未知插件抛异常"""
        from lumina.plugins import get_plugin
        with pytest.raises(ValueError):
            get_plugin("unknown")

    def test_list_plugins(self):
        """测试列出所有插件"""
        from lumina.plugins import list_plugins
        plugins = list_plugins()

        names = list(plugins.keys())
        assert "obsidian" in names
        assert "notion" in names
        assert "plain" in names


class TestBasePlugin:
    """BasePlugin 基类测试"""

    def test_abstract_methods(self):
        """测试抽象方法"""
        from lumina.plugins import BasePlugin

        # 不能直接实例化
        with pytest.raises(TypeError):
            BasePlugin()

    def test_format_must_implement(self):
        """测试 format 必须实现"""
        from lumina.plugins import BasePlugin

        class IncompletePlugin(BasePlugin):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompletePlugin()
