#!/usr/bin/env python3
"""
Lumina 快速启动脚本
提供生产和调试两种模式
"""

import sys
import os
from pathlib import Path

# 添加源码路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        # 调试模式
        from lumina.debug import run_debug_mode
        # 移除 --debug 参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        run_debug_mode()
    else:
        # 正常模式
        from lumina.cli import cli
        cli()


if __name__ == "__main__":
    main()
