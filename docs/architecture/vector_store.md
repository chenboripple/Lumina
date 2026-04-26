# Vector Store 模块文档

## 🎯 模块定位

Vector Store 是 Lumina 的**语义大脑**，基于 ChromaDB 实现向量存储、语义搜索、知识关联和知识图谱构建。

## ✨ 核心能力

### 1. 🔍 语义搜索
- **向量相似度搜索**：基于内容语义而非关键词匹配
- **自然语言查询**：用自然语言描述搜索意图
- **相关性排序**：按语义相似度排序结果

### 2. 🔗 知识关联
- **自动发现关联**：基于语义相似度自动发现笔记关联
- **相似度阈值**：可配置最小相似度阈值
- **关联强度**：返回关联分数，量化关联强度

### 3. 📊 知识图谱
- **自动构建图谱**：基于向量相似度构建知识图谱
- **节点和边**：支持节点（笔记）和边（关联）
- **聚类分析**：自动发现知识主题聚类

### 4. 💾 持久化存储
- **本地存储**：向量数据持久化到本地磁盘
- **增量更新**：支持添加、更新、删除文档
- **元数据过滤**：基于标签、类型等过滤搜索

### 5. 🏷️ 混合搜索
- **语义 + 关键词**：结合语义搜索和关键词匹配
- **加权排序**：综合语义分数和关键词分数
- **灵活过滤**：支持多种过滤条件

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│              Vector Store 模块               │
├─────────────────────────────────────────────┤
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │        Embedding Provider            │    │
│  │  ┌─────────┐  ┌─────────────────┐  │    │
│  │  │  Local  │  │    OpenAI API   │  │    │
│  │  │(MiniLM) │  │  (text-embedding)│  │    │
│  │  └─────────┘  └─────────────────┘  │    │
│  └─────────────────────────────────────┘    │
│                     ↓                        │
│  ┌─────────────────────────────────────┐    │
│  │         ChromaDB Collection          │    │
│  │  ┌─────────┐  ┌─────────┐          │    │
│  │  │Document │  │Document │  ...     │    │
│  │  │+ Vector │  │+ Vector │          │    │
│  │  │+ Metadata│  │+ Metadata│         │    │
│  │  └─────────┘  └─────────┘          │    │
│  └─────────────────────────────────────┘    │
│                     ↓                        │
│  ┌─────────────────────────────────────┐    │
│  │         Search & Analysis            │    │
│  │  ┌─────────┐  ┌─────────┐          │    │
│  │  │ Semantic│  │Knowledge│          │    │
│  │  │ Search  │  │  Graph  │          │    │
│  │  └─────────┘  └─────────┘          │    │
│  └─────────────────────────────────────┘    │
│                                              │
└─────────────────────────────────────────────┘
```

## 📋 数据结构

### VectorDocument（向量文档）
```python
@dataclass
class VectorDocument:
    id: str                    # 文档唯一标识
    content: str               # 文档内容
    metadata: Dict[str, Any]   # 元数据（标题、标签、来源等）
    embedding: List[float]     # 嵌入向量（可选）
```

### SearchResult（搜索结果）
```python
@dataclass
class SearchResult:
    document: VectorDocument   # 文档
    score: float               # 相似度分数（0~1）
    distance: float            # 向量距离
```

## 🚀 快速使用

### 初始化向量数据库
```python
from lumina.vector_store import VectorStore, EmbeddingProvider

# 使用本地模型（默认）
vector_store = VectorStore(
    collection_name="my_notes",
    persist_directory="./.lumina/vector_store"
)

# 使用 OpenAI Embedding API
vector_store = VectorStore(
    collection_name="my_notes",
    embedding_provider_config={
        "provider": "openai",
        "model": "text-embedding-ada-002",
        "api_key": "your-api-key"
    }
)
```

### 添加笔记
```python
# 添加单条笔记
doc_id = vector_store.add_note(
    note_id="note_001",
    title="Python 异步编程",
    content="asyncio 是 Python 的异步编程库...",
    tags=["python", "async", "programming"],
    source="./notes/python_async.md"
)

# 批量添加笔记
from lumina.executor import NoteOutput

for note in notes:
    vector_store.add_note(
        note_id=note.source,
        title=note.title,
        content=note.content,
        tags=note.tags,
        source=note.source,
        metadata=note.metadata
    )
```

### 语义搜索
```python
# 自然语言搜索
results = vector_store.search(
    query="Python 异步编程的最佳实践",
    n_results=5
)

for result in results:
    print(f"标题: {result.document.metadata['title']}")
    print(f"相似度: {result.score:.2%}")
    print(f"内容: {result.document.content[:100]}...")
    print()
```

### 查找相似笔记
```python
# 查找与某篇笔记相似的内容
similar = vector_store.find_similar("note_001", n_results=5)

for result in similar:
    print(f"相似笔记: {result.document.metadata['title']}")
    print(f"相似度: {result.score:.2%}")
```

### 查找关联笔记
```python
# 查找关联笔记（用于构建知识图谱）
related = vector_store.find_related_notes(
    note_id="note_001",
    min_score=0.7
)

for note in related:
    print(f"关联: {note['title']} (score: {note['score']:.2f})")
```

## 🎛️ 配置参数

### EmbeddingProvider 配置
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| provider | str | "local" | 嵌入提供者：local/openai |
| model | str | "all-MiniLM-L6-v2" | 模型名称 |
| api_key | str | None | OpenAI API 密钥 |

### VectorStore 配置
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| collection_name | str | "lumina_notes" | 集合名称 |
| persist_directory | str | "./.lumina/vector_store" | 持久化目录 |
| embedding_provider | EmbeddingProvider | None | 自定义嵌入提供者 |
| embedding_provider_config | Dict | None | 嵌入提供者配置 |

## 📊 输出示例

### 搜索结果
```python
results = vector_store.search("Python 异步编程")

# 输出:
# [
#     SearchResult(
#         document=VectorDocument(
#             id="note_001",
#             content="asyncio 是 Python 的异步编程库...",
#             metadata={"title": "Python 异步编程", "tags": "[\"python\", \"async\"]"}
#         ),
#         score=0.92,
#         distance=0.08
#     ),
#     ...
# ]
```

### 知识图谱
```python
from lumina.vector_store import KnowledgeGraph

kg = KnowledgeGraph(vector_store)
graph = kg.build_graph(min_similarity=0.7)

print(f"节点数: {graph['stats']['total_nodes']}")
print(f"边数: {graph['stats']['total_edges']}")
print(f"平均度数: {graph['stats']['avg_degree']:.2f}")

# 输出:
# 节点数: 100
# 边数: 350
# 平均度数: 3.50
```

### 知识聚类
```python
clusters = kg.find_clusters(n_clusters=5)

for cluster in clusters:
    print(f"主题: {cluster['theme']}")
    print(f"笔记数: {cluster['document_count']}")
    for doc in cluster['documents'][:3]:
        print(f"  - {doc['title']}")
```

## 🔧 扩展开发

### 自定义嵌入模型
```python
class CustomEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_path: str):
        self.model_path = model_path
        # 加载自定义模型
        
    def embed(self, texts: List[str]) -> List[List[float]]:
        # 自定义嵌入逻辑
        embeddings = []
        for text in texts:
            # 使用自定义模型生成嵌入
            embedding = self._custom_embed(text)
            embeddings.append(embedding)
        return embeddings

# 使用自定义提供者
vector_store = VectorStore(
    embedding_provider=CustomEmbeddingProvider("./my_model")
)
```

### 自定义过滤条件
```python
# 按标签过滤
results = vector_store.search(
    query="Python",
    filter_metadata={"tags": "[\"python\"]"}
)

# 按来源过滤
results = vector_store.search(
    query="异步编程",
    filter_metadata={"source": "./notes/python"}
)
```

## 🎯 性能特性

- **O(1) 查询**：基于 HNSW 索引的近似最近邻搜索
- **本地存储**：数据持久化到本地，无需网络
- **增量更新**：支持动态添加、更新、删除
- **内存优化**：大数据集自动分页加载

## 🔒 安全特性

- **数据隔离**：每个集合独立存储
- **路径安全**：使用 Path 对象避免路径注入
- **输入验证**：检查文档 ID 和内容长度

## 📈 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|----------|----------|
| 0.2.0 | 2026-04-25 | 初始版本，语义搜索、知识图谱、聚类分析 |

---

## 🤝 贡献指南

1. 新搜索算法需要基准测试
2. 嵌入模型支持需要兼容性测试
3. 性能优化需要对比数据
4. 所有新功能需要文档说明
