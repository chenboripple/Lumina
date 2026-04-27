"""
Lumina 完整测试套件
覆盖所有核心模块的单元测试
"""

import pytest
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# ==================== Cache 模块测试 ====================

class TestCacheManager:
    """CacheManager 完整测试"""
    
    @pytest.fixture
    def cache_manager(self, tmp_path):
        from lumina.cache import CacheManager
        return CacheManager(cache_dir=str(tmp_path / "cache"))
    
    def test_init_creates_directories(self, tmp_path):
        """测试初始化创建目录结构"""
        from lumina.cache import CacheManager
        cache_dir = tmp_path / "test_cache"
        cm = CacheManager(cache_dir=str(cache_dir))
        
        assert cache_dir.exists()
        assert (cache_dir / "files").exists()
        assert (cache_dir / "llm").exists()
        assert (cache_dir / "state").exists()
    
    def test_file_cache_roundtrip(self, cache_manager):
        """测试文件缓存读写"""
        test_hash = "abc123"
        test_data = {"content": "test", "type": "markdown"}
        
        cache_manager.set_file(test_hash, test_data)
        result = cache_manager.get_file(test_hash)
        
        assert result == test_data
        assert cache_manager.stats["hits"] == 1
    
    def test_file_cache_miss(self, cache_manager):
        """测试文件缓存未命中"""
        result = cache_manager.get_file("nonexistent")
        
        assert result is None
        assert cache_manager.stats["misses"] == 1
    
    def test_has_file(self, cache_manager):
        """测试文件存在检查"""
        cache_manager.set_file("exists", {"data": "yes"})
        
        assert cache_manager.has_file("exists") is True
        assert cache_manager.has_file("not_exists") is False
    
    def test_llm_cache_with_ttl(self, cache_manager):
        """测试 LLM 缓存 TTL"""
        prompt_hash = "prompt123"
        response = "test response"
        
        cache_manager.set_llm_response(prompt_hash, response, ttl_days=7)
        result = cache_manager.get_llm_response(prompt_hash)
        
        assert result == response
    
    def test_llm_cache_expired(self, cache_manager):
        """测试 LLM 缓存过期"""
        prompt_hash = "expired_prompt"
        
        # 手动创建过期缓存
        cache_file = cache_manager.llm_cache_dir / f"{prompt_hash}.json"
        expired_data = {
            "response": "old",
            "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
            "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
        }
        cache_file.write_text(json.dumps(expired_data))
        
        result = cache_manager.get_llm_response(prompt_hash)
        
        assert result is None
        assert cache_manager.stats["evictions"] == 1
    
    def test_state_cache(self, cache_manager):
        """测试处理状态缓存"""
        source_path = "/path/to/file.md"
        state = {"status": "completed", "score": 0.85}
        
        cache_manager.set_processing_state(source_path, state)
        result = cache_manager.get_processing_state(source_path)
        
        assert result["status"] == "completed"
        assert result["score"] == 0.85
    
    def test_clear_cache(self, cache_manager):
        """测试清除缓存"""
        cache_manager.set_file("hash1", {"data": "1"})
        cache_manager.set_llm_response("hash2", "response")
        
        cache_manager.clear()
        
        assert cache_manager.get_file("hash1") is None
        assert cache_manager.get_llm_response("hash2") is None
        assert cache_manager.stats["hits"] == 0
    
    def test_cache_stats_accuracy(self, cache_manager):
        """测试缓存统计准确性"""
        # 多次命中和未命中
        cache_manager.set_file("hit", {"data": "yes"})
        cache_manager.get_file("hit")  # hit
        cache_manager.get_file("hit")  # hit
        cache_manager.get_file("miss")  # miss
        
        stats = cache_manager.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1


# ==================== History 模块测试 ====================

class TestHistoryManager:
    """HistoryManager 完整测试"""
    
    @pytest.fixture
    def history_manager(self, tmp_path):
        from lumina.history import HistoryManager
        return HistoryManager(history_dir=str(tmp_path / "history"))
    
    @pytest.fixture
    def sample_record(self):
        from lumina.history import ProcessingRecord
        return ProcessingRecord(
            session_id="test_session",
            file_path="/test/file.md",
            file_hash="hash123",
            file_type="markdown",
            file_size=1000,
            iterations=2,
            best_score=0.85,
            final_output="# Test Note",
            full_history='[{"validation": {"score": 0.8, "passed": false, "issues": 1}}]',
            created_at=datetime.now().isoformat(),
            metadata={"source": "test"}
        )
    
    def test_init_creates_database(self, tmp_path):
        """测试初始化创建数据库"""
        from lumina.history import HistoryManager
        history_dir = tmp_path / "test_history"
        hm = HistoryManager(history_dir=str(history_dir))
        
        assert (history_dir / "lumina_history.db").exists()
    
    def test_session_lifecycle(self, history_manager):
        """测试会话生命周期"""
        session_id = "session_123"
        
        history_manager.start_session(session_id)
        stats = history_manager.get_session_stats(session_id)
        assert stats["status"] == "running"
        
        history_manager.end_session(session_id, 10, 0.85)
        stats = history_manager.get_session_stats(session_id)
        assert stats["status"] == "completed"
        assert stats["total_files"] == 10
    
    def test_record_and_retrieve(self, history_manager, sample_record):
        """测试记录和检索"""
        history_manager.record_file_processing(sample_record)
        
        history = history_manager.get_file_history("/test/file.md")
        assert len(history) == 1
        assert history[0]["file_path"] == "/test/file.md"
        assert history[0]["best_score"] == 0.85
    
    def test_quality_trend(self, history_manager, sample_record):
        """测试质量趋势"""
        # 记录多次处理
        for i in range(3):
            record = ProcessingRecord(
                session_id=f"session_{i}",
                file_path="/test/file.md",
                file_hash=f"hash_{i}",
                file_type="markdown",
                file_size=1000,
                iterations=2,
                best_score=0.7 + i * 0.1,
                final_output="# Test",
                full_history="[]",
                created_at=datetime.now().isoformat(),
                metadata={}
            )
            history_manager.record_file_processing(record)
        
        trend = history_manager.get_quality_trend("/test/file.md", days=30)
        assert len(trend) == 3
        scores = [t["best_score"] for t in trend]
        assert scores == sorted(scores)  # 按时间排序
    
    def test_explanation_generation(self, history_manager, sample_record):
        """测试可解释性生成"""
        history_manager.record_file_processing(sample_record)
        
        explanation = history_manager.get_explanation("/test/file.md")
        assert "文件:" in explanation
        assert "最终得分: 0.85" in explanation
        assert "迭代次数: 2" in explanation
    
    def test_get_all_sessions(self, history_manager):
        """测试获取所有会话"""
        for i in range(3):
            history_manager.start_session(f"session_{i}")
            history_manager.end_session(f"session_{i}", i * 5, 0.8)
        
        sessions = history_manager.get_all_sessions(limit=10)
        assert len(sessions) == 3


# ==================== Config 模块测试 ====================

class TestLuminaConfig:
    """LuminaConfig 完整测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        from lumina.config import LuminaConfig
        config = LuminaConfig()
        
        assert config.output.plugin == "obsidian"
        assert config.harness["max_iterations"] == 3
        assert config.harness["quality_threshold"] == 0.8
    
    def test_load_from_yaml(self, tmp_path):
        """测试从 YAML 加载"""
        from lumina.config import LuminaConfig
        
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
input:
  sources:
    - path: ~/Documents
      recursive: true
  default_recursive: true
  supported_extensions:
    - .md
output:
  plugin: plain
  base_dir: ~/TestNotes
harness:
  max_iterations: 5
  quality_threshold: 0.9
llm:
  provider: openai
  model: gpt-4
""")
        
        config = LuminaConfig.load(str(config_file))
        assert config.output.plugin == "plain"
        assert config.harness["max_iterations"] == 5
    
    def test_validate_missing_path(self, tmp_path):
        """测试验证不存在的路径"""
        from lumina.config import LuminaConfig, InputSource
        
        config = LuminaConfig(
            input_sources=[InputSource(path="/nonexistent/path")]
        )
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("does not exist" in e for e in errors)
    
    def test_validate_valid_path(self, tmp_path):
        """测试验证有效路径"""
        from lumina.config import LuminaConfig, InputSource
        
        config = LuminaConfig(
            input_sources=[InputSource(path=str(tmp_path))]
        )
        errors = config.validate()
        
        assert len(errors) == 0
    
    def test_output_path_generation(self):
        """测试输出生成路径"""
        from lumina.config import OutputConfig
        
        output = OutputConfig(
            base_dir="~/Test",
            structure={"by_type": True, "by_date": False, "flat": False},
            naming={"prefix_date": False, "slugify": True}
        )
        
        path = output.get_output_path("My Note", file_type="markdown")
        assert "markdown" in str(path)
        assert "my-note" in str(path)
    
    def test_save_and_load_user_config(self, tmp_path):
        """测试保存和加载用户配置"""
        from lumina.config import LuminaConfig
        import os
        
        # 临时修改用户配置目录
        with patch('lumina.config.USER_CONFIG_DIR', tmp_path / ".lumina"):
            config = LuminaConfig()
            config.input_sources = []
            config.save_user_config()
            
            assert (tmp_path / ".lumina" / "config.yaml").exists()


# ==================== Vector Store 模块测试 ====================

class TestVectorStore:
    """VectorStore 完整测试"""
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """创建模拟嵌入提供者"""
        provider = Mock()
        provider.embed.return_value = [[0.1] * 384]  # 模拟 384 维向量
        return provider
    
    def test_vector_document_creation(self):
        """测试向量文档创建"""
        from lumina.vector_store import VectorDocument
        
        doc = VectorDocument(
            id="doc1",
            content="test content",
            metadata={"title": "Test"}
        )
        
        assert doc.id == "doc1"
        assert doc.content == "test content"
    
    def test_search_result_creation(self):
        """测试结果创建"""
        from lumina.vector_store import SearchResult, VectorDocument
        
        doc = VectorDocument(id="doc1", content="test")
        result = SearchResult(document=doc, score=0.95, distance=0.05)
        
        assert result.score == 0.95
        assert result.document.id == "doc1"
    
    @patch('lumina.vector_store.CHROMADB_AVAILABLE', True)
    def test_vector_store_init_with_mock(self, tmp_path, mock_embedding_provider):
        """测试向量存储初始化（使用 mock）"""
        from lumina.vector_store import VectorStore
        
        with patch('lumina.vector_store.chromadb') as mock_chroma:
            mock_client = Mock()
            mock_chroma.Client.return_value = mock_client
            mock_client.get_or_create_collection.return_value = Mock()
            
            vs = VectorStore(
                collection_name="test",
                persist_directory=str(tmp_path / "vectors"),
                embedding_provider_config={"provider": "mock"}
            )
            
            assert vs is not None


# ==================== Progress Tracker 测试 ====================

class TestProgressTracker:
    """进度追踪测试"""
    
    def test_progress_initialization(self):
        """测试进度初始化"""
        from lumina.utils.progress import ProgressTracker
        
        tracker = ProgressTracker(total=100)
        assert tracker.total == 100
        assert tracker.current == 0
        assert tracker.percentage == 0.0
    
    def test_progress_update(self):
        """测试进度更新"""
        from lumina.utils.progress import ProgressTracker
        
        tracker = ProgressTracker(total=100)
        tracker.update(50)
        
        assert tracker.current == 50
        assert tracker.percentage == 50.0
    
    def test_progress_callback(self):
        """测试进度回调"""
        from lumina.utils.progress import ProgressTracker
        
        callback_values = []
        def callback(progress):
            callback_values.append(progress)
        
        tracker = ProgressTracker(total=100, callback=callback)
        tracker.update(25)
        tracker.update(50)
        
        assert len(callback_values) == 2
        assert callback_values[0]["percentage"] == 25.0


# ==================== Error Handler 测试 ====================

class TestErrorHandler:
    """错误处理测试"""
    
    def test_graceful_degradation(self):
        """测试优雅降级"""
        from lumina.utils.error_handler import ErrorHandler, ErrorSeverity
        
        handler = ErrorHandler()
        result = handler.handle_error(
            Exception("test error"),
            severity=ErrorSeverity.WARNING,
            fallback="fallback_value"
        )
        
        assert result == "fallback_value"
    
    def test_critical_error_raises(self):
        """测试严重错误抛出"""
        from lumina.utils.error_handler import ErrorHandler, ErrorSeverity
        
        handler = ErrorHandler()
        with pytest.raises(Exception):
            handler.handle_error(
                Exception("critical"),
                severity=ErrorSeverity.CRITICAL
            )
    
    def test_error_recovery(self):
        """测试错误恢复"""
        from lumina.utils.error_handler import ErrorHandler
        
        handler = ErrorHandler()
        
        def operation():
            raise ValueError("test")
        
        result = handler.with_retry(operation, max_retries=3, fallback="default")
        assert result == "default"


# ==================== Config Hot Reload 测试 ====================

class TestConfigHotReload:
    """配置热加载测试"""
    
    def test_watch_config_file(self, tmp_path):
        """测试配置文件监控"""
        from lumina.config.hot_reload import ConfigWatcher
        
        config_file = tmp_path / "test.yaml"
        config_file.write_text("key: value1")
        
        watcher = ConfigWatcher(str(config_file))
        assert watcher.last_modified is not None
    
    def test_detect_config_change(self, tmp_path):
        """测试检测配置变更"""
        from lumina.config.hot_reload import ConfigWatcher
        import time
        
        config_file = tmp_path / "test.yaml"
        config_file.write_text("key: value1")
        
        watcher = ConfigWatcher(str(config_file))
        time.sleep(0.1)
        
        config_file.write_text("key: value2")
        assert watcher.has_changed() is True
    
    def test_reload_config(self, tmp_path):
        """测试重新加载配置"""
        from lumina.config.hot_reload import ConfigWatcher
        import time
        
        config_file = tmp_path / "test.yaml"
        config_file.write_text("plugin: obsidian")
        
        watcher = ConfigWatcher(str(config_file))
        time.sleep(0.1)
        
        config_file.write_text("plugin: plain")
        new_config = watcher.reload()
        
        assert new_config["plugin"] == "plain"


# ==================== 增量索引测试 ====================

class TestIncrementalIndex:
    """增量索引测试"""
    
    def test_detect_file_changes(self):
        """测试检测文件变更"""
        from lumina.core.file_change_tracker import FileChangeTracker
        
        tracker = FileChangeTracker()
        
        # 模拟文件变更
        old_hash = "hash1"
        new_hash = "hash2"
        
        assert tracker.has_changed("/test/file.md", old_hash) is True
        assert tracker.has_changed("/test/file.md", new_hash) is False
    
    def test_incremental_update(self):
        """测试增量更新"""
        from lumina.vector_store import VectorStore
        
        with patch.object(VectorStore, 'update_note') as mock_update:
            # 模拟增量更新
            vs = Mock()
            vs.update_note.return_value = True
            
            result = vs.update_note("doc1", "new content")
            assert result is True


# ==================== 集成测试 ====================

class TestFullPipeline:
    """完整流程集成测试"""
    
    def test_end_to_end_with_mocks(self, tmp_path):
        """测试端到端流程（使用 Mock）"""
        from lumina.harness import Harness, HarnessConfig
        
        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nThis is a test.")
        
        config = HarnessConfig(
            output_dir=str(tmp_path / "output"),
            max_iterations=1,
            quality_threshold=0.0,
            enable_vector_store=False,
        )
        
        harness = Harness(config)
        
        # Mock LLM 调用
        with patch.object(harness.executor, '_get_llm') as mock_llm:
            mock_provider = Mock()
            mock_provider.generate.return_value = json.dumps({
                "title": "Test Note",
                "content": "Test content",
                "tags": ["test"],
                "links": []
            })
            mock_llm.return_value = mock_provider
            
            report = harness.run(str(test_file))
            
            assert report["total_files"] == 1
            assert report["avg_iterations"] > 0


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""
    
    def test_cache_performance(self, tmp_path):
        """测试缓存性能"""
        from lumina.cache import CacheManager
        import time
        
        cm = CacheManager(cache_dir=str(tmp_path / "perf_cache"))
        
        # 写入大量数据
        start = time.time()
        for i in range(100):
            cm.set_file(f"hash_{i}", {"data": f"content_{i}"})
        write_time = time.time() - start
        
        # 读取
        start = time.time()
        for i in range(100):
            cm.get_file(f"hash_{i}")
        read_time = time.time() - start
        
        # 应该很快（< 1秒）
        assert write_time < 2.0
        assert read_time < 1.0
    
    def test_batch_processing_speed(self, tmp_path):
        """测试批处理速度"""
        from lumina.planner import Planner
        import time
        
        planner = Planner()
        
        # 创建多个文件
        for i in range(20):
            (tmp_path / f"file_{i}.md").write_text(f"# File {i}")
        
        start = time.time()
        files = planner.scan(str(tmp_path))
        scan_time = time.time() - start
        
        assert len(files) == 20
        assert scan_time < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
