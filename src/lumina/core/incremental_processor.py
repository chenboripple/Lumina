
"""
增量更新处理器
整合文件变化追踪和实时监控，实现智能增量处理
"""

import time
import threading
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .file_change_tracker import FileChangeTracker, DiffBlock
from .directory_monitor import DirectoryMonitor
from ..planner import Planner, FileInfo
from ..executor import Executor, ExecutionContext
from ..validator import Validator
from ..cache import CacheManager
from ..history import HistoryManager


class IncrementalProcessor:
    """
    增量更新处理器
    核心能力：
    1. 基于内容哈希的精准变化检测
    2. 大文件分块处理，只处理变化部分
    3. 实时监控目录变化，自动触发更新
    4. 支持批量合并处理，降低 LLM 调用次数
    """
    
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        validator: Validator,
        cache_manager: Optional[CacheManager] = None,
        history_manager: Optional[HistoryManager] = None,
        max_workers: int = 4,
        batch_size: int = 5,
        batch_timeout: float = 10.0
    ):
        self.planner = planner
        self.executor = executor
        self.validator = validator
        self.cache_manager = cache_manager
        self.history_manager = history_manager
        
        self.change_tracker = FileChangeTracker()
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # 批处理队列
        self._pending_files: List[Path] = []
        self._batch_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._monitor: Optional[DirectoryMonitor] = None
        
        # 处理回调
        self.on_processing_complete: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_processing_error: Optional[Callable[[str, str], None]] = None
    
    def process_files(self, files: List[Path], force_full: bool = False) -> Dict[str, Any]:
        """
        增量处理文件列表
        Args:
            files: 要处理的文件列表
            force_full: 是否强制全量处理（忽略变化检测）
        Returns:
            处理结果报告
        """
        results = {
            "total": len(files),
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }
        
        for file_path in files:
            try:
                result = self._process_single_file(file_path, force_full)
                
                if result["action"] == "processed":
                    results["processed"] += 1
                elif result["action"] == "skipped":
                    results["skipped"] += 1
                
                results["details"].append(result)
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "file": str(file_path),
                    "action": "failed",
                    "error": str(e)
                })
                
                if self.on_processing_error:
                    self.on_processing_error(str(file_path), str(e))
        
        return results
    
    def _process_single_file(self, file_path: Path, force_full: bool) -> Dict[str, Any]:
        """处理单个文件"""
        # 1. 检查文件是否变化
        if not force_full:
            changed, fingerprint = self.change_tracker.has_file_changed(file_path)
            if not changed:
                return {
                    "file": str(file_path),
                    "action": "skipped",
                    "reason": "file unchanged"
                }
        else:
            fingerprint = self.change_tracker.calculate_file_fingerprint(file_path)
        
        # 2. 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {
                "file": str(file_path),
                "action": "failed",
                "error": f"Failed to read file: {e}"
            }
        
        # 3. 如果是增量更新，尝试只处理变化部分
        old_content = None
        if not force_full and fingerprint.last_processed_hash:
            # 尝试获取旧版本内容（从缓存或历史记录）
            old_content = self._get_previous_content(file_path)
        
        # 4. 分析差异（如果有旧版本）
        diff_blocks = None
        if old_content:
            diff_blocks = self.change_tracker.get_file_diff(old_content, content)
            # 只保留变化的块
            changed_blocks = [b for b in diff_blocks if b.type != 'unchanged']
            if changed_blocks and len(changed_blocks) < len(diff_blocks) * 0.5:
                # 如果变化块少于总块数的一半，尝试增量处理
                return self._process_incremental(file_path, content, changed_blocks, fingerprint)
        
        # 5. 全量处理
        return self._process_full(file_path, content, fingerprint)
    
    def _get_previous_content(self, file_path: Path) -> Optional[str]:
        """获取文件的上一个处理版本内容"""
        # 尝试从缓存获取
        if self.cache_manager:
            cached = self.cache_manager.get_file_content(str(file_path))
            if cached:
                return cached
        
        # 尝试从历史记录获取
        if self.history_manager:
            history = self.history_manager.get_last_processed(str(file_path))
            if history and history.get("content"):
                return history["content"]
        
        return None
    
    def _process_full(self, file_path: Path, content: str, fingerprint: Any) -> Dict[str, Any]:
        """全量处理文件"""
        # 创建 FileInfo
        file_info = FileInfo(
            path=file_path,
            size=len(content.encode('utf-8')),
            modified=fingerprint.modified_time,
            hash=fingerprint.hash
        )
        
        # 构建执行上下文
        context = ExecutionContext(
            session_id=f"incremental_{int(time.time())}",
            file_info=file_info,
            plan={"strategy": "full"}
        )
        
        # 执行处理
        output = self.executor.execute(context)
        
        # 验证
        validation = self.validator.validate(output, file_info, context)
        
        # 标记为已处理
        self.change_tracker.mark_as_processed(fingerprint)
        
        # 缓存内容
        if self.cache_manager:
            self.cache_manager.set_file_content(str(file_path), content)
        
        return {
            "file": str(file_path),
            "action": "processed",
            "strategy": "full",
            "score": validation.score,
            "passed": validation.passed
        }
    
    def _process_incremental(
        self, 
        file_path: Path, 
        content: str, 
        changed_blocks: List[DiffBlock],
        fingerprint: Any
    ) -> Dict[str, Any]:
        """增量处理文件（只处理变化部分）"""
        # 构建增量处理提示词
        changed_content = "\n".join([b.content for b in changed_blocks])
        
        # 创建增量处理的 FileInfo
        file_info = FileInfo(
            path=file_path,
            size=len(changed_content.encode('utf-8')),
            modified=fingerprint.modified_time,
            hash=fingerprint.hash
        )
        
        # 构建执行上下文（标记为增量处理）
        context = ExecutionContext(
            session_id=f"incremental_{int(time.time())}",
            file_info=file_info,
            plan={
                "strategy": "incremental",
                "changed_blocks": len(changed_blocks),
                "total_blocks": len(changed_blocks)  # 简化
            }
        )
        
        # 执行增量处理
        output = self.executor.execute(context)
        
        # 验证
        validation = self.validator.validate(output, file_info, context)
        
        # 标记为已处理
        self.change_tracker.mark_as_processed(fingerprint)
        
        # 缓存内容
        if self.cache_manager:
            self.cache_manager.set_file_content(str(file_path), content)
        
        return {
            "file": str(file_path),
            "action": "processed",
            "strategy": "incremental",
            "changed_blocks": len(changed_blocks),
            "score": validation.score,
            "passed": validation.passed
        }
    
    def start_monitoring(
        self, 
        directories: List[Path],
        recursive: bool = True,
        ignore_patterns: Optional[List[str]] = None
    ) -> None:
        """启动目录实时监控"""
        def handle_changes(changed_files: List[Path]) -> None:
            print(f"\n🔄 Detected changes in {len(changed_files)} files")
            results = self.process_files(changed_files)
            
            if self.on_processing_complete:
                self.on_processing_complete(results)
            
            print(f"✅ Processed: {results['processed']}, Skipped: {results['skipped']}, Failed: {results['failed']}")
        
        self._monitor = DirectoryMonitor(
            directories=directories,
            callback=handle_changes,
            recursive=recursive,
            ignore_patterns=ignore_patterns,
            debounce_seconds=5.0  # 5秒防抖，合并批量处理
        )
        
        self._monitor.start()
        print("👀 Incremental processor monitoring started")
    
    def stop_monitoring(self) -> None:
        """停止目录监控"""
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        print("🛑 Incremental processor monitoring stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取增量处理器统计信息"""
        processed_files = self.change_tracker.get_processed_files()
        return {
            "total_processed": len(processed_files),
            "processed_files": processed_files,
            "monitoring_active": self._monitor is not None and self._monitor.is_running()
        }
