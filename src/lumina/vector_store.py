"""
Vector Store - 向量数据库模块
基于 ChromaDB 实现语义搜索、知识关联、相似度查询
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 尝试导入 ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# 尝试导入 sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """搜索结果"""
    document: VectorDocument
    score: float
    distance: float


class EmbeddingProvider:
    """
    嵌入向量提供者
    
    支持多种嵌入模型：
    1. sentence-transformers (本地)
    2. OpenAI Embedding API
    3. 其他自定义模型
    """
    
    def __init__(self, provider: str = "local", model: str = None, api_key: str = None):
        self.provider = provider
        self.model_name = model
        self.api_key = api_key
        self._model = None
        
        if provider == "local":
            self._init_local_model()
        elif provider == "openai":
            self._init_openai_model()
    
    def _init_local_model(self):
        """初始化本地模型"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers not installed. "
                            "Install with: pip install sentence-transformers")
        
        # 默认使用轻量级模型
        model_name = self.model_name or "all-MiniLM-L6-v2"
        self._model = SentenceTransformer(model_name)
    
    def _init_openai_model(self):
        """初始化 OpenAI 模型"""
        if not self.api_key:
            raise ValueError("OpenAI API key required for OpenAI embedding provider")
        
        try:
            import openai
            openai.api_key = self.api_key
            self._client = openai
        except ImportError:
            raise ImportError("openai not installed. Install with: pip install openai")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        将文本转换为嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        if self.provider == "local":
            return self._embed_local(texts)
        elif self.provider == "openai":
            return self._embed_openai(texts)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型生成嵌入"""
        if self._model is None:
            self._init_local_model()
        
        embeddings = self._model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()
    
    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """使用 OpenAI API 生成嵌入"""
        model = self.model_name or "text-embedding-ada-002"
        
        response = self._client.embeddings.create(
            model=model,
            input=texts
        )
        
        return [item.embedding for item in response.data]
    
    def embed_single(self, text: str) -> List[float]:
        """嵌入单个文本"""
        embeddings = self.embed([text])
        return embeddings[0]


class VectorStore:
    """
    向量数据库管理器
    
    核心能力：
    1. 🔍 语义搜索 - 基于向量相似度搜索相关内容
    2. 🔗 知识关联 - 自动发现笔记之间的关联
    3. 📊 相似度分析 - 分析内容相似度
    4. 💾 持久化存储 - 本地存储向量数据
    5. 🏷️ 元数据过滤 - 基于标签、类型等过滤
    """
    
    def __init__(
        self,
        collection_name: str = "lumina_notes",
        persist_directory: str = "./.lumina/vector_store",
        embedding_provider: Optional[EmbeddingProvider] = None,
        embedding_provider_config: Dict[str, Any] = None
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # 初始化嵌入提供者
        if embedding_provider:
            self.embedding_provider = embedding_provider
        else:
            config = embedding_provider_config or {}
            self.embedding_provider = EmbeddingProvider(**config)
        
        # 初始化 ChromaDB
        self._init_chromadb()
        
        # 统计信息
        self.stats = {
            "total_documents": 0,
            "total_searches": 0,
            "avg_search_time": 0.0,
        }
    
    def _init_chromadb(self):
        """初始化 ChromaDB"""
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb not installed. "
                            "Install with: pip install chromadb")
        
        # 创建持久化客户端
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=self.persist_directory
        ))
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )
        
        # 更新统计
        self.stats["total_documents"] = self.collection.count()
    
    def add_document(
        self,
        document: VectorDocument,
        generate_embedding: bool = True
    ) -> str:
        """
        添加文档到向量数据库
        
        Args:
            document: 向量文档
            generate_embedding: 是否自动生成嵌入向量
            
        Returns:
            文档 ID
        """
        # 生成嵌入向量
        if generate_embedding and not document.embedding:
            document.embedding = self.embedding_provider.embed_single(document.content)
        
        # 添加到集合
        self.collection.add(
            ids=[document.id],
            embeddings=[document.embedding] if document.embedding else None,
            documents=[document.content],
            metadatas=[document.metadata]
        )
        
        self.stats["total_documents"] = self.collection.count()
        
        return document.id
    
    def add_note(
        self,
        note_id: str,
        title: str,
        content: str,
        tags: List[str] = None,
        source: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        添加笔记到向量数据库（便捷方法）
        
        Args:
            note_id: 笔记唯一标识
            title: 笔记标题
            content: 笔记内容
            tags: 标签列表
            source: 源文件路径
            metadata: 额外元数据
            
        Returns:
            文档 ID
        """
        # 构建文档内容（标题 + 内容）
        full_content = f"{title}\n\n{content}"
        
        # 构建元数据
        doc_metadata = {
            "title": title,
            "tags": json.dumps(tags or []),
            "source": source or "",
            "created_at": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        document = VectorDocument(
            id=note_id,
            content=full_content,
            metadata=doc_metadata
        )
        
        return self.add_document(document)
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            query: 搜索查询
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            搜索结果列表
        """
        import time
        start_time = time.time()
        
        # 生成查询嵌入向量
        query_embedding = self.embedding_provider.embed_single(query)
        
        # 执行搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata
        )
        
        # 解析结果
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                document = VectorDocument(
                    id=doc_id,
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i],
                    embedding=results["embeddings"][0][i] if results["embeddings"] else None
                )
                
                distance = results["distances"][0][i]
                score = 1 - distance  # 将距离转换为相似度分数
                
                search_results.append(SearchResult(
                    document=document,
                    score=score,
                    distance=distance
                ))
        
        # 更新统计
        search_time = time.time() - start_time
        self.stats["total_searches"] += 1
        self.stats["avg_search_time"] = (
            (self.stats["avg_search_time"] * (self.stats["total_searches"] - 1) + search_time)
            / self.stats["total_searches"]
        )
        
        return search_results
    
    def find_similar(
        self,
        document_id: str,
        n_results: int = 5
    ) -> List[SearchResult]:
        """
        查找相似文档
        
        Args:
            document_id: 参考文档 ID
            n_results: 返回结果数量
            
        Returns:
            相似文档列表
        """
        # 获取参考文档
        doc = self.collection.get(ids=[document_id])
        if not doc["ids"]:
            raise ValueError(f"Document not found: {document_id}")
        
        # 使用参考文档的嵌入向量搜索
        reference_embedding = doc["embeddings"][0]
        
        results = self.collection.query(
            query_embeddings=[reference_embedding],
            n_results=n_results + 1  # +1 因为会包含自身
        )
        
        # 解析结果（排除自身）
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id == document_id:
                    continue
                
                document = VectorDocument(
                    id=doc_id,
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i],
                    embedding=results["embeddings"][0][i] if results["embeddings"] else None
                )
                
                distance = results["distances"][0][i]
                score = 1 - distance
                
                search_results.append(SearchResult(
                    document=document,
                    score=score,
                    distance=distance
                ))
        
        return search_results[:n_results]
    
    def find_related_notes(
        self,
        note_id: str,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        查找关联笔记（用于知识图谱构建）
        
        Args:
            note_id: 笔记 ID
            min_score: 最小相似度阈值
            
        Returns:
            关联笔记列表
        """
        similar = self.find_similar(note_id, n_results=10)
        
        related = []
        for result in similar:
            if result.score >= min_score:
                related.append({
                    "id": result.document.id,
                    "title": result.document.metadata.get("title", "Unknown"),
                    "score": result.score,
                    "tags": json.loads(result.document.metadata.get("tags", "[]")),
                    "source": result.document.metadata.get("source", ""),
                })
        
        return related
    
    def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        
        Args:
            document_id: 文档 ID
            
        Returns:
            是否成功
        """
        try:
            self.collection.delete(ids=[document_id])
            self.stats["total_documents"] = self.collection.count()
            return True
        except Exception:
            return False
    
    def update_document(
        self,
        document_id: str,
        content: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        更新文档
        
        Args:
            document_id: 文档 ID
            content: 新内容（为 None 则不更新）
            metadata: 新元数据（为 None 则不更新）
            
        Returns:
            是否成功
        """
        try:
            update_data = {}
            
            if content is not None:
                update_data["documents"] = [content]
                # 重新生成嵌入向量
                update_data["embeddings"] = [self.embedding_provider.embed_single(content)]
            
            if metadata is not None:
                update_data["metadatas"] = [metadata]
            
            if update_data:
                self.collection.update(
                    ids=[document_id],
                    **update_data
                )
            
            return True
        except Exception:
            return False
    
    def get_document(self, document_id: str) -> Optional[VectorDocument]:
        """
        获取文档
        
        Args:
            document_id: 文档 ID
            
        Returns:
            文档对象，不存在则返回 None
        """
        try:
            result = self.collection.get(ids=[document_id])
            if not result["ids"]:
                return None
            
            return VectorDocument(
                id=result["ids"][0],
                content=result["documents"][0],
                metadata=result["metadatas"][0],
                embedding=result["embeddings"][0] if result["embeddings"] else None
            )
        except Exception:
            return None
    
    def list_documents(
        self,
        filter_metadata: Dict[str, Any] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[VectorDocument]:
        """
        列出文档
        
        Args:
            filter_metadata: 元数据过滤条件
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            文档列表
        """
        results = self.collection.get(
            where=filter_metadata,
            limit=limit,
            offset=offset
        )
        
        documents = []
        for i, doc_id in enumerate(results["ids"]):
            documents.append(VectorDocument(
                id=doc_id,
                content=results["documents"][i],
                metadata=results["metadatas"][i],
                embedding=results["embeddings"][i] if results["embeddings"] else None
            ))
        
        return documents
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "embedding_provider": self.embedding_provider.provider,
            "embedding_model": self.embedding_provider.model_name,
        }
    
    def persist(self):
        """持久化数据"""
        if hasattr(self.client, "persist"):
            self.client.persist()
    
    def reset(self):
        """重置集合（删除所有数据）"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.stats["total_documents"] = 0


class KnowledgeGraph:
    """
    知识图谱构建器
    
    基于向量相似度自动构建笔记之间的关联关系
    """
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    def build_graph(
        self,
        min_similarity: float = 0.7,
        max_connections: int = 5
    ) -> Dict[str, Any]:
        """
        构建知识图谱
        
        Args:
            min_similarity: 最小相似度阈值
            max_connections: 每个节点的最大连接数
            
        Returns:
            知识图谱数据
        """
        # 获取所有文档
        documents = self.vector_store.list_documents(limit=1000)
        
        nodes = []
        edges = []
        
        for doc in documents:
            # 添加节点
            nodes.append({
                "id": doc.id,
                "title": doc.metadata.get("title", "Unknown"),
                "tags": json.loads(doc.metadata.get("tags", "[]")),
                "source": doc.metadata.get("source", ""),
            })
            
            # 查找关联
            related = self.vector_store.find_related_notes(
                doc.id,
                min_score=min_similarity
            )
            
            # 添加边（限制连接数）
            for rel in related[:max_connections]:
                edges.append({
                    "source": doc.id,
                    "target": rel["id"],
                    "weight": rel["score"],
                    "type": "semantic_similarity"
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "avg_degree": len(edges) / max(len(nodes), 1),
            }
        }
    
    def find_clusters(
        self,
        n_clusters: int = 5
    ) -> List[Dict[str, Any]]:
        """
        发现知识聚类（主题分组）
        
        Args:
            n_clusters: 聚类数量
            
        Returns:
            聚类列表
        """
        # 获取所有文档
        documents = self.vector_store.list_documents(limit=1000)
        
        if len(documents) < n_clusters:
            return []
        
        # 使用 K-Means 聚类
        from sklearn.cluster import KMeans
        
        embeddings = [doc.embedding for doc in documents if doc.embedding]
        if not embeddings:
            return []
        
        kmeans = KMeans(n_clusters=min(n_clusters, len(embeddings)), random_state=42)
        labels = kmeans.fit_predict(embeddings)
        
        # 构建聚类结果
        clusters = []
        for i in range(n_clusters):
            cluster_docs = [
                {
                    "id": documents[j].id,
                    "title": documents[j].metadata.get("title", "Unknown"),
                }
                for j, label in enumerate(labels) if label == i
            ]
            
            if cluster_docs:
                # 提取聚类主题（使用 TF-IDF 或简单词频）
                cluster_text = " ".join([
                    documents[j].content
                    for j, label in enumerate(labels) if label == i
                ])
                
                # 简单主题提取（取高频词）
                words = cluster_text.lower().split()
                from collections import Counter
                common_words = Counter(words).most_common(5)
                theme = ", ".join([word for word, _ in common_words])
                
                clusters.append({
                    "id": i,
                    "theme": theme,
                    "document_count": len(cluster_docs),
                    "documents": cluster_docs,
                })
        
        return clusters


class SemanticSearchEngine:
    """
    语义搜索引擎
    
    提供高级搜索功能：
    1. 语义搜索
    2. 混合搜索（语义 + 关键词）
    3. 过滤搜索
    4. 相关性排序
    """
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        filters: Dict[str, Any] = None,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        高级搜索
        
        Args:
            query: 搜索查询
            n_results: 返回结果数量
            filters: 过滤条件
            min_score: 最小相似度
            
        Returns:
            搜索结果
        """
        # 执行语义搜索
        results = self.vector_store.search(
            query=query,
            n_results=n_results * 2,  # 获取更多结果用于过滤
            filter_metadata=filters
        )
        
        # 过滤和格式化
        formatted_results = []
        for result in results:
            if result.score >= min_score:
                formatted_results.append({
                    "id": result.document.id,
                    "title": result.document.metadata.get("title", "Unknown"),
                    "content_preview": result.document.content[:200] + "...",
                    "score": result.score,
                    "tags": json.loads(result.document.metadata.get("tags", "[]")),
                    "source": result.document.metadata.get("source", ""),
                })
        
        return formatted_results[:n_results]
    
    def hybrid_search(
        self,
        query: str,
        keywords: List[str] = None,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        混合搜索（语义 + 关键词）
        
        Args:
            query: 语义搜索查询
            keywords: 关键词列表
            n_results: 返回结果数量
            
        Returns:
            搜索结果
        """
        # 语义搜索
        semantic_results = self.search(query, n_results=n_results * 2)
        
        # 关键词匹配
        if keywords:
            keyword_results = []
            for doc in self.vector_store.list_documents(limit=1000):
                content = doc.content.lower()
                keyword_matches = sum(1 for kw in keywords if kw.lower() in content)
                if keyword_matches > 0:
                    keyword_results.append({
                        "id": doc.id,
                        "title": doc.metadata.get("title", "Unknown"),
                        "content_preview": doc.content[:200] + "...",
                        "keyword_score": keyword_matches / len(keywords),
                        "tags": json.loads(doc.metadata.get("tags", "[]")),
                        "source": doc.metadata.get("source", ""),
                    })
            
            # 合并结果（简单加权）
            combined = {}
            
            for r in semantic_results:
                combined[r["id"]] = {
                    **r,
                    "semantic_score": r["score"],
                    "keyword_score": 0,
                    "final_score": r["score"] * 0.7,
                }
            
            for r in keyword_results:
                if r["id"] in combined:
                    combined[r["id"]]["keyword_score"] = r["keyword_score"]
                    combined[r["id"]]["final_score"] += r["keyword_score"] * 0.3
                else:
                    combined[r["id"]] = {
                        **r,
                        "semantic_score": 0,
                        "keyword_score": r["keyword_score"],
                        "final_score": r["keyword_score"] * 0.3,
                    }
            
            # 按最终得分排序
            results = sorted(combined.values(), key=lambda x: x["final_score"], reverse=True)
            return results[:n_results]
        
        return semantic_results[:n_results]
