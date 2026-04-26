# Lumina 向量数据库集成说明

## 🎉 功能概述

Lumina 现在集成了强大的向量数据库能力，支持语义搜索、知识关联和知识图谱构建。

## ✨ 新增功能

### 1. 🔍 语义搜索
- **自然语言查询**：用自然语言描述搜索意图
- **向量相似度匹配**：基于内容语义而非关键词
- **相关度排序**：按语义相似度返回结果

### 2. 🔗 知识关联
- **自动发现关联**：基于语义相似度自动发现相关笔记
- **可配置阈值**：调整最小相似度阈值
- **关联强度量化**：返回关联分数，量化关联紧密程度

### 3. 📊 知识图谱
- **自动构建图谱**：基于向量相似度构建知识图谱
- **节点和边**：支持节点（笔记）和边（关联）
- **聚类分析**：自动发现知识主题聚类

### 4. ⚙️ 灵活配置
- **本地/OpenAI 嵌入**：支持本地 MiniLM 模型和 OpenAI 嵌入 API
- **持久化存储**：向量数据持久化到本地磁盘
- **增量索引**：处理新文件时自动增量索引

## 🚀 快速开始

### 安装依赖
```bash
# 核心依赖（本地嵌入 + 向量数据库）
pip install chromadb sentence-transformers

# 可选：使用 OpenAI Embedding API
pip install openai
```

### 基本使用

#### 1. 处理文件并自动索引
```bash
# 处理文件，自动索引到向量数据库
lumina process ./notes --vector
```

#### 2. 语义搜索
```bash
# 搜索相关笔记
lumina search "Python 异步编程最佳实践"

# 返回 10 条结果
lumina search "机器学习" -n 10

# 保存结果到文件
lumina search "架构设计" -o search_results.json
```

#### 3. 查找关联笔记
```bash
# 查找与指定笔记相关的内容
lumina related "./notes/python_async.md"

# 调整相似度阈值
lumina related "./notes/python_async.md" -s 0.8
```

#### 4. 构建知识图谱
```bash
# 构建知识图谱并保存到文件
lumina graph -o knowledge_graph.json

# 调整最小相似度
lumina graph -s 0.75
```

#### 5. 查看统计信息
```bash
lumina stats
```

### Python API 使用

```python
from lumina import Harness, HarnessConfig

# 初始化
config = HarnessConfig(
    enable_vector_store=True,
    embedding_provider="openai",  # 使用 OpenAI Embedding
    embedding_api_key="your-api-key"
)

harness = Harness(config)

# 处理文件
harness.run("./notes")

# 语义搜索
results = harness.search_notes("Python 异步编程")
for result in results:
    print(f"标题: {result['title']}, 相似度: {result['score']:.2%}")

# 查找关联笔记
related = harness.find_related_notes("./notes/python_async.md")

# 构建知识图谱
graph = harness.build_knowledge_graph()
print(f"节点数: {graph['stats']['total_nodes']}, 边数: {graph['stats']['total_edges']}")
```

## 🎛️ 配置选项

### 向量数据库配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| enable_vector_store | bool | True | 是否启用向量数据库 |
| vector_store_persist_dir | str | "./.lumina/vector_store" | 向量数据存储目录 |
| embedding_provider | str | "local" | 嵌入提供者：local/openai |
| embedding_model | str | None | 嵌入模型名称（local 默认为 all-MiniLM-L6-v2，openai 默认为 text-embedding-ada-002） |
| embedding_api_key | str | None | OpenAI API 密钥（使用 OpenAI 时需要） |

### 搜索配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| search_n_results | int | 5 | 默认返回搜索结果数量 |
| search_min_score | float | 0.0 | 最小相似度阈值 |

## 📊 性能对比

### 本地 vs OpenAI 嵌入
| 维度 | Local (MiniLM) | OpenAI Embedding |
|------|----------------|------------------|
| 速度 | 快（本地运行） | 中等（API 调用） |
| 成本 | 免费 | 付费（$0.0001 / 1K tokens） |
| 准确性 | 较好 | 非常好 |
| 离线使用 | 支持 | 不支持 |
| 模型大小 | ~80MB | 云端模型 |

### 建议
- 个人使用、对成本敏感：使用本地模型
- 企业使用、需要更高准确性：使用 OpenAI Embedding
- 首次处理大量文件时建议使用本地模型，速度更快

## 🔧 技术实现

### 核心组件
- **ChromaDB**：轻量级嵌入向量数据库
- **Sentence Transformers**：本地嵌入模型支持
- **OpenAI Embedding API**：云端嵌入支持
- **余弦相似度**：向量相似度计算
- **HNSW 索引**：近似最近邻快速搜索

### 存储结构
```
./.lumina/
└── vector_store/
    ├── chroma.sqlite3        # 元数据存储
    └── collections/
        └── lumina_notes/     # 笔记向量集合
            ├── data.parquet
            └── index/
```

## 📈 升级后的项目架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Lumina 知识萃取 Agent                      │
├─────────────────────────────────────────────────────────────┤
│  🔧 CLI / API               │  📊 报表 / 输出                  │
│  ───────────────────────────┼──────────────────────────────  │
│  🧠 Harness (协调器)        │  🔮 Vector Store (语义大脑)      │
│  • 工作流调度               │  • 语义搜索                     │
│  • 增量处理                 │  • 知识关联                     │
│  • 并行处理                 │  • 知识图谱                     │
│  • 容错机制                 │  • 聚类分析                     │
│  ───────────────────────────┼──────────────────────────────  │
│  📅 Planner / 🚀 Executor / ✅ Validator  (核心三元组)        │
│  ──────────────────────────────────────────────────────────  │
│  💾 Cache / 📜 History / 🔌 Plugins  (基础设施)                │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 核心优势

### 1. 零额外配置
- 默认启用本地嵌入模型，无需 API 密钥
- 自动安装依赖（chromadb 和 sentence-transformers）
- 自动增量索引，无需额外操作

### 2. 成本优化
- 本地嵌入完全免费
- 向量缓存避免重复计算
- 增量索引仅处理变化的文件

### 3. 高性能
- 基于 HNSW 索引的快速搜索（毫秒级）
- 支持百万级向量规模
- 内存高效存储

### 4. 可扩展
- 支持自定义嵌入模型
- 支持向量数据库扩展
- 开放 API 接口

## 🚀 下一步规划

1. **向量可视化**：Web 界面展示知识图谱
2. **自动标签推荐**：基于语义自动推荐标签
3. **知识图谱推理**：基于图谱的知识推理和补全
4. **多模态支持**：支持图片、PDF、文档等多模态内容
5. **向量同步**：支持多设备向量数据同步

## 📝 注意事项

1. 首次运行会自动下载 MiniLM 模型（~80MB）
2. 向量数据存储在 `./.lumina/vector_store` 目录
3. 使用 OpenAI Embedding 时需要网络连接
4. 大量文件首次索引可能需要较长时间（取决于文件数量和大小）

---

向量数据库功能已经完全集成到 Lumina 中，开箱即用，无需额外配置即可享受语义搜索和知识关联的强大能力！
