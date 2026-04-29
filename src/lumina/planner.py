"""
Planner - 智能规划模块 (Agent 能力增强版)
分析文件结构，制定最优笔记生成策略
支持动态决策、资源分配、批量优化
"""

import os
import json
import hashlib
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .cache import CacheManager
from .utils.file_utils import get_file_hash, detect_file_type
from .document_cluster import DocumentClusterer, ClusterStrategy
from .content_filter import ContentFilter


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
    
    def __init__(self, cache_manager: CacheManager = None, history_manager=None, llm_config: Dict[str, Any] = None, enable_clustering: bool = True):
        self.cache = cache_manager
        self.history = history_manager
        self.llm_config = llm_config or {}
        
        # 初始化文档聚合器
        self.clusterer = DocumentClusterer() if enable_clustering else None
        
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
            
            return FileInfo(
                path=file_path,
                type=file_type,
                size=stat.st_size,
                modified=stat.st_mtime,
                hash=file_hash,
                metadata={
                    "filename": file_path.name,
                    "extension": file_path.suffix,
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
    
    def plan(self, files: List[FileInfo], existing_notes: Optional[List[Dict[str, Any]]] = None) -> ProcessingPlan:
        """
        制定处理计划
        
        增强功能：
        1. 文档聚合 - 将相关短文档合并处理
        2. 保留关联关系
        
        Args:
            files: 文件信息列表
            
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
                summary="No files to process"
            )
        
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
        
        # 合并所有待处理文件
        all_files = clustered_files + individual_files
        
        # 按优先级排序
        sorted_files = sorted(all_files, key=lambda f: (
            f.processing_priority,
            -f.estimated_cost,  # 成本高的优先（大文件优先）
        ))
        
        # 分批处理
        batches = self._create_batches(sorted_files)
        
        # 计算总计
        total_cost = sum(f.estimated_cost for f in all_files)
        total_time = sum(f.estimated_time for f in all_files)
        
        # 生成策略名称
        strategy = self._determine_strategy(all_files)
        
        # 生成摘要
        summary = self._generate_summary(all_files, batches, total_cost, total_time)
        
        self.stats["total_estimated_cost"] = total_cost
        
        return ProcessingPlan(
            total_files=len(all_files),
            total_estimated_cost=total_cost,
            total_estimated_time=total_time,
            strategy=strategy,
            batches=batches,
            summary=summary
        )
    
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
