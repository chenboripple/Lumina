#!/usr/bin/env python3
"""
Lumina 安装脚本
支持 Windows、macOS、Linux
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def print_banner():
    """打印安装横幅"""
    print("""
╔══════════════════════════════════════════╗
║                                          ║
║   Lumina - 知识萃取 Agent                 ║
║   本地文件 → 智能整理 → 格式化笔记         ║
║                                          ║
╚══════════════════════════════════════════╝
    """)


def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 版本过低: {version.major}.{version.minor}")
        print("   需要 Python 3.8 或更高版本")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-e", "."
        ])
        print("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False


def create_config():
    """创建默认配置"""
    config_dir = Path.home() / ".lumina"
    config_file = config_dir / "config.yaml"
    
    if config_file.exists():
        print(f"⚠️  配置文件已存在: {config_file}")
        return True
    
    print("\n⚙️  创建默认配置...")
    config_dir.mkdir(parents=True, exist_ok=True)
    
    default_config = """# Lumina 用户配置
# 修改此文件以自定义 Lumina 行为

input:
  sources:
    - path: "~/Documents"
      recursive: true
      filter: "*.md"

output:
  plugin: obsidian
  base_dir: "~/Lumina/Notes"
  vault_path: "~/Obsidian/Vault"

llm:
  provider: "openai"
  # api_key: "your-api-key-here"
  # 或设置环境变量: OPENAI_API_KEY
  model: "gpt-4"
  temperature: 0.3

harness:
  max_iterations: 3
  quality_threshold: 0.8
"""
    
    config_file.write_text(default_config, encoding='utf-8')
    print(f"✅ 配置文件创建: {config_file}")
    return True


def setup_shell_completion():
    """设置 Shell 补全"""
    shell = os.environ.get("SHELL", "").split("/")[-1]
    
    if shell == "zsh":
        rc_file = Path.home() / ".zshrc"
        completion_cmd = "eval \"$(lumina --show-completion zsh)\""
    elif shell == "bash":
        rc_file = Path.home() / ".bashrc"
        completion_cmd = "eval \"$(lumina --show-completion bash)\""
    else:
        return
    
    if rc_file.exists():
        content = rc_file.read_text()
        if "lumina --show-completion" not in content:
            with open(rc_file, "a") as f:
                f.write(f"\n# Lumina shell completion\n{completion_cmd}\n")
            print(f"✅ Shell 补全已添加到 {rc_file}")


def main():
    """主安装流程"""
    print_banner()
    
    print(f"\n🔍 系统信息:")
    print(f"   平台: {platform.system()} {platform.release()}")
    print(f"   架构: {platform.machine()}")
    
    if not check_python():
        sys.exit(1)
    
    if not install_dependencies():
        sys.exit(1)
    
    create_config()
    setup_shell_completion()
    
    print("\n" + "="*50)
    print("🎉 Lumina 安装完成!")
    print("="*50)
    print("\n快速开始:")
    print("   lumina scan ~/Documents --output ./notes")
    print("\n配置文件:")
    print(f"   {Path.home() / '.lumina' / 'config.yaml'}")
    print("\n更多帮助:")
    print("   lumina --help")
    print()


if __name__ == "__main__":
    main()