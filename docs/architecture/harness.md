# Harness 模块 (Agent 增强版) 文档

## 🎯 模块定位

Harness 是 Lumina 的**核心大脑**，负责协调 Planner、Executor、Validator、Cache、History 五个模块，实现完整的知识萃取 Agent 工作流。

## ✨ 核心能力

### 1. 🧠 完整 Agent 工作流
- **规划 → 执行 → 验证 → 迭代修复 → 输出**
- 每个文件自动经历完整的质量优化循环
- 支持最多 3 轮迭代修复，直到达到质量阈值

### 2. ⚡ 增量处理
- **只处理变化的文件**，大幅提升重复运行速度
- 基于文件哈希和时间戳判断文件是否变化
- 未变化的文件自动跳过，无需重新处理

### 3. 💾 缓存集成
- **自动利用 LLM 缓存**，降低 API 调用成本
- 缓存命中时直接返回结果，无需调用 LLM
- 支持处理结果缓存，避免重复处理相同文件

### 4. 📜 历史记录
- **完整记录处理过程**，支持审计和回溯
- 记录每次迭代的得分、问题、修复建议
- 支持质量趋势分析和版本对比

### 5. 🚀 并行处理
- **多线程并发处理**，提升批量处理速度
- 可配置并行工作线程数（默认 4 个）
- 自动处理并发异常，不影响整体流程

### 6. 📊 实时进度
- **流式输出处理进度和状态**
- 显示每个文件的迭代过程、得分变化
- 最终生成完整的统计报告

### 7. 🛡️ 容错机制
- **处理失败时优雅降级**
- 单个文件失败不影响整体流程
- 自动记录错误信息，便于排查

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Harness (Agent 增强版)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Planner   │ →  │  Executor   │ →  │  Validator  │     │
│  │  (智能规划)  │    │  (智能执行)  │    │  (质量验证)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        ↓                   ↓                   ↓            │
│   增量扫描            LLM 缓存            历史对比          │
│   优先级排序          智能分块            质量报告          │
│   成本预估            迭代修复            修复建议          │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐                        │
│  │    Cache    │    │   History   │                        │
│  │  (三级缓存)  │    │  (历史记录)  │                        │
│  └─────────────┘    └─────────────┘                        │
│                                                              │
│  工作流程：                                                   │
│  扫描 → 增量过滤 → 规划 → [缓存检查] → 执行 → 验证 → [修复] → 输出 → 历史记录 │
│         ↑                                                              ↑    │
│         └──────────────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 📋 数据结构

### HarnessConfig（配置）
```python
@dataclass
class HarnessConfig:
    max_iterations: int = 3              # 最大迭代次数
    quality_threshold: float = 0.8       # 质量阈值
    output_dir: str = "./output"         # 输出目录
    vault_path: Optional[str] = None     # Obsidian 仓库路径
    plugin: str = "obsidian"             # 输出插件
    use_cache: bool = True               # 是否使用缓存
    incremental: bool = True             # 是否增量处理
    parallel: bool = True                # 是否并行处理
    max_workers: int = 4                 # 并行线程数
    stream_output: bool = False          # 是否流式输出
    enable_history: bool = True          # 是否启用历史
    quick_validation_first: bool = True  # 是否先快速验证
    allow_partial: bool = True           # 是否允许部分通过
    metadata_prefix: str = "lumina_"     # 元数据前缀
```

### HarnessState（运行状态）
```python
@dataclass
class HarnessState:
    session_id: str                      # 会话 ID
    start_time: float                    # 开始时间
    end_time: Optional[float]            # 结束时间
    total_files: int                     # 总文件数
    processed_files: int                 # 已处理文件数
    skipped_files: int                   # 跳过文件数
    failed_files: int                    # 失败文件数
    total_iterations: int                # 总迭代次数
    cache_hits: int                      # 缓存命中数
    cache_misses: int                    # 缓存未命中数
    total_cost: float                    # 总成本
    avg_score: float                     # 平均得分
    status: str                          # 运行状态
    errors: List[Dict]                   # 错误列表
```

## 🚀 快速使用

### 基础用法
```python
from lumina.harness import Harness, HarnessConfig

# 创建配置
config = HarnessConfig(
    max_iterations=3,
    quality_threshold=0.8,
    output_dir="./my_notes",
    use_cache=True,
    incremental=True,
)

# 初始化 Harness
harness = Harness(config)

# 执行处理
report = harness.run("./source_files")

# 查看结果
print(f"处理文件数: {report['statistics']['processed_files']}")
print(f"平均得分: {report['statistics']['avg_score']:.2f}")
print(f"缓存命中率: {report['statistics']['cache_hit_rate']:.1%}")
print(f"总耗时: {report['statistics']['total_duration']:.1f}s")
```

### 增量处理
```python
# 第一次运行：处理所有文件
report1 = harness.run("./source_files")
print(f"第一次处理: {report1['statistics']['processed_files']} 个文件")

# 第二次运行：只处理变化的文件
report2 = harness.run("./source_files")
print(f"第二次处理: {report2['statistics']['processed_files']} 个文件")
print(f"跳过的文件: {report2['statistics']['skipped_files']} 个")
```

### 查看处理状态
```python
# 实时查看运行状态
state = harness.get_state()
print(f"状态: {state['status']}")
print(f"已处理: {state['processed_files']}/{state['total_files']}")
print(f"平均得分: {state['avg_score']:.2f}")
print(f"已耗时: {state['elapsed_time']:.1f}s")
```

## 🎛️ 配置参数

### 核心配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_iterations | 3 | 每个文件最大迭代次数 |
| quality_threshold | 0.8 | 质量通过阈值 |
| output_dir | "./output" | 输出目录 |
| plugin | "obsidian" | 输出格式插件 |

### 性能配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| use_cache | True | 启用 LLM 缓存 |
| incremental | True | 启用增量处理 |
| parallel | True | 启用并行处理 |
| max_workers | 4 | 并行线程数 |

### 功能开关
| 参数 | 默认值 | 说明 |
|------|--------|------|
| enable_history | True | 记录处理历史 |
| quick_validation_first | True | 先快速验证 |
| allow_partial | True | 允许部分通过 |
| stream_output | False | 流式输出进度 |

## 📊 输出示例

### 执行报告
```json
{
  "session_id": "session_1714000000",
  "status": "completed",
  "config": {
    "max_iterations": 3,
    "quality_threshold": 0.8,
    "incremental": true,
    "parallel": true,
    "use_cache": true
  },
  "statistics": {
    "start_time": "2026-04-25T10:00:00",
    "end_time": "2026-04-25T10:05:30",
    "total_duration": 330.5,
    "total_files": 100,
    "processed_files": 15,
    "skipped_files": 85,
    "failed_files": 0,
    "total_iterations": 28,
    "cache_hits": 12,
    "cache_misses": 3,
    "cache_hit_rate": 0.8,
    "estimated_total_cost": 0.0125,
    "avg_score": 0.85,
    "score_distribution": {
      "A+": 5,
      "A": 6,
      "B": 3,
      "C": 1,
      "D": 0,
      "F": 0
    },
    "pass_rate": 1.0
  },
  "results": [
    {
      "source": "/path/to/file1.md",
      "file_type": "markdown",
      "file_size": 1024,
      "processed": true,
      "passed": true,
      "iterations": 2,
      "best_score": 0.88,
      "processing_time": 15.2
    }
  ],
  "errors": []
}
```

### 终端输出示例
```
[10:00:00] ============================================================
[10:00:00] 🚀 Lumina Harness v0.2.0 (Agent Enhanced)
[10:00:00] 🆔 Session ID: session_1714000000
[10:00:00] ⚙️  Config: max_iterations=3, quality_threshold=0.8, incremental=True, parallel=True
[10:00:00] ============================================================
[10:00:00] 📂 Phase 1: Scanning & Planning
[10:00:01] 📊 Found 100 files total
[10:00:01] ⚡ 15 files need processing (incremental mode)
[10:00:01] 🎯 Processing strategy: resource_aware
[10:00:01] 📦 Total batches: 3

[10:00:01] 🚀 Phase 2: Processing files
[10:00:01] 📦 Processing batch 1/3 (5 files)
[10:00:02] 📄 Processing: /path/to/file1.md
[10:00:05] ✨ Round 1: NEW BEST score=0.88, passed=True, issues=0
[10:00:05] ✅ Quality threshold reached!
[10:00:05] ✅ Processing complete, best score=0.88
[10:00:05] 💾 Saved: ./output/file1.md
...
[10:05:30] ✅ Batch completed in 329.4s

[10:05:30] 💾 Phase 3: Saving outputs
[10:05:30] ✅ Saved 15 files to ./output

[10:05:30] ============================================================
[10:05:30] 📊 Final Results
[10:05:30] ============================================================
[10:05:30] ✅ Status: completed
[10:05:30] ⏱️  Total Duration: 330.5s
[10:05:30] 📂 Total Files: 100
[10:05:30] ✅ Processed: 15
[10:05:30] ⏭️  Skipped: 85
[10:05:30] ❌ Failed: 0
[10:05:30] 🔄 Total Iterations: 28
[10:05:30] 💾 Cache Hit Rate: 80.0%
[10:05:30] ⭐ Average Score: 0.85
[10:05:30] 🎯 Pass Rate: 100.0%
[10:05:30] 💰 Estimated Cost: $0.0125

[10:05:30] 📈 Score Distribution:
[10:05:30]   A+: 5 ████████████████
[10:05:30]   A:  6 ███████████████████
[10:05:30]   B:  3 ██████████
[10:05:30]   C:  1 ███

[10:05:30] 🎉 Processing complete!
[10:05:30] ============================================================
```

## 🔧 扩展开发

### 自定义插件
```python
from lumina.plugins import BasePlugin

class CustomPlugin(BasePlugin):
    def format(self, note_data: NoteData) -> str:
        # 自定义输出格式
        return f"# {note_data.title}\n\n{note_data.content}"

# 注册插件
HarnessConfig(plugin="custom")
```

### 自定义质量阈值
```python
config = HarnessConfig(
    quality_threshold=0.9,  # 要求更高质量
    max_iterations=5,       # 更多迭代次数
    allow_partial=False,    # 不允许部分通过
)
```

### 处理结果回调
```python
class MyHarness(Harness):
    def _process_single(self, file_info, plan):
        result = super()._process_single(file_info, plan)
        
        # 自定义后处理
        if result["best_score"] < 0.7:
            print(f"⚠️  Low quality: {result['source']}")
        
        return result
```

## 🎯 性能特性

- **O(n) 扫描**：线性时间扫描文件
- **增量优化**：只处理变化的文件，速度提升 10x+
- **并行处理**：多线程并发，速度提升 2~4x
- **缓存优化**：缓存命中时速度提升 100x+
- **内存安全**：大文件分块处理，避免内存溢出

## 🔒 安全特性

- **路径安全**：使用 Path 对象避免路径注入
- **输入验证**：检查文件大小和类型
- **错误隔离**：单个文件失败不影响整体流程
- **资源限制**：限制最大迭代次数和并行线程数

## 📈 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|----------|----------|
| 0.1.0 | 2026-04-21 | 基础 Harness，支持 Planner/Executor/Validator 三元组 |
| 0.2.0 | 2026-04-25 | Agent 增强版，增量处理、缓存集成、历史记录、并行处理 |

---

## 🤝 贡献指南

1. 新功能需要附带单元测试
2. 性能优化需要基准测试数据
3. 文档更新需要同步更新
4. 所有 PR 需要通过代码审查
