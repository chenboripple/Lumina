"""
Planner - 规划模块
分析文件结构，制定笔记生成策略
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    type: str
    size: int
    modified: float
    metadata: Dict[str, Any]


class Planner:
    """
    规划器：分析输入，制定执行计划
    
    职责：
    1. 扫描目录，发现文件
    2. 分类文件类型
    3. 评估内容复杂度
    4. 生成执行计划
    """
    
    SUPPORTED_TYPES = {
        '.md': 'markdown',
        '.txt': 'text',
        '.pdf': 'pdf',
        '.py': 'code',
        '.js': 'code',
        '.ts': 'code',
        '.json': 'data',
        '.yaml': 'data',
        '.yml': 'data',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.file_cache: List[FileInfo] = []
    
    def scan(self, path: str, recursive: bool = True) -> List[FileInfo]:
        """
        扫描目录，收集文件信息
        
        Args:
            path: 扫描路径
            recursive: 是否递归子目录
            
        Returns:
            文件信息列表
        """
        target = Path(path)
        files = []
        
        if target.is_file():
            files = [target]
        elif target.is_dir():
            pattern = "**/*" if recursive else "*"
            files = [f for f in target.glob(pattern) if f.is_file()]
        
        self.file_cache = [
            FileInfo(
                path=f,
                type=self._detect_type(f),
                size=f.stat().st_size,
                modified=f.stat().st_mtime,
                metadata=self._extract_metadata(f)
            )
            for f in files
        ]
        
        return self.file_cache
    
    def plan(self, files: List[FileInfo] = None) -> Dict[str, Any]:
        """
        制定执行计划
        
        Returns:
            执行计划字典
        """
        files = files or self.file_cache
        
        # 按类型分组
        by_type = {}
        for f in files:
            by_type.setdefault(f.type, []).append(f)
        
        # 评估复杂度
        complexity = self._assess_complexity(files)
        
        plan = {
            "total_files": len(files),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "complexity": complexity,
            "strategy": self._select_strategy(complexity),
            "batches": self._create_batches(files),
        }
        
        return plan
    
    def _detect_type(self, path: Path) -> str:
        """检测文件类型"""
        ext = path.suffix.lower()
        return self.SUPPORTED_TYPES.get(ext, 'unknown')
    
    def _extract_metadata(self, path: Path) -> Dict[str, Any]:
        """提取文件元数据"""
        return {
            "name": path.stem,
            "parent": str(path.parent),
            "extension": path.suffix,
        }
    
    def _assess_complexity(self, files: List[FileInfo]) -> str:
        """评估整体复杂度"""
        total_size = sum(f.size for f in files)
        
        if total_size < 1024 * 1024:  # < 1MB
            return "simple"
        elif total_size < 50 * 1024 * 1024:  # < 50MB
            return "moderate"
        else:
            return "complex"
    
    def _select_strategy(self, complexity: str) -> str:
        """根据复杂度选择策略"""
        strategies = {
            "simple": "direct",
            "moderate": "chunked",
            "complex": "hierarchical",
        }
        return strategies.get(complexity, "chunked")
    
    def _create_batches(self, files: List[FileInfo], batch_size: int = 10) -> List[List[FileInfo]]:
        """创建处理批次"""
        return [
            files[i:i + batch_size]
            for i in range(0, len(files), batch_size)
        ]