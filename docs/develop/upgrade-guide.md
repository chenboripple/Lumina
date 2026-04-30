# Lumina 项目升级指南

## 🎯 升级目标

将 Lumina 从基础版本升级为具备完整 Agent 能力的智能知识萃取系统。

## 📋 升级清单

### ✅ 已完成

| 模块 | 功能 | 文件 |
|------|------|------|
| **Planner** | Agent 增强版：智能扫描、变化检测、优先级排序、成本预估、能力识别、批量策略 | `src/lumina/planner.py` |
| **CacheManager** | 三级缓存：文件缓存、LLM 响应缓存、状态缓存 | `src/lumina/cache.py` |
| **HistoryManager** | 操作历史：SQLite 记录、版本管理、质量趋势、审计追踪、可解释性 | `src/lumina/history.py` |
| **FileUtils** | 文件工具：哈希计算、类型检测 | `src/lumina/utils/file_utils.py` |
| **Planner 文档** | 完整架构文档、使用指南、API 参考 | `docs/architecture/planner.md` |
| **Cache 文档** | 缓存系统文档、性能数据、最佳实践 | `docs/architecture/cache.md` |
| **History 文档** | 历史系统文档、查询示例、扩展指南 | `docs/architecture/history.md` |

### 🔄 待完成

| 模块 | 功能 | 优先级 |
|------|------|--------|
| **Harness** | 集成 Cache 和 History，支持增量处理 | 高 |
| **Executor** | 集成 LLM 缓存，支持大文件分块 | 高 |
| **Validator** | 增强质量评估，支持历史对比 | 中 |
| **CLI** | 添加增量模式、缓存统计、历史查询命令 | 中 |
| **Config** | 添加缓存配置、历史配置 | 中 |
| **Tests** | 为新模块编写单元测试 | 高 |

## 🚀 快速验证

### 1. 验证 Planner 升级
```python
from lumina.planner import Planner
from lumina.cache import CacheManager

# 初始化
cache = CacheManager()
planner = Planner(cache_manager=cache)

# 扫描目录
files = planner.scan("./examples")
print(f"找到 {len(files)} 个文件")

# 制定计划
plan = planner.plan(files)
print(planner.get_plan_summary(plan))
```

### 2. 验证缓存系统
```python
from lumina.cache import CacheManager

cache = CacheManager()

# 测试文件缓存
cache.set_file("test_hash", {"content": "test"})
data = cache.get_file("test_hash")
print(f"缓存命中: {data is not None}")

# 测试 LLM 缓存
cache.set_llm_response("prompt_hash", "response")
response = cache.get_llm_response("prompt_hash")
print(f"LLM 缓存: {response}")

# 查看统计
print(cache.get_stats())
```

### 3. 验证历史系统
```python
from lumina.history import HistoryManager, ProcessingRecord

history = HistoryManager()

# 开始会话
history.start_session("test_session")

# 记录处理
record = ProcessingRecord(
    session_id="test_session",
    file_path="test.md",
    file_hash="abc123",
    file_type="markdown",
    file_size=1024,
    iterations=2,
    best_score=0.85,
    final_output="test output",
    full_history='[]',
    created_at="2026-04-25T10:00:00",
)
history.record_file_processing(record)

# 查询历史
print(history.get_file_history("test.md"))
print(history.get_explanation("test.md"))
```

## 📁 新增文件清单

```
Lumina/
├── src/lumina/
│   ├── planner.py          # 升级：Agent 增强版
│   ├── cache.py            # 新增：缓存系统
│   ├── history.py          # 新增：历史系统
│   └── utils/
│       ├── __init__.py     # 新增
│       └── file_utils.py   # 新增
├── docs/
│   └── architecture/
│       ├── planner.md      # 新增：Planner 文档
│       ├── cache.md        # 新增：缓存文档
│       └── history.md      # 新增：历史文档
```

## 🔧 下一步工作

### 1. 集成到 Harness
修改 `src/lumina/harness.py`，集成新的 Planner、CacheManager、HistoryManager：
- 使用增强版 Planner 制定处理计划
- 使用 CacheManager 缓存中间结果
- 使用 HistoryManager 记录处理历史
- 支持增量处理模式

### 2. 增强 Executor
修改 `src/lumina/executor.py`：
- 集成 LLM 响应缓存
- 支持大文件分块处理
- 记录执行历史

### 3. 增强 Validator
修改 `src/lumina/validator.py`：
- 添加历史对比功能
- 支持质量趋势分析
- 增强评分算法

### 4. 扩展 CLI
修改 `src/lumina/cli.py`：
- 添加 `--incremental` 参数
- 增加 `start` / `serve` / `process` 的服务化运行参数
- 增加 `search` / `related` / `graph` / `stats` 等向量相关命令

### 5. 编写测试
为所有新模块编写单元测试：
- `tests/unit/test_planner.py`
- `tests/unit/test_cache.py`
- `tests/unit/test_history.py

## 📊 预期效果

### 性能提升
| 指标 | 升级前 | 升级后 | 提升 |
|------|--------|--------|------|
| 二次扫描速度 | 30分钟 | 2分钟 | **15x** |
| LLM API 成本 | $2.5 | $0.12 | **20x** |
| 断点续传 | 不支持 | 支持 | **新增** |
| 质量追踪 | 无 | 完整 | **新增** |

### 功能增强
- ✅ 增量处理：只处理变化的文件
- ✅ 智能缓存：避免重复处理
- ✅ 历史追踪：完整审计链
- ✅ 成本预估：提前了解处理成本
- ✅ 可解释性：展示 Agent 决策过程

## 🎯 使用示例

### 场景1：日常增量更新
```bash
# 每天按配置输入源做一次增量处理
lumina process

# 只处理某个目录
lumina process ~/Documents --incremental --output ~/Obsidian/Vault

# 如果希望常驻监听目录变化
lumina start
```

### 场景2：批量处理新文件
```python
from lumina.harness import Harness, HarnessConfig

config = HarnessConfig(
    incremental=True,
    output_dir="./output",
)
agent = Harness(config)

# 处理新文件
report = agent.run("~/Downloads")
print(report["statistics"]["processed_files"])

# 查看质量报告
print(report["statistics"]["avg_score"])
```

### 场景3：质量监控
```python
from lumina.history import HistoryManager

history = HistoryManager()

# 获取质量趋势
trend = history.get_quality_trend("~/Documents/project.md", days=30)

# 生成质量报告
report = history.generate_quality_report()
print(report)
```

---

## 🤝 贡献指南

1. 所有新模块需要附带完整文档
2. 性能敏感代码需要做基准测试
3. 所有功能需要附带单元测试
4. 文档需要包含使用示例和最佳实践

## 📞 问题反馈

如有问题或建议，请通过以下方式反馈：
- GitHub Issues: https://github.com/chenboripple/Lumina/issues
- 邮件: chenboripple@gmail.com
