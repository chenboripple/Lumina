"""
utils/file_utils.py - 文件工具函数
"""

import hashlib
from pathlib import Path


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希（用于变化检测）"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def detect_file_type(file_path: Path) -> str:
    """检测文件类型"""
    suffix = file_path.suffix.lower()
    type_map = {
        '.md': 'markdown',
        '.txt': 'text',
        '.sql': 'text',
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
        '.gif': 'image',
    }
    return type_map.get(suffix, 'unknown')
