import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lumina.executor import Executor
from lumina.plugins import ObsidianPlugin, NoteData
from lumina.scene_detector import SceneDetector


def test_executor_markdown_includes_richer_sections():
    executor = Executor.__new__(Executor)

    markdown = executor._to_markdown({
        "title": "Structured Note",
        "summary": "A concise but meaningful overview.",
        "key_points": ["Point A", "Point B"],
        "supporting_details": ["Detail 1", "Detail 2"],
        "action_items": ["Follow up with team"],
        "open_questions": ["Should this be split further?"],
        "suggested_links": ["Topic X"],
        "metadata": {
            "complexity": "moderate",
            "confidence": 0.88,
            "knowledge_density": "high",
            "document_type": "spec",
        },
    })

    assert "## Supporting Details" in markdown
    assert "## Action Items" in markdown
    assert "## Open Questions" in markdown
    assert "- [ ] Follow up with team" in markdown
    assert "- Knowledge Density: high" in markdown
    assert "- Document Type: spec" in markdown


def test_generic_scene_formatter_surfaces_detail_sections():
    detector = SceneDetector()

    markdown = detector._format_generic_notes({
        "title": "通用知识笔记",
        "summary": "这是一段摘要。",
        "key_points": ["要点一"],
        "supporting_details": ["细节一"],
        "action_items": ["动作一"],
        "open_questions": ["问题一"],
        "suggested_links": ["主题一"],
        "tags": ["标签一"],
    })

    assert "## 支撑细节" in markdown
    assert "## 后续动作" in markdown
    assert "## 未决问题" in markdown
    assert "- [ ] 动作一" in markdown


def test_obsidian_plugin_adds_organization_callout():
    plugin = ObsidianPlugin()
    content = plugin.format(NoteData(
        title="System Design",
        content="## 概述\n内容主体",
        tags=["architecture"],
        links=["API Gateway"],
        source="/tmp/design.md",
        metadata={
            "scene": "technical_doc",
            "para": "Projects",
            "note_subdir": "technical_doc/Projects",
            "score": 0.91,
            "confidence": 0.87,
        },
    ))

    assert "[!tip] Organization" in content
    assert "path: technical_doc/Projects" in content
    assert "levels: technical_doc -> Projects" in content
    assert "scene: technical_doc" in content
    assert "para: Projects" in content
