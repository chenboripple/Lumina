"""
Config Hot Reload - 配置热加载模块
支持文件监控、自动重载、配置变更通知
"""

import os
import time
import yaml
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from ..config import LuminaConfig


class ConfigChangeEvent:
    """配置变更事件"""
    def __init__(self, config_path: str, old_config: Dict, new_config: Dict):
        self.config_path = config_path
        self.old_config = old_config
        self.new_config = new_config
        self.timestamp = time.time()
        
        # 计算变更差异
        self.changes = self._calculate_changes()
    
    def _calculate_changes(self) -> List[Dict[str, Any]]:
        """计算配置变更差异"""
        changes = []
        
        def compare_dict(old: Dict, new: Dict, path: str = ""):
            all_keys = set(old.keys()) | set(new.keys())
            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                
                if key not in old:
                    changes.append({
                        "path": current_path,
                        "type": "added",
                        "new_value": new[key]
                    })
                elif key not in new:
                    changes.append({
                        "path": current_path,
                        "type": "removed",
                        "old_value": old[key]
                    })
                elif old[key] != new[key]:
                    if isinstance(old[key], dict) and isinstance(new[key], dict):
                        compare_dict(old[key], new[key], current_path)
                    else:
                        changes.append({
                            "path": current_path,
                            "type": "modified",
                            "old_value": old[key],
                            "new_value": new[key]
                        })
        
        compare_dict(self.old_config, self.new_config)
        return changes
    
    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0
    
    def get_changed_paths(self) -> List[str]:
        """获取变更的配置路径"""
        return [c["path"] for c in self.changes]


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件事件处理器"""
    
    def __init__(self, callback: Callable[[ConfigChangeEvent], None]):
        self.callback = callback
        self._last_modified = 0
        self._debounce_interval = 0.5  # 防抖间隔（秒）
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(('.yaml', '.yml')):
            now = time.time()
            if now - self._last_modified < self._debounce_interval:
                return
            self._last_modified = now
            
            # 通知回调
            self.callback(event)


class ConfigWatcher:
    """
    配置监控器
    
    支持：
    1. 文件系统事件监控
    2. 配置变更检测
    3. 自动重新加载
    4. 变更通知回调
    """
    
    def __init__(
        self,
        config_path: str,
        auto_reload: bool = True,
        on_change: Optional[Callable[[ConfigChangeEvent], None]] = None
    ):
        self.config_path = Path(config_path)
        self.auto_reload = auto_reload
        self.on_change = on_change
        
        self._current_config: Optional[Dict] = None
        self._last_modified: Optional[float] = None
        self._observer: Optional[Observer] = None
        self._lock = threading.Lock()
        
        # 初始化
        self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            stat = self.config_path.stat()
            self._last_modified = stat.st_mtime
            self._current_config = config
            
            return config
        except Exception as e:
            print(f"⚠️  Failed to load config: {e}")
            return self._current_config or {}
    
    def has_changed(self) -> bool:
        """检查配置是否变更"""
        if not self.config_path.exists():
            return False
        
        try:
            stat = self.config_path.stat()
            return stat.st_mtime != self._last_modified
        except Exception:
            return False
    
    def reload(self) -> Dict:
        """重新加载配置"""
        with self._lock:
            old_config = self._current_config.copy() if self._current_config else {}
            new_config = self._load_config()
            
            event = ConfigChangeEvent(
                str(self.config_path),
                old_config,
                new_config
            )
            
            if event.has_changes and self.on_change:
                self.on_change(event)
            
            return new_config
    
    def start_watching(self):
        """开始监控文件变更"""
        if self._observer:
            return
        
        self._observer = Observer()
        handler = ConfigFileHandler(self._on_file_changed)
        
        # 监控配置文件所在目录
        watch_dir = str(self.config_path.parent)
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.start()
    
    def stop_watching(self):
        """停止监控"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def _on_file_changed(self, event: FileModifiedEvent):
        """文件变更回调"""
        if str(self.config_path) != event.src_path:
            return
        
        if self.auto_reload:
            self.reload()
    
    def get_config(self) -> Dict:
        """获取当前配置"""
        with self._lock:
            return self._current_config.copy() if self._current_config else {}
    
    def __enter__(self):
        self.start_watching()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_watching()


class HotReloadManager:
    """
    热加载管理器
    
    管理多个配置的监控和重载
    """
    
    def __init__(self):
        self.watchers: Dict[str, ConfigWatcher] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def add_config(
        self,
        config_path: str,
        auto_reload: bool = True,
        on_change: Optional[Callable[[ConfigChangeEvent], None]] = None
    ) -> ConfigWatcher:
        """添加配置监控"""
        watcher = ConfigWatcher(
            config_path,
            auto_reload=auto_reload,
            on_change=on_change
        )
        self.watchers[config_path] = watcher
        
        if auto_reload:
            watcher.start_watching()
        
        return watcher
    
    def remove_config(self, config_path: str):
        """移除配置监控"""
        if config_path in self.watchers:
            self.watchers[config_path].stop_watching()
            del self.watchers[config_path]
    
    def reload_all(self):
        """重新加载所有配置"""
        for watcher in self.watchers.values():
            watcher.reload()
    
    def stop_all(self):
        """停止所有监控"""
        for watcher in self.watchers.values():
            watcher.stop_watching()
        self.watchers.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all()
