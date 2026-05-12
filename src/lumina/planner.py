"""
Planner - 智能规划模块 (Agent 能力增强版)
分析文件结构，制定最优笔记生成策略
支持动态决策、资源分配、批量优化
"""

import os
import re
import json
import hashlib
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .cache import CacheManager
from .utils.file_operations import get_file_hash, detect_file_type
from .document_cluster import DocumentClusterer, ClusterStrategy
from .content_filter import ContentFilter
from .content_analyzer import ContentAnalyzer, ContentBrief, BatchBriefResult


@dataclass
class FileInfo:
    """文件信息（增强版）"""
    path: Path
    type: str
    size: int
    modified: float
    hash: str  # 文件内容哈希，用于变化检测
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_priority: int = 0  # 处理优先级，0最高
    estimated_cost: float = 0.0  # 预估 LLM 成本（Token 数量）
    estimated_time: float = 0.0  # 预估处理时间（秒）
    required_capabilities: List[str] = field(default_factory=list)  # 需要的能力（OCR/视觉/数学等）


@dataclass
class ProcessingPlan:
    """处理计划"""
    total_files: int
    total_estimated_cost: float
    total_estimated_time: float
    strategy: str  # 策略名称
    batches: List[List[FileInfo]]  # 分批处理
    summary: str  # 计划摘要
    note_structure_plan: Dict[str, Any] = field(default_factory=dict)  # 基于摘要/标签生成的笔记结构建议


class Planner:
    """
    智能规划器（Agent 增强版）
    
    核心能力：
    1. 🔍 增量扫描 - 基于文件哈希只处理变化的文件
    2. 📊 智能优先级 - 按类型、大小、重要性排序
    3. 💰 成本预估 - 自动估算 LLM Token 消耗
    4. 🧠 能力识别 - 自动识别 OCR、视觉、PDF解析等需求
    5. 📦 批量策略 - 资源感知批量大小
    6. 📈 可视化 - 生成结构化计划摘要
    """
    
    # 文件类型优先级（数字越小优先级越高）
    TYPE_PRIORITY = {
        'markdown': 1,
        'text': 2,
        'code': 3,
        'pdf': 4,
        'image': 5,
        'data': 6,
        'unknown': 7,
    }
    
    # 预估 Token 消耗系数（每字符）
    TOKEN_RATIO = {
        'markdown': 0.25,
        'text': 0.25,
        'code': 0.3,
        'pdf': 0.35,
        'image': 0.1,  # 图片描述
        'data': 0.2,
        'unknown': 0.25,
    }
    
    # 批量大小配置
    BATCH_SIZES = {
        'small': 5,   # 小文件（<100KB）
        'medium': 3,  # 中等文件（100KB-1MB）
        'large': 1,   # 大文件（>1MB）
    }
    
    # PARA 方法论分类目录（默认映射，可在 lumina.yaml output.note_organization.categories 中覆盖）
    # Projects: 有明确截止目标的临时项目
    # Areas:    需长期维护的责任/兴趣领域
    # Resources:仅供参考的资料，不承担责任
    # Archive:  已完成或不再使用的材料
    PARA_CATEGORY_MAP: Dict[str, str] = {
        "projects":  "Projects",
        "areas":     "Areas",
        "resources": "Resources",
        "archive":   "Archive",
    }
    NOTE_ORGANIZATION_LEVELS = {"scene", "para"}
    DEFAULT_NOTE_ORGANIZATION_LEVELS = ["scene", "para"]

    def __init__(
        self,
        cache_manager: CacheManager = None,
        history_manager=None,
        llm_config: Dict[str, Any] = None,
        enable_clustering: bool = True,
        output_structure: Optional[Dict[str, bool]] = None,
        note_organization: Optional[Dict[str, Any]] = None,
    ):
        self.cache = cache_manager
        self.history = history_manager
        self.llm_config = llm_config or {}
        self.output_structure = output_structure or {"by_date": False, "by_type": False, "flat": False}
        self.note_organization = self._normalize_note_organization(note_organization)
        # PARA 分类映射（用户可覆盖）
        self.categories: Dict[str, str] = {
            **self.PARA_CATEGORY_MAP,
            **self.note_organization.get("categories", {}),
        }
        # 生活场景列表：[{name: "工作", keywords: [...]}, ...]
        self.scenes: List[Dict[str, Any]] = self.note_organization.get("scenes", [])
        self.default_scene: str = self.note_organization.get("default_scene", "")
        
        # 初始化文档聚合器
        self.clusterer = DocumentClusterer() if enable_clustering else None

        # 初始化内容分析器（用于逐文件摘要/标签与学习价值判断）
        self.content_analyzer = None
        try:
            if self.llm_config:
                self.content_analyzer = ContentAnalyzer(
                    llm_config=self.llm_config,
                    cache_manager=self.cache,
                    max_content_length=3000,
                )
        except Exception as e:
            print(f"Warning: ContentAnalyzer initialization failed: {e}")
        
        # 统计信息
        self.stats = {
            "total_scanned": 0,
            "new_files": 0,
            "modified_files": 0,
            "unchanged_files": 0,
            "total_estimated_cost": 0,
            "clusters_created": 0,
            "files_in_clusters": 0,
        }
        self.last_skipped_files: List[FileInfo] = []

    @staticmethod
    def is_supported_extension(file_path: Path, supported_extensions: Optional[List[str]] = None) -> bool:
        """检查文件扩展名是否在允许列表中"""
        if not supported_extensions:
            return True
        normalized_extensions = {ext.lower() for ext in supported_extensions}
        return file_path.suffix.lower() in normalized_extensions

    @staticmethod
    def matches_file_filter(file_path: Path, root_path: Path, file_filter: Optional[str] = None) -> bool:
        """检查文件是否匹配 glob 过滤规则"""
        patterns = [p.strip() for p in (file_filter or "").split(",") if p.strip()]
        if not patterns:
            return True

        try:
            relative_path = file_path.relative_to(root_path)
        except ValueError:
            relative_path = file_path

        relative_text = str(relative_path)
        full_text = str(file_path)
        for pattern in patterns:
            if (
                fnmatch.fnmatch(file_path.name, pattern)
                or fnmatch.fnmatch(relative_text, pattern)
                or fnmatch.fnmatch(full_text, pattern)
                or file_path.match(pattern)
                or relative_path.match(pattern)
            ):
                return True
        return False
    
    def scan(self, input_path: str, recursive: bool = True, file_filter: Optional[str] = None, supported_extensions: Optional[List[str]] = None) -> List[FileInfo]:
        """
        扫描目录，返回文件信息列表
        
        Args:
            input_path: 输入路径（文件或目录）
            recursive: 是否递归扫描
            file_filter: 文件过滤规则，支持 glob，多个模式可用逗号分隔
            supported_extensions: 允许处理的文件扩展名列表
            
        Returns:
            文件信息列表
        """
        path = Path(input_path)
        files = []
        
        if path.is_file():
            # 单文件
            if self.is_supported_extension(path, supported_extensions) and self.matches_file_filter(path, path.parent, file_filter):
                file_info = self._analyze_file(path)
                if file_info:
                    files.append(file_info)
        elif path.is_dir():
            # 目录扫描
            pattern = "**/*" if recursive else "*"
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    if not self.is_supported_extension(file_path, supported_extensions):
                        continue
                    if not self.matches_file_filter(file_path, path, file_filter):
                        continue
                    file_info = self._analyze_file(file_path)
                    if file_info:
                        files.append(file_info)
        
        self.stats["total_scanned"] = len(files)
        return files
    
    def _analyze_file(self, file_path: Path) -> Optional[FileInfo]:
        """分析单个文件"""
        try:
            stat = file_path.stat()
            file_type = detect_file_type(file_path)
            file_hash = get_file_hash(file_path)
            
            # 计算预估成本
            estimated_cost = self._estimate_cost(file_path, file_type)
            
            # 识别所需能力
            required_capabilities = self._identify_capabilities(file_path, file_type)

            # 基于 LLM 的轻量内容分析（摘要、标签、学习价值）
            content_insight = self._analyze_content_insight(file_path, file_type, file_hash, stat.st_size)
            
            return FileInfo(
                path=file_path,
                type=file_type,
                size=stat.st_size,
                modified=stat.st_mtime,
                hash=file_hash,
                metadata={
                    "filename": file_path.name,
                    "extension": file_path.suffix,
                    **content_insight,
                },
                processing_priority=self.TYPE_PRIORITY.get(file_type, 7),
                estimated_cost=estimated_cost,
                estimated_time=estimated_cost * 0.5,  # 粗略估计：每 Token 0.5秒
                required_capabilities=required_capabilities,
            )
        except Exception as e:
            print(f"Warning: Failed to analyze {file_path}: {e}")
            return None
    
    def _estimate_cost(self, file_path: Path, file_type: str) -> float:
        """预估 LLM 处理成本（Token 数量）"""
        try:
            if file_type == 'image':
                # 图片使用固定成本
                return 500
            
            # 读取文件内容估算
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            ratio = self.TOKEN_RATIO.get(file_type, 0.25)
            return len(content) * ratio
            
        except Exception:
            return 1000  # 默认成本
    
    def _identify_capabilities(self, file_path: Path, file_type: str) -> List[str]:
        """识别处理所需的能力"""
        capabilities = []
        
        if file_type == 'image':
            capabilities.append('vision')
        elif file_type == 'pdf':
            capabilities.append('pdf_parser')
        elif file_type == 'code':
            capabilities.append('code_understanding')
        
        # 检查是否需要 OCR
        if file_type == 'image' and self._needs_ocr(file_path):
            capabilities.append('ocr')
        
        return capabilities
    
    def _needs_ocr(self, file_path: Path) -> bool:
        """判断图片是否需要 OCR"""
        # 简化判断：所有图片都尝试 OCR
        return True

    def _analyze_content_insight(self, file_path: Path, file_type: str, file_hash: str, file_size: int) -> Dict[str, Any]:
        """提取文件摘要、标签和学习价值判断。"""
        insight_state_key = f"insight::{str(file_path)}"
        default = {
            "content_summary": "",
            "content_tags": [],
            "content_type": file_type,
            "learning_value_score": 0.0,
            "has_learning_value": False,
            "learning_action": "process",
            "learning_reasoning": "",
            "analysis_source": "none",
            "analysis_truncated": False,
        }

        # 优先读取持久化洞察；哈希一致则直接复用。
        if self.history:
            try:
                stored = self.history.get_file_insight(str(file_path))
                if stored and stored.get("file_hash") == file_hash:
                    return {
                        "content_summary": stored.get("content_summary", ""),
                        "content_tags": stored.get("content_tags", []),
                        "content_type": stored.get("content_type", file_type),
                        "learning_value_score": stored.get("learning_value_score", 0.0),
                        "has_learning_value": bool(stored.get("has_learning_value", False)),
                        "learning_action": stored.get("learning_action", "process"),
                        "learning_reasoning": stored.get("learning_reasoning", ""),
                        "analysis_source": stored.get("analysis_source", "history"),
                        "analysis_truncated": bool(stored.get("analysis_truncated", False)),
                        "analyzed_file_hash": file_hash,
                    }
            except Exception as e:
                print(f"Warning: Failed to load persisted insight for {file_path}: {e}")

        if self.cache:
            try:
                cached_state = self.cache.get_processing_state(insight_state_key)
                if cached_state and cached_state.get("file_hash") == file_hash:
                    return {
                        "content_summary": cached_state.get("content_summary", ""),
                        "content_tags": cached_state.get("content_tags", []),
                        "content_type": cached_state.get("content_type", file_type),
                        "learning_value_score": cached_state.get("learning_value_score", 0.0),
                        "has_learning_value": bool(cached_state.get("has_learning_value", False)),
                        "learning_action": cached_state.get("learning_action", "process"),
                        "learning_reasoning": cached_state.get("learning_reasoning", ""),
                        "analysis_source": cached_state.get("analysis_source", "cache_state"),
                        "analysis_truncated": bool(cached_state.get("analysis_truncated", False)),
                        "analyzed_file_hash": file_hash,
                    }
            except Exception as e:
                print(f"Warning: Failed to load cached insight for {file_path}: {e}")

        if not self.content_analyzer:
            return default

        try:
            # 超大文件只读取前 1000 字符做判断，降低开销
            max_length = 1000 if file_size >= 1024 * 1024 else 3000
            brief = self.content_analyzer.analyze_file(file_path, file_type=file_type, max_length=max_length)
            insight = {
                "content_summary": brief.brief_summary,
                "content_tags": brief.key_topics,
                "content_type": brief.content_type or file_type,
                "learning_value_score": brief.estimated_value,
                "has_learning_value": brief.estimated_value >= 0.6 and brief.suggested_action != "skip",
                "learning_action": brief.suggested_action,
                "learning_reasoning": brief.metadata.get("reasoning", ""),
                "analysis_source": "llm",
                "analysis_truncated": max_length == 1000,
                "analyzed_file_hash": file_hash,
            }

            # 持久化：同一路径会随 file_hash 变化自动覆盖更新。
            if self.history:
                try:
                    self.history.upsert_file_insight(str(file_path), file_hash, insight)
                except Exception as e:
                    print(f"Warning: Failed to persist insight for {file_path}: {e}")

            if self.cache:
                try:
                    self.cache.set_processing_state(
                        insight_state_key,
                        {
                            "file_hash": file_hash,
                            "content_summary": insight.get("content_summary", ""),
                            "content_tags": insight.get("content_tags", []),
                            "content_type": insight.get("content_type", file_type),
                            "learning_value_score": insight.get("learning_value_score", 0.0),
                            "has_learning_value": insight.get("has_learning_value", False),
                            "learning_action": insight.get("learning_action", "process"),
                            "learning_reasoning": insight.get("learning_reasoning", ""),
                            "analysis_source": insight.get("analysis_source", "llm"),
                            "analysis_truncated": insight.get("analysis_truncated", False),
                        },
                    )
                except Exception as e:
                    print(f"Warning: Failed to cache insight state for {file_path}: {e}")

            return insight
        except Exception as e:
            default["analysis_source"] = "fallback"
            default["learning_reasoning"] = str(e)
            return default
    
    def plan(self, files: List[FileInfo], existing_notes: Optional[List[Dict[str, Any]]] = None, content_briefs: Optional[List[ContentBrief]] = None) -> ProcessingPlan:
        """
        制定处理计划（增强版：支持基于内容简述的智能决策）
        
        Args:
            files: 文件信息列表
            existing_notes: 已有笔记列表（用于聚类）
            content_briefs: 内容简述列表（可选，用于智能过滤和合并）
            
        Returns:
            处理计划
        """
        if not files:
            return ProcessingPlan(
                total_files=0,
                total_estimated_cost=0,
                total_estimated_time=0,
                strategy="empty",
                batches=[],
                summary="No files to process",
                note_structure_plan={}
            )
        
        # 如果有内容简述，进行智能过滤和合并建议
        if content_briefs:
            files, merge_groups, skipped_files = self._apply_content_briefs(files, content_briefs)
            self.last_skipped_files = list(skipped_files)
        else:
            merge_groups = []
            self.last_skipped_files = []
        
        # 文档聚合
        clustered_files = []
        individual_files = []
        
        if self.clusterer:
            file_paths = [f.path for f in files]
            clusters, individual = self.clusterer.cluster(file_paths, existing_notes=existing_notes)
            
            # 将聚类结果转换为 FileInfo
            for cluster in clusters:
                # 创建一个代表整个簇的 FileInfo
                cluster_info = FileInfo(
                    path=cluster.files[0],  # 以第一个文件为代表
                    type="cluster",
                    size=sum(f.stat().st_size for f in cluster.files if f.exists()),
                    modified=max(f.stat().st_mtime for f in cluster.files if f.exists()),
                    hash=hashlib.md5("|".join(sorted(str(f) for f in cluster.files)).encode("utf-8")).hexdigest(),
                    metadata={
                        "filename": f"cluster_{cluster.cluster_id}",
                        "extension": ".cluster",
                        "is_cluster": True,
                        "cluster_id": cluster.cluster_id,
                        "cluster_files": [str(f) for f in cluster.files],
                        "cluster_strategy": cluster.strategy.value,
                        "cluster_title": cluster.title,
                        "cluster_description": cluster.description,
                    },
                    processing_priority=1,  # 簇优先处理
                    estimated_cost=sum(
                        self._estimate_cost(f, detect_file_type(f))
                        for f in cluster.files
                    ),
                    estimated_time=0,
                    required_capabilities=[],
                )
                clustered_files.append(cluster_info)
            
            # 保留独立文件
            for path in individual:
                for file_info in files:
                    if file_info.path == path:
                        individual_files.append(file_info)
                        break
            
            self.stats["clusters_created"] = len(clusters)
            self.stats["files_in_clusters"] = sum(len(c.files) for c in clusters)
        else:
            individual_files = files
        
        # 合并用户指定的合并组到聚类结果中
        all_files = clustered_files + individual_files + merge_groups

        # 可选插入全局概览任务
        overview_file = self._build_global_overview_cluster(all_files)
        if overview_file:
            all_files.insert(0, overview_file)

        # 按优先级排序
        sorted_files = sorted(all_files, key=lambda f: (f.processing_priority, -f.estimated_cost))

        # 为每个文件规划输出目录
        self._assign_note_structure(sorted_files)

        # 基于全部文件摘要/标签生成笔记结构建议
        note_structure_plan = self._llm_design_note_structure(sorted_files)

        # 分批处理
        batches = self._create_batches(sorted_files)

        # 计算总成本
        total_cost = sum(f.estimated_cost for f in sorted_files)
        total_time = sum(f.estimated_time for f in sorted_files)

        # 生成策略摘要
        strategy = self._determine_strategy(sorted_files)

        # 生成计划摘要
        summary = self._generate_summary(sorted_files, batches, total_cost, total_time)
        
        self.stats["total_estimated_cost"] = total_cost
        
        return ProcessingPlan(
            total_files=len(sorted_files),
            total_estimated_cost=total_cost,
            total_estimated_time=total_time,
            strategy=strategy,
            batches=batches,
            summary=summary,
            note_structure_plan=note_structure_plan,
        )
    
    def _apply_content_briefs(self, files: List[FileInfo], briefs: List[ContentBrief]) -> tuple:
        """
        应用内容简述进行智能过滤和合并建议
        
        Returns:
            (过滤后的文件列表, 合并组列表)
        """
        # 建立文件路径到简述的映射
        brief_map = {b.file_path: b for b in briefs}
        
        filtered_files = []
        skipped_files: List[FileInfo] = []
        skipped_count = 0
        merge_groups: Dict[str, List[FileInfo]] = {}  # merge_key -> files
        
        for file_info in files:
            brief = brief_map.get(str(file_info.path))
            if not brief:
                # 没有简述，保留
                filtered_files.append(file_info)
                continue
            
            # 注入简述信息到 FileInfo metadata
            file_info.metadata["content_brief_summary"] = brief.brief_summary
            file_info.metadata["content_type"] = brief.content_type
            file_info.metadata["key_topics"] = brief.key_topics
            file_info.metadata["estimated_value"] = brief.estimated_value
            
            # 根据建议操作过滤
            if brief.suggested_action == "skip":
                skipped_count += 1
                self.stats["skipped_files"] = self.stats.get("skipped_files", 0) + 1
                file_info.metadata["learning_action"] = "skip"
                file_info.metadata["skip_reason"] = brief.metadata.get("reasoning", "low learning value")
                skipped_files.append(file_info)
                continue
            
            elif brief.suggested_action == "merge":
                # 寻找合并候选
                merge_key = self._find_merge_key(brief, file_info)
                if merge_key not in merge_groups:
                    merge_groups[merge_key] = []
                merge_groups[merge_key].append(file_info)
                continue
            
            # "process" - 保留
            filtered_files.append(file_info)
        
        # 将合并组转换为 FileInfo
        merge_file_infos = []
        for merge_key, group_files in merge_groups.items():
            if len(group_files) < 2:
                # 只有一个文件，直接保留
                filtered_files.extend(group_files)
                continue
            
            # 创建合并组的 FileInfo
            merge_info = FileInfo(
                path=group_files[0].path,  # 以第一个文件为代表
                type="merge_group",
                size=sum(f.size for f in group_files),
                modified=max(f.modified for f in group_files),
                hash=hashlib.md5("|".join(sorted(f.hash for f in group_files)).encode("utf-8")).hexdigest(),
                metadata={
                    "filename": f"merge_{merge_key}",
                    "extension": ".merge",
                    "is_merge_group": True,
                    "merge_key": merge_key,
                    "merge_files": [str(f.path) for f in group_files],
                    "merge_count": len(group_files),
                    "content_brief_summary": " | ".join(
                        f.metadata.get("content_brief_summary", "") for f in group_files
                    ),
                },
                processing_priority=1,
                estimated_cost=sum(f.estimated_cost for f in group_files) * 0.7,  # 合并处理节省30%
                estimated_time=sum(f.estimated_time for f in group_files) * 0.7,
                required_capabilities=[],
            )
            merge_file_infos.append(merge_info)
        
        print(f"Content brief filtering: {skipped_count} skipped, {len(merge_file_infos)} merge groups created")
        
        return filtered_files, merge_file_infos, skipped_files
    
    def _find_merge_key(self, brief: ContentBrief, file_info: FileInfo) -> str:
        """根据简述找到合并键"""
        # 优先使用内容类型
        if brief.content_type:
            return f"type_{brief.content_type}"
        
        # 使用关键主题
        if brief.key_topics:
            return f"topic_{brief.key_topics[0]}"
        
        # 使用文件类型
        return f"filetype_{file_info.type}"

    def _build_global_overview_cluster(self, files: List[FileInfo]) -> Optional[FileInfo]:
        """为一批文件生成全局知识地图任务。"""
        if len(files) < 8:
            return None

        representative_files = sorted(files, key=lambda item: item.estimated_cost, reverse=True)[:16]
        catalog = self._build_overview_catalog(files)
        anchor = representative_files[0]
        return FileInfo(
            path=anchor.path,
            type="cluster",
            size=sum(item.size for item in representative_files),
            modified=max(item.modified for item in representative_files),
            hash=hashlib.md5("|".join(sorted(item.hash for item in representative_files)).encode("utf-8")).hexdigest(),
            metadata={
                "filename": "global_overview.cluster",
                "extension": ".cluster",
                "is_cluster": True,
                "cluster_id": "global_overview",
                "cluster_files": [str(item.path) for item in representative_files],
                "cluster_strategy": ClusterStrategy.SUMMARIZE_MULTIPLE.value,
                "cluster_title": "全局知识地图",
                "cluster_description": "Global overview of the current batch",
                "overview_scope": "global",
                "overview_catalog": catalog,
                "title_hint": "全局知识地图",
                "para": "resources",
            },
            processing_priority=0,
            estimated_cost=sum(item.estimated_cost for item in representative_files),
            estimated_time=sum(item.estimated_time for item in representative_files),
            required_capabilities=[],
        )

    def _build_overview_catalog(self, files: List[FileInfo]) -> str:
        type_counts: Dict[str, int] = {}
        para_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        directory_counts: Dict[str, int] = {}

        for file_info in files:
            type_counts[file_info.type] = type_counts.get(file_info.type, 0) + 1
            scene_ctx = self._infer_scene_context(file_info) if self.scenes else ""
            para = self._infer_para(file_info, scene_ctx)
            para_counts[para] = para_counts.get(para, 0) + 1
            domain = self._infer_domain(file_info)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            parent = file_info.path.parent.name or "/"
            directory_counts[parent] = directory_counts.get(parent, 0) + 1

        top_dirs = sorted(directory_counts.items(), key=lambda item: item[1], reverse=True)[:8]
        return (
            f"Domain counts: {domain_counts}\n"
            f"PARA counts: {para_counts}\n"
            f"Type counts: {type_counts}\n"
            f"Top directories: {top_dirs}"
        )

    def _infer_domain(self, file_info: FileInfo) -> str:
        text = str(file_info.path).lower()
        if re.search(r"论文|paper|study|学习|课程|book|reading", text):
            return "学习"
        if re.search(r"chat|聊天|邮件|mail|wecom|微信|qq", text):
            return "沟通"
        if re.search(r"travel|旅行|家庭|购物|health|健康|movie|music|diary|journal", text):
            return "生活兴趣"
        if re.search(r"project|项目|需求|prd|design|meeting|sql|ops|deploy|code|repo|service", text):
            return "工作"
        return "参考资料"
    
    def _create_batches(self, files: List[FileInfo]) -> List[List[FileInfo]]:
        """创建处理批次"""
        batches = []
        current_batch = []
        current_batch_size = 0
        
        for file in files:
            # 确定批次大小
            if file.size < 100 * 1024:
                max_batch = self.BATCH_SIZES['small']
            elif file.size < 1024 * 1024:
                max_batch = self.BATCH_SIZES['medium']
            else:
                max_batch = self.BATCH_SIZES['large']
            
            # 检查是否需要新批次
            if len(current_batch) >= max_batch:
                batches.append(current_batch)
                current_batch = []
            
            current_batch.append(file)
        
        # 添加最后一批
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _determine_strategy(self, files: List[FileInfo]) -> str:
        """确定处理策略"""
        total_size = sum(f.size for f in files)
        avg_size = total_size / len(files) if files else 0
        
        if avg_size < 100 * 1024:
            return "batch_parallel"  # 小文件并行批处理
        elif avg_size < 1024 * 1024:
            return "sequential"  # 中等文件串行处理
        else:
            return "resource_aware"  # 大文件资源感知处理
    
    def _generate_summary(
        self,
        files: List[FileInfo],
        batches: List[List[FileInfo]],
        total_cost: float,
        total_time: float
    ) -> str:
        """生成计划摘要"""
        type_counts = {}
        for f in files:
            type_counts[f.type] = type_counts.get(f.type, 0) + 1
        
        type_summary = ", ".join([f"{t}: {c}" for t, c in sorted(type_counts.items())])
        
        return (
            f"Processing {len(files)} files in {len(batches)} batches. "
            f"Types: {type_summary}. "
            f"Estimated cost: {total_cost:.0f} tokens, "
            f"Estimated time: {total_time:.1f}s"
        )

    def _llm_design_note_structure(self, files: List[FileInfo]) -> Dict[str, Any]:
        """基于文件摘要与标签生成笔记结构建议。"""
        if not files:
            return {}

        # 没有可用 LLM 时，返回规则推导的结构建议
        if not self.content_analyzer:
            return self._fallback_note_structure_plan(files)

        sample_rows = []
        for item in files[:120]:
            sample_rows.append({
                "path": str(item.path),
                "type": item.type,
                "tags": item.metadata.get("content_tags", []),
                "summary": item.metadata.get("content_summary", ""),
                "learning_value": item.metadata.get("has_learning_value", False),
                "note_subdir": item.metadata.get("note_subdir", ""),
            })

        prompt = (
            "You are an information architecture expert. "
            "Design a practical note folder structure based on file briefs/tags and current hierarchy settings.\n\n"
            f"Hierarchy levels config: {self.note_organization.get('levels', [])}\n"
            f"Categories mapping: {self.categories}\n"
            "File samples (JSON):\n"
            f"{json.dumps(sample_rows, ensure_ascii=False)}\n\n"
            "Return ONLY JSON with this schema:\n"
            "{\n"
            "  \"recommended_roots\": [\"root1\", \"root2\"],\n"
            "  \"folders\": [{\"path\": \"scene/para\", \"reason\": \"...\", \"priority\": \"high|medium|low\"}],\n"
            "  \"study_queue\": [{\"path\": \"...\", \"reason\": \"...\", \"score\": 0.0}],\n"
            "  \"guidelines\": [\"...\"]\n"
            "}"
        )

        try:
            response_text = self.content_analyzer.llm_provider.complete(prompt)
            parsed = self._parse_json_object(response_text)
            if isinstance(parsed, dict):
                parsed["source"] = "llm"
                parsed["generated_at"] = datetime.now().isoformat()
                return parsed
        except Exception as e:
            print(f"Warning: note structure LLM design failed: {e}")

        return self._fallback_note_structure_plan(files)

    def _fallback_note_structure_plan(self, files: List[FileInfo]) -> Dict[str, Any]:
        """无 LLM 时基于已有规划结果生成结构建议。"""
        folder_counts: Dict[str, int] = {}
        study_queue: List[Dict[str, Any]] = []

        for item in files:
            subdir = item.metadata.get("note_subdir", "") or "Resources"
            folder_counts[subdir] = folder_counts.get(subdir, 0) + 1
            if item.metadata.get("has_learning_value"):
                study_queue.append({
                    "path": str(item.path),
                    "reason": item.metadata.get("learning_reasoning", "high learning value"),
                    "score": float(item.metadata.get("learning_value_score", 0.0)),
                })

        folders = [
            {"path": key, "reason": f"contains {count} files", "priority": "high" if count >= 5 else "medium"}
            for key, count in sorted(folder_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]
        study_queue.sort(key=lambda item: item["score"], reverse=True)

        return {
            "source": "fallback",
            "generated_at": datetime.now().isoformat(),
            "recommended_roots": list(dict.fromkeys(part.split("/")[0] for part in folder_counts.keys() if part)),
            "folders": folders,
            "study_queue": study_queue[:30],
            "guidelines": [
                "Prioritize folders with dense high-value files.",
                "Keep low-value transient files out of weekly study queue.",
                "Use scene/para defaults when tags are sparse.",
            ],
        }

    def _parse_json_object(self, content: str) -> Dict[str, Any]:
        """从 LLM 文本中解析 JSON 对象。"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        code_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
        if code_match:
            return json.loads(code_match.group(1))

        brace_match = re.search(r"\{.*\}", content, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(0))

        raise ValueError("No valid JSON object found")

    def _assign_note_structure(self, files: List[FileInfo]):
        """为每个文件规划 note_subdir。

        目录层级由 output.note_organization.levels 决定。
        默认两层为：scene -> para。
        若未配置 scenes，scene 层自动跳过。
        flat=true 时不分目录。
        """
        if not files:
            return

        if self.output_structure.get("flat"):
            for f in files:
                f.metadata["note_subdir"] = ""
            return

        for f in files:
            f.metadata["note_subdir"] = self._build_note_subdir(f)

    def _normalize_note_organization(self, note_organization: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """标准化目录组织配置。"""
        config = note_organization if isinstance(note_organization, dict) else {}

        raw_levels = config.get("levels", [])
        levels = [str(part).strip().lower() for part in raw_levels if str(part).strip()]
        normalized_levels: List[str] = []
        for level in levels:
            if level in self.NOTE_ORGANIZATION_LEVELS and level not in normalized_levels:
                normalized_levels.append(level)
        if not normalized_levels:
            normalized_levels = self.DEFAULT_NOTE_ORGANIZATION_LEVELS.copy()

        raw_scenes = config.get("scenes", [])
        scenes = raw_scenes if isinstance(raw_scenes, list) else []

        raw_categories = config.get("categories", {})
        categories = raw_categories if isinstance(raw_categories, dict) else {}

        return {
            "levels": normalized_levels[:2],
            "default_scene": str(config.get("default_scene", "") or ""),
            "scenes": scenes,
            "categories": categories,
        }

    def _build_note_subdir(self, file_info: FileInfo) -> str:
        """根据目录层级配置构建 note_subdir。"""
        scene_ctx = self._infer_scene_context(file_info) if self.scenes else ""
        para = self._infer_para(file_info, scene_ctx)

        parts: List[str] = []
        for level in self.note_organization.get("levels", self.DEFAULT_NOTE_ORGANIZATION_LEVELS):
            if level == "scene" and scene_ctx:
                parts.append(scene_ctx)
            elif level == "para" and para:
                parts.append(para)

        # 保底仍输出 PARA，避免路径为空。
        if not parts and para:
            parts.append(para)

        return "/".join(parts)

    def _infer_scene_context(self, file_info: FileInfo) -> str:
        """按用户配置的关键词列表匹配生活场景（第一层目录）。"""
        text = f"{file_info.path.name} {file_info.path.stem}".lower()
        for scene_def in self.scenes:
            name = scene_def.get("name", "")
            keywords = scene_def.get("keywords", [])
            if any(re.search(str(kw).lower(), text) for kw in keywords if kw):
                return name
        # 匹配失败：用默认场景，没有则用第一个
        if self.default_scene:
            return self.default_scene
        return self.scenes[0]["name"] if self.scenes else ""

    def _get_scene_definition(self, scene_name: str) -> Dict[str, Any]:
        if not scene_name:
            return {}
        for scene_def in self.scenes:
            if str(scene_def.get("name", "")).strip() == scene_name:
                return scene_def
        return {}

    def _apply_scene_para_policy(self, scene_name: str, para_key: str) -> str:
        """按 scene 级别规则调整 PARA 键。"""
        scene_def = self._get_scene_definition(scene_name)
        if not scene_def:
            return para_key

        enabled_raw = scene_def.get("enabled_categories", [])
        if not isinstance(enabled_raw, list) or not enabled_raw:
            return para_key

        enabled = [
            str(item).strip().lower()
            for item in enabled_raw
            if str(item).strip().lower() in self.PARA_CATEGORY_MAP
        ]
        if not enabled:
            return para_key

        if para_key in enabled:
            return para_key

        fallback = str(scene_def.get("fallback_category", "")).strip().lower()
        if fallback in enabled:
            return fallback

        if "resources" in enabled:
            return "resources"
        return enabled[0]

    def _resolve_para_key(self, para_value: str) -> str:
        value = str(para_value or "").strip()
        if not value:
            return ""

        lowered = value.lower()
        if lowered in self.categories:
            return lowered

        for key, label in self.categories.items():
            if str(label).strip().lower() == lowered:
                return key

        return ""

    def _infer_para_key(self, file_info: FileInfo) -> str:
        """按 PARA 方法论推断分类键。

        优先级：
          1. metadata["para"] 显式标注
          2. 文件名关键词 → Archive / Projects / Areas
          3. scene → PARA 映射
          4. 文件类型兜底 → Resources
        """
        # 1. 显式标注
        para = self._resolve_para_key(file_info.metadata.get("para", ""))
        if para:
            return para

        # 2. 集群文件 → Resources
        if file_info.type == "cluster":
            return "resources"

        text = f"{file_info.path.name} {file_info.path.stem}".lower()

        # 3. Archive：已完成/归档/历史材料
        if re.search(
            r"总结|归档|archive|旧版|已完成|复盘|年度|历史|obsolete|deprecated|_old|old_|backup",
            text
        ):
            return "archive"

        # 4. Projects：有明确截止目标的临时任务
        if re.search(
            r"需求|requirement|spec\b|项目|project|sprint|roadmap|milestone"
            r"|计划书|方案|proposal|prd\b|mrd\b|开发计划|排期|deadline",
            text
        ):
            return "projects"

        # 5. Areas：长期维护的责任/兴趣领域
        if re.search(
            r"规范|标准|流程|制度|指南|架构|design|architecture|维护|运营"
            r"|管理体系|sop\b|policy|日记|diary|journal|周报|月报",
            text
        ):
            return "areas"

        # 6. scene → PARA 映射
        scene = file_info.metadata.get("scene", "")
        scene_to_para = {
            "meeting_notes":    "projects",
            "requirements":     "projects",
            "task_list":        "projects",
            "technical_doc":    "areas",
            "code_explanation": "areas",
            "diary":            "areas",
            "book_notes":       "resources",
            "knowledge_essay":  "resources",
            "generic_notes":    "resources",
        }
        return scene_to_para.get(scene, "resources")

    def _infer_para(self, file_info: FileInfo, scene_name: str = "") -> str:
        para_key = self._infer_para_key(file_info)
        para_key = self._apply_scene_para_policy(scene_name, para_key)
        return self.categories.get(para_key, self.PARA_CATEGORY_MAP.get(para_key, "Resources"))

    def _sanitize_component(self, name: str) -> str:
        value = (name or "").strip().replace("\\", "/")
        value = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "_", value)
        value = re.sub(r"\s+", "_", value)
        return value.strip("._/")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取扫描统计"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_scanned": 0,
            "new_files": 0,
            "modified_files": 0,
            "unchanged_files": 0,
            "total_estimated_cost": 0,
        }
