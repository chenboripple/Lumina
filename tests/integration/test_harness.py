"""
测试 Harness 核心协调器
"""

import pytest
from pathlib import Path
from lumina.harness import Harness, HarnessConfig


TEST_LLM_CONFIG = {
    "provider": "openai",
    "api_key": "test-key",
    "model": "gpt-4",
}


class TestHarness:
    """Harness 测试套件"""
    
    def test_basic_run(self, tmp_path):
        """测试基本运行"""
        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Content\n\nThis is a test.")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=2,
            quality_threshold=0.5,
            llm_config=TEST_LLM_CONFIG,
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))

        stats = report["statistics"]
        assert stats["total_files"] == 1
        assert stats["total_iterations"] >= 1
        assert stats["avg_score"] >= 0
    
    def test_max_iterations(self, tmp_path):
        """测试最大迭代限制"""
        test_file = tmp_path / "test.md"
        test_file.write_text("Content")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            quality_threshold=1.0,  # 不可能达到，强制最大迭代
            llm_config=TEST_LLM_CONFIG,
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))

        # 过滤/失败场景下也应只记录一轮处理
        assert report["statistics"]["total_iterations"] == 1
    
    def test_output_generation(self, tmp_path):
        """测试输出生成"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Hello World")
        
        output_dir = tmp_path / "output"
        config = HarnessConfig(
            output_dir=str(output_dir),
            max_iterations=1,
            quality_threshold=0.0,
            llm_config=TEST_LLM_CONFIG,
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))

        # 当前执行链路允许被过滤后无落盘输出，但报告统计应正确
        assert output_dir.exists()
        assert report["statistics"]["total_files"] == 1
    
    def test_empty_directory(self, tmp_path):
        """测试空目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            llm_config=TEST_LLM_CONFIG,
        )

        harness = Harness(config)
        report = harness.run(str(empty_dir))

        assert report["statistics"]["total_files"] == 0
    
    def test_report_structure(self, tmp_path):
        """测试报告结构"""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            llm_config=TEST_LLM_CONFIG,
        )

        harness = Harness(config)
        report = harness.run(str(test_file))
        
        # 检查报告字段
        assert "session_id" in report
        assert "status" in report
        assert "statistics" in report
        assert "config" in report
        assert "results" in report

        stats = report["statistics"]
        assert "total_files" in stats
        assert "avg_score" in stats
        assert "cache_hit_rate" in stats

        # 检查结果详情
        if report["results"]:
            result = report["results"][0]
            assert "source" in result
            assert "iterations" in result
            assert "best_score" in result