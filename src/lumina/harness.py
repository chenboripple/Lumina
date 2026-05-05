"""
Harness - 智能核心协调器 (Agent 增强版)
整合 Planner + Executor + Validator + Cache + History，实现完整的知识萃取 Agent 工作流
"""

import json
import time
import re
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

from .planner import Planner, FileInfo
from .executor import Executor, NoteOutput, ExecutionContext
from .validator import Validator, ValidationResult, ValidationIssue
from .cache import CacheManager
from .history import HistoryManager, ProcessingRecord
from .vector_store import VectorStore, KnowledgeGraph, SemanticSearchEngine
from .plugins import get_plugin, NoteData
from .content_analyzer import ContentAnalyzer
from .core.multimodal_extractor import MultimodalExtractor
from .core.file_change_tracker import FileChangeTracker
from .utils.progress import ProgressTracker, BatchProgressTracker
from .utils.error_handler import ErrorHandler, ErrorSeverity, GracefulDegradation
from .utils.file_operations import (
    write_file_with_metadata, read_file_with_metadata, FileMetadata,
    check_write_permission, check_sensitive_content, is_file_modified
)
from .document_cluster import DocumentCluster, DocumentClusterer, ClusterResult, ClusterStrategy



@dataclass
class HarnessConfig:
    """Harness 配置（增强版）"""
    max_iterations: int = 3
    quality_threshold: float = 0.8
    output_dir: str = "./output"
    vault_path: Optional[str] = None
    plugin: str = "obsidian"
    use_cache: bool = True  # 是否使用缓存
    incremental: bool = True  # 是否增量处理
    parallel: bool = True  # 是否并行处理
    max_workers: int = 4  # 并行处理线程数
    stream_output: bool = False  # 是否流式输出进度
    enable_history: bool = True  # 是否启用历史记录
    quick_validation_first: bool = True  # 是否先进行快速验证
    allow_partial: bool = True  # 是否允许部分通过的结果输出
    metadata_prefix: str = "lumina_"  # 元数据前缀
    enable_vector_store: bool = True  # 是否启用向量数据库
    vector_store_persist_dir: str = "./.lumina/vector_store"  # 向量数据库存储目录
    embedding_provider: str = "local"  # 嵌入提供者：local/openai
    embedding_model: Optional[str] = None  # 嵌入模型名称
    embedding_api_key: Optional[str] = None  # 嵌入 API 密钥
    enable_progress: bool = True  # 是否启用进度可视化
    enable_error_handler: bool = True  # 是否启用错误处理增强
    progress_callback: Optional[Any] = None  # 进度回调函数
    error_handler: Optional[Any] = None  # 错误处理器实例
    supported_extensions: List[str] = field(default_factory=list)  # 允许处理的文件扩展名
    output_structure: Dict[str, bool] = field(default_factory=dict)  # 输出目录结构策略
    note_organization: Dict[str, Any] = field(default_factory=dict)  # 笔记目录组织（scene/PARA）
    
    # 新增功能配置（默认启用）
    enable_clustering: bool = True  # 是否启用文档聚合
    enable_content_filter: bool = True  # 是否启用内容过滤
    enable_scene_detection: bool = True  # 是否启用场景检测
    
    # LLM 配置 - 分别为不同的 Agent 配置
    llm_config_planner: Optional[Dict[str, Any]] = None  # Planner 的 LLM 配置
    llm_config_executor: Optional[Dict[str, Any]] = None  # Executor 的 LLM 配置
    llm_config_validator: Optional[Dict[str, Any]] = None  # Validator 的 LLM 配置
    llm_config: Dict[str, Any] = field(default_factory=dict)  # 默认 LLM 配置（所有 Agent 共用）
    
    # 文件操作安全配置
    enable_write_permission_check: bool = False  # 是否启用写入权限检查
    write_permission_rules: List[str] = field(default_factory=lambda: [
        "+**/*",  # 默认允许所有位置写入
    ])
    enable_sensitive_content_check: bool = True  # 是否启用敏感内容检测
    backup_before_write: bool = True  # 写入前是否自动备份原始文件
    
    # 内容预分析配置
    enable_content_analyzer: bool = True  # 是否启用内容预分析
    llm_config_analyzer: Optional[Dict[str, Any]] = None  # 分析器专用 LLM 配置（轻量模型）
    content_analyzer_max_length: int = 3000  # 分析器读取内容最大长度
    
    def get_llm_config_for(self, agent_name: str) -> Dict[str, Any]:
        """获取指定 Agent 的 LLM 配置
        
        Args:
            agent_name: 代理名称 ('planner', 'executor', 'validator')
            
        Returns:
            对应 Agent 的 LLM 配置字典
        """
        # analyzer 默认沿用 planner 配置，避免单独未配置时退化到缺少 key 的默认项。
        if agent_name == "analyzer" and self.llm_config_planner:
            return {**self.llm_config, **self.llm_config_planner}

        agent_config_attr = f"llm_config_{agent_name}"
        agent_config = getattr(self, agent_config_attr, None)

        if agent_config:
            return {**self.llm_config, **agent_config}

        # 如果没有单独配置，使用默认配置
        return dict(self.llm_config)


@dataclass
class HarnessState:
    """Harness 运行状态"""
    session_id: str = field(default_factory=lambda: f"session_{int(time.time())}")
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_files: int = 0
    scanned_files: int = 0
    changed_files: int = 0
    in_progress_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    total_iterations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_cost: float = 0.0
    avg_score: float = 0.0
    status: str = "initialized"
    errors: List[Dict[str, Any]] = field(default_factory=list)


class Harness:
    """
    智能核心协调器 (Agent 增强版)
    
    核心能力：
    1. 🧠 完整 Agent 工作流：规划 → 执行 → 验证 → 迭代修复 → 输出
    2. ⚡ 增量处理：只处理变化的文件，大幅提升重复运行速度
    3. 💾 缓存集成：自动利用 LLM 缓存，降低成本
    4. 📜 历史记录：完整记录处理过程，支持审计和回溯
    5. 🔄 智能迭代：基于验证反馈自动修复，直到达到质量阈值
    6. 🚀 并行处理：多线程并发处理，提升批量处理速度
    7. 📊 实时进度：流式输出处理进度和状态
    8. 🛡️ 容错机制：处理失败时优雅降级，不影响整体流程
    
    增强工作流程：
    ```
    扫描 → 增量过滤 → 规划 → [缓存检查] → 执行 → 验证 → [修复] → 输出 → 历史记录
            ↑                                                                 ↑
            └─────────────────────────────────────────────────────────────────┘
    ```
    """
    
    def __init__(self, config: HarnessConfig = None):
        self.config = config or HarnessConfig()
        self.state = HarnessState()
        self._state_lock = threading.Lock()
        
        # 初始化核心组件
        self.cache = CacheManager() if self.config.use_cache else None
        self.history = HistoryManager() if self.config.enable_history else None
        self.change_tracker = FileChangeTracker()  # 文件变化追踪器
        
        # 初始化向量数据库
        self.vector_store = None
        if self.config.enable_vector_store:
            self._init_vector_store()
        
        # 初始化三元组（注入依赖，各自使用独立的 LLM 配置）
        self.planner = Planner(
            cache_manager=self.cache, 
            history_manager=self.history,
            llm_config=self.config.get_llm_config_for('planner'),
            enable_clustering=self.config.enable_clustering,
            output_structure=self.config.output_structure,
            note_organization=self.config.note_organization,
        )
        self.executor = Executor(
            llm_config=self.config.get_llm_config_for('executor'),
            cache_manager=self.cache,
            history_manager=self.history,
            enable_content_filter=self.config.enable_content_filter,
            enable_scene_detection=self.config.enable_scene_detection
        )
        self.validator = Validator(
            history_manager=self.history,
            llm_config=self.config.get_llm_config_for('validator')
        )
        
        # 初始化内容预分析器
        self.content_analyzer = None
        if self.config.enable_content_analyzer:
            try:
                self.content_analyzer = ContentAnalyzer(
                    llm_config=self.config.get_llm_config_for('analyzer'),
                    cache_manager=self.cache,
                    max_content_length=self.config.content_analyzer_max_length
                )
            except Exception as e:
                # 分析器初始化失败时降级，不阻塞主处理流程。
                self.content_analyzer = None
                self.config.enable_content_analyzer = False
                self._log(f"⚠️  ContentAnalyzer disabled: {e}", level="warning")
        
        # 初始化插件
        self.plugin = get_plugin(self.config.plugin)
        
        # 初始化错误处理器
        self.error_handler = ErrorHandler() if self.config.enable_error_handler else None
        
        # 初始化进度追踪器
        self.progress_tracker = None
        if self.config.enable_progress:
            self.progress_tracker = BatchProgressTracker(
                total_files=0,  # 将在扫描后更新
                callback=self.config.progress_callback
            )
    
    def _init_vector_store(self):
        """初始化向量数据库"""
        try:
            embedding_config = {
                "provider": self.config.embedding_provider,
                "model": self.config.embedding_model,
                "api_key": self.config.embedding_api_key,
            }
            
            self.vector_store = VectorStore(
                collection_name="lumina_notes",
                persist_directory=self.config.vector_store_persist_dir,
                embedding_provider_config=embedding_config
            )
            self._log(f"🔮 Vector store initialized")
        except ImportError as e:
            self._log(f"⚠️  Vector store not available: {e}")
            self.vector_store = None
        except Exception as e:
            self._log(f"⚠️  Failed to initialize vector store: {e}")
            self.vector_store = None
    
    def _index_to_vector_store(self, result: Dict[str, Any]):
        """将处理结果索引到向量数据库"""
        if not self.vector_store or not result["final_output"]:
            return
        
        try:
            output = result["final_output"]
            doc_id = result["source"]
            
            self.vector_store.add_note(
                note_id=doc_id,
                title=output.title,
                content=output.content,
                tags=output.tags,
                source=output.source,
                metadata={
                    "score": result["best_score"],
                    "iterations": result["iterations"],
                    "session_id": self.state.session_id,
                }
            )
            self._log(f"🔮 Indexed to vector store: {doc_id}")
        except Exception as e:
            self._log(f"⚠️  Failed to index to vector store: {e}")
    
    def search_notes(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索笔记
        
        Args:
            query: 搜索查询
            n_results: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if not self.vector_store:
            self._log("⚠️  Vector store not available")
            return []
        
        try:
            results = self.vector_store.search(query, n_results=n_results)
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.document.id,
                    "title": result.document.metadata.get("title", "Unknown"),
                    "content_preview": result.document.content[:200] + "...",
                    "score": result.score,
                    "tags": json.loads(result.document.metadata.get("tags", "[]")),
                    "source": result.document.metadata.get("source", ""),
                })
            
            return formatted_results
        except Exception as e:
            self._log(f"⚠️  Search failed: {e}")
            return []
    
    def find_related_notes(self, note_id: str, min_score: float = 0.7) -> List[Dict[str, Any]]:
        """
        查找关联笔记
        
        Args:
            note_id: 笔记 ID
            min_score: 最小相似度阈值
            
        Returns:
            关联笔记列表
        """
        if not self.vector_store:
            self._log("⚠️  Vector store not available")
            return []
        
        try:
            return self.vector_store.find_related_notes(note_id, min_score)
        except Exception as e:
            self._log(f"⚠️  Find related failed: {e}")
            return []
    
    def build_knowledge_graph(self, min_similarity: float = 0.7) -> Dict[str, Any]:
        """
        构建知识图谱
        
        Args:
            min_similarity: 最小相似度阈值
            
        Returns:
            知识图谱数据
        """
        if not self.vector_store:
            self._log("⚠️  Vector store not available")
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}
        
        try:
            kg = KnowledgeGraph(self.vector_store)
            return kg.build_graph(min_similarity)
        except Exception as e:
            self._log(f"⚠️  Build knowledge graph failed: {e}")
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}
    
    def get_vector_stats(self) -> Dict[str, Any]:
        """获取向量数据库统计"""
        if not self.vector_store:
            return {"available": False}
        
        return {
            "available": True,
            **self.vector_store.get_stats()
        }

    def _reset_run_state(self):
        """在每次 run 前重置与本轮运行相关的状态字段。"""
        now = time.time()
        self.state.session_id = f"session_{int(now)}"
        self.state.start_time = now
        self.state.end_time = None
        self.state.total_files = 0
        self.state.scanned_files = 0
        self.state.changed_files = 0
        self.state.in_progress_files = 0
        self.state.processed_files = 0
        self.state.skipped_files = 0
        self.state.failed_files = 0
        self.state.total_iterations = 0
        self.state.cache_hits = 0
        self.state.cache_misses = 0
        self.state.total_cost = 0.0
        self.state.avg_score = 0.0
        self.state.errors = []
    
    def run(
        self,
        input_path: str,
        recursive: bool = True,
        file_filter: Optional[str] = None,
        pre_scanned_files: Optional[List[FileInfo]] = None,
    ) -> Dict[str, Any]:
        """
        执行完整 Harness 流程（Agent 增强版）
        
        Args:
            input_path: 输入文件或目录
            recursive: 是否递归扫描
            file_filter: 文件过滤规则，支持 glob，多个模式可用逗号分隔
            pre_scanned_files: 预先扫描并聚合好的文件列表（用于多 source 一次规划）
            
        Returns:
            详细执行结果报告
        """
        self._reset_run_state()
        self.state.status = "running"
        self._log_start()
        
        try:
            # Phase 1: 扫描 & 规划
            self._log("📂 Phase 1: Scanning & Planning")
            
            # 初始化进度追踪
            if self.progress_tracker:
                self.progress_tracker.start_file("scanning")
                self.progress_tracker.next_phase()
            
            if pre_scanned_files is None:
                files = self.planner.scan(
                    input_path,
                    recursive,
                    file_filter=file_filter,
                    supported_extensions=self.config.supported_extensions,
                )
            else:
                files = list(pre_scanned_files)
                self._log(f"📊 Using pre-scanned files: {len(files)}")
            self.state.total_files = len(files)
            self.state.scanned_files = len(files)
            self._log(f"📊 Found {len(files)} files total")
            
            # 更新进度追踪器总文件数
            if self.progress_tracker:
                self.progress_tracker.total_files = len(files)
            
            # 增量过滤（只处理变化的文件）
            if self.config.incremental and self.history:
                if self.progress_tracker:
                    self.progress_tracker.set_phase("incremental_filter")
                
                files = self._filter_incremental(files)
                self.state.changed_files = len(files)
                self._log(f"⚡ {len(files)} files need processing (incremental mode)")
            else:
                self.state.changed_files = len(files)
            
            if not files:
                self.state.in_progress_files = 0
                self._log("✅ No files need processing, exiting")
                return self._generate_final_report([])
            
            # Phase 1.5: 内容预分析（可选，用于智能过滤和合并）
            content_briefs = None
            if self.config.enable_content_analyzer and self.content_analyzer:
                self._log("\n🔍 Phase 1.5: Content Analysis (lightweight LLM)")
                if self.progress_tracker:
                    self.progress_tracker.set_phase("content_analysis")
                
                brief_result = self.content_analyzer.analyze_batch(files)
                content_briefs = brief_result.briefs
                
                # 记录统计
                self._log(f"📊 Analysis complete: {brief_result.cache_hits} cache hits, "
                         f"{brief_result.cache_misses} new analyses")
                self._log(f"💰 Analysis cost: ${brief_result.total_cost:.4f} ({brief_result.total_tokens} tokens)")
                
                # 显示过滤和合并建议
                skip_count = sum(1 for b in content_briefs if b.suggested_action == "skip")
                merge_count = sum(1 for b in content_briefs if b.suggested_action == "merge")
                self._log(f"🎯 Suggestions: {skip_count} skip, {merge_count} merge, "
                         f"{len(content_briefs) - skip_count - merge_count} process")
            
            # 生成处理计划（传入内容简述）
            if self.progress_tracker:
                self.progress_tracker.set_phase("planning")
            
            existing_notes = self._collect_existing_notes() if self.config.enable_clustering else None
            plan = self.planner.plan(files, existing_notes=existing_notes, content_briefs=content_briefs)
            self._log(f"🎯 Processing strategy: {plan.strategy}")
            self._log(f"📦 Total batches: {len(plan.batches)}")

            # Planner 低价值跳过：标记为“无需处理”，并写入指纹，后续仅在文件变化后重新判断。
            skipped_by_value = list(getattr(self.planner, "last_skipped_files", []) or [])
            if skipped_by_value:
                self.state.skipped_files += len(skipped_by_value)
                self._log(f"🧠 Planner marked {len(skipped_by_value)} files as no-note-value (skip)")
                for skipped_file in skipped_by_value:
                    try:
                        fingerprint = self.change_tracker.calculate_file_fingerprint(skipped_file.path)
                        self.change_tracker.mark_as_processed(fingerprint)
                    except Exception as e:
                        self._log(f"⚠️  Failed to mark skipped file as processed: {e}", level="warning")
            
            # Phase 2-4: 执行 → 验证 → 迭代
            self._log("\n🚀 Phase 2: Processing files")
            if self.progress_tracker:
                self.progress_tracker.set_phase("processing")
            
            results = self._process_batches(plan)
            
            # Phase 5: 输出结果
            self._log("\n💾 Phase 3: Saving outputs")
            if self.progress_tracker:
                self.progress_tracker.set_phase("saving")
            
            self._save_outputs(results)
            
            # Phase 6: 记录历史
            if self.history:
                if self.progress_tracker:
                    self.progress_tracker.set_phase("recording_history")
                self._record_history(results)
            
            # 生成最终报告（包含分析器统计）
            self.state.status = "completed"
            final_report = self._generate_final_report(results)
            
            # 添加内容分析统计
            if content_briefs:
                final_report["content_analysis"] = {
                    "total_analyzed": len(content_briefs),
                    "cache_hits": brief_result.cache_hits,
                    "cache_misses": brief_result.cache_misses,
                    "total_tokens": brief_result.total_tokens,
                    "total_cost": brief_result.total_cost,
                    "duration": brief_result.duration,
                    "suggested_skips": sum(1 for b in content_briefs if b.suggested_action == "skip"),
                    "suggested_merges": sum(1 for b in content_briefs if b.suggested_action == "merge"),
                }
            
            self._log_final_results(final_report)
            
            return final_report
            
        except Exception as e:
            self.state.status = "failed"
            self.state.errors.append({"type": "system_error", "message": str(e)})
            self._log(f"❌ System error: {e}", level="error")
            
            # 使用错误处理器处理严重错误
            if self.error_handler:
                self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.CRITICAL,
                    context="Harness.run"
                )
            
            raise
    
    def _filter_incremental(self, files: List[FileInfo]) -> List[FileInfo]:
        """过滤出需要增量处理的文件（基于内容哈希检测）"""
        files_to_process = []
        
        for file_info in files:
            # 使用 FileChangeTracker 检查文件内容是否发生变化
            try:
                changed, fingerprint = self.change_tracker.has_file_changed(file_info.path, force_check_content=False)
                if changed:
                    files_to_process.append(file_info)
                    self._log(f"🔄 Needs processing: {file_info.path} (content changed)")
                else:
                    # 文件未变化，跳过
                    self.state.skipped_files += 1
                    self._log(f"⏭️  Skipped: {file_info.path} (content unchanged)")
            except Exception as e:
                # 如果检测失败，默认处理该文件
                self._log(f"⚠️  Failed to check changes for {file_info.path}: {e}, processing anyway", level="warning")
                files_to_process.append(file_info)
        
        return files_to_process
    
    def _process_batches(self, plan) -> List[Dict[str, Any]]:
        """处理所有批次"""
        results = []
        
        for batch_idx, batch in enumerate(plan.batches):
            self._log(f"\n📦 Processing batch {batch_idx + 1}/{len(plan.batches)} "
                     f"({len(batch)} files)")
            
            batch_start = time.time()
            
            if self.config.parallel and len(batch) > 1:
                # 并行处理批次
                batch_results = self._process_batch_parallel(batch, plan)
            else:
                # 串行处理批次
                batch_results = self._process_batch_serial(batch, plan)
            
            results.extend(batch_results)
            
            batch_duration = time.time() - batch_start
            self._log(f"✅ Batch completed in {batch_duration:.1f}s")
        
        return results
    
    def _process_batch_serial(self, batch: List[FileInfo], plan) -> List[Dict[str, Any]]:
        """串行处理批次"""
        results = []
        for file_info in batch:
            with self._state_lock:
                self.state.in_progress_files = 1
            try:
                result = self._process_single(file_info, plan)
                results.append(result)
                if result.get("processed"):
                    self.state.processed_files += 1
            except Exception as e:
                self.state.failed_files += 1
                error_msg = f"Failed to process {file_info.path}: {e}"
                self.state.errors.append({"file": str(file_info.path), "error": str(e)})
                self._log(f"❌ {error_msg}", level="error")
            finally:
                with self._state_lock:
                    self.state.in_progress_files = 0
        return results
    
    def _process_batch_parallel(self, batch: List[FileInfo], plan) -> List[Dict[str, Any]]:
        """并行处理批次"""
        results = []
        with self._state_lock:
            self.state.in_progress_files = len(batch)
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {executor.submit(self._process_single, file_info, plan): file_info 
                      for file_info in batch}
            
            for future in as_completed(futures):
                file_info = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result.get("processed"):
                        self.state.processed_files += 1
                except Exception as e:
                    self.state.failed_files += 1
                    error_msg = f"Failed to process {file_info.path}: {e}"
                    self.state.errors.append({"file": str(file_info.path), "error": str(e)})
                    self._log(f"❌ {error_msg}", level="error")
                finally:
                    with self._state_lock:
                        self.state.in_progress_files = max(0, self.state.in_progress_files - 1)
        
        return results
    
    def _process_single(self, file_info: FileInfo, plan) -> Dict[str, Any]:
        """
        处理单个文件或文档簇，包含完整的迭代优化流程
        
        增强功能：
        1. 支持文档簇聚合处理
        2. 保留关联关系
        
        流程：
        1. 检查缓存 → 命中则直接返回
        2. 生成初始版本
        3. 快速验证（可选）→ 快速过滤低质量
        4. 完整验证 → 生成修复建议
        5. 迭代修复 → 直到达到阈值或最大迭代次数
        6. 选择最佳版本 → 输出
        """
        file_start = time.time()
        file_path_str = str(file_info.path)
        
        # 检查是否为文档簇
        is_cluster = file_info.metadata.get("is_cluster", False)
        
        if is_cluster:
            self._log(f"\n📦 Processing cluster: {file_info.metadata.get('cluster_title', 'Unknown')}")
            self._log(f"   Files in cluster: {len(file_info.metadata.get('cluster_files', []))}")
        else:
            self._log(f"\n📄 Processing: {file_path_str}")
        
        # 更新进度追踪器
        if self.progress_tracker:
            self.progress_tracker.start_file(file_path_str)
        
        iteration_history = []
        all_outputs = []
        best_output: Optional[NoteOutput] = None
        best_score = 0.0
        best_validation: Optional[ValidationResult] = None
        
        try:
            # Step 1: 检查缓存
            if self.config.use_cache and self.cache:
                cached_result = self.cache.get_processed_result(file_info.hash)
                if cached_result:
                    try:
                        # 兼容两种缓存格式：
                        # 1) 旧格式: {"score":...,"output":...}
                        # 2) 当前 CacheManager 包装格式: {"result":"{...}","created_at":...}
                        parsed = json.loads(cached_result)
                        if isinstance(parsed, dict) and "result" in parsed:
                            result_payload = parsed.get("result", "")
                            if isinstance(result_payload, str):
                                cached_data = json.loads(result_payload)
                            else:
                                cached_data = result_payload
                        else:
                            cached_data = parsed

                        if not isinstance(cached_data, dict) or "output" not in cached_data:
                            raise ValueError("invalid processed cache payload")

                        self._log(f"💾 Cache hit! Using cached result")
                        self.state.cache_hits += 1
                        return {
                            "source": file_path_str,
                            "cached": True,
                            "best_score": float(cached_data.get("score", 0.0)),
                            "final_output": NoteOutput(**cached_data["output"]),
                            "processing_time": 0,
                            "success": True,
                            "processed": True,
                            "final_passed": True,
                            "iterations": 0,
                            "best_round": 0,
                            "best_output": NoteOutput(**cached_data["output"]),
                            "best_validation": None,
                            "all_outputs": [],
                            "iteration_history": [],
                            "file_info": {
                                "path": file_path_str,
                                "size": file_info.size,
                                "type": file_info.type,
                                "modified": file_info.modified,
                                "hash": file_info.hash,
                                "metadata": dict(file_info.metadata),
                            },
                        }
                    except Exception as e:
                        self._log(f"⚠️  Invalid processed cache for {file_path_str}: {e}, recomputing", level="warning")
                self.state.cache_misses += 1
            
            # Step 2: 迭代处理
            for iteration in range(self.config.max_iterations):
                if self.progress_tracker:
                    self.progress_tracker.next_phase()
                
                iter_start = time.time()
                self.state.total_iterations += 1
                
                # 构建执行上下文
                context = ExecutionContext(
                    session_id=self.state.session_id,
                    file_info=file_info,
                    plan=plan,
                    iteration=iteration,
                    previous_output=best_output,
                    previous_validation=best_validation,
                )
                
                # 如果是文档簇，需要特殊处理
                if is_cluster:
                    note = self._execute_cluster(file_info, context)
                    current_output = note
                    all_outputs.append(current_output)
                    
                    # 文档簇跳过验证流程，直接返回
                    best_output = current_output
                    best_score = 0.8  # 聚合文档默认质量分
                    
                    iteration_result = {
                        "round": iteration + 1,
                        "output": {
                            "title": current_output.title,
                            "content_length": len(current_output.content),
                            "tags": current_output.tags,
                            "links": current_output.links,
                        },
                        "validation": {
                            "score": best_score,
                            "passed": True,
                            "issue_count": 0,
                            "error_count": 0,
                            "warning_count": 0,
                        },
                        "duration": time.time() - iter_start,
                    }
                    iteration_history.append(iteration_result)
                    break  # 文档簇只处理一轮
                else:
                    # 执行（生成/修复内容）- 使用 GracefulDegradation
                    with GracefulDegradation(fallback=None, severity=ErrorSeverity.WARNING, context=f"Executor round {iteration+1}", handler=self.error_handler) as gd:
                        if iteration == 0:
                            gd.result = self.executor.execute(context)
                        else:
                            gd.result = self.executor.revise(context)
                    
                    current_output = gd.result
                    if current_output is None:
                        self._log(f"⚠️  Failed to generate output in round {iteration+1}, skipping iteration", level="warning")
                        if self.error_handler:
                            self.state.errors.append({"file": file_path_str, "error": f"Failed to generate output in round {iteration+1}"})
                        continue

                    # 内容过滤命中：直接作为跳过处理，不进入验证/保存
                    if current_output.metadata.get("filtered"):
                        reason = current_output.metadata.get("filter_reason", "filtered")
                        self._log(f"⏭️  Filtered: {file_path_str} ({reason})")
                        self.state.skipped_files += 1
                        processing_duration = time.time() - file_start
                        if self.progress_tracker:
                            self.progress_tracker.file_complete({
                                "file": file_path_str,
                                "score": 0.0,
                                "success": True
                            })
                        return {
                            "source": file_path_str,
                            "file_info": {
                                "path": file_path_str,
                                "size": file_info.size,
                                "type": file_info.type,
                                "modified": file_info.modified,
                                "hash": file_info.hash,
                            },
                            "processed": False,
                            "filtered": True,
                            "filter_reason": reason,
                            "cached": False,
                            "final_passed": False,
                            "iterations": 1,
                            "best_round": 0,
                            "best_score": 0.0,
                            "best_output": None,
                            "best_validation": None,
                            "final_output": None,
                            "all_outputs": [],
                            "iteration_history": [],
                            "processing_time": processing_duration,
                            "success": True
                        }
                    
                    all_outputs.append(current_output)
                    
                    # 快速验证（只检查基础规则，不调用 LLM）
                    quick_validation = None
                    if iteration == 0 and self.config.quick_validation_first:
                        with GracefulDegradation(fallback=None, severity=ErrorSeverity.WARNING, context="Quick validation", handler=self.error_handler) as gd:
                            gd.result = self.validator.validate_quick(current_output)
                        quick_validation = gd.result
                        
                        if quick_validation and not quick_validation.passed and quick_validation.score < 0.5:
                            self._log(f"⚠️  Quick validation failed (score={quick_validation.score:.2f}), "
                                 f"re-trying with better prompt")
                
                # 完整验证
                validation = None
                with GracefulDegradation(fallback=None, severity=ErrorSeverity.WARNING, context="Full validation", handler=self.error_handler) as gd:
                    gd.result = self.validator.validate(current_output, file_info, context)
                validation = gd.result
                
                if validation is None:
                    self._log(f"⚠️  Validation failed, using best so far", level="warning")
                    validation = best_validation
                    if not validation:
                        # 如果没有任何验证结果，创建一个临时的
                        from dataclasses import dataclass
                        @dataclass
                        class TempValidation:
                            passed: bool = False
                            score: float = 0.0
                            issues: list = field(default_factory=list)
                            suggestions: list = field(default_factory=list)
                        validation = TempValidation()
                
                # 记录迭代结果
                iteration_result = {
                    "round": iteration + 1,
                    "output": {
                        "title": current_output.title,
                        "content_length": len(current_output.content),
                        "tags": current_output.tags,
                        "links": current_output.links,
                    },
                    "validation": {
                        "score": validation.score,
                        "passed": validation.passed,
                        "issue_count": len(validation.issues),
                        "error_count": len([i for i in validation.issues if hasattr(i, 'severity') and i.severity == "error"]),
                        "warning_count": len([i for i in validation.issues if hasattr(i, 'severity') and i.severity == "warning"]),
                    },
                    "duration": time.time() - iter_start,
                }
                iteration_history.append(iteration_result)
                
                # 更新最佳结果
                if validation.score > best_score:
                    best_score = validation.score
                    best_output = current_output
                    best_validation = validation
                    self._log(f"✨ Round {iteration + 1}: NEW BEST score={best_score:.2f}, "
                             f"passed={validation.passed}, issues={len(validation.issues)}")
                else:
                    self._log(f"🔄 Round {iteration + 1}: score={validation.score:.2f}, "
                             f"passed={validation.passed}, issues={len(validation.issues)}")
                
                # 检查终止条件
                if validation.passed and validation.score >= self.config.quality_threshold:
                    self._log(f"✅ Quality threshold reached!")
                    break
                
                if iteration == self.config.max_iterations - 1:
                    self._log(f"⚠️  Max iterations reached, stopping")
                    break
                
                if not validation.suggestions:
                    self._log(f"⚠️  No suggestions for improvement, stopping")
                    break
            
            # Step 3: 处理最终结果
            final_passed = bool(best_output) and (
                (best_validation.passed if best_validation else False) or self.config.allow_partial
            )
            
            if not final_passed:
                self._log(f"❌ Processing failed, quality did not meet threshold")
                self.state.failed_files += 1
            else:
                self._log(f"✅ Processing complete, best score={best_score:.2f}")
            
            processing_duration = time.time() - file_start
            
            # Step 4: 缓存结果
            if self.config.use_cache and self.cache and best_output:
                cache_data = {
                    "score": best_score,
                    "output": {
                        "title": best_output.title,
                        "content": best_output.content,
                        "tags": best_output.tags,
                        "links": best_output.links,
                        "source": best_output.source,
                        "metadata": best_output.metadata,
                        "processing_info": best_output.processing_info,
                    }
                }
                self.cache.set_processed_result(file_info.hash, json.dumps(cache_data))
            
            # Step 5: 标记文件为已处理（更新指纹）
            if best_output:
                try:
                    fingerprint = self.change_tracker.calculate_file_fingerprint(file_info.path)
                    self.change_tracker.mark_as_processed(fingerprint)
                    self._log(f"✅ Marked as processed: {file_info.path}")
                except Exception as e:
                    self._log(f"⚠️  Failed to mark file as processed: {e}", level="warning")
                    if self.error_handler:
                        self.error_handler.handle_error(e, severity=ErrorSeverity.WARNING, context="Mark file processed")
            else:
                self._log(f"⚠️  Skipping processed mark for {file_info.path} because no output was generated", level="warning")
            
            # 计算成本
            exec_stats = self.executor.get_stats()
            self.state.total_cost += exec_stats["total_cost"] / self.state.total_files if self.state.total_files else 0
            
            # 更新进度追踪器
            if self.progress_tracker:
                self.progress_tracker.file_complete({
                    "file": file_path_str,
                    "score": best_score,
                    "success": final_passed
                })
            
            return {
                "source": file_path_str,
                "file_info": {
                    "path": file_path_str,
                    "size": file_info.size,
                    "type": file_info.type,
                    "modified": file_info.modified,
                    "hash": file_info.hash,
                    "metadata": dict(file_info.metadata),
                },
                "processed": best_output is not None,
                "cached": False,
                "final_passed": final_passed,
                "iterations": len(iteration_history),
                "best_round": (iteration_history.index(max(iteration_history, key=lambda x: x['validation']['score'])) + 1) if iteration_history else 0,
                "best_score": best_score,
                "best_output": best_output,
                "best_validation": best_validation,
                "final_output": best_output,
                "all_outputs": all_outputs,
                "iteration_history": iteration_history,
                "processing_time": processing_duration,
                "success": final_passed
            }
            
        except Exception as e:
            self.state.failed_files += 1
            processing_duration = time.time() - file_start
            
            self._log(f"❌ Critical failure processing {file_path_str}: {e}", level="error")
            if self.error_handler:
                self.error_handler.handle_error(e, severity=ErrorSeverity.ERROR, context=f"Process file {file_path_str}")
                self.state.errors.append({"file": file_path_str, "error": str(e)})
            
            return {
                "source": file_path_str,
                "file_info": {
                    "path": file_path_str,
                    "size": file_info.size,
                    "type": file_info.type,
                    "modified": file_info.modified,
                    "hash": file_info.hash,
                    "metadata": dict(file_info.metadata),
                },
                "processed": False,
                "cached": False,
                "final_passed": False,
                "iterations": 0,
                "best_score": 0.0,
                "best_output": None,
                "best_validation": None,
                "final_output": None,
                "all_outputs": [],
                "iteration_history": [],
                "processing_time": processing_duration,
                "success": False,
                "error": str(e)
            }
    
    def _save_outputs(self, results: List[Dict]):
        """保存输出到文件（增强版：支持编码保留、权限检查、敏感信息检测）"""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_count = 0
        for result in results:
            if not result["processed"] or not result["final_output"]:
                continue
            
            output = result["final_output"]

            # 追加模式：写入已有笔记，不创建新文件
            if output.metadata.get("is_append"):
                target = output.metadata.get("append_to_path")
                if not target:
                    append_title = output.metadata.get("append_to")
                    if append_title:
                        fallback = self._find_existing_note_path(output_dir, NoteOutput(
                            title=str(append_title),
                            content="",
                            tags=[],
                            links=[],
                            source=output.source,
                            metadata={},
                        ))
                        if fallback:
                            target = str(fallback)
                if target:
                    target_path = Path(target).expanduser()
                    try:
                        if target_path.exists():
                            existing_content, existing_meta = read_file_with_metadata(target_path)
                            merged_content = existing_content.rstrip() + "\n\n" + output.content.strip() + "\n"
                            write_file_with_metadata(merged_content, existing_meta, backup=False)
                        else:
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            new_meta = FileMetadata(
                                path=target_path,
                                encoding='utf-8',
                                line_endings='LF',
                                size=len(output.content.encode('utf-8')),
                                modified=0,
                                is_symlink=False,
                            )
                            write_file_with_metadata(output.content, new_meta, backup=False)
                        saved_count += 1
                        self._log(f"💾 Appended: {target_path}")
                        self._index_to_vector_store(result)
                        continue
                    except Exception as e:
                        self._log(f"❌ Failed to append {target_path}: {e}", level="error")
                        self.state.errors.append({"file": str(target_path), "error": str(e)})
                        continue
                else:
                    self._log("⚠️  Append mode missing append_to_path, fallback to new file", level="warning")

            file_meta = result.get("file_info", {}).get("metadata", {}) if isinstance(result.get("file_info"), dict) else {}

            # 根据 planner 规划的结构落盘
            note_subdir = str(file_meta.get("note_subdir", "")).strip("/")
            target_output_dir = (output_dir / note_subdir) if note_subdir else output_dir
            target_output_dir.mkdir(parents=True, exist_ok=True)

            # 常规笔记去重写入：优先按 source，其次按标题相似度
            existing_note_path = self._find_existing_note_path(output_dir, output)

            # 生成安全文件名
            safe_title = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in output.title)
            safe_title = safe_title.strip() or "untitled"
            filename = f"{safe_title}.md"
            filepath = existing_note_path if existing_note_path else (target_output_dir / filename)
            migrate_from_path = None

            # 如果命中的是旧的平铺文件，而 planner 已规划子目录，则迁移到新结构
            if existing_note_path and note_subdir and existing_note_path.parent == output_dir:
                filepath = target_output_dir / existing_note_path.name
                migrate_from_path = existing_note_path

            # 新文件才做避免冲突；已有文件直接覆盖更新，避免重复堆积
            if not existing_note_path:
                counter = 1
                while filepath.exists():
                    filepath = target_output_dir / f"{safe_title}_{counter}.md"
                    counter += 1
            
            # 格式化输出内容
            content = self._format_output(output, result)
            
            # 权限检查（如果配置了权限规则）
            if hasattr(self.config, 'write_permission_rules') and self.config.write_permission_rules:
                allowed, errors = check_write_permission(filepath, self.config.write_permission_rules)
                if not allowed:
                    self._log(f"❌ Permission denied for {filepath}: {errors}", level="error")
                    self.state.errors.append({"file": str(filepath), "error": f"Permission denied: {errors}"})
                    continue
            
            # 敏感信息检测
            sensitive_issues = check_sensitive_content(content)
            if sensitive_issues:
                self._log(f"⚠️  Sensitive content detected in {filepath}:", level="warning")
                for issue in sensitive_issues:
                    self._log(f"  - {issue}", level="warning")
                # 不阻止写入，但记录警告
                self.state.errors.append({
                    "file": str(filepath), 
                    "warning": f"Sensitive content detected: {sensitive_issues}"
                })
            
            # 使用增强的文件写入（保留编码和换行符）
            try:
                # 创建 FileMetadata（新文件使用 UTF-8 + LF）
                metadata = FileMetadata(
                    path=filepath,
                    encoding='utf-8',
                    line_endings='LF',
                    size=len(content.encode('utf-8')),
                    modified=0,
                    is_symlink=False
                )
                
                write_file_with_metadata(content, metadata, backup=False)

                # 迁移旧平铺文件到新结构后，清理原文件
                if migrate_from_path and migrate_from_path != filepath and migrate_from_path.exists():
                    try:
                        migrate_from_path.unlink()
                        self._log(f"📦 Migrated note to structured path: {filepath}")
                    except Exception as e:
                        self._log(f"⚠️  Failed to remove old flat note {migrate_from_path}: {e}", level="warning")

                saved_count += 1
                if existing_note_path:
                    self._log(f"♻️  Updated existing note: {filepath}")
                else:
                    self._log(f"💾 Saved: {filepath}")
                
            except Exception as e:
                self._log(f"❌ Failed to save {filepath}: {e}", level="error")
                self.state.errors.append({"file": str(filepath), "error": str(e)})
                continue
            
            # 索引到向量数据库
            self._index_to_vector_store(result)
        
        self._log(f"✅ Saved {saved_count} files to {output_dir}")

    def _find_existing_note_path(self, output_dir: Path, output: NoteOutput) -> Optional[Path]:
        """查找可复用的已有笔记文件（先按 source，再按标题相似度）。"""
        md_files = list(output_dir.rglob("*.md"))
        if not md_files:
            return None

        source = (output.source or "").strip()
        if source:
            for md in md_files:
                try:
                    content, _ = read_file_with_metadata(md)
                except Exception:
                    continue

                # Obsidian frontmatter 里通常有 source: ...
                if self._content_has_source(content, source):
                    return md

        # 没有 source 命中时，按标题相似度做兜底匹配
        normalized_target = self._normalize_title(output.title)
        best_match = None
        best_score = 0.0
        for md in md_files:
            score = SequenceMatcher(None, normalized_target, self._normalize_title(md.stem)).ratio()
            if score > best_score:
                best_score = score
                best_match = md

        if best_match and best_score >= 0.92:
            return best_match
        return None

    def _content_has_source(self, content: str, source: str) -> bool:
        """检查笔记内容/Frontmatter 是否记录了同一个 source。"""
        # 匹配 YAML 风格：source: /path/to/file
        pattern = rf"(?m)^source:\s*['\"]?{re.escape(source)}['\"]?\s*$"
        if re.search(pattern, content):
            return True

        # 兼容纯 markdown 中的 Source: /path
        return source in content

    @staticmethod
    def _normalize_title(title: str) -> str:
        text = (title or "").lower()
        text = re.sub(r"[_\-\s]+", " ", text)
        text = re.sub(r"\d+$", "", text).strip()
        return text
    
    def _format_output(self, output: NoteOutput, result: Dict) -> str:
        """格式化输出内容（委托给插件渲染）"""
        file_meta = result.get("file_info", {}).get("metadata", {}) if isinstance(result.get("file_info"), dict) else {}
        note_subdir = str(file_meta.get("note_subdir", "")).strip("/")

        para = ""
        if note_subdir:
            parts = [p for p in note_subdir.split("/") if p]
            para_candidates = {"projects", "areas", "resources", "archive", "archives"}
            for part in parts:
                if part.lower() in para_candidates:
                    para = "Archive" if part.lower() == "archives" else part
                    break
            if not para and parts:
                para = parts[-1]

        # 构建元数据
        metadata = {
            **output.metadata,
            "note_subdir": note_subdir,
            "para": output.metadata.get("para") or para,
            f"{self.config.metadata_prefix}score": result["best_score"],
            f"{self.config.metadata_prefix}iterations": result["iterations"],
            f"{self.config.metadata_prefix}best_round": result["best_round"],
            f"{self.config.metadata_prefix}source": output.source,
            f"{self.config.metadata_prefix}processed_at": datetime.now().isoformat(),
            f"{self.config.metadata_prefix}session_id": self.state.session_id,
        }
        
        note_data = NoteData(
            title=output.title,
            content=output.content,
            tags=output.tags,
            links=output.links,
            source=output.source,
            metadata=metadata,
        )
        return self.plugin.format(note_data)
    
    def _record_history(self, results: List[Dict]):
        """记录处理历史"""
        for result in results:
            if not result["processed"] or not result["final_output"]:
                continue
            
            record = ProcessingRecord(
                session_id=self.state.session_id,
                file_path=result["source"],
                file_hash=result["file_info"]["hash"],
                file_type=result["file_info"]["type"],
                file_size=result["file_info"]["size"],
                iterations=result["iterations"],
                best_score=result["best_score"],
                final_output=json.dumps(result["final_output"].__dict__),
                full_history=json.dumps(result["iteration_history"]),
                created_at=datetime.now().isoformat(),
                metadata={"session_id": self.state.session_id}
            )
            
            self.history.record_file_processing(record)
    
    def _generate_final_report(self, results: List[Dict]) -> Dict[str, Any]:
        """生成最终执行报告"""
        self.state.end_time = time.time()
        total_duration = self.state.end_time - self.state.start_time
        
        # 计算统计数据
        successful_results = [r for r in results if r["processed"] and r["final_output"]]
        scores = [r["best_score"] for r in successful_results]
        self.state.avg_score = sum(scores) / len(scores) if scores else 0.0
        
        cache_hit_rate = self.state.cache_hits / max(self.state.cache_hits + self.state.cache_misses, 1)
        
        # 生成质量分布
        score_distribution = {
            "A+": len([s for s in scores if s >= 0.9]),
            "A": len([s for s in scores if 0.8 <= s < 0.9]),
            "B": len([s for s in scores if 0.7 <= s < 0.8]),
            "C": len([s for s in scores if 0.6 <= s < 0.7]),
            "D": len([s for s in scores if 0.5 <= s < 0.6]),
            "F": len([s for s in scores if s < 0.5]),
        }
        
        return {
            "session_id": self.state.session_id,
            "status": self.state.status,
            "config": {
                "max_iterations": self.config.max_iterations,
                "quality_threshold": self.config.quality_threshold,
                "incremental": self.config.incremental,
                "parallel": self.config.parallel,
                "use_cache": self.config.use_cache,
            },
            "statistics": {
                "start_time": datetime.fromtimestamp(self.state.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.state.end_time).isoformat(),
                "total_duration": total_duration,
                "total_files": self.state.total_files,
                "processed_files": self.state.processed_files,
                "skipped_files": self.state.skipped_files,
                "failed_files": self.state.failed_files,
                "total_iterations": self.state.total_iterations,
                "cache_hits": self.state.cache_hits,
                "cache_misses": self.state.cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "estimated_total_cost": self.state.total_cost,
                "avg_score": self.state.avg_score,
                "score_distribution": score_distribution,
                "pass_rate": len([r for r in results if r.get("final_passed", False)]) / max(len(results), 1),
            },
            "results": [
                {
                    "source": r['source'],
                    "file_type": r['file_info']['type'],
                    "file_size": r['file_info']['size'],
                    "processed": r['processed'],
                    "passed": r.get('final_passed', False),
                    "iterations": r['iterations'],
                    "best_score": r['best_score'],
                    "processing_time": r['processing_time'],
                }
                for r in results
            ],
            "errors": self.state.errors,
        }
    
    def _execute_cluster(self, file_info: FileInfo, context: ExecutionContext) -> NoteOutput:
        """
        执行文档簇处理
        
        将多个相关短文档合并为一篇笔记，保留关联关系
        """
        cluster_files = file_info.metadata.get("cluster_files", [])
        cluster_strategy = file_info.metadata.get("cluster_strategy", "combine_short_docs")
        cluster_title = file_info.metadata.get("cluster_title", "Combined Notes")
        
        if not cluster_files:
            return NoteOutput(
                title="Empty Cluster",
                content="_No files in cluster_",
                tags=["error"],
                links=[],
                source=str(file_info.path),
                metadata={"error": "empty_cluster"},
            )
        
        # 读取所有文件内容
        file_contents = {}
        for file_path_str in cluster_files:
            file_path = Path(file_path_str)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_contents[file_path_str] = f.read()
            except Exception as e:
                file_contents[file_path_str] = f"[Error reading: {e}]"
        
        # 使用 DocumentClusterer 格式化
        from .document_cluster import DocumentCluster, DocumentClusterer, ClusterStrategy
        
        strategy_map = {
            "combine_short_docs": ClusterStrategy.COMBINE_SHORT_DOCS,
            "summarize_multiple": ClusterStrategy.SUMMARIZE_MULTIPLE,
            "append_to_existing": ClusterStrategy.APPEND_TO_EXISTING,
        }
        
        cluster = DocumentCluster(
            cluster_id=file_info.metadata.get("cluster_id", "unknown"),
            files=[Path(f) for f in cluster_files],
            strategy=strategy_map.get(cluster_strategy, ClusterStrategy.COMBINE_SHORT_DOCS),
            title=cluster_title,
            description=file_info.metadata.get("cluster_description"),
            metadata=file_info.metadata,
        )

        # summarize_multiple 使用 LLM 真实总结
        if cluster.strategy == ClusterStrategy.SUMMARIZE_MULTIPLE:
            source_blocks = []
            for idx, src in enumerate(cluster_files[:10]):
                text = file_contents.get(src, "")
                source_blocks.append(f"## Source {idx + 1}: {Path(src).name}\n{text[:1800]}")
            overview_scope = str(file_info.metadata.get("overview_scope", "")).strip().lower()
            overview_catalog = str(file_info.metadata.get("overview_catalog", "")).strip()
            title_hint = str(file_info.metadata.get("title_hint", cluster_title)).strip() or cluster_title
            if overview_scope == "global":
                prompt = (
                    "You are a knowledge architect. Build one high-value portfolio overview note from the batch.\n"
                    "Group the materials into a small hierarchy such as work, learning, life, communication or other appropriate domains.\n"
                    "Identify which materials deserve standalone notes, which should be merged, which belong to tasks or follow-up, and which are low-value raw data.\n"
                    "Generate a precise note title, not a raw filename.\n"
                    "Return JSON with fields: title, summary, key_points, tags, suggested_links, metadata.\n\n"
                    f"Title hint: {title_hint}\n"
                    f"File catalog:\n{overview_catalog}\n\n"
                    + "\n\n".join(source_blocks)
                )
            elif overview_scope == "project":
                prompt = (
                    "You are a technical program analyst. Summarize the project directory into one concise project overview note.\n"
                    "Focus on architecture, purpose, major modules, workflows, operational concerns, and learning value.\n"
                    "Do not produce a file-by-file inventory. Merge related files into a few themes.\n"
                    "Generate a clear topical title, such as 项目总览, 组件说明, or 操作手册.\n"
                    "Return JSON with fields: title, summary, key_points, tags, suggested_links, metadata.\n\n"
                    f"Title hint: {title_hint}\n"
                    f"Directory: {file_info.metadata.get('directory', '')}\n"
                    f"Source count: {len(cluster_files)}\n\n"
                    + "\n\n".join(source_blocks)
                )
            else:
                prompt = (
                    "You are a knowledge synthesis expert. Summarize the related documents into one high-quality note.\n"
                    "Generate a precise topical title and never use raw directory names like Collection, Append to, cluster, or date-only folder names.\n"
                    "Return JSON with fields: title, summary, key_points, tags, suggested_links, metadata.\n\n"
                    f"Title hint: {title_hint}\n"
                    f"Cluster title: {cluster_title}\n"
                    f"Source count: {len(cluster_files)}\n\n"
                    + "\n\n".join(source_blocks)
                )
            raw = self.executor._call_llm(prompt, context)
            note = self.executor._parse_output(raw, file_info, context)
            note.metadata.update({
                "is_cluster": True,
                "cluster_files": cluster_files,
                "cluster_strategy": cluster_strategy,
                "cluster_id": cluster.cluster_id,
                "overview_scope": overview_scope,
            })
            note.links = list(set(note.links + [Path(src).name for src in cluster_files]))
            note.content = note.content.rstrip() + "\n\n## Source Files\n" + "\n".join([f"- {src}" for src in cluster_files]) + "\n"
            return note

        clusterer = DocumentClusterer()
        result = clusterer.format_cluster(cluster, file_contents)
        
        # 构建 NoteOutput
        note = NoteOutput(
            title=result.title,
            content=result.content,
            tags=result.tags,
            links=[Path(src).name for src in result.sources],
            source=str(file_info.path),
            metadata={
                **result.metadata,
                "is_cluster": True,
                "cluster_files": cluster_files,
                "cluster_strategy": cluster_strategy,
            },
            processing_info={
                "session_id": context.session_id,
                "iteration": context.iteration,
                "cluster_id": cluster.cluster_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
        
        return note

    def _collect_existing_notes(self) -> List[Dict[str, Any]]:
        """收集输出目录中已有笔记，用于 append 匹配。"""
        notes: List[Dict[str, Any]] = []
        output_dir = Path(self.config.output_dir).expanduser()
        if not output_dir.exists() or not output_dir.is_dir():
            return notes

        for md in output_dir.rglob("*.md"):
            title = md.stem.replace("_", " ").strip()
            try:
                content, _ = read_file_with_metadata(md)
                for line in content.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip() or title
                        break
            except Exception:
                pass
            notes.append({"title": title, "path": str(md)})

        return notes
    
    def _log(self, message: str, level: str = "info"):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def _log_start(self):
        """记录启动信息"""
        self._log("=" * 60)
        self._log(f"🚀 Lumina Harness v0.2.0 (Agent Enhanced)")
        self._log(f"🆔 Session ID: {self.state.session_id}")
        self._log(f"⚙️  Config: max_iterations={self.config.max_iterations}, "
                 f"quality_threshold={self.config.quality_threshold}, "
                 f"incremental={self.config.incremental}, "
                 f"parallel={self.config.parallel}, "
                 f"vector_store={self.config.enable_vector_store}")
        self._log("=" * 60)
    
    def _log_final_results(self, report: Dict[str, Any]):
        """记录最终结果"""
        stats = report["statistics"]
        self._log("\n" + "=" * 60)
        self._log("📊 Final Results")
        self._log("=" * 60)
        self._log(f"✅ Status: {report['status']}")
        self._log(f"⏱️  Total Duration: {stats['total_duration']:.1f}s")
        self._log(f"📂 Total Files: {stats['total_files']}")
        self._log(f"✅ Processed: {stats['processed_files']}")
        self._log(f"⏭️  Skipped: {stats['skipped_files']}")
        self._log(f"❌ Failed: {stats['failed_files']}")
        self._log(f"🔄 Total Iterations: {stats['total_iterations']}")
        self._log(f"💾 Cache Hit Rate: {stats['cache_hit_rate']:.1%}")
        self._log(f"⭐ Average Score: {stats['avg_score']:.2f}")
        self._log(f"🎯 Pass Rate: {stats['pass_rate']:.1%}")
        self._log(f"💰 Estimated Cost: ${stats['estimated_total_cost']:.4f}")
        
        self._log("\n📈 Score Distribution:")
        max_distribution_count = max(stats['score_distribution'].values(), default=1)
        for grade, count in stats['score_distribution'].items():
            if count > 0:
                bar = "█" * int(count / max_distribution_count * 20)
                self._log(f"  {grade}: {count:2d} {bar}")
        
        errors = report.get("errors", [])
        if errors:
            self._log(f"\n⚠️  Errors ({len(errors)}):")
            for error in errors:
                self._log(f"  ❌ {error.get('file', 'System')}: {error.get('message', str(error))}")
        
        self._log("\n🎉 Processing complete!")
        self._log("=" * 60)
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前运行状态"""
        return {
            "session_id": self.state.session_id,
            "status": self.state.status,
            "total_files": self.state.total_files,
            "scanned_files": self.state.scanned_files,
            "changed_files": self.state.changed_files,
            "in_progress_files": self.state.in_progress_files,
            "processed_files": self.state.processed_files,
            "skipped_files": self.state.skipped_files,
            "failed_files": self.state.failed_files,
            "avg_score": self.state.avg_score,
            "total_cost": self.state.total_cost,
            "elapsed_time": time.time() - self.state.start_time,
        }
