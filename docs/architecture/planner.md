# Planner 模块 (Agent 增强版) 文档

## 🎯 模块定位

Planner 是 Lumina 的**智能决策大脑**，负责分析输入、制定最优处理策略，是 Agent 能力的核心体现。

## ✨ 核心能力

### 1. 🔍 智能扫描与变化检测
- 自动识别新增/修改的文件，支持增量处理
- 文件哈希校验，避免重复处理相同内容
- 跳过系统文件、隐藏文件、超大文件
- 支持按目录递归扫描

### 2. 📊 文件智能评估
- **优先级排序**：按文件类型、大小、重要性自动分配处理优先级
- **成本预估**：自动估算 LLM Token 消耗和处理成本
- **时间预估**：智能估算每个文件的处理时间
- **能力识别**：自动识别文件处理所需的特殊能力（OCR、视觉、PDF解析等）

### 3. 🧠 资源感知的批量策略
- 按文件大小智能分批次：小文件批量大，大文件批量小
- 按能力需求分批次：同类能力需求的文件一起处理
- 优先级保障：高优先级文件优先处理

### 4. 💾 缓存与增量处理
- 自动识别已处理文件，避免重复劳动
- 支持断点续传，程序中断后无需重新处理
- 缓存命中统计，提升处理效率

### 5. 📈 处理计划可视化
- 生成结构化处理计划，包含完整的成本、时间、资源预估
- 友好的文本摘要输出，让用户提前了解处理规模

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│                   Planner                     │
├─────────────────────────────────────────────┤
│  1. 扫描器 (Scanner)                         │
│     - 文件发现                               │
│     - 哈希计算                               │
│     - 类型识别                               │
│                                             │
│  2. 评估器 (Evaluator)                       │
│     - 优先级计算                             │
│     - 成本/时间预估                          │
│     - 能力需求识别                           │
│                                             │
│  3. 批次生成器 (Batcher)                     │
│     - 智能分批次                             │
│     - 资源感知调度                           │
│                                             │
│  4. 状态管理器 (StateManager)                │
│     - 已处理文件追踪                         │
│     - 增量更新                               │
└─────────────────────────────────────────────┘
```

## 📋 数据结构

### FileInfo（文件信息）
```python
@dataclass
class FileInfo:
    path: Path                    # 文件路径
    type: str                     # 文件类型
    size: int                     # 文件大小（字节）
    modified: float               # 修改时间
    hash: str                     # 内容哈希（MD5）
    processing_priority: int      # 处理优先级（0最高）
    estimated_cost: float         # 预估成本（美元）
    estimated_time: float         # 预估时间（秒）
    required_capabilities: List[str]  # 需要的能力
```

### ProcessingPlan（处理计划）
```python
@dataclass
class ProcessingPlan:
    plan_id: str                  # 计划ID
    created_at: float             # 创建时间
    total_files: int              # 总文件数
    total_estimated_cost: float   # 总成本预估
    total_estimated_time: float   # 总时间预估
    batches: List[List[FileInfo]] # 处理批次
    strategy: str                 # 处理策略描述
    priorities: Dict              # 优先级分组
    capabilities_required: List[str]  # 需要的能力
    cache_hits: int               # 缓存命中数
    incremental_files: int        # 增量文件数
```

## 🚀 快速使用

### 基础用法
```python
from lumina.planner import Planner
from lumina.cache import CacheManager

# 初始化
cache_manager = CacheManager()
planner = Planner(cache_manager=cache_manager)

# 扫描目录
files = planner.scan("/path/to/your/documents")
print(f"找到 {len(files)} 个需要处理的文件")

# 制定计划
plan = planner.plan(files)

# 打印计划摘要
print(planner.get_plan_summary(plan))

# 执行计划...
```

### 增量扫描
```python
# 只扫描新增/修改的文件（默认开启）
files = planner.scan("/path/to/your/documents", incremental=True)
```

### 全量扫描
```python
# 扫描所有文件，不管是否处理过
files = planner.scan("/path/to/your/documents", incremental=False)
```

## 🎛️ 配置参数

### 优先级规则
| 优先级 | 文件类型 | 说明 |
|--------|----------|------|
| 0（最高） | Markdown、文本文件（<100KB） | 笔记类优先处理 |
| 1 | 代码、配置文件 | 重要结构化数据 |
| 2 | PDF、Word、Excel | 文档类 |
| 3 | 图片、媒体文件 | 资源类 |
| 4（最低） | 大文件、其他类型 | 低优先级 |

### 批量规则
| 文件大小 | 批量大小 | 说明 |
|----------|----------|------|
| <100KB | 20 | 小文件批量大，提升处理效率 |
| 100KB~1MB | 10 | 中等文件批量适中 |
| >1MB | 3 | 大文件批量小，避免OOM |

### 阈值配置
```python
# 可配置阈值
SMALL_FILE_THRESHOLD = 100 * 1024  # 100KB
LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
HUGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
```

## 📊 输出示例

### 计划摘要
```
📋 处理计划 #a1b2c3d4
📂 总文件数: 126
💰 预估成本: $0.2450
⏱️  预估时间: 125.3s
📦 批次数: 14
💡 处理策略: 35个markdown，28个code，22个image，20个pdf，14个data，3个大文件批次，7个中等文件批次，4个小文件批次处理
⚡ 缓存命中: 42 个文件
🔄 增量文件: 126 个文件
🛠️  需要能力: pdf_parsing, vision
🔝 高优先级文件 (35): README.md, INSTALL.md, CONFIG.md...
```

## 🔧 扩展开发

### 添加新的文件类型支持
```python
# 在 Planner.SUPPORTED_TYPES 中添加
SUPPORTED_TYPES = {
    '.md': 'markdown',
    '.txt': 'text',
    '.docx': 'document',  # 新增
    # ...
}
```

### 自定义优先级规则
```python
def _evaluate_file(self, file_info: FileInfo) -> FileInfo:
    # 自定义优先级逻辑
    if "重要" in file_info.path.name:
        file_info.processing_priority = 0  # 强制最高优先级
    # ... 其他逻辑
```

### 添加新的能力识别
```python
# 在 _evaluate_file 中添加
if file_info.path.suffix == '.docx':
    file_info.required_capabilities.append('docx_parsing')
```

## 🎯 性能特性

- **O(n) 扫描速度**：线性时间扫描目录
- **哈希缓存**：文件哈希只计算一次
- **增量处理**：二次扫描只处理变化的文件，速度提升10~50x
- **内存高效**：文件内容按需加载，不会一次性加载所有文件

## 🔒 安全特性

- 自动跳过系统文件和隐藏文件
- 自动跳过超大文件（>100MB）
- 路径注入防护
- 安全的哈希计算

## 📈 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|----------|----------|
| 0.1.0 | 2026-04-25 | 初始版本，基础文件扫描与计划 |
| 0.2.0 | 2026-04-25 | Agent 能力增强，缓存、增量、批量策略 |

---

## 🤝 贡献指南

1. 优先级逻辑修改需要附带性能测试
2. 新增文件类型需要在文档中更新类型列表
3. 性能敏感代码需要做内存和速度测试
4. 所有新功能需要附带单元测试
