"""
Prompt Manager - 提示词管理系统
支持模板管理、版本控制、A/B 测试、变量注入
"""
import os
import re
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict
import yaml

from .utils.logging import get_logger

logger = get_logger("lumina.prompt_manager")


# ==================== 数据模型 ====================

@dataclass
class PromptVariable:
    """提示词变量定义"""
    name: str
    description: str = ""
    required: bool = True
    default_value: Optional[str] = None
    validation_pattern: Optional[str] = None
    
    def validate(self, value: Any) -> bool:
        """验证变量值"""
        if value is None and self.required:
            return False
        if self.validation_pattern and value is not None:
            return bool(re.match(self.validation_pattern, str(value)))
        return True


@dataclass
class PromptTemplate:
    """提示词模板"""
    name: str
    content: str
    description: str = ""
    version: str = "1.0.0"
    variables: List[PromptVariable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        # 自动提取变量
        if not self.variables:
            self.variables = self._extract_variables()
    
    def _extract_variables(self) -> List[PromptVariable]:
        """从模板内容中提取变量"""
        pattern = r'\{\{(\w+)(?::([^}]+))?\}\}'
        matches = re.findall(pattern, self.content)
        
        variables = []
        for match in matches:
            var_name = match[0]
            default_val = match[1] if len(match) > 1 and match[1] else None
            variables.append(PromptVariable(
                name=var_name,
                default_value=default_val,
            ))
        
        return variables
    
    def render(self, **kwargs) -> str:
        """渲染模板"""
        result = self.content
        
        for var in self.variables:
            value = kwargs.get(var.name, var.default_value)
            
            if value is None and var.required:
                raise ValueError(f"Missing required variable: {var.name}")
            
            if value is not None:
                result = result.replace(f"{{{{{var.name}}}}}", str(value))
                if var.default_value:
                    result = result.replace(f"{{{{{var.name}:{var.default_value}}}}}", str(value))
        
        return result
    
    def validate(self, **kwargs) -> Dict[str, Any]:
        """验证变量并返回错误信息"""
        errors = {}
        
        for var in self.variables:
            value = kwargs.get(var.name, var.default_value)
            if not var.validate(value):
                errors[var.name] = f"Invalid or missing value for variable '{var.name}'"
        
        return errors
    
    def get_hash(self) -> str:
        """获取模板哈希（用于缓存）"""
        content = f"{self.name}:{self.version}:{self.content}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "version": self.version,
            "variables": [
                {
                    "name": v.name,
                    "description": v.description,
                    "required": v.required,
                    "default_value": v.default_value,
                    "validation_pattern": v.validation_pattern,
                }
                for v in self.variables
            ],
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        """从字典创建"""
        variables = [
            PromptVariable(
                name=v["name"],
                description=v.get("description", ""),
                required=v.get("required", True),
                default_value=v.get("default_value"),
                validation_pattern=v.get("validation_pattern"),
            )
            for v in data.get("variables", [])
        ]
        
        return cls(
            name=data["name"],
            content=data["content"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            variables=variables,
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class PromptVersion:
    """提示词版本"""
    template: PromptTemplate
    version: str
    created_at: float
    author: Optional[str] = None
    change_log: str = ""
    is_active: bool = False


@dataclass
class PromptScore:
    """提示词评分"""
    template_name: str
    version: str
    score: float  # 0-1
    feedback_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    average_quality: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== Prompt Manager ====================

class PromptManager:
    """提示词管理器"""
    
    # 默认模板目录
    DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "templates"
    USER_TEMPLATES_DIR = Path.home() / ".lumina" / "prompts"
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or self.USER_TEMPLATES_DIR
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # 模板存储
        self._templates: Dict[str, PromptTemplate] = {}
        self._versions: Dict[str, List[PromptVersion]] = defaultdict(list)
        self._scores: Dict[str, PromptScore] = {}
        
        # 回调函数
        self.on_template_loaded: Optional[Callable] = None
        self.on_template_saved: Optional[Callable] = None
        
        # 加载内置模板
        self._load_builtin_templates()
        
        # 加载用户模板
        self._load_user_templates()
        
        logger.info(f"📋 PromptManager initialized with {len(self._templates)} templates")
    
    def _load_builtin_templates(self) -> None:
        """加载内置模板"""
        # 内置模板直接定义在代码中
        builtin_templates = {
            "default_extractor": PromptTemplate(
                name="default_extractor",
                description="默认文档提取模板",
                content="""你是一个知识管理专家。请分析以下文档内容，提取关键信息并生成结构化笔记。

文档路径: {{file_path}}
文档类型: {{file_type}}
内容:
```
{{content}}
```

请生成以下格式的笔记:
1. 标题（简洁概括）
2. 摘要（3-5句话）
3. 关键要点（bullet points）
4. 相关概念和链接
5. 标签（3-5个）

注意:
- 保留原文的核心观点和关键信息
- 用自己的语言重新组织，不要简单复制
- 识别并标注重要概念和术语
- 如果内容过于简单或重复，直接说明"内容价值较低"
""",
                tags=["default", "extraction"],
            ),
            
            "meeting_notes": PromptTemplate(
                name="meeting_notes",
                description="会议纪要提取模板",
                content="""你是一个会议记录专家。请从以下会议记录中提取关键信息。

会议记录:
```
{{content}}
```

请生成结构化会议纪要:
1. 会议基本信息（主题、时间、参会人员）
2. 讨论议题
3. 关键决策
4. 行动项（负责人 + 截止日期）
5. 待跟进事项

注意:
- 明确标注每个行动项的负责人
- 标注决策的优先级
- 区分"已决定"和"待讨论"
""",
                tags=["meeting", "extraction"],
            ),
            
            "technical_doc": PromptTemplate(
                name="technical_doc",
                description="技术文档提取模板",
                content="""你是一个技术文档专家。请分析以下技术文档，提取关键信息。

文档:
```
{{content}}
```

请生成技术笔记:
1. 文档概述
2. 核心概念和术语
3. 架构/设计要点
4. 关键代码示例
5. 配置和部署信息
6. 依赖关系
7. 最佳实践
8. 常见问题

注意:
- 使用代码块标注关键代码
- 标注版本兼容性信息
- 区分"核心内容"和"参考信息"
""",
                tags=["technical", "extraction"],
            ),
            
            "code_explanation": PromptTemplate(
                name="code_explanation",
                description="代码解释模板",
                content="""你是一个代码分析专家。请分析以下代码，生成详细的技术笔记。

代码文件: {{file_path}}
```
{{content}}
```

请生成:
1. 代码概述（功能描述）
2. 关键类和函数说明
3. 设计模式识别
4. 依赖关系
5. 潜在问题和改进建议
6. 使用示例

注意:
- 标注关键算法和数据结构
- 识别性能瓶颈
- 标注安全注意事项
""",
                tags=["code", "extraction"],
            ),
            
            "quality_validator": PromptTemplate(
                name="quality_validator",
                description="质量验证模板",
                content="""你是一个内容质量评估专家。请评估以下笔记的质量。

原始文档:
```
{{source_content}}
```

生成的笔记:
```
{{note_content}}
```

请从以下维度评估（每项0-1分）:
1. 信息完整性 - 是否保留了原文的核心信息
2. 结构清晰度 - 组织结构是否合理
3. 准确性 - 内容是否准确，有无误解
4. 简洁性 - 是否简洁，无冗余
5. 可操作性 - 是否有实际价值

总分 = 各项平均分

请返回 JSON 格式:
{
    "score": 0.0-1.0,
    "dimensions": {
        "completeness": 0.0-1.0,
        "structure": 0.0-1.0,
        "accuracy": 0.0-1.0,
        "conciseness": 0.0-1.0,
        "actionability": 0.0-1.0
    },
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}
""",
                tags=["validation", "quality"],
            ),
            
            "content_analyzer": PromptTemplate(
                name="content_analyzer",
                description="内容预分析模板",
                content="""你是一个文档分析专家。请快速分析以下文档，给出简要判断。

文档路径: {{file_path}}
文档类型: {{file_type}}
内容预览（前3000字符）:
```
{{content_preview}}
```

请返回 JSON:
{
    "brief_summary": "一句话概括",
    "content_type": "technical_doc/meeting_notes/code/requirements/design_doc/knowledge_base/personal_notes/data/other",
    "key_topics": ["主题1", "主题2"],
    "estimated_value": 0.0-1.0,
    "suggested_action": "process/skip/merge",
    "reasoning": "简要解释"
}
""",
                tags=["analysis", "preprocessing"],
            ),
        }
        
        for name, template in builtin_templates.items():
            self._templates[name] = template
            self._versions[name].append(PromptVersion(
                template=template,
                version=template.version,
                created_at=template.created_at,
                is_active=True,
            ))
    
    def _load_user_templates(self) -> None:
        """加载用户模板"""
        if not self.templates_dir.exists():
            return
        
        for template_file in self.templates_dir.glob("*.yaml"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                if data and "name" in data and "content" in data:
                    template = PromptTemplate.from_dict(data)
                    self._templates[template.name] = template
                    
                    # 加载版本历史
                    versions_file = template_file.with_suffix(".versions.yaml")
                    if versions_file.exists():
                        with open(versions_file, 'r', encoding='utf-8') as f:
                            versions_data = yaml.safe_load(f)
                        
                        if versions_data:
                            for v_data in versions_data:
                                version = PromptVersion(
                                    template=PromptTemplate.from_dict(v_data.get("template", data)),
                                    version=v_data.get("version", "1.0.0"),
                                    created_at=v_data.get("created_at", time.time()),
                                    author=v_data.get("author"),
                                    change_log=v_data.get("change_log", ""),
                                    is_active=v_data.get("is_active", False),
                                )
                                self._versions[template.name].append(version)
                    
                    logger.debug(f"📋 Loaded user template: {template.name}")
            except Exception as e:
                logger.warning(f"📋 Failed to load template {template_file}: {e}")
    
    def get(self, name: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(name)
    
    def get_or_default(self, name: str, default_name: str = "default_extractor") -> PromptTemplate:
        """获取模板，不存在则返回默认"""
        template = self.get(name)
        if template is None:
            template = self.get(default_name)
            if template is None:
                raise ValueError(f"Template not found: {name} (default also not found)")
        return template
    
    def list_templates(self, tag: Optional[str] = None) -> List[PromptTemplate]:
        """列出所有模板"""
        templates = list(self._templates.values())
        
        if tag:
            templates = [t for t in templates if tag in t.tags]
        
        return sorted(templates, key=lambda t: t.name)
    
    def save(self, template: PromptTemplate) -> None:
        """保存模板"""
        # 更新版本历史
        if template.name in self._templates:
            old_template = self._templates[template.name]
            # 保存旧版本
            self._versions[template.name].append(PromptVersion(
                template=old_template,
                version=old_template.version,
                created_at=old_template.created_at,
            ))
            # 更新版本号
            template.version = self._bump_version(old_template.version)
        
        template.updated_at = time.time()
        self._templates[template.name] = template
        
        # 保存到文件
        template_file = self.templates_dir / f"{template.name}.yaml"
        with open(template_file, 'w', encoding='utf-8') as f:
            yaml.dump(template.to_dict(), f, default_flow_style=False, allow_unicode=True)
        
        # 保存版本历史
        versions_file = template_file.with_suffix(".versions.yaml")
        versions_data = [
            {
                "template": v.template.to_dict(),
                "version": v.version,
                "created_at": v.created_at,
                "author": v.author,
                "change_log": v.change_log,
                "is_active": v.is_active,
            }
            for v in self._versions.get(template.name, [])
        ]
        with open(versions_file, 'w', encoding='utf-8') as f:
            yaml.dump(versions_data, f, default_flow_style=False, allow_unicode=True)
        
        if self.on_template_saved:
            self.on_template_saved(template)
        
        logger.info(f"📋 Saved template: {template.name} (v{template.version})")
    
    def delete(self, name: str) -> bool:
        """删除模板"""
        if name not in self._templates:
            return False
        
        del self._templates[name]
        
        # 删除文件
        template_file = self.templates_dir / f"{name}.yaml"
        if template_file.exists():
            template_file.unlink()
        
        versions_file = template_file.with_suffix(".versions.yaml")
        if versions_file.exists():
            versions_file.unlink()
        
        logger.info(f"📋 Deleted template: {name}")
        return True
    
    def render(self, name: str, **kwargs) -> str:
        """渲染模板"""
        template = self.get(name)
        if template is None:
            raise ValueError(f"Template not found: {name}")
        
        # 验证变量
        errors = template.validate(**kwargs)
        if errors:
            raise ValueError(f"Template validation failed: {errors}")
        
        return template.render(**kwargs)
    
    def get_versions(self, name: str) -> List[PromptVersion]:
        """获取模板的所有版本"""
        return self._versions.get(name, [])
    
    def rollback(self, name: str, version: str) -> bool:
        """回滚到指定版本"""
        versions = self._versions.get(name, [])
        target = next((v for v in versions if v.version == version), None)
        
        if target is None:
            return False
        
        # 停用当前版本
        for v in versions:
            v.is_active = False
        
        # 激活目标版本
        target.is_active = True
        self._templates[name] = target.template
        
        logger.info(f"📋 Rolled back template {name} to v{version}")
        return True
    
    def score_template(
        self,
        name: str,
        score: float,
        feedback: Optional[str] = None,
        is_positive: bool = True,
    ) -> None:
        """对模板评分"""
        template = self.get(name)
        if template is None:
            return
        
        key = f"{name}:{template.version}"
        
        if key not in self._scores:
            self._scores[key] = PromptScore(
                template_name=name,
                version=template.version,
                score=0.0,
            )
        
        score_obj = self._scores[key]
        score_obj.feedback_count += 1
        
        if is_positive:
            score_obj.positive_count += 1
        else:
            score_obj.negative_count += 1
        
        # 更新平均分
        score_obj.score = score_obj.positive_count / max(score_obj.feedback_count, 1)
        
        if feedback:
            if "feedbacks" not in score_obj.metadata:
                score_obj.metadata["feedbacks"] = []
            score_obj.metadata["feedbacks"].append({
                "score": score,
                "feedback": feedback,
                "is_positive": is_positive,
                "timestamp": time.time(),
            })
        
        logger.debug(f"📋 Scored template {name} v{template.version}: {score:.2f}")
    
    def get_best_template(self, tag: str) -> Optional[PromptTemplate]:
        """获取评分最高的模板"""
        templates = self.list_templates(tag=tag)
        
        if not templates:
            return None
        
        # 按评分排序
        scored_templates = []
        for t in templates:
            key = f"{t.name}:{t.version}"
            score = self._scores.get(key, PromptScore(
                template_name=t.name,
                version=t.version,
                score=0.5,
            )).score
            scored_templates.append((score, t))
        
        scored_templates.sort(key=lambda x: x[0], reverse=True)
        return scored_templates[0][1] if scored_templates else None
    
    def export_all(self, output_path: str) -> None:
        """导出所有模板"""
        data = {
            "templates": {
                name: template.to_dict()
                for name, template in self._templates.items()
            },
            "versions": {
                name: [
                    {
                        "version": v.version,
                        "created_at": v.created_at,
                        "author": v.author,
                        "change_log": v.change_log,
                        "is_active": v.is_active,
                    }
                    for v in versions
                ]
                for name, versions in self._versions.items()
            },
            "scores": {
                key: {
                    "template_name": s.template_name,
                    "version": s.version,
                    "score": s.score,
                    "feedback_count": s.feedback_count,
                    "positive_count": s.positive_count,
                    "negative_count": s.negative_count,
                }
                for key, s in self._scores.items()
            },
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📋 Exported {len(self._templates)} templates to {output_path}")
    
    def import_all(self, input_path: str) -> None:
        """导入模板"""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for name, template_data in data.get("templates", {}).items():
            template = PromptTemplate.from_dict(template_data)
            self._templates[name] = template
        
        logger.info(f"📋 Imported {len(data.get('templates', {}))} templates from {input_path}")
    
    @staticmethod
    def _bump_version(version: str) -> str:
        """版本号递增"""
        parts = version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except ValueError:
            parts.append("1")
        return ".".join(parts)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "total_templates": len(self._templates),
            "templates": [
                {
                    "name": t.name,
                    "version": t.version,
                    "tags": t.tags,
                    "variables": len(t.variables),
                }
                for t in self._templates.values()
            ],
            "total_versions": sum(len(v) for v in self._versions.values()),
            "total_scores": len(self._scores),
        }


# ==================== 便捷函数 ====================

# 全局单例
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """获取全局 PromptManager 实例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def render_template(name: str, **kwargs) -> str:
    """渲染模板（便捷函数）"""
    return get_prompt_manager().render(name, **kwargs)


def get_template(name: str) -> Optional[PromptTemplate]:
    """获取模板（便捷函数）"""
    return get_prompt_manager().get(name)


def list_templates(tag: Optional[str] = None) -> List[PromptTemplate]:
    """列出模板（便捷函数）"""
    return get_prompt_manager().list_templates(tag=tag)


def save_template(template: PromptTemplate) -> None:
    """保存模板（便捷函数）"""
    get_prompt_manager().save(template)


def score_template(name: str, score: float, feedback: Optional[str] = None, is_positive: bool = True) -> None:
    """评分模板（便捷函数）"""
    get_prompt_manager().score_template(name, score, feedback, is_positive)
