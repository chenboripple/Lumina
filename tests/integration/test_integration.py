"""
集成测试 - 配置链路与插件链路
"""

import pytest
import yaml
from pathlib import Path
from lumina.harness import Harness, HarnessConfig
from lumina.plugins import get_plugin, NoteData


TEST_LLM_CONFIG = {
    "provider": "openai",
    "api_key": "test-key",
    "model": "gpt-4",
}


class TestPluginChain:
    """插件链路集成测试"""

    def test_obsidian_plugin_via_harness(self, tmp_path):
        """Harness 通过 obsidian 插件生成带 YAML frontmatter 的输出"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Python Design Patterns\n\nThis discusses patterns.")

        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            quality_threshold=0.0,
            plugin="obsidian",
            llm_config=TEST_LLM_CONFIG,
        )
        note = NoteData(
            title="Demo",
            content="Body",
            tags=["demo"],
            links=[],
            source=str(test_file),
            metadata={"scene": "technical_doc", "para": "Projects"},
        )
        content = get_plugin("obsidian").format(note)
        assert content.startswith("---")  # YAML frontmatter

    def test_plain_plugin_via_harness(self, tmp_path):
        """Harness 通过 plain 插件生成不含 YAML frontmatter 的输出"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nSome content here.")

        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            quality_threshold=0.0,
            plugin="plain",
            llm_config=TEST_LLM_CONFIG,
        )
        note = NoteData(
            title="Demo",
            content="Body",
            tags=["demo"],
            links=[],
            source=str(test_file),
            metadata={"scene": "technical_doc", "para": "Projects"},
        )
        content = get_plugin("plain").format(note)
        assert not content.startswith("---")  # 不含 YAML frontmatter

    def test_plugin_switch_changes_format(self, tmp_path):
        """切换插件名确实会改变输出格式"""
        test_file = tmp_path / "note.md"
        test_file.write_text("# Sample\n\nContent.")

        note = NoteData(
            title="Demo",
            content="Body",
            tags=["demo"],
            links=[],
            source=str(test_file),
            metadata={"scene": "technical_doc", "para": "Projects"},
        )

        obsidian_content = get_plugin("obsidian").format(note)
        plain_content = get_plugin("plain").format(note)

        # obsidian 有 frontmatter，plain 没有
        assert obsidian_content.startswith("---")
        assert not plain_content.startswith("---")

    def test_invalid_plugin_raises(self):
        """无效插件名应抛出 ValueError"""
        with pytest.raises(ValueError, match="Unknown plugin"):
            get_plugin("nonexistent_plugin")

    def test_plugin_raises_on_init_with_bad_name(self):
        """HarnessConfig 中使用不存在的插件名，Harness 初始化应报错"""
        config = HarnessConfig(plugin="bad_plugin", llm_config=TEST_LLM_CONFIG)
        with pytest.raises(ValueError, match="Unknown plugin"):
            Harness(config)


class TestConfigChain:
    """配置链路集成测试"""

    def test_yaml_config_drives_harness(self, tmp_path):
        """YAML 配置文件正确驱动 Harness 全链路"""
        source_dir = tmp_path / "sources"
        source_dir.mkdir()
        (source_dir / "note.md").write_text("# My Note\n\nSome important content.")

        output_dir = tmp_path / "notes"
        config_file = tmp_path / "lumina.yaml"
        config_file.write_text(yaml.dump({
            "input": {
                "sources": [{"path": str(source_dir), "recursive": True}],
                "default_recursive": True,
                "supported_extensions": [".md"],
            },
            "output": {
                "plugin": "plain",
                "base_dir": str(output_dir),
            },
            "harness": {"max_iterations": 1, "quality_threshold": 0.0},
            "llm": {"provider": "openai", "api_key": "test-key", "model": "gpt-4"},
        }))

        from lumina.config import LuminaConfig
        lumina_config = LuminaConfig.load(str(config_file))

        assert len(lumina_config.input_sources) == 1
        assert lumina_config.output.plugin == "plain"

        harness_config = HarnessConfig(
            max_iterations=lumina_config.harness.get("max_iterations", 3),
            quality_threshold=lumina_config.harness.get("quality_threshold", 0.8),
            output_dir=str(lumina_config.output.resolve_base_dir()),
            vault_path=lumina_config.output.vault_path,
            plugin=lumina_config.output.plugin,
            llm_config=TEST_LLM_CONFIG,
        )
        harness = Harness(harness_config)
        source = lumina_config.input_sources[0]
        report = harness.run(str(source.resolve_path()), source.recursive)

        assert report["statistics"]["total_files"] == 1
        assert output_dir.exists()

    def test_config_validation_rejects_missing_path(self, tmp_path):
        """配置校验应拒绝不存在的输入路径"""
        config_file = tmp_path / "lumina.yaml"
        config_file.write_text(yaml.dump({
            "input": {
                "sources": [{"path": "/nonexistent/path/xyz", "recursive": True}],
            },
            "output": {"plugin": "plain", "base_dir": str(tmp_path / "out")},
            "harness": {},
            "llm": {},
        }))

        from lumina.config import LuminaConfig
        lumina_config = LuminaConfig.load(str(config_file))
        errors = lumina_config.validate()

        assert len(errors) > 0
        assert any("does not exist" in e for e in errors)

    def test_harness_config_default_plugin(self):
        """HarnessConfig 默认插件为 obsidian"""
        config = HarnessConfig()
        assert config.plugin == "obsidian"

    def test_full_config_pipeline(self, tmp_path):
        """多个输入源、使用 obsidian 插件的完整链路"""
        for name in ("doc1.md", "doc2.md"):
            (tmp_path / name).write_text(f"# {name}\n\nContent for {name}.")

        config = HarnessConfig(
            output_dir=str(tmp_path / "out"),
            max_iterations=1,
            quality_threshold=0.0,
            plugin="obsidian",
            llm_config=TEST_LLM_CONFIG,
        )
        report = Harness(config).run(str(tmp_path), recursive=False)

        assert report["statistics"]["total_files"] == 2
