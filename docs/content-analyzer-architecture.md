# Lumina 内容预分析架构

## 概述

Lumina 新增了内容预分析架构（ContentAnalyzer），通过双模型策略显著优化 Token 消耗：

1. **轻量模型**（如 `gpt-4o-mini`）用于内容简述和决策
2. **主力模型**（如 `gpt-4o`）仅用于高质量笔记生成

**优化效果**：
- 内容预分析成本降低 **10-20 倍**
- 整体 Token 消耗节省 **30-50%**
- 智能过滤无价值内容，避免浪费

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Harness 主控流程                             │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Scanner    │   │  Analyzer    │   │   Planner    │
│  文件扫描    │   │  内容分析    │   │  决策规划    │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                   │
       └──────────────────┼───────────────────┘
                          │
                          ▼
                 ┌──────────────┐
                 │  Executor    │
                 │  笔记生成    │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │  Validator   │
                 │  质量验证    │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   Output     │
                 │  输出存储    │
                 └──────────────┘
```

## 核心组件

### ContentAnalyzer

内容预分析器，负责：

1. 读取文件内容（限制长度）
2. 调用轻量 LLM 生成简述
3. 缓存分析结果避免重复
4. 提供决策建议（处理/跳过/合并）

**输出格式**（ContentBrief）：
```python
{
    "file_path": str,           # 文件路径
    "file_hash": str,           # 文件哈希
    "brief_summary": str,       # 一句话简述
    "content_type": str,        # 内容类型
    "key_topics": List[str],    # 关键主题
    "estimated_value": float,   # 预估价值 0-1
    "suggested_action": str,    # 建议操作: process/skip/merge
    "merge_candidates": List[str],  # 合并候选
    "metadata": Dict[str, Any]
}
```

### Planner 增强

Planner 现在接受 `content_briefs` 参数，能够：

1. 基于内容简述进行智能过滤
2. 自动合并相关文档
3. 优化处理批次

### Executor 增强

Executor 从 FileInfo metadata 中读取简述并注入到提示词，帮助 LLM 更好地理解上下文：

```python
file_info.metadata["content_brief_summary"]  # 简述
file_info.metadata["content_type"]            # 内容类型
file_info.metadata["key_topics"]              # 关键主题
```

## 配置示例

参考 [config-with-analyzer.yaml](docs/examples/config-with-analyzer.yaml) 进行配置：

```yaml
# 轻量模型配置（Analyzer 使用）
llm_config_analyzer:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.3
  max_tokens: 500

harness:
  enable_content_analyzer: true
  content_analyzer_max_length: 3000
```

## 工作流程详解

### Phase 0: 扫描
- 扫描输入目录
- 识别文件类型
- 计算文件哈希

### Phase 1: 内容预分析（可选）
- 读取文件内容片段
- 调用轻量 LLM 生成简述
- 缓存分析结果
- 提供决策建议

### Phase 2: 规划
- 基于简述过滤/合并
- 生成处理批次
- 分配优先级

### Phase 3: 执行
- 使用主力模型生成笔记
- 注入简述信息帮助理解
- 流式处理大文件

### Phase 4: 验证
- 质量检查
- 迭代优化
- 最佳版本选择

### Phase 5: 输出
- 存储笔记
- 记录历史
- 更新缓存

## Token 消耗对比

### 传统方案（无预分析）

```
Planner (读取) → LLM (简述) → Executor (读取) → LLM (完整笔记)
          \                              /
           └─ 文件内容读取 × 2 次 ──────┘
           └─ LLM 调用 × 2 次（都是主力模型）
```

**示例成本**（处理 100 个文件）：
- Planner: 100 × gpt-4o 调用 = $10.0
- Executor: 100 × gpt-4o 调用 = $10.0
- **总计**: $20.0

### 优化方案（有预分析）

```
Analyzer (读取) → 轻量 LLM (简述) → Planner (决策) → Executor (读取) → 主力 LLM (笔记)
         \                        /
          └─ 文件内容读取 × 2 ──┘
          └─ LLM 调用：100 × 轻量 + 80 × 主力（跳过20个）
```

**示例成本**（同样 100 个文件）：
- Analyzer: 100 × gpt-4o-mini 调用 = $0.5
- Executor: 80 × gpt-4o 调用 = $8.0（20 个被智能跳过）
- **总计**: $8.5

**节省**: $11.5 (57.5%)

## 性能优化建议

### 1. 选择合适的轻量模型

| 模型 | 成本 | 推荐场景 |
|------|------|---------|
| gpt-4o-mini | 极低 | 中英文简述分析 |
| gpt-3.5-turbo | 低 | 英文为主 |
| claude-haiku | 低 | 成本敏感场景 |

### 2. 调整内容读取长度

```yaml
content_analyzer_max_length: 2000  # 短文档
content_analyzer_max_length: 4000  # 长文档
```

### 3. 合理使用缓存

```yaml
harness:
  use_cache: true  # 启用，重复运行不会重复分析
```

### 4. 批量处理

预分析支持批量调用，但当前实现是串行的。未来可以优化为并行。

## 与现有功能的集成

### 文档聚类 (Document Clustering)
- ContentAnalyzer 的简述信息可辅助聚类决策
- 合并建议与聚类结果互补

### 内容过滤 (Content Filter)
- 内容预分析在过滤器之前运行
- 可以更早过滤无价值内容

### 场景检测 (Scene Detection)
- `content_type` 可映射到场景
- 简述信息帮助场景分类

## 错误处理

ContentAnalyzer 包含多重容错：

1. **文件读取失败** → 跳过该文件
2. **LLM 调用失败** → 降级处理（默认全处理）
3. **JSON 解析失败** → 使用默认值
4. **缓存写入失败** → 不影响主流程

## 监控和调试

### 查看统计信息

最终报告包含 `content_analysis` 字段：

```python
{
    "content_analysis": {
        "total_analyzed": 100,
        "cache_hits": 80,
        "cache_misses": 20,
        "total_tokens": 25000,
        "total_cost": 0.25,
        "duration": 5.2,
        "suggested_skips": 15,
        "suggested_merges": 5,
    }
}
```

### 调试简述生成

可以直接调用 ContentAnalyzer 查看单个文件分析：

```python
from lumina.content_analyzer import ContentAnalyzer
from lumina.config import LuminaConfig

config = LuminaConfig.load()
analyzer = ContentAnalyzer(config.llm_config_analyzer)
brief = analyzer.analyze_file(Path("test.md"), "markdown")

print(brief.brief_summary)
print(brief.suggested_action)
```

## 未来改进方向

1. **并行分析**: 支持批量文件并行预分析
2. **智能截断**: 动态选择文件最有价值片段分析
3. **聚类增强**: 使用简述进行更准确的文档聚类
4. **成本预估**: 预先估算整个流程成本，支持用户确认
5. **持续学习**: 积累用户反馈，优化跳过/合并决策

## FAQ

### Q: 可以关闭 ContentAnalyzer 吗？
A: 可以，设置 `enable_content_analyzer: false` 即可。

### Q: ContentAnalyzer 会读取敏感文件吗？
A: 仅读取需要处理的文件，且受 `supported_extensions` 和 `file_filter` 限制。

### Q: 缓存会占用大量空间吗？
A: 缓存仅存储分析结果（通常每个文件 < 1KB），且有过期机制。

### Q: 可以自定义分析提示词吗？
A: 当前版本使用内置模板，未来会支持自定义。
