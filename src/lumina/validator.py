"""
Validator - 验证模块
检查笔记质量，提供修复建议
"""

from typing import Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    score: float
    issues: List[Dict[str, Any]]
    suggestions: List[str]
    metadata: Dict[str, Any]


class Validator:
    """
    验证器：质量检查与反馈
    
    职责：
    1. 检查笔记完整性
    2. 评估内容质量
    3. 检测潜在问题
    4. 提供修复建议
    """
    
    # 质量阈值
    THRESHOLDS = {
        "content_min_length": 100,
        "max_link_ratio": 0.3,
        "min_tag_count": 1,
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.rules = self._load_rules()
    
    def validate(self, note_output) -> ValidationResult:
        """
        验证笔记质量
        
        Args:
            note_output: 生成的笔记
            
        Returns:
            验证结果
        """
        issues = []
        
        # 检查内容长度
        if len(note_output.content) < self.THRESHOLDS["content_min_length"]:
            issues.append({
                "type": "content_too_short",
                "severity": "error",
                "message": f"Content too short: {len(note_output.content)} chars"
            })
        
        # 检查标题
        if not note_output.title or note_output.title == "Untitled":
            issues.append({
                "type": "missing_title",
                "severity": "error",
                "message": "Title is missing or generic"
            })
        
        # 检查标签
        if len(note_output.tags) < self.THRESHOLDS["min_tag_count"]:
            issues.append({
                "type": "insufficient_tags",
                "severity": "warning",
                "message": f"Only {len(note_output.tags)} tags found"
            })
        
        # 检查链接质量
        link_ratio = len(note_output.links) / max(len(note_output.content.split()), 1)
        if link_ratio > self.THRESHOLDS["max_link_ratio"]:
            issues.append({
                "type": "too_many_links",
                "severity": "warning",
                "message": f"Link ratio too high: {link_ratio:.2%}"
            })
        
        # 计算总分
        score = self._calculate_score(note_output, issues)
        passed = score >= 0.7 and not any(i["severity"] == "error" for i in issues)
        
        # 生成建议
        suggestions = self._generate_suggestions(note_output, issues)
        
        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            metadata={
                "total_checks": len(self.rules),
                "failed_checks": len([i for i in issues if i["severity"] == "error"]),
                "warning_count": len([i for i in issues if i["severity"] == "warning"])
            }
        )
    
    def _calculate_score(self, note_output, issues: List[Dict]) -> float:
        """计算质量分数"""
        base_score = 1.0
        
        # 扣分
        for issue in issues:
            if issue["severity"] == "error":
                base_score -= 0.3
            elif issue["severity"] == "warning":
                base_score -= 0.1
        
        # 加分项
        if len(note_output.tags) >= 3:
            base_score += 0.1
        if note_output.links:
            base_score += 0.1
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_suggestions(self, note_output, issues: List[Dict]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        for issue in issues:
            if issue["type"] == "content_too_short":
                suggestions.append("Add more detail or examples to the content")
            elif issue["type"] == "missing_title":
                suggestions.append("Generate a more descriptive title based on content")
            elif issue["type"] == "insufficient_tags":
                suggestions.append("Extract more keywords from the content")
        
        # 通用建议
        if not note_output.links:
            suggestions.append("Consider adding links to related topics")
        
        return suggestions
    
    def _load_rules(self) -> List[Dict[str, Any]]:
        """加载验证规则"""
        return [
            {"name": "content_length", "weight": 0.3},
            {"name": "title_quality", "weight": 0.2},
            {"name": "tag_coverage", "weight": 0.2},
            {"name": "link_quality", "weight": 0.15},
            {"name": "structure", "weight": 0.15},
        ]