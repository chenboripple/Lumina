"""
Lumina 工具模块 __init__
"""

from .progress import ProgressTracker, BatchProgressTracker, ProgressState
from .error_handler import (
    ErrorHandler, ErrorSeverity, ErrorRecord,
    safe_execute, GracefulDegradation
)
from .logging import (
    get_logger, timed, set_log_level,
    log_info, log_warning, log_error, log_debug,
    get_performance_stats, reset_performance_stats,
    log_with_recovery, get_error_recovery,
)
from .file_operations import (
    FileMetadata, ReplaceResult,
    FilePermissionError, FileOperationError,
    get_file_hash, detect_file_type,
    detect_encoding, detect_line_endings,
    read_file_with_metadata, write_file_with_metadata,
    exact_replace, check_write_permission,
    check_sensitive_content, is_file_modified,
)

__all__ = [
    'ProgressTracker',
    'BatchProgressTracker',
    'ProgressState',
    'ErrorHandler',
    'ErrorSeverity',
    'ErrorRecord',
    'safe_execute',
    'GracefulDegradation',
    'get_logger',
    'timed',
    'set_log_level',
    'log_info',
    'log_warning',
    'log_error',
    'log_debug',
    'get_performance_stats',
    'reset_performance_stats',
    'log_with_recovery',
    'get_error_recovery',
    'FileMetadata',
    'ReplaceResult',
    'FilePermissionError',
    'FileOperationError',
    'get_file_hash',
    'detect_file_type',
    'detect_encoding',
    'detect_line_endings',
    'read_file_with_metadata',
    'write_file_with_metadata',
    'exact_replace',
    'check_write_permission',
    'check_sensitive_content',
    'is_file_modified',
]
