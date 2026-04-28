
"""
文件变化追踪器（增量更新核心）
实现基于内容哈希的精准变化检测，支持大文件分块哈希、内容差异分析
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import difflib


@dataclass
class FileFingerprint:
    """文件指纹，用于变化检测"""
    file_path: str
    hash: str  # 全文件哈希
    block_hashes: List[str]  # 分块哈希列表
    size: int
    modified_time: float
    last_processed_time: Optional[float] = None
    last_processed_hash: Optional[str] = None
    processing_version: int = 0


@dataclass
class DiffBlock:
    """文件内容差异块"""
    type: str  # 'added', 'removed', 'modified', 'unchanged'
    start_line: int
    end_line: int
    content: str
    old_content: Optional[str] = None


class FileChangeTracker:
    """
    文件变化追踪器
    负责记录文件指纹、检测变化、分析差异
    """
    
    # 分块大小（4KB，平衡性能和精度）
    BLOCK_SIZE = 4096
    # 指纹存储路径
    FINGERPRINT_DIR = Path.home() / ".lumina" / "fingerprints"
    
    def __init__(self):
        self.FINGERPRINT_DIR.mkdir(parents=True, exist_ok=True)
        self._fingerprints: Dict[str, FileFingerprint] = self._load_fingerprints()
    
    def _load_fingerprints(self) -> Dict[str, FileFingerprint]:
        """加载已保存的文件指纹"""
        fingerprints = {}
        fingerprint_file = self.FINGERPRINT_DIR / "fingerprints.json"
        
        if fingerprint_file.exists():
            try:
                with open(fingerprint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for fp_data in data.values():
                        fp = FileFingerprint(**fp_data)
                        fingerprints[fp.file_path] = fp
            except Exception as e:
                print(f"⚠️  Failed to load fingerprints: {e}")
        
        return fingerprints
    
    def _save_fingerprints(self) -> None:
        """保存文件指纹到磁盘"""
        fingerprint_file = self.FINGERPRINT_DIR / "fingerprints.json"
        
        try:
            data = {
                fp.file_path: {
                    "file_path": fp.file_path,
                    "hash": fp.hash,
                    "block_hashes": fp.block_hashes,
                    "size": fp.size,
                    "modified_time": fp.modified_time,
                    "last_processed_time": fp.last_processed_time,
                    "last_processed_hash": fp.last_processed_hash,
                    "processing_version": fp.processing_version
                }
                for fp in self._fingerprints.values()
            }
            
            with open(fingerprint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Failed to save fingerprints: {e}")
    
    def calculate_file_fingerprint(self, file_path: Path) -> FileFingerprint:
        """
        计算文件指纹（分块哈希）
        支持大文件高效计算
        """
        file_path_str = str(file_path.resolve())
        stat = file_path.stat()
        file_size = stat.st_size
        modified_time = stat.st_mtime
        
        # 读取文件并计算哈希
        full_hash = hashlib.sha256()
        block_hashes = []
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    block = f.read(self.BLOCK_SIZE)
                    if not block:
                        break
                    full_hash.update(block)
                    block_hash = hashlib.sha256(block).hexdigest()
                    block_hashes.append(block_hash)
            
            full_hash_hex = full_hash.hexdigest()
            
            # 检查是否已有指纹
            existing_fp = self._fingerprints.get(file_path_str)
            if existing_fp:
                return FileFingerprint(
                    file_path=file_path_str,
                    hash=full_hash_hex,
                    block_hashes=block_hashes,
                    size=file_size,
                    modified_time=modified_time,
                    last_processed_time=existing_fp.last_processed_time,
                    last_processed_hash=existing_fp.last_processed_hash,
                    processing_version=existing_fp.processing_version
                )
            
            return FileFingerprint(
                file_path=file_path_str,
                hash=full_hash_hex,
                block_hashes=block_hashes,
                size=file_size,
                modified_time=modified_time
            )
            
        except Exception as e:
            raise ValueError(f"Failed to calculate fingerprint for {file_path}: {e}") from e
    
    def has_file_changed(self, file_path: Path, force_check_content: bool = False) -> Tuple[bool, FileFingerprint]:
        """
        检查文件是否发生变化
        Args:
            file_path: 文件路径
            force_check_content: 是否强制检查内容（跳过 mtime 快速判断）
        Returns:
            (是否变化, 文件指纹)
        """
        file_path_str = str(file_path.resolve())
        
        # 首先检查文件是否存在
        if not file_path.exists():
            return False, None
        
        # 计算当前指纹
        current_fp = self.calculate_file_fingerprint(file_path)
        existing_fp = self._fingerprints.get(file_path_str)
        
        # 新文件，肯定变化
        if not existing_fp:
            return True, current_fp
        
        # 如果不需要强制检查，先快速检查大小和修改时间
        if not force_check_content:
            if (current_fp.size == existing_fp.size and 
                abs(current_fp.modified_time - existing_fp.modified_time) < 0.001):
                # 大小和修改时间都没变，认为文件未修改
                return False, current_fp
        
        # 检查内容哈希
        if current_fp.hash == existing_fp.last_processed_hash:
            return False, current_fp
        
        # 内容哈希变化，说明文件已修改
        return True, current_fp
    
    def get_file_diff(self, old_content: str, new_content: str) -> List[DiffBlock]:
        """
        分析两个版本的文件内容差异
        Returns:
            差异块列表
        """
        diff_blocks = []
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # 未修改
                content = ''.join(new_lines[j1:j2])
                diff_blocks.append(DiffBlock(
                    type='unchanged',
                    start_line=j1 + 1,
                    end_line=j2,
                    content=content
                ))
            elif tag == 'replace':
                # 修改
                old_content = ''.join(old_lines[i1:i2])
                new_content = ''.join(new_lines[j1:j2])
                diff_blocks.append(DiffBlock(
                    type='modified',
                    start_line=j1 + 1,
                    end_line=j2,
                    content=new_content,
                    old_content=old_content
                ))
            elif tag == 'delete':
                # 删除
                content = ''.join(old_lines[i1:i2])
                diff_blocks.append(DiffBlock(
                    type='removed',
                    start_line=i1 + 1,
                    end_line=i2,
                    content=content
                ))
            elif tag == 'insert':
                # 新增
                content = ''.join(new_lines[j1:j2])
                diff_blocks.append(DiffBlock(
                    type='added',
                    start_line=j1 + 1,
                    end_line=j2,
                    content=content
                ))
        
        return diff_blocks
    
    def mark_as_processed(self, fingerprint: FileFingerprint) -> None:
        """标记文件为已处理"""
        fingerprint.last_processed_time = datetime.now().timestamp()
        fingerprint.last_processed_hash = fingerprint.hash
        fingerprint.processing_version += 1
        self._fingerprints[fingerprint.file_path] = fingerprint
        self._save_fingerprints()
    
    def get_processed_files(self) -> List[str]:
        """获取所有已处理的文件路径"""
        return [
            fp.file_path 
            for fp in self._fingerprints.values() 
            if fp.last_processed_hash is not None
        ]

    def get_recent_processed_files(self, limit: int = 20, roots: Optional[List[Path]] = None) -> List[Dict[str, Any]]:
        """获取最近标记为已处理的文件记录，可按根路径过滤。"""
        normalized_roots = []
        if roots:
            for root in roots:
                try:
                    normalized_roots.append(str(Path(root).resolve()))
                except Exception:
                    continue

        recent = []
        for fp in self._fingerprints.values():
            if fp.last_processed_hash is None or fp.last_processed_time is None:
                continue

            try:
                resolved_file = str(Path(fp.file_path).resolve())
            except Exception:
                resolved_file = fp.file_path

            if normalized_roots:
                in_scope = False
                for root in normalized_roots:
                    if resolved_file == root or resolved_file.startswith(root + os.sep):
                        in_scope = True
                        break
                if not in_scope:
                    continue

            recent.append({
                "file_path": resolved_file,
                "last_processed_time": fp.last_processed_time,
                "processing_version": fp.processing_version,
            })

        recent.sort(key=lambda item: item["last_processed_time"], reverse=True)
        return recent[:limit]
    
    def get_unprocessed_files(self, files: List[Path]) -> List[Path]:
        """从文件列表中筛选出未处理或已修改的文件"""
        unprocessed = []
        for file_path in files:
            changed, _ = self.has_file_changed(file_path)
            if changed:
                unprocessed.append(file_path)
        return unprocessed
    
    def cleanup_old_fingerprints(self, days_to_keep: int = 30) -> None:
        """清理超过指定天数未处理的指纹"""
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        to_remove = []
        
        for file_path, fp in self._fingerprints.items():
            if fp.last_processed_time and fp.last_processed_time < cutoff_time:
                to_remove.append(file_path)
        
        for file_path in to_remove:
            del self._fingerprints[file_path]
        
        if to_remove:
            print(f"🧹 Cleaned up {len(to_remove)} old fingerprints")
            self._save_fingerprints()
