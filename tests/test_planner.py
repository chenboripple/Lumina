"""
测试 Planner 模块
"""

import pytest
from pathlib import Path
from lumina.planner import Planner, FileInfo


class TestPlanner:
    """Planner 测试套件"""
    
    def test_scan_single_file(self, tmp_path):
        """测试扫描单个文件"""
        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")
        
        planner = Planner()
        files = planner.scan(str(test_file))
        
        assert len(files) == 1
        assert files[0].path == test_file
        assert files[0].type == "markdown"
    
    def test_scan_directory(self, tmp_path):
        """测试扫描目录"""
        # 创建多个测试文件
        (tmp_path / "a.md").write_text("A")
        (tmp_path / "b.txt").write_text("B")
        (tmp_path / "c.py").write_text("C")
        
        planner = Planner()
        files = planner.scan(str(tmp_path), recursive=False)
        
        assert len(files) == 3
        types = {f.type for f in files}
        assert types == {"markdown", "text", "code"}
    
    def test_plan_complexity(self, tmp_path):
        """测试复杂度评估"""
        # 创建小文件（< 1MB）
        (tmp_path / "small.md").write_text("x" * 100)
        
        planner = Planner()
        files = planner.scan(str(tmp_path))
        plan = planner.plan(files)
        
        assert plan["complexity"] == "simple"
        assert plan["strategy"] == "direct"
    
    def test_detect_type(self):
        """测试文件类型检测"""
        planner = Planner()
        
        assert planner._detect_type(Path("test.md")) == "markdown"
        assert planner._detect_type(Path("test.py")) == "code"
        assert planner._detect_type(Path("test.unknown")) == "unknown"
    
    def test_create_batches(self, tmp_path):
        """测试批次创建"""
        # 创建12个文件
        for i in range(12):
            (tmp_path / f"file{i}.md").write_text(f"Content {i}")
        
        planner = Planner()
        files = planner.scan(str(tmp_path))
        plan = planner.plan(files)
        
        # 默认批次大小为10，所以应该分成2批
        assert len(plan["batches"]) == 2
        assert len(plan["batches"][0]) == 10
        assert len(plan["batches"][1]) == 2