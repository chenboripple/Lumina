"""
Multi-Device Sync - 多设备同步模块
支持向量数据、笔记、配置的多设备同步
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"


@dataclass
class SyncItem:
    """同步项"""
    id: str
    type: str  # note, config, vector, history
    content_hash: str
    modified_at: float
    device_id: str
    status: SyncStatus = SyncStatus.PENDING
    version: int = 1


@dataclass
class SyncConflict:
    """同步冲突"""
    item_id: str
    local_version: SyncItem
    remote_version: SyncItem
    resolution: Optional[str] = None  # local, remote, merge


class SyncManager:
    """
    多设备同步管理器
    
    支持：
    1. 笔记同步 - Markdown 文件
    2. 向量数据同步 - 向量数据库
    3. 配置同步 - YAML 配置文件
    4. 历史记录同步 - SQLite 数据库
    5. 冲突解决 - 自动/手动
    """
    
    def __init__(
        self,
        device_id: str = None,
        sync_dir: str = "~/.lumina/sync",
        conflict_strategy: str = "newest"  # newest, local, remote, manual
    ):
        self.device_id = device_id or self._generate_device_id()
        self.sync_dir = Path(sync_dir).expanduser()
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.conflict_strategy = conflict_strategy
        
        # 同步状态
        self.sync_state_file = self.sync_dir / "sync_state.json"
        self.sync_state = self._load_sync_state()
        
        # 待同步队列
        self.pending_queue: List[SyncItem] = []
        
        # 冲突记录
        self.conflicts: List[SyncConflict] = []
    
    def _generate_device_id(self) -> str:
        """生成设备唯一标识"""
        import uuid
        return f"device_{uuid.uuid4().hex[:8]}"
    
    def _load_sync_state(self) -> Dict[str, Any]:
        """加载同步状态"""
        if self.sync_state_file.exists():
            try:
                return json.loads(self.sync_state_file.read_text())
            except Exception:
                pass
        return {
            "last_sync": None,
            "devices": {},
            "synced_items": {}
        }
    
    def _save_sync_state(self):
        """保存同步状态"""
        self.sync_state_file.write_text(
            json.dumps(self.sync_state, indent=2, default=str)
        )
    
    def _calculate_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def queue_note_for_sync(
        self,
        note_path: str,
        note_content: str
    ) -> SyncItem:
        """
        将笔记加入同步队列
        
        Args:
            note_path: 笔记文件路径
            note_content: 笔记内容
            
        Returns:
            同步项
        """
        item = SyncItem(
            id=note_path,
            type="note",
            content_hash=self._calculate_hash(note_content),
            modified_at=time.time(),
            device_id=self.device_id,
            status=SyncStatus.PENDING
        )
        
        self.pending_queue.append(item)
        return item
    
    def queue_config_for_sync(
        self,
        config_path: str,
        config_content: str
    ) -> SyncItem:
        """将配置加入同步队列"""
        item = SyncItem(
            id=config_path,
            type="config",
            content_hash=self._calculate_hash(config_content),
            modified_at=time.time(),
            device_id=self.device_id,
            status=SyncStatus.PENDING
        )
        
        self.pending_queue.append(item)
        return item
    
    def queue_vector_for_sync(
        self,
        vector_id: str,
        vector_data: Dict[str, Any]
    ) -> SyncItem:
        """将向量数据加入同步队列"""
        content = json.dumps(vector_data, sort_keys=True)
        item = SyncItem(
            id=vector_id,
            type="vector",
            content_hash=self._calculate_hash(content),
            modified_at=time.time(),
            device_id=self.device_id,
            status=SyncStatus.PENDING
        )
        
        self.pending_queue.append(item)
        return item
    
    def sync(
        self,
        target_device: str = None,
        sync_all: bool = False
    ) -> Dict[str, Any]:
        """
        执行同步
        
        Args:
            target_device: 目标设备（None 表示所有设备）
            sync_all: 是否同步所有数据
            
        Returns:
            同步结果
        """
        results = {
            "synced": 0,
            "failed": 0,
            "conflicts": 0,
            "skipped": 0,
            "details": []
        }
        
        # 处理待同步队列
        for item in self.pending_queue:
            try:
                item.status = SyncStatus.SYNCING
                
                # 检查冲突
                conflict = self._check_conflict(item)
                if conflict:
                    resolution = self._resolve_conflict(conflict)
                    if resolution == "skip":
                        item.status = SyncStatus.SYNCED
                        results["skipped"] += 1
                        continue
                
                # 执行同步
                success = self._sync_item(item, target_device)
                if success:
                    item.status = SyncStatus.SYNCED
                    results["synced"] += 1
                else:
                    item.status = SyncStatus.ERROR
                    results["failed"] += 1
                    
            except Exception as e:
                item.status = SyncStatus.ERROR
                results["failed"] += 1
                results["details"].append({
                    "item": item.id,
                    "error": str(e)
                })
        
        # 清空队列
        self.pending_queue.clear()
        
        # 更新同步状态
        self.sync_state["last_sync"] = time.time()
        self._save_sync_state()
        
        return results
    
    def _check_conflict(self, item: SyncItem) -> Optional[SyncConflict]:
        """检查是否存在冲突"""
        # 检查本地状态
        local_item = self.sync_state["synced_items"].get(item.id)
        if not local_item:
            return None
        
        # 检查是否有更新版本
        if local_item.get("version", 0) >= item.version:
            # 检查内容是否不同
            if local_item.get("content_hash") != item.content_hash:
                return SyncConflict(
                    item_id=item.id,
                    local_version=SyncItem(**local_item),
                    remote_version=item
                )
        
        return None
    
    def _resolve_conflict(self, conflict: SyncConflict) -> str:
        """
        解决冲突
        
        Returns:
            解决策略: local, remote, merge, skip
        """
        if self.conflict_strategy == "newest":
            # 选择最新的版本
            if conflict.remote_version.modified_at > conflict.local_version.modified_at:
                return "remote"
            else:
                return "local"
        
        elif self.conflict_strategy == "local":
            return "local"
        
        elif self.conflict_strategy == "remote":
            return "remote"
        
        elif self.conflict_strategy == "manual":
            # 记录冲突，等待手动解决
            self.conflicts.append(conflict)
            return "skip"
        
        return "remote"  # 默认
    
    def _sync_item(
        self,
        item: SyncItem,
        target_device: str = None
    ) -> bool:
        """
        同步单个项目
        
        Args:
            item: 同步项
            target_device: 目标设备
            
        Returns:
            是否成功
        """
        # 这里实现具体的同步逻辑
        # 可以基于文件系统、云存储、Git 等
        
        # 示例：保存到同步目录
        sync_file = self.sync_dir / f"{item.type}_{item.id.replace('/', '_')}"
        
        try:
            sync_data = {
                "item": {
                    "id": item.id,
                    "type": item.type,
                    "content_hash": item.content_hash,
                    "modified_at": item.modified_at,
                    "device_id": item.device_id,
                    "version": item.version
                },
                "synced_at": time.time(),
                "from_device": self.device_id,
                "to_device": target_device or "all"
            }
            
            sync_file.write_text(json.dumps(sync_data, indent=2))
            
            # 更新同步状态
            self.sync_state["synced_items"][item.id] = {
                "id": item.id,
                "type": item.type,
                "content_hash": item.content_hash,
                "modified_at": item.modified_at,
                "device_id": item.device_id,
                "version": item.version,
                "last_sync": time.time()
            }
            
            return True
            
        except Exception:
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "device_id": self.device_id,
            "last_sync": self.sync_state.get("last_sync"),
            "pending_count": len(self.pending_queue),
            "conflict_count": len(self.conflicts),
            "synced_items_count": len(self.sync_state.get("synced_items", {})),
            "devices": list(self.sync_state.get("devices", {}).keys())
        }
    
    def get_conflicts(self) -> List[Dict[str, Any]]:
        """获取所有冲突"""
        return [
            {
                "item_id": c.item_id,
                "local_device": c.local_version.device_id,
                "local_modified": c.local_version.modified_at,
                "remote_device": c.remote_version.device_id,
                "remote_modified": c.remote_version.modified_at,
                "resolution": c.resolution
            }
            for c in self.conflicts
        ]
    
    def resolve_conflict_manually(
        self,
        conflict_id: str,
        resolution: str
    ) -> bool:
        """
        手动解决冲突
        
        Args:
            conflict_id: 冲突项 ID
            resolution: 解决策略 (local, remote, merge)
            
        Returns:
            是否成功
        """
        conflict = next(
            (c for c in self.conflicts if c.item_id == conflict_id),
            None
        )
        
        if not conflict:
            return False
        
        conflict.resolution = resolution
        
        # 应用解决策略
        if resolution == "local":
            # 保留本地版本
            pass
        elif resolution == "remote":
            # 使用远程版本
            pass
        elif resolution == "merge":
            # 合并版本（需要具体实现）
            pass
        
        # 从冲突列表移除
        self.conflicts = [c for c in self.conflicts if c.item_id != conflict_id]
        
        return True
    
    def export_sync_package(
        self,
        output_path: str,
        include_notes: bool = True,
        include_config: bool = True,
        include_vectors: bool = True,
        include_history: bool = False
    ) -> str:
        """
        导出同步包
        
        Args:
            output_path: 输出路径
            include_notes: 是否包含笔记
            include_config: 是否包含配置
            include_vectors: 是否包含向量数据
            include_history: 是否包含历史记录
            
        Returns:
            导出文件路径
        """
        import zipfile
        
        output_file = Path(output_path)
        
        with zipfile.ZipFile(output_file, 'w') as zf:
            # 添加同步状态
            zf.writestr(
                "sync_state.json",
                json.dumps(self.sync_state, indent=2, default=str)
            )
            
            # 添加设备信息
            zf.writestr(
                "device_info.json",
                json.dumps({
                    "device_id": self.device_id,
                    "exported_at": time.time()
                })
            )
        
        return str(output_file)
    
    def import_sync_package(
        self,
        package_path: str,
        merge_strategy: str = "newest"
    ) -> Dict[str, Any]:
        """
        导入同步包
        
        Args:
            package_path: 包文件路径
            merge_strategy: 合并策略
            
        Returns:
            导入结果
        """
        import zipfile
        
        results = {
            "imported": 0,
            "skipped": 0,
            "conflicts": 0
        }
        
        with zipfile.ZipFile(package_path, 'r') as zf:
            # 读取同步状态
            sync_state_data = zf.read("sync_state.json")
            remote_state = json.loads(sync_state_data)
            
            # 合并同步状态
            for item_id, item_data in remote_state.get("synced_items", {}).items():
                local_item = self.sync_state["synced_items"].get(item_id)
                
                if not local_item:
                    # 本地不存在，直接导入
                    self.sync_state["synced_items"][item_id] = item_data
                    results["imported"] += 1
                else:
                    # 需要合并
                    if merge_strategy == "newest":
                        if item_data.get("modified_at", 0) > local_item.get("modified_at", 0):
                            self.sync_state["synced_items"][item_id] = item_data
                            results["imported"] += 1
                        else:
                            results["skipped"] += 1
                    elif merge_strategy == "remote":
                        self.sync_state["synced_items"][item_id] = item_data
                        results["imported"] += 1
                    else:
                        results["skipped"] += 1
        
        self._save_sync_state()
        
        return results


class CloudSyncProvider:
    """
    云同步提供者基类
    
    子类需要实现具体的云存储同步逻辑
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def upload(self, local_path: str, remote_path: str) -> bool:
        """上传文件"""
        raise NotImplementedError
    
    def download(self, remote_path: str, local_path: str) -> bool:
        """下载文件"""
        raise NotImplementedError
    
    def list_remote(self, remote_dir: str) -> List[Dict[str, Any]]:
        """列出远程文件"""
        raise NotImplementedError
    
    def delete_remote(self, remote_path: str) -> bool:
        """删除远程文件"""
        raise NotImplementedError


class GitSyncProvider(CloudSyncProvider):
    """
    Git 同步提供者
    
    使用 Git 进行版本控制和同步
    """
    
    def __init__(self, repo_path: str, remote_url: str = None):
        super().__init__({"repo_path": repo_path, "remote_url": remote_url})
        self.repo_path = Path(repo_path)
        self.remote_url = remote_url
    
    def init_repo(self) -> bool:
        """初始化 Git 仓库"""
        import subprocess
        
        try:
            self.repo_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "init"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            if self.remote_url:
                subprocess.run(
                    ["git", "remote", "add", "origin", self.remote_url],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True
                )
            
            return True
        except Exception:
            return False
    
    def sync(self, message: str = "Sync from Lumina") -> bool:
        """执行 Git 同步"""
        import subprocess
        
        try:
            # 添加所有变更
            subprocess.run(
                ["git", "add", "."],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            # 提交
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=False,  # 允许没有变更的情况
                capture_output=True
            )
            
            # 推送
            if self.remote_url:
                subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=self.repo_path,
                    check=False,
                    capture_output=True
                )
            
            return True
        except Exception:
            return False
