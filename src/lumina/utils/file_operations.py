"""
文件操作工具集（增强版）
支持编码自动检测、换行符保留、精确替换、权限检查、文件哈希、类型检测等
"""

import hashlib
import re
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import fnmatch


@dataclass
class FileMetadata:
    """文件元数据"""
    path: Path
    encoding: str
    line_endings: str  # 'LF' | 'CRLF'
    size: int
    modified: float
    is_symlink: bool


@dataclass
class ReplaceResult:
    """替换结果"""
    success: bool
    old_content: str
    new_content: str
    matches: int
    errors: List[str]
    changes: List[Tuple[int, str, str]]  # 行号, 旧内容, 新内容


class FilePermissionError(Exception):
    """文件权限错误"""
    pass


class FileOperationError(Exception):
    """文件操作错误"""
    pass


_FILE_TYPE_MAP = {
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


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希（用于变化检测）"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def detect_file_type(file_path: Path) -> str:
    """检测文件类型"""
    return _FILE_TYPE_MAP.get(file_path.suffix.lower(), 'unknown')


def detect_encoding(file_path: Path) -> str:
    """
    自动检测文件编码
    参考: https://chardet.readthedocs.io/ 简化实现
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'utf-16le', 'utf-16be', 'latin-1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(4096)
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue

    return 'latin-1'


def detect_line_endings(content: str) -> str:
    """检测文件换行符风格，返回 'LF' 或 'CRLF'"""
    crlf_count = content.count('\r\n')
    lf_count = content.count('\n') - crlf_count

    if crlf_count > lf_count:
        return 'CRLF'
    return 'LF'


def read_file_with_metadata(file_path: Path, encoding: Optional[str] = None) -> Tuple[str, FileMetadata]:
    """
    读取文件内容并返回元数据（编码、换行符等）
    写入时可以保留原始格式
    """
    if not file_path.exists():
        raise FileOperationError(f"File not found: {file_path}")

    if not encoding:
        encoding = detect_encoding(file_path)

    try:
        with open(file_path, 'r', encoding=encoding, newline='') as f:
            raw_content = f.read()

        line_endings = detect_line_endings(raw_content)
        normalized_content = raw_content.replace('\r\n', '\n')

        stat = file_path.stat()
        metadata = FileMetadata(
            path=file_path,
            encoding=encoding,
            line_endings=line_endings,
            size=stat.st_size,
            modified=stat.st_mtime,
            is_symlink=file_path.is_symlink()
        )

        return normalized_content, metadata

    except Exception as e:
        raise FileOperationError(f"Failed to read file {file_path}: {str(e)}") from e


def write_file_with_metadata(content: str, metadata: FileMetadata, backup: bool = True) -> Path:
    """使用原始元数据写入文件，保留编码和换行符"""
    backup_path = None
    try:
        if metadata.line_endings == 'CRLF':
            content = content.replace('\n', '\r\n')

        if backup and metadata.path.exists():
            backup_path = metadata.path.with_suffix(metadata.path.suffix + '.bak')
            metadata.path.rename(backup_path)

        with open(metadata.path, 'w', encoding=metadata.encoding, newline='') as f:
            f.write(content)

        return metadata.path

    except Exception as e:
        if backup_path is not None and backup_path.exists():
            backup_path.rename(metadata.path)
        raise FileOperationError(f"Failed to write file {metadata.path}: {str(e)}") from e


def exact_replace(
    file_path: Path,
    old_str: str,
    new_str: str,
    replace_all: bool = False,
    encoding: Optional[str] = None
) -> ReplaceResult:
    """
    精确字符串替换
    要求 old_str 在文件中完全匹配（包括空格、换行）
    """
    errors = []
    changes = []

    try:
        content, metadata = read_file_with_metadata(file_path, encoding)

        matches = list(re.finditer(re.escape(old_str), content))

        if not matches:
            return ReplaceResult(
                success=False,
                old_content=content,
                new_content=content,
                matches=0,
                errors=["No matches found"],
                changes=[]
            )

        if len(matches) > 1 and not replace_all:
            return ReplaceResult(
                success=False,
                old_content=content,
                new_content=content,
                matches=len(matches),
                errors=[f"Multiple matches ({len(matches)}) found, use replace_all=True to replace all"],
                changes=[]
            )

        new_content = content
        for match in reversed(matches):
            line_num = content.count('\n', 0, match.start()) + 1
            old_line = content[match.start():match.end()]
            new_content = new_content[:match.start()] + new_str + new_content[match.end():]
            changes.append((line_num, old_line, new_str))

        write_file_with_metadata(new_content, metadata)

        return ReplaceResult(
            success=True,
            old_content=content,
            new_content=new_content,
            matches=len(matches),
            errors=[],
            changes=changes
        )

    except Exception as e:
        errors.append(str(e))
        return ReplaceResult(
            success=False,
            old_content="",
            new_content="",
            matches=0,
            errors=errors,
            changes=[]
        )


def check_write_permission(file_path: Path, rules: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """
    检查文件写入权限
    rules: 权限规则列表，支持通配符
           前缀 '-' 表示拒绝，前缀 '+' 表示允许
           示例: ["-**/.ssh/*", "+**/notes/*", "-**/*.env"]
    """
    errors = []

    if not rules:
        return True, []

    path_str = str(file_path.resolve())

    for rule in rules:
        if rule.startswith('-'):
            pattern = rule[1:]
            if fnmatch.fnmatch(path_str, pattern):
                errors.append(f"Path is denied by rule: {rule}")
                return False, errors

    for rule in rules:
        if rule.startswith('+'):
            pattern = rule[1:]
            if fnmatch.fnmatch(path_str, pattern):
                return True, []

    errors.append("No allow rule matched")
    return False, errors


def check_sensitive_content(content: str, patterns: Optional[List[str]] = None) -> List[str]:
    """检查内容是否包含敏感信息（API Key、密码等）"""
    default_patterns = [
        r'(?i)api[_-]key\s*=\s*["\']?[A-Za-z0-9]+["\']?',
        r'(?i)secret\s*=\s*["\']?[A-Za-z0-9]+["\']?',
        r'(?i)password\s*=\s*["\']?.+["\']?',
        r'(?i)token\s*=\s*["\']?[A-Za-z0-9]+["\']?',
        r'sk-[A-Za-z0-9]{20,}',
        r'ghp_[A-Za-z0-9]{20,}',
    ]

    patterns = patterns or default_patterns
    issues = []

    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            masked = match[:10] + "****" if len(match) > 10 else match
            issues.append(f"Sensitive content detected: {masked}")

    return issues


def is_file_modified(file_path: Path, last_modified: float) -> bool:
    """检查文件是否被外部修改"""
    if not file_path.exists():
        return True

    current_modified = file_path.stat().st_mtime
    return abs(current_modified - last_modified) > 0.001
