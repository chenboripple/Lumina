"""
Lumina Configuration Manager (兼容层)

⚠️  此模块已弃用，请直接使用 `lumina.config_core`。
此模块仅作为向后兼容的薄 re-export 层，将所有公共 API 转发到 `config_core`。

迁移指南：
    # 旧:
    from lumina.config import LuminaConfig, InputSource, OutputConfig

    # 新:
    from lumina.config_core import LuminaConfig, InputSource, OutputConfig
"""

from .config_core import (  # noqa: F401
    USER_CONFIG_DIR,
    USER_CONFIG_FILE,
    DEFAULT_SUPPORTED_EXTENSIONS,
    InputSource,
    OutputConfig,
    LuminaConfig,
)

__all__ = [
    "USER_CONFIG_DIR",
    "USER_CONFIG_FILE",
    "DEFAULT_SUPPORTED_EXTENSIONS",
    "InputSource",
    "OutputConfig",
    "LuminaConfig",
]
