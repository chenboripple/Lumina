"""
Lumina - 知识萃取 Agent
基于 Harness Engineering 三元架构
"""

__version__ = "0.1.0"
__author__ = "Ripple"

from .planner import Planner
from .executor import Executor
from .validator import Validator
from .harness import Harness
from .plugins import (
    BasePlugin,
    ObsidianPlugin,
    PlainMarkdownPlugin,
    get_plugin,
    list_plugins,
)

__all__ = [
    "Planner",
    "Executor",
    "Validator",
    "Harness",
    "BasePlugin",
    "ObsidianPlugin",
    "PlainMarkdownPlugin",
    "get_plugin",
    "list_plugins",
]