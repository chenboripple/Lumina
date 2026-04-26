
"""
目录实时监控器
基于 watchdog 实现文件系统变化的实时监控，支持增量更新触发
"""

import time
import threading
from pathlib import Path
from typing import Callable, List, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from collections import deque


class DirectoryChangeHandler(FileSystemEventHandler):
    """目录变化事件处理器"""
    
    def __init__(
        self, 
        callback: Callable[[List[Path]], None],
        ignore_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0
    ):
        self.callback = callback
        self.ignore_patterns = ignore_patterns or []
        self.debounce_seconds = debounce_seconds
        
        # 防抖队列
        self._pending_files: Set[Path] = set()
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
    
    def _should_ignore(self, file_path: Path) -> bool:
        """判断是否应该忽略该文件"""
        # 忽略隐藏文件和目录
        for part in file_path.parts:
            if part.startswith('.'):
                return True
        
        # 忽略临时文件
        suffix = file_path.suffix.lower()
        if suffix in ['.tmp', '.swp', '.swap', '.~', '.log']:
            return True
        
        # 忽略用户指定的模式
        file_path_str = str(file_path)
        for pattern in self.ignore_patterns:
            if pattern in file_path_str:
                return True
        
        return False
    
    def _process_pending_files(self) -> None:
        """处理累积的文件变化（防抖）"""
        with self._lock:
            if not self._pending_files:
                return
            
            files = list(self._pending_files)
            self._pending_files.clear()
            self._debounce_timer = None
        
        # 回调处理
        try:
            self.callback(files)
        except Exception as e:
            print(f"⚠️  Error processing changed files: {e}")
    
    def _enqueue_file(self, file_path: Path) -> None:
        """将变化的文件加入队列，防抖处理"""
        if self._should_ignore(file_path):
            return
        
        with self._lock:
            self._pending_files.add(file_path)
            
            # 取消之前的定时器
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # 创建新的定时器
            self._debounce_timer = threading.Timer(
                self.debounce_seconds, 
                self._process_pending_files
            )
            self._debounce_timer.start()
    
    def on_created(self, event: FileSystemEvent) -> None:
        """文件创建事件"""
        if not event.is_directory:
            self._enqueue_file(Path(event.src_path))
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """文件修改事件"""
        if not event.is_directory:
            self._enqueue_file(Path(event.src_path))
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """文件移动/重命名事件"""
        if not event.is_directory:
            # 源文件删除
            self._enqueue_file(Path(event.src_path))
            # 目标文件新增
            self._enqueue_file(Path(event.dest_path))
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """文件删除事件"""
        if not event.is_directory:
            self._enqueue_file(Path(event.src_path))


class DirectoryMonitor:
    """
    目录监控器
    监控一个或多个目录的文件变化，支持防抖合并处理
    """
    
    def __init__(
        self, 
        directories: List[Path],
        callback: Callable[[List[Path]], None],
        recursive: bool = True,
        ignore_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0
    ):
        self.directories = [dir.resolve() for dir in directories]
        self.callback = callback
        self.recursive = recursive
        self.ignore_patterns = ignore_patterns or []
        self.debounce_seconds = debounce_seconds
        
        self._observer: Optional[Observer] = None
        self._handlers: List[DirectoryChangeHandler] = []
        self._running = False
    
    def start(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._observer = Observer()
        
        for directory in self.directories:
            if not directory.exists() or not directory.is_dir():
                print(f"⚠️  Directory not found: {directory}, skipping")
                continue
            
            handler = DirectoryChangeHandler(
                callback=self.callback,
                ignore_patterns=self.ignore_patterns,
                debounce_seconds=self.debounce_seconds
            )
            self._handlers.append(handler)
            
            self._observer.schedule(
                handler, 
                str(directory), 
                recursive=self.recursive
            )
            print(f"👀 Started monitoring directory: {directory}")
        
        self._observer.start()
        self._running = True
        print("✅ Directory monitor started")
    
    def stop(self) -> None:
        """停止监控"""
        if not self._running:
            return
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
        
        # 清理定时器
        for handler in self._handlers:
            with handler._lock:
                if handler._debounce_timer:
                    handler._debounce_timer.cancel()
        
        self._running = False
        print("🛑 Directory monitor stopped")
    
    def is_running(self) -> bool:
        """检查监控是否正在运行"""
        return self._running
    
    def run_forever(self) -> None:
        """运行直到被中断"""
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


# 示例使用
if __name__ == "__main__":
    def handle_changes(files: List[Path]) -> None:
        print(f"\n🔄 Detected changes in {len(files)} files:")
        for file in files:
            print(f"  - {file}")
        # 这里可以触发增量更新
        # incremental_processor.process_files(files)
    
    # 监控当前目录
    monitor = DirectoryMonitor(
        directories=[Path('.')],
        callback=handle_changes,
        recursive=True,
        debounce_seconds=3.0
    )
    
    monitor.start()
    print("Monitoring for changes... Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
