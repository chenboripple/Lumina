
"""
文件编辑工具（参考 Claude Code 实现）
支持精确替换、编码保留、换行符保留、权限检查等功能
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .base_tool import BaseTool, ToolResult, ToolContext
from ..utils.file_operations import (
    read_file_with_metadata, write_file_with_metadata,
    exact_replace, check_write_permission, check_sensitive_content,
    is_file_modified, FileMetadata, FileOperationError
)


@dataclass
class FileEditInput:
    """文件编辑输入参数"""
    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False
    encoding: Optional[str] = None


class FileEditTool(BaseTool):
    """
    文件编辑工具
    参考 Claude Code 的 FileEditTool 实现
    """
    
    name = "file_edit"
    display_name = "File Edit Tool"
    description = "Edit file contents with exact string replacement. Preserves encoding and line endings."
    version = "1.0.0"
    author = "Lumina Team"
    
    default_config = {
        "max_file_size": 1024 * 1024 * 1024,  # 1GB
        "backup_before_edit": True,
        "check_permissions": True,
        "check_sensitive_content": True,
    }
    
    def _validate_config(self) -> None:
        """验证配置"""
        if self.config["max_file_size"] <= 0:
            raise ValueError("max_file_size must be positive")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数 Schema"""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to replace (must match exactly including whitespace)"
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement string"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "If true, replace all occurrences. If false, only replace the first match",
                    "default": False
                }
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    
    def execute(self, context: ToolContext, **kwargs) -> ToolResult:
        """
        执行文件编辑
        
        流程：
        1. 验证输入
        2. 检查文件大小
        3. 检查权限
        4. 读取文件（检测编码和换行符）
        5. 检查敏感内容
        6. 执行精确替换
        7. 写入文件（保留编码和换行符）
        8. 返回结果
        """
        import time
        start_time = time.time()
        
        try:
            # 1. 解析输入
            input_data = FileEditInput(**kwargs)
            file_path = Path(input_data.file_path).expanduser().resolve()
            
            # 2. 验证文件存在
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}"
                )
            
            # 3. 检查文件大小
            file_size = file_path.stat().st_size
            if file_size > self.config["max_file_size"]:
                return ToolResult(
                    success=False,
                    error=f"File too large: {file_size} bytes (max: {self.config['max_file_size']})"
                )
            
            # 4. 检查权限
            if self.config["check_permissions"]:
                rules = context.config.get("write_permission_rules", ["+**/*"])
                allowed, errors = check_write_permission(file_path, rules)
                if not allowed:
                    return ToolResult(
                        success=False,
                        error=f"Permission denied: {errors}"
                    )
            
            # 5. 检查文件是否被外部修改
            if file_path.exists():
                last_modified = context.config.get("last_modified", 0)
                if is_file_modified(file_path, last_modified):
                    return ToolResult(
                        success=False,
                        error="File was modified externally. Please re-read the file."
                    )
            
            # 6. 读取文件
            content, metadata = read_file_with_metadata(file_path, input_data.encoding)
            
            # 7. 检查敏感内容
            if self.config["check_sensitive_content"]:
                sensitive_issues = check_sensitive_content(input_data.new_string)
                if sensitive_issues:
                    return ToolResult(
                        success=False,
                        error=f"Sensitive content detected in replacement: {sensitive_issues}"
                    )
            
            # 8. 检查 old_string 和 new_string 是否相同
            if input_data.old_string == input_data.new_string:
                return ToolResult(
                    success=False,
                    error="old_string and new_string are identical, no change needed"
                )
            
            # 9. 执行精确替换
            result = exact_replace(
                file_path=file_path,
                old_str=input_data.old_string,
                new_str=input_data.new_string,
                replace_all=input_data.replace_all,
                encoding=input_data.encoding
            )
            
            if not result.success:
                return ToolResult(
                    success=False,
                    error=result.errors[0] if result.errors else "Replacement failed"
                )
            
            # 10. 生成变更摘要
            changes_summary = "\n".join([
                f"  Line {line_num}: {old[:50]}... -> {new[:50]}..."
                for line_num, old, new in result.changes[:5]  # 最多显示5条
            ])
            
            execution_time = time.time() - start_time
            
            return ToolResult(
                success=True,
                data={
                    "file_path": str(file_path),
                    "matches": result.matches,
                    "changes": result.changes,
                    "encoding": metadata.encoding,
                    "line_endings": metadata.line_endings,
                },
                message=f"Successfully replaced {result.matches} occurrence(s)\n{changes_summary}",
                execution_time=execution_time
            )
            
        except FileOperationError as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
