# Validator 模块 (Agent 增强版) 文档

## 🎯 模块定位

Validator 是 Lumina 的**质量守门员**，负责全面检查笔记质量，提供精确修复建议，确保输出内容达到高质量标准。

## ✨ 核心能力

### 1. 🔍 多维度质量检查
- **结构完整性**：检查标题、章节、层级结构
- **内容质量**：检查长度、标签、关键要点、链接
- **语义质量**：检查置信度、逻辑连贯性（可集成 LLM）
- **风格一致性**：检查 Markdown 格式、标点符号
- **元数据完整性**：检查必需字段、有效值

### 2. 📊 历史对比分析
- **版本对比**：与之前版本对比质量变化
- **趋势分析**：追踪质量提升/下降趋势
- **改进识别**：自动识别质量改进点

### 3. 🧠 智能修复建议
- **问题分类**：按严重程度（error/warning/info）分类
- **具体建议**：每个问题附带具体修复方案
- **自动修复标记**：标识哪些问题可以自动修复
- **优先级排序**：按重要性排序修复建议

### 4. 📈 质量报告生成
- **综合评分**：0~1 分综合质量得分
- **等级评定**：A+/A/B/C/D/F 等级
- **分类得分**：结构/内容/语义/风格/元数据各维度得分
- **优势识别**：自动识别内容优势
- **改进空间**：指出具体改进方向

### 5. 🎯 可配置规则
- **阈值配置**：支持自定义各项质量阈值
- **权重配置**：支持调整各维度权重
- **规则扩展**：支持添加自定义验证规则

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│                 Validator                    │
├─────────────────────────────────────────────┤
│  1. 结构检查器 (StructureChecker)            │
│     - 标题完整性                            │
│     - Markdown 结构                         │
│     - 必需章节                              │
│                                             │
│  2. 内容检查器 (ContentChecker)              │
│     - 长度检查                              │
│     - 标签数量                              │
│     - 关键要点                              │
│     - 链接质量                              │
│                                             │
│  3. 语义检查器 (SemanticChecker)             │
│     - 置信度检查                            │
│     - 逻辑连贯性（LLM）                      │
│                                             │
│  4. 风格检查器 (StyleChecker)                │
│     - 格式一致性                            │
│     - 标点符号                              │
│                                             │
│  5. 元数据检查器 (MetadataChecker)           │
│     - 必需字段                              │
│     - 有效值                                │
└─────────────────────────────────────────────┘
```

## 📋 数据结构

### ValidationIssue（验证问题）
```python
@dataclass
class ValidationIssue:
    type: str              # 问题类型
    severity: str          # 严重程度：error/warning/info
    message: str           # 问题描述
    details: Dict          # 详细信息
    fix_suggestion: str    # 修复建议
    auto_fixable: bool     # 是否可自动修复
```

### ValidationResult（验证结果）
```python
@dataclass
class ValidationResult:
    passed: bool           # 是否通过
    score: float           # 综合得分（0~1）
    issues: List[ValidationIssue]  # 问题列表
    suggestions: List[str] # 修复建议
    metadata: Dict         # 元数据
    quality_report: Dict   # 详细质量报告
    comparison_with_history: Dict  # 历史对比
```

## 🚀 快速使用

### 基础用法
```python
from lumina.validator import Validator
from lumina.executor import NoteOutput

# 初始化
validator = Validator()

# 创建笔记（示例）
note = NoteOutput(
    title="示例笔记",
    content="# 示例\n\n## Summary\n这是一个示例笔记。\n\n## Key Points\n- 要点1\n- 要点2",
    tags=["示例", "测试"],
    links=["相关主题"],
    source="example.md",
    metadata={"complexity": "simple", "confidence": 0.9}
)

# 验证
result = validator.validate(note)

print(f"通过: {result.passed}")
print(f"得分: {result.score:.2f}")
print(f"等级: {result.quality_report['grade']}")
print(f"问题数: {len(result.issues)}")

# 打印修复建议
for suggestion in result.suggestions:
    print(f"- {suggestion}")
```

### 使用历史对比
```python
from lumina.history import HistoryManager

# 初始化历史管理器
history = HistoryManager()

# 验证时传入历史管理器
validator = Validator(history_manager=history)

# 验证（自动进行历史对比）
result = validator.validate(note, file_info=file_info)

if result.comparison_with_history:
    comparison = result.comparison_with_history
    print(f"上次得分: {comparison['previous_score']:.2f}")
    print(f"当前得分: {comparison['current_score']:.2f}")
    print(f"变化: {'+' if comparison['improved'] else ''}{comparison['score_diff']:.2f}")
    print(f"趋势: {comparison['trend']}")
```

### 快速验证（不调用 LLM）
```python
# 快速验证（只检查基础规则）
result = validator.validate_quick(note)

print(f"快速验证通过: {result.passed}")
print(f"基础得分: {result.score:.2f}")
```

## 🎛️ 配置参数

### 默认阈值
| 参数 | 默认值 | 说明 |
|------|--------|------|
| content_min_length | 100 | 内容最小长度 |
| content_max_length | 50000 | 内容最大长度 |
| title_min_length | 3 | 标题最小长度 |
| title_max_length | 100 | 标题最大长度 |
| min_tag_count | 2 | 最少标签数 |
| max_tag_count | 10 | 最多标签数 |
| min_key_points | 2 | 最少关键要点 |
| max_link_ratio | 0.3 | 最大链接比例 |
| min_confidence | 0.6 | 最小置信度 |
| quality_threshold | 0.7 | 质量阈值 |

### 规则权重
| 维度 | 权重 | 说明 |
|------|------|------|
| structure | 0.25 | 结构完整性 |
| content | 0.30 | 内容质量 |
| semantic | 0.20 | 语义质量 |
| style | 0.15 | 风格一致性 |
| metadata | 0.10 | 元数据完整性 |

### 自定义配置
```python
# 自定义阈值
config = {
    "thresholds": {
        "content_min_length": 200,  # 要求更长内容
        "quality_threshold": 0.8,   # 要求更高质量
    }
}

validator = Validator(config=config)
```

## 📊 输出示例

### 质量报告
```python
report = result.quality_report

print(f"综合得分: {report['overall_score']:.2f}")
print(f"等级: {report['grade']}")

print("\n分类得分:")
for category, score in report['category_scores'].items():
    print(f"  {category}: {score:.2f}")

print("\n优势:")
for strength in report['strengths']:
    print(f"  ✓ {strength}")

print("\n改进空间:")
for area in report['improvement_areas']:
    print(f"  → {area}")

print("\n内容统计:")
stats = report['content_stats']
print(f"  总长度: {stats['total_length']} 字符")
print(f"  标题长度: {stats['title_length']} 字符")
print(f"  标签数: {stats['tag_count']}")
print(f"  链接数: {stats['link_count']}")
print(f"  标题数: {stats['header_count']}")
print(f"  列表项数: {stats['list_item_count']}")
```

### 问题列表
```python
for issue in result.issues:
    icon = "❌" if issue.severity == "error" else "⚠️" if issue.severity == "warning" else "ℹ️"
    print(f"{icon} [{issue.severity.upper()}] {issue.type}")
    print(f"   说明: {issue.message}")
    print(f"   建议: {issue.fix_suggestion}")
    print(f"   自动修复: {'是' if issue.auto_fixable else '否'}")
    print()
```

## 🔧 扩展开发

### 添加自定义验证规则
```python
class CustomValidator(Validator):
    def _check_custom(self, note_output):
        issues = []
        
        # 自定义规则：检查是否包含代码示例
        if "```" not in note_output.content:
            issues.append(ValidationIssue(
                type="missing_code_example",
                severity="info",
                message="技术文档建议包含代码示例",
                fix_suggestion="添加代码块示例",
                auto_fixable=False,
            ))
        
        return issues
    
    def validate(self, note_output, file_info=None, context=None):
        # 先调用父类验证
        result = super().validate(note_output, file_info, context)
        
        # 添加自定义检查
        custom_issues = self._check_custom(note_output)
        result.issues.extend(custom_issues)
        
        # 重新计算得分
        result.score = self._calculate_comprehensive_score(note_output, result.issues)
        
        return result
```

### 自定义评分算法
```python
def _calculate_comprehensive_score(self, note_output, issues):
    # 自定义评分逻辑
    base_score = 1.0
    
    # 根据问题类型和严重程度扣分
    for issue in issues:
        if issue.type == "content_too_short":
            base_score -= 0.5  # 内容太短扣更多分
        elif issue.severity == "error":
            base_score -= 0.2
        elif issue.severity == "warning":
            base_score -= 0.1
    
    # 自定义加分项
    if "最佳实践" in note_output.content:
        base_score += 0.1
    
    return max(0.0, min(1.0, base_score))
```

## 🎯 性能特性

- **O(n) 检查速度**：线性时间检查内容
- **快速模式**：validate_quick 不调用 LLM，速度极快
- **缓存支持**：可缓存验证结果，避免重复检查
- **增量验证**：只检查变化的部分

## 🔒 安全特性

- **输入验证**：检查内容长度，防止内存溢出
- **正则安全**：使用安全的正则表达式
- **错误降级**：检查失败时返回 warning 而不是 error

## 📈 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|----------|----------|
| 0.1.0 | 2026-04-21 | 基础验证规则 |
| 0.2.0 | 2026-04-25 | Agent 增强版，多维度检查、历史对比、质量报告 |

---

## 🤝 贡献指南

1. 新验证规则需要附带测试用例
2. 评分算法修改需要 A/B 测试验证
3. 性能敏感代码需要基准测试
4. 所有新功能需要文档说明
