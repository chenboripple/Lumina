"""
测试 Validator 模块
"""

import pytest
from lumina.validator import Validator, ValidationResult
from lumina.executor import NoteOutput


class TestValidator:
    """Validator 测试套件"""
    
    def test_validate_pass(self):
        """测试通过验证"""
        note = NoteOutput(
            title="Good Title",
            content="A" * 200,  # 足够长
            tags=["tag1", "tag2", "tag3"],
            links=["Topic A"],
            source="test.md",
            metadata={}
        )
        
        validator = Validator()
        result = validator.validate(note)
        
        assert result.passed is True
        assert result.score >= 0.7
        assert len(result.issues) == 0
    
    def test_validate_fail_short_content(self):
        """测试内容太短"""
        note = NoteOutput(
            title="Short",
            content="Too short",
            tags=["tag1"],
            links=[],
            source="test.md",
            metadata={}
        )
        
        validator = Validator()
        result = validator.validate(note)
        
        assert result.passed is False
        assert any(i["type"] == "content_too_short" for i in result.issues)
    
    def test_validate_fail_missing_title(self):
        """测试缺少标题"""
        note = NoteOutput(
            title="Untitled",
            content="A" * 200,
            tags=["tag1"],
            links=[],
            source="test.md",
            metadata={}
        )
        
        validator = Validator()
        result = validator.validate(note)
        
        assert any(i["type"] == "missing_title" for i in result.issues)
    
    def test_score_calculation(self):
        """测试分数计算"""
        # 完美笔记
        perfect = NoteOutput(
            title="Perfect",
            content="A" * 500,
            tags=["a", "b", "c"],
            links=["X", "Y"],
            source="test.md",
            metadata={}
        )
        
        validator = Validator()
        result = validator.validate(perfect)
        
        assert result.score > 0.9
    
    def test_suggestions_generation(self):
        """测试建议生成"""
        note = NoteOutput(
            title="Untitled",
            content="Short",
            tags=[],
            links=[],
            source="test.md",
            metadata={}
        )
        
        validator = Validator()
        result = validator.validate(note)
        
        assert len(result.suggestions) > 0
        assert any("title" in s.lower() for s in result.suggestions)