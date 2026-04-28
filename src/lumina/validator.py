"""
Validator - 智能验证模块 (Agent 增强版)
多维度质量检查、历史对比、LLM 深度评估、智能修复建议
"""

import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .cache import CacheManager
from .history import HistoryManager


@dataclass
class ValidationIssue:
    """验证问题（增强版）"""
    type: str
    severity: str  # error, warning, info
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    fix_suggestion: str = ""  # 具体修复建议
    auto_fixable: bool = False  # 是否可自动修复


@dataclass
class ValidationResult:
    """验证结果（增强版）"""
    passed: bool
    score: float
    issues: List[ValidationIssue]
    suggestions: List[str]
    metadata: Dict[str, Any]
    quality_report: Dict[str, Any] = field(default_factory=dict)  # 详细质量报告
    comparison_with_history: Optional[Dict[str, Any]] = None  # 与历史版本对比


class Validator:
    """
    智能验证器（Agent 增强版）
    
    核心能力：
    1. 🔍 多维度质量检查（结构、内容、语义、风格）
    2. 📊 历史对比分析（与之前版本对比质量变化）
    3. 🧠 LLM 深度评估（利用 LLM 进行语义质量评估）
    4. 💡 智能修复建议（具体问题 + 修复方案）
    5. 📈 质量趋势分析（追踪质量变化趋势）
    6. 🎯 可配置规则（支持自定义验证规则）
    """
    
    # 质量阈值配置
    DEFAULT_THRESHOLDS = {
        "content_min_length": 100,
        "content_max_length": 50000,
        "title_min_length": 3,
        "title_max_length": 100,
        "min_tag_count": 2,
        "max_tag_count": 10,
        "min_key_points": 2,
        "max_link_ratio": 0.3,
        "min_confidence": 0.6,
        "quality_threshold": 0.7,
    }
    
    # 验证规则权重
    RULE_WEIGHTS = {
        "structure": 0.25,      # 结构完整性
        "content": 0.30,        # 内容质量
        "semantic": 0.20,       # 语义质量
        "style": 0.15,          # 风格一致性
        "metadata": 0.10,       # 元数据完整性
    }
    
    def __init__(
        self, 
        config: Dict[str, Any] = None,
        cache_manager: CacheManager = None,
        history_manager: HistoryManager = None,
        llm_config: Dict[str, Any] = None
    ):
        self.config = config or {}
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **self.config.get("thresholds", {})}
        self.cache_manager = cache_manager
        self.history_manager = history_manager
        self.llm_config = llm_config or {}
        
        # 初始化 LLM Provider（用于语义验证）
        self._llm_provider = None
        if self.llm_config:
            try:
                from .llm import get_llm_provider
                self._llm_provider = get_llm_provider(self.llm_config)
            except Exception as e:
                self._log(f"Failed to initialize LLM for validator: {e}", level="error")
        
        # 统计信息
        self.stats = {
            "total_validations": 0,
            "passed_count": 0,
            "failed_count": 0,
            "avg_score": 0.0,
        }

    def _log(self, message: str, level: str = "info"):
        """输出验证器日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level.upper()}] Validator: {message}")
    
    def validate(self, note_output, file_info=None, context=None) -> ValidationResult:
        """
        全面验证笔记质量（Agent 增强版）
        
        Args:
            note_output: 生成的笔记
            file_info: 文件信息（用于历史对比）
            context: 执行上下文
            
        Returns:
            详细验证结果
        """
        self.stats["total_validations"] += 1
        
        issues = []
        
        # 1. 结构完整性检查
        structure_issues = self._check_structure(note_output)
        issues.extend(structure_issues)
        
        # 2. 内容质量检查
        content_issues = self._check_content(note_output)
        issues.extend(content_issues)
        
        # 3. 语义质量检查（使用 LLM）
        if self.llm_config:
            semantic_issues = self._check_semantic(note_output, file_info)
            issues.extend(semantic_issues)
        
        # 4. 风格一致性检查
        style_issues = self._check_style(note_output)
        issues.extend(style_issues)
        
        # 5. 元数据完整性检查
        metadata_issues = self._check_metadata(note_output)
        issues.extend(metadata_issues)
        
        # 6. 计算综合得分
        score = self._calculate_comprehensive_score(note_output, issues)
        
        # 7. 判断是否通过
        passed = score >= self.thresholds["quality_threshold"] and \
                 not any(i.severity == "error" for i in issues)
        
        # 8. 生成修复建议
        suggestions = self._generate_smart_suggestions(note_output, issues)
        
        # 9. 生成质量报告
        quality_report = self._generate_quality_report(note_output, issues, score)
        
        # 10. 历史对比（如果有历史记录）
        comparison = None
        if self.history_manager and file_info:
            comparison = self._compare_with_history(note_output, file_info)
        
        # 更新统计
        if passed:
            self.stats["passed_count"] += 1
        else:
            self.stats["failed_count"] += 1
        
        # 计算平均分
        total = self.stats["total_validations"]
        self.stats["avg_score"] = (self.stats["avg_score"] * (total - 1) + score) / total
        
        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            metadata={
                "total_checks": len(issues),
                "error_count": len([i for i in issues if i.severity == "error"]),
                "warning_count": len([i for i in issues if i.severity == "warning"]),
                "info_count": len([i for i in issues if i.severity == "info"]),
                "validation_time": datetime.now().isoformat(),
            },
            quality_report=quality_report,
            comparison_with_history=comparison,
        )
    
    def validate_quick(self, note_output) -> ValidationResult:
        """
        快速验证（只检查基础规则，不调用 LLM）
        
        用于：
        - 快速筛选明显低质量的内容
        - 减少 LLM 调用成本
        - 初步质量评估
        """
        issues = []
        
        # 基础结构检查
        issues.extend(self._check_structure(note_output))
        
        # 基础内容检查
        issues.extend(self._check_content(note_output))
        
        score = self._calculate_comprehensive_score(note_output, issues)
        passed = score >= self.thresholds["quality_threshold"] and \
                 not any(i.severity == "error" for i in issues)
        
        suggestions = self._generate_smart_suggestions(note_output, issues)
        
        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            metadata={"quick_validation": True},
        )
    
    def _check_structure(self, note_output) -> List[ValidationIssue]:
        """检查结构完整性"""
        issues = []
        content = note_output.content
        
        # 检查标题
        if not note_output.title or note_output.title == "Untitled":
            issues.append(ValidationIssue(
                type="missing_title",
                severity="error",
                message="标题缺失或过于通用",
                fix_suggestion="基于内容生成一个描述性标题",
                auto_fixable=True,
            ))
        elif len(note_output.title) < self.thresholds["title_min_length"]:
            issues.append(ValidationIssue(
                type="title_too_short",
                severity="warning",
                message=f"标题太短 ({len(note_output.title)} 字符)",
                fix_suggestion="增加标题的描述性",
                auto_fixable=True,
            ))
        
        # 检查 Markdown 结构
        has_headers = bool(re.search(r'^#{1,6}\s', content, re.MULTILINE))
        if not has_headers:
            issues.append(ValidationIssue(
                type="missing_structure",
                severity="warning",
                message="缺少 Markdown 标题结构",
                fix_suggestion="添加适当的标题层级（# ## ###）",
                auto_fixable=True,
            ))
        
        # 检查关键部分
        required_sections = ["Summary", "Key Points"]
        for section in required_sections:
            if section not in content:
                issues.append(ValidationIssue(
                    type=f"missing_{section.lower().replace(' ', '_')}",
                    severity="warning",
                    message=f"缺少 '{section}' 部分",
                    fix_suggestion=f"添加 '{section}' 部分",
                    auto_fixable=True,
                ))
        
        return issues
    
    def _check_content(self, note_output) -> List[ValidationIssue]:
        """检查内容质量"""
        issues = []
        content = note_output.content
        
        # 检查内容长度
        content_length = len(content)
        if content_length < self.thresholds["content_min_length"]:
            issues.append(ValidationIssue(
                type="content_too_short",
                severity="error",
                message=f"内容太短 ({content_length} 字符，要求至少 {self.thresholds['content_min_length']})",
                fix_suggestion="扩展内容，添加更多细节和例子",
                auto_fixable=False,
            ))
        elif content_length > self.thresholds["content_max_length"]:
            issues.append(ValidationIssue(
                type="content_too_long",
                severity="warning",
                message=f"内容过长 ({content_length} 字符)",
                fix_suggestion="精简内容，保留核心信息",
                auto_fixable=False,
            ))
        
        # 检查标签数量
        tag_count = len(note_output.tags)
        if tag_count < self.thresholds["min_tag_count"]:
            issues.append(ValidationIssue(
                type="insufficient_tags",
                severity="warning",
                message=f"标签数量不足 ({tag_count} 个，建议至少 {self.thresholds['min_tag_count']})",
                fix_suggestion="从内容中提取更多关键词作为标签",
                auto_fixable=True,
            ))
        elif tag_count > self.thresholds["max_tag_count"]:
            issues.append(ValidationIssue(
                type="too_many_tags",
                severity="info",
                message=f"标签过多 ({tag_count} 个)",
                fix_suggestion="精简标签，保留最核心的",
                auto_fixable=True,
            ))
        
        # 检查关键要点数量
        key_points = re.findall(r'^-\s+(.+)$', content, re.MULTILINE)
        if len(key_points) < self.thresholds["min_key_points"]:
            issues.append(ValidationIssue(
                type="insufficient_key_points",
                severity="warning",
                message=f"关键要点数量不足 ({len(key_points)} 个)",
                fix_suggestion="提取更多关键要点",
                auto_fixable=False,
            ))
        
        # 检查链接质量
        if note_output.links:
            link_ratio = len(note_output.links) / max(len(content.split()), 1)
            if link_ratio > self.thresholds["max_link_ratio"]:
                issues.append(ValidationIssue(
                    type="too_many_links",
                    severity="warning",
                    message=f"链接比例过高 ({link_ratio:.1%})",
                    fix_suggestion="减少链接数量，保留最相关的",
                    auto_fixable=True,
                ))
        
        # 检查重复内容
        lines = content.split('\n')
        seen = set()
        duplicates = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped in seen:
                duplicates.append(stripped)
            seen.add(stripped)
        
        if duplicates:
            issues.append(ValidationIssue(
                type="duplicate_content",
                severity="info",
                message=f"发现 {len(duplicates)} 处重复内容",
                fix_suggestion="删除重复内容",
                auto_fixable=True,
            ))
        
        return issues
    
    def _check_semantic(self, note_output, file_info) -> List[ValidationIssue]:
        """语义质量检查（使用 LLM）"""
        issues = []
        
        # 如果配置了 LLM，使用 LLM 进行深度语义分析
        if self._llm_provider:
            try:
                # 构建语义检查提示词
                prompt = f"""请分析以下笔记内容的质量，重点关注：
1. 内容一致性和逻辑连贯性
2. 信息准确性和完整性
3. 与源文件的相关性

笔记标题: {note_output.title}
笔记内容:
{note_output.content[:2000]}  # 限制长度避免 token 过多

请用 JSON 格式返回分析结果：
{{
    "issues": [
        {{
            "type": "问题类型",
            "severity": "error/warning/info",
            "message": "问题描述",
            "fix_suggestion": "修复建议"
        }}
    ],
    "confidence": 0.85
}}"""
                
                response = self._llm_provider.complete(prompt)
                
                # 尝试解析 JSON 响应
                try:
                    import json
                    # 提取 JSON 部分
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                        
                        for issue_data in result.get("issues", []):
                            issues.append(ValidationIssue(
                                type=issue_data.get("type", "semantic_issue"),
                                severity=issue_data.get("severity", "warning"),
                                message=issue_data.get("message", "语义问题"),
                                fix_suggestion=issue_data.get("fix_suggestion", ""),
                                auto_fixable=False
                            ))
                        
                        # 更新置信度
                        if "confidence" in result:
                            note_output.metadata["llm_confidence"] = result["confidence"]
                            
                except (json.JSONDecodeError, Exception) as e:
                    self._log(
                        f"Failed to parse semantic validation response for {getattr(file_info, 'path', 'unknown')}: {e}",
                        level="warning"
                    )
                    
            except Exception as e:
                self._log(
                    f"Semantic validation LLM request failed for {getattr(file_info, 'path', 'unknown')}: {e}",
                    level="error"
                )
        
        # 基础检查：检查置信度
        confidence = note_output.metadata.get("confidence", 0)
        if confidence < self.thresholds["min_confidence"]:
            issues.append(ValidationIssue(
                type="low_confidence",
                severity="warning",
                message=f"置信度较低 ({confidence:.2f})",
                fix_suggestion="增加更多上下文信息或验证数据来源",
                auto_fixable=False,
            ))
        
        return issues
    
    def _check_style(self, note_output) -> List[ValidationIssue]:
        """检查风格一致性"""
        issues = []
        content = note_output.content
        
        # 检查 Markdown 格式一致性
        # 标题层级是否连续
        headers = re.findall(r'^(#{1,6})\s', content, re.MULTILINE)
        if headers:
            header_levels = [len(h) for h in headers]
            if max(header_levels) - min(header_levels) > 2:
                issues.append(ValidationIssue(
                    type="inconsistent_header_levels",
                    severity="info",
                    message="标题层级跨度太大",
                    fix_suggestion="调整标题层级，保持层次清晰",
                    auto_fixable=True,
                ))
        
        # 检查标点符号使用
        if content.count('。') > 0 and content.count('.') > content.count('。'):
            issues.append(ValidationIssue(
                type="mixed_punctuation",
                severity="info",
                message="中英文标点混用",
                fix_suggestion="统一使用中文或英文标点",
                auto_fixable=True,
            ))
        
        return issues
    
    def _check_metadata(self, note_output) -> List[ValidationIssue]:
        """检查元数据完整性"""
        issues = []
        metadata = note_output.metadata
        
        # 检查必需字段
        required_fields = ["complexity", "confidence"]
        for field in required_fields:
            if field not in metadata:
                issues.append(ValidationIssue(
                    type=f"missing_metadata_{field}",
                    severity="info",
                    message=f"缺少元数据字段: {field}",
                    fix_suggestion=f"添加 {field} 元数据",
                    auto_fixable=True,
                ))
        
        # 检查复杂度值
        if "complexity" in metadata:
            valid_complexities = ["simple", "moderate", "complex"]
            if metadata["complexity"] not in valid_complexities:
                issues.append(ValidationIssue(
                    type="invalid_complexity",
                    severity="info",
                    message=f"无效的复杂度值: {metadata['complexity']}",
                    fix_suggestion=f"使用有效值: {', '.join(valid_complexities)}",
                    auto_fixable=True,
                ))
        
        return issues
    
    def _calculate_comprehensive_score(self, note_output, issues: List[ValidationIssue]) -> float:
        """计算综合质量得分"""
        # 基础分
        score = 1.0
        
        # 按严重程度和规则类型扣分
        structure_penalty = 0
        content_penalty = 0
        semantic_penalty = 0
        style_penalty = 0
        metadata_penalty = 0
        
        for issue in issues:
            if issue.severity == "error":
                penalty = 0.3
            elif issue.severity == "warning":
                penalty = 0.1
            else:  # info
                penalty = 0.02
            
            # 根据问题类型归类
            if issue.type.startswith(("missing_title", "title_too_short", "missing_structure")):
                structure_penalty += penalty
            elif issue.type.startswith(("content_too_short", "content_too_long", "insufficient_tags", 
                                      "insufficient_key_points", "too_many_links", "duplicate_content")):
                content_penalty += penalty
            elif issue.type.startswith(("low_confidence",)):
                semantic_penalty += penalty
            elif issue.type.startswith(("inconsistent_header_levels", "mixed_punctuation")):
                style_penalty += penalty
            else:
                metadata_penalty += penalty
        
        # 应用权重
        score -= structure_penalty * self.RULE_WEIGHTS["structure"]
        score -= content_penalty * self.RULE_WEIGHTS["content"]
        score -= semantic_penalty * self.RULE_WEIGHTS["semantic"]
        score -= style_penalty * self.RULE_WEIGHTS["style"]
        score -= metadata_penalty * self.RULE_WEIGHTS["metadata"]
        
        # 加分项
        if len(note_output.tags) >= 5:
            score += 0.05
        if note_output.links:
            score += 0.05
        if len(note_output.content) > 500:
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def _generate_smart_suggestions(self, note_output, issues: List[ValidationIssue]) -> List[str]:
        """生成智能修复建议"""
        suggestions = []
        
        # 按优先级排序问题
        sorted_issues = sorted(issues, key=lambda x: 
            {"error": 0, "warning": 1, "info": 2}[x.severity])
        
        for issue in sorted_issues:
            if issue.fix_suggestion:
                suggestions.append(f"[{issue.severity.upper()}] {issue.type}: {issue.fix_suggestion}")
        
        # 添加通用建议
        if not any(i.type == "missing_structure" for i in issues):
            suggestions.append("考虑添加更多结构化元素（表格、列表、代码块）")
        
        if not note_output.links:
            suggestions.append("添加相关主题链接，增强知识网络")
        
        return suggestions
    
    def _generate_quality_report(self, note_output, issues: List[ValidationIssue], score: float) -> Dict[str, Any]:
        """生成详细质量报告"""
        # 按类别分组
        categories = {
            "structure": [],
            "content": [],
            "semantic": [],
            "style": [],
            "metadata": [],
        }
        
        for issue in issues:
            if issue.type.startswith(("missing_title", "title_too_short", "missing_structure")):
                categories["structure"].append(issue)
            elif issue.type.startswith(("content_too_short", "content_too_long", "insufficient_tags", 
                                      "insufficient_key_points", "too_many_links", "duplicate_content")):
                categories["content"].append(issue)
            elif issue.type.startswith(("low_confidence",)):
                categories["semantic"].append(issue)
            elif issue.type.startswith(("inconsistent_header_levels", "mixed_punctuation")):
                categories["style"].append(issue)
            else:
                categories["metadata"].append(issue)
        
        # 计算各类别得分
        category_scores = {}
        for cat, cat_issues in categories.items():
            penalty = sum(0.3 if i.severity == "error" else 0.1 if i.severity == "warning" else 0.02 
                         for i in cat_issues)
            category_scores[cat] = max(0, 1.0 - penalty)
        
        return {
            "overall_score": score,
            "grade": self._score_to_grade(score),
            "category_scores": category_scores,
            "category_issues": {k: len(v) for k, v in categories.items()},
            "strengths": self._identify_strengths(note_output, issues),
            "improvement_areas": self._identify_improvement_areas(issues),
            "content_stats": {
                "total_length": len(note_output.content),
                "title_length": len(note_output.title),
                "tag_count": len(note_output.tags),
                "link_count": len(note_output.links),
                "header_count": len(re.findall(r'^#{1,6}\s', note_output.content, re.MULTILINE)),
                "list_item_count": len(re.findall(r'^-\s+', note_output.content, re.MULTILINE)),
            }
        }
    
    def _score_to_grade(self, score: float) -> str:
        """分数转等级"""
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B"
        elif score >= 0.6:
            return "C"
        elif score >= 0.5:
            return "D"
        else:
            return "F"
    
    def _identify_strengths(self, note_output, issues: List[ValidationIssue]) -> List[str]:
        """识别优势"""
        strengths = []
        
        if len(note_output.content) > 500:
            strengths.append("内容充实，信息量大")
        
        if len(note_output.tags) >= 5:
            strengths.append("标签丰富，便于分类检索")
        
        if note_output.links:
            strengths.append("关联性强，知识网络完善")
        
        if not any(i.type.startswith("missing_structure") for i in issues):
            strengths.append("结构清晰，层次分明")
        
        if not any(i.severity == "error" for i in issues):
            strengths.append("基础质量扎实，无严重问题")
        
        return strengths
    
    def _identify_improvement_areas(self, issues: List[ValidationIssue]) -> List[str]:
        """识别改进空间"""
        areas = []
        
        error_types = set(i.type for i in issues if i.severity == "error")
        warning_types = set(i.type for i in issues if i.severity == "warning")
        
        if "content_too_short" in error_types or "content_too_short" in warning_types:
            areas.append("内容深度")
        
        if "missing_title" in error_types or "title_too_short" in warning_types:
            areas.append("标题质量")
        
        if "insufficient_tags" in warning_types:
            areas.append("标签覆盖")
        
        if "missing_structure" in warning_types:
            areas.append("结构组织")
        
        if "low_confidence" in warning_types:
            areas.append("信息准确性")
        
        return areas
    
    def _compare_with_history(self, note_output, file_info) -> Optional[Dict[str, Any]]:
        """与历史版本对比"""
        if not self.history_manager:
            return None
        
        history = self.history_manager.get_file_history(str(file_info.path), limit=5)
        if not history or len(history) < 2:
            return None
        
        # 获取上一次处理记录
        last_record = history[1]  # [0] 是当前，[1] 是上一次
        
        current_score = note_output.metadata.get("score", 0)
        last_score = last_record["best_score"]
        
        score_diff = current_score - last_score
        
        return {
            "previous_score": last_score,
            "current_score": current_score,
            "score_diff": score_diff,
            "improved": score_diff > 0,
            "previous_iterations": last_record["iterations"],
            "trend": "improving" if score_diff > 0.05 else "stable" if abs(score_diff) < 0.05 else "declining",
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取验证统计"""
        total = self.stats["total_validations"]
        return {
            **self.stats,
            "pass_rate": self.stats["passed_count"] / max(total, 1),
            "fail_rate": self.stats["failed_count"] / max(total, 1),
        }
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_validations": 0,
            "passed_count": 0,
            "failed_count": 0,
            "avg_score": 0.0,
        }
