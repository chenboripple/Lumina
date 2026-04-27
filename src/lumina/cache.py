"""
CacheManager - 缓存管理系统
支持文件内容缓存、LLM响应缓存、处理状态缓存
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime, timedelta


class CacheManager:
    """
    缓存管理器
    
    职责：
    1. 文件内容缓存（按文件哈希）
    2. LLM 响应缓存（按提示词哈希）
    3. 处理状态缓存（按源路径）
    4. 缓存淘汰策略（LRU + TTL）
    """
    
    def __init__(self, cache_dir: str = "~/.lumina/cache"):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 子目录
        self.file_cache_dir = self.cache_dir / "files"
        self.llm_cache_dir = self.cache_dir / "llm"
        self.state_cache_dir = self.cache_dir / "state"
        
        self.file_cache_dir.mkdir(exist_ok=True)
        self.llm_cache_dir.mkdir(exist_ok=True)
        self.state_cache_dir.mkdir(exist_ok=True)
        
        # 缓存统计
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
    
    def get_file(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """获取文件缓存"""
        cache_file = self.file_cache_dir / f"{file_hash}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding='utf-8'))
                self.stats["hits"] += 1
                return data
            except Exception:
                pass
        
        self.stats["misses"] += 1
        return None
    
    def set_file(self, file_hash: str, data: Dict[str, Any]):
        """设置文件缓存"""
        cache_file = self.file_cache_dir / f"{file_hash}.json"
        cache_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def has_file(self, file_hash: str) -> bool:
        """检查文件是否已缓存"""
        cache_file = self.file_cache_dir / f"{file_hash}.json"
        return cache_file.exists()
    
    def get_llm_response(self, prompt_hash: str) -> Optional[str]:
        """获取 LLM 响应缓存"""
        cache_file = self.llm_cache_dir / f"{prompt_hash}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding='utf-8'))
                # 检查 TTL（默认7天）
                if self._is_valid(data):
                    self.stats["hits"] += 1
                    return data.get("response")
                else:
                    # TTL 过期，删除缓存
                    cache_file.unlink()
                    self.stats["evictions"] += 1
            except Exception:
                pass
        
        self.stats["misses"] += 1
        return None
    
    def set_llm_response(self, prompt_hash: str, response: str, ttl_days: int = 7):
        """设置 LLM 响应缓存"""
        cache_file = self.llm_cache_dir / f"{prompt_hash}.json"
        data = {
            "response": response,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=ttl_days)).isoformat(),
        }
        cache_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def get_processing_state(self, source_path: str) -> Optional[Dict[str, Any]]:
        """获取处理状态缓存"""
        state_hash = hashlib.md5(source_path.encode()).hexdigest()
        cache_file = self.state_cache_dir / f"{state_hash}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding='utf-8'))
                self.stats["hits"] += 1
                return data
            except Exception:
                pass
        
        self.stats["misses"] += 1
        return None
    
    def get_processed_result(self, file_hash: str) -> Optional[str]:
        """获取完整的处理结果缓存"""
        cache_file = self.state_cache_dir / f"processed_{file_hash}.json"
        if cache_file.exists():
            try:
                data = cache_file.read_text(encoding='utf-8')
                self.stats["hits"] += 1
                return data
            except Exception:
                pass
        
        self.stats["misses"] += 1
        return None
    
    def set_processing_state(self, source_path: str, state: Dict[str, Any]):
        """设置处理状态缓存"""
        state_hash = hashlib.md5(source_path.encode()).hexdigest()
        cache_file = self.state_cache_dir / f"{state_hash}.json"
        data = {
            **state,
            "updated_at": datetime.now().isoformat(),
        }
        cache_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def set_processed_result(self, file_hash: str, result: str):
        """设置完整的处理结果缓存"""
        cache_file = self.state_cache_dir / f"processed_{file_hash}.json"
        data = {
            "result": result,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        }
        cache_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def _is_valid(self, data: Dict[str, Any]) -> bool:
        """检查缓存是否有效（未过期）"""
        if "expires_at" in data:
            expires = datetime.fromisoformat(data["expires_at"])
            return datetime.now() < expires
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return self.stats.copy()
    
    def clear(self):
        """清除所有缓存"""
        for dir_path in [self.file_cache_dir, self.llm_cache_dir, self.state_cache_dir]:
            for f in dir_path.glob("*.json"):
                f.unlink()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}
