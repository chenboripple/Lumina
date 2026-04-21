"""
测试 Harness 核心协调器
"""

import pytest
from pathlib import Path
from lumina.harness import Harness, HarnessConfig


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
            quality_threshold=0.5
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))
        
        assert report["total_files"] == 1
        assert report["avg_iterations"] > 0
        assert report["avg_score"] >= 0
    
    def test_max_iterations(self, tmp_path):
        """测试最大迭代限制"""
        test_file = tmp_path / "test.md"
        test_file.write_text("Content")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            quality_threshold=1.0  # 不可能达到，强制最大迭代
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))
        
        # 应该只迭代1次
        assert report["avg_iterations"] == 1.0
    
    def test_output_generation(self, tmp_path):
        """测试输出生成"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Hello World")
        
        output_dir = tmp_path / "output"
        config = HarnessConfig(
            output_dir=str(output_dir),
            max_iterations=1,
            quality_threshold=0.0
        )
        
        harness = Harness(config)
        harness.run(str(test_file))
        
        # 检查输出文件
        assert output_dir.exists()
        md_files = list(output_dir.glob("*.md"))
        assert len(md_files) > 0
    
    def test_empty_directory(self, tmp_path):
        """测试空目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1
        )
        
        harness = Harness(config)
        report = harness.run(str(empty_dir))
        
        assert report["total_files"] == 0
    
    def test_report_structure(self, tmp_path):
        """测试报告结构"""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1
        )
        
        harness = Harness(config)
        report = harness.run(str(test_file))
        
        # 检查报告字段
        assert "total_files" in report
        assert "avg_iterations" in report
        assert "avg_score" in report
        assert "threshold" in report
        assert "results" in report
        
        # 检查结果详情
        if report["results"]:
            result = report["results"][0]
            assert "source" in result
            assert "iterations" in result
            assert "best_score" in result