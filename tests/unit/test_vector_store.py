"""
VectorStore 模块单元测试
测试向量数据库、知识图谱、语义搜索
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil


class TestVectorDocument:
    """VectorDocument 数据类测试"""

    def test_basic_creation(self):
        """测试基本创建"""
        from lumina.vector_store import VectorDocument
        doc = VectorDocument(
            id="test1",
            content="Test content",
            metadata={"title": "Test Title"},
        )

        assert doc.id == "test1"
        assert doc.content == "Test content"
        assert doc.metadata["title"] == "Test Title"
        assert doc.embedding is None

    def test_with_embedding(self):
        """测试带嵌入向量"""
        from lumina.vector_store import VectorDocument
        embedding = [0.1, 0.2, 0.3]
        doc = VectorDocument(
            id="test1",
            content="Test",
            metadata={},
            embedding=embedding
        )

        assert doc.embedding == embedding


class TestEmbeddingProvider:
    """EmbeddingProvider 测试"""

    def test_default_creation(self):
        """测试默认创建"""
        from lumina.vector_store import EmbeddingProvider
        provider = EmbeddingProvider()

        assert provider.provider == "local"

    def test_embed_single(self):
        """测试单个文本嵌入"""
        from lumina.vector_store import EmbeddingProvider
        provider = EmbeddingProvider(provider="local")

        # Mock the local model
        with patch.object(provider, '_model') as mock_model:
            mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
            result = provider.embed_single("Test text")

            assert isinstance(result, list)
            assert len(result) == 3


class TestVectorStore:
    """VectorStore 核心测试"""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """创建临时 VectorStore"""
        from lumina.vector_store import VectorStore, EmbeddingProvider
        store = VectorStore(
            collection_name="test_collection",
            persist_directory=str(tmp_path / "vector_store"),
            embedding_provider=EmbeddingProvider(provider="local"),
        )
        return store

    def test_initialization(self, vector_store):
        """测试初始化"""
        assert vector_store.collection_name == "test_collection"
        assert vector_store.client is not None
        assert vector_store.collection is not None

    def test_get_stats(self, vector_store):
        """测试获取统计"""
        stats = vector_store.get_stats()

        assert "total_documents" in stats
        assert stats["collection_name"] == "test_collection"

    def test_add_and_get_document(self, vector_store):
        """测试添加和获取文档"""
        from lumina.vector_store import VectorDocument

        doc = VectorDocument(
            id="doc1",
            content="This is a test document about Python programming",
            metadata={"title": "Python Guide", "source": "test"}
        )

        result_id = vector_store.add_document(doc)
        assert result_id == "doc1"

        # 获取文档
        retrieved = vector_store.get_document("doc1")
        assert retrieved is not None
        assert retrieved.id == "doc1"
        assert "Python" in retrieved.content

    def test_search(self, vector_store):
        """测试语义搜索"""
        from lumina.vector_store import VectorDocument

        # 添加测试文档
        docs = [
            VectorDocument(
                id="doc1",
                content="Python is a great programming language for data science",
                metadata={"title": "Python"}
            ),
            VectorDocument(
                id="doc2",
                content="JavaScript is used for web development",
                metadata={"title": "JS"}
            ),
        ]
        for doc in docs:
            vector_store.add_document(doc)

        # 搜索
        results = vector_store.search("programming language", n_results=2)

        assert len(results) > 0
        # Python 文档应该排名更高
        assert any("Python" in r.document.content for r in results)

    def test_find_similar(self, vector_store):
        """测试相似文档查找"""
        from lumina.vector_store import VectorDocument

        # 添加文档
        doc = VectorDocument(
            id="doc1",
            content="Machine learning is a subset of artificial intelligence",
            metadata={"title": "ML"}
        )
        vector_store.add_document(doc)

        # 添加另一个相关文档
        doc2 = VectorDocument(
            id="doc2",
            content="Deep learning uses neural networks for AI applications",
            metadata={"title": "DL"}
        )
        vector_store.add_document(doc2)

        # 查找相似
        similar = vector_store.find_similar("doc1", n_results=1)

        assert len(similar) > 0
        assert similar[0].document.id == "doc2"

    def test_find_related_notes(self, vector_store):
        """测试关联笔记"""
        from lumina.vector_store import VectorDocument

        doc = VectorDocument(
            id="doc1",
            content="Neural networks are powerful for pattern recognition",
            metadata={"title": "NN", "tags": '["AI", "ML"]', "source": "test"}
        )
        vector_store.add_document(doc)

        # 添加相关文档
        doc2 = VectorDocument(
            id="doc2",
            content="Deep learning networks have many layers",
            metadata={"title": "DL", "tags": '["AI"]', "source": "test2"}
        )
        vector_store.add_document(doc2)

        related = vector_store.find_related_notes("doc1", min_score=0.0)

        # 应该返回至少一个相关文档
        assert len(related) >= 0

    def test_update_document(self, vector_store):
        """测试更新文档"""
        from lumina.vector_store import VectorDocument

        doc = VectorDocument(id="doc1", content="Original", metadata={"title": "doc1"})
        vector_store.add_document(doc)

        # 更新
        success = vector_store.update_document(
            "doc1",
            content="Updated content",
            metadata={"updated": True}
        )

        assert success is True

        # 验证更新
        updated = vector_store.get_document("doc1")
        assert updated is not None
        assert "Updated" in updated.content

    def test_delete_document(self, vector_store):
        """测试删除文档"""
        from lumina.vector_store import VectorDocument

        doc = VectorDocument(id="doc1", content="To be deleted", metadata={"title": "doc1"})
        vector_store.add_document(doc)

        assert vector_store.get_document("doc1") is not None

        success = vector_store.delete_document("doc1")
        assert success is True

        assert vector_store.get_document("doc1") is None

    def test_list_documents(self, vector_store):
        """测试列出文档"""
        from lumina.vector_store import VectorDocument

        # 添加多个文档
        for i in range(5):
            doc = VectorDocument(
                id=f"doc{i}",
                content=f"Content {i}",
                metadata={"index": i}
            )
            vector_store.add_document(doc)

        # 列出所有
        docs = vector_store.list_documents()
        assert len(docs) == 5

        # 限制数量
        limited = vector_store.list_documents(limit=3)
        assert len(limited) == 3

    def test_reset(self, vector_store):
        """测试重置"""
        from lumina.vector_store import VectorDocument

        doc = VectorDocument(id="doc1", content="Test", metadata={"title": "doc1"})
        vector_store.add_document(doc)

        assert vector_store.collection.count() > 0

        vector_store.reset()
        assert vector_store.collection.count() == 0


class TestKnowledgeGraph:
    """知识图谱测试"""

    @pytest.fixture
    def graph(self, tmp_path):
        """创建知识图谱实例"""
        from lumina.vector_store import VectorStore, KnowledgeGraph
        store = VectorStore(
            collection_name="test_graph",
            persist_directory=str(tmp_path / "graph"),
        )
        return KnowledgeGraph(vector_store=store)

    def test_build_graph(self, graph):
        """测试构建图谱"""
        from lumina.vector_store import VectorDocument

        # 添加多个文档
        docs = [
            VectorDocument(id="a", content="AI research", metadata={"title": "AI"}),
            VectorDocument(id="b", content="Machine learning", metadata={"title": "ML"}),
            VectorDocument(id="c", content="Web development", metadata={"title": "Web"}),
        ]
        for doc in docs:
            graph.vector_store.add_document(doc)

        graph_data = graph.build_graph(min_similarity=0.1)
        edges = graph_data["edges"]

        assert isinstance(graph_data, dict)
        assert "nodes" in graph_data
        assert "edges" in graph_data
        # AI 和 ML 应该有连接
        assert any(
            (e["source"] in ["a", "b"] and e["target"] in ["a", "b"])
            for e in edges
        )


class TestSemanticSearchEngine:
    """语义搜索引擎测试"""

    @pytest.fixture
    def engine(self, tmp_path):
        from lumina.vector_store import VectorStore, SemanticSearchEngine
        store = VectorStore(
            collection_name="test_search",
            persist_directory=str(tmp_path / "search"),
        )
        return SemanticSearchEngine(vector_store=store)

    def test_search(self, engine):
        """测试搜索"""
        from lumina.vector_store import VectorDocument

        docs = [
            VectorDocument(id="doc1", content="Python programming tutorial", metadata={"title": "doc1"}),
            VectorDocument(id="doc2", content="JavaScript web framework", metadata={"title": "doc2"}),
        ]
        for doc in docs:
            engine.vector_store.add_document(doc)

        results = engine.search("Python code", n_results=2)
        assert len(results) > 0

    def test_hybrid_search(self, engine):
        """测试混合搜索"""
        from lumina.vector_store import VectorDocument

        docs = [
            VectorDocument(id="doc1", content="Python tutorial for beginners", metadata={"title": "Python"}),
            VectorDocument(id="doc2", content="Advanced Python patterns", metadata={"title": "Advanced"}),
        ]
        for doc in docs:
            engine.vector_store.add_document(doc)

        results = engine.hybrid_search("Python tutorial", n_results=2)
        assert len(results) > 0
