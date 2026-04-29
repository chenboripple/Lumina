#!/usr/bin/env python3
"""
Lumina 安装脚本
支持 Windows、macOS、Linux
"""

import os
import sys
import subprocess
import platform
import argparse
import importlib.util
import importlib.metadata
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


def get_install_dir():
    """获取安装目录"""
    return Path(__file__).parent


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


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _is_chromadb_compatible() -> bool:
    """当前项目使用旧版 Chroma 客户端配置，需 chromadb<0.5。"""
    try:
        version = importlib.metadata.version("chromadb")
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        if major >= 1:
            return False
        if major == 0 and minor >= 5:
            return False
        return True
    except Exception:
        return False


def _is_numpy_compatible_for_chromadb() -> bool:
    """chromadb 0.4.x 在本项目路径下需要 numpy<2。"""
    try:
        version = importlib.metadata.version("numpy")
        major = int(version.split(".")[0])
        return major < 2
    except Exception:
        return False


def ensure_runtime_dependencies():
    """安装后补齐关键运行依赖（缺失则自动安装）。"""
    deps = [
        ("PyPDF2", "PyPDF2"),
        ("pdfplumber", "pdfplumber"),
        ("PyMuPDF", "fitz"),
        ("chromadb", "chromadb"),
        ("sentence-transformers", "sentence_transformers"),
    ]

    missing = [pkg for pkg, module in deps if not _module_available(module)]
    if _module_available("chromadb") and not _is_chromadb_compatible():
        missing.append("chromadb<0.5")
    if _module_available("chromadb") and not _is_numpy_compatible_for_chromadb():
        missing.append("numpy<2")
    if not missing:
        print("✅ 关键运行依赖检查通过")
        return True

    missing = list(dict.fromkeys(missing))
    print(f"\n📦 检测到缺失运行依赖，正在安装: {', '.join(missing)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    except subprocess.CalledProcessError as e:
        print(f"❌ 关键运行依赖安装失败: {e}")
        return False

    still_missing = [pkg for pkg, module in deps if not _module_available(module)]
    if still_missing:
        print("❌ 安装后仍缺失依赖: " + ", ".join(still_missing))
        return False

    print("✅ 关键运行依赖安装完成")
    return True


def update_lumina():
    """更新 Lumina"""
    print("\n🔄 检查更新...")
    install_dir = get_install_dir()
    
    # 检查是否是 git 仓库
    git_dir = install_dir / ".git"
    if not git_dir.exists():
        print("❌ 不是 git 仓库，无法自动更新")
        print("   建议重新克隆仓库:")
        print("   git clone https://github.com/chenboripple/Lumina.git")
        return False
    
    try:
        # 拉取最新代码
        print("📥 拉取最新代码...")
        subprocess.check_call(
            ["git", "pull", "origin", "release-ripple"],
            cwd=install_dir
        )
        
        # 重新安装
        print("📦 重新安装...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-e", "."
        ], cwd=install_dir)
        
        print("✅ 更新完成!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 更新失败: {e}")
        return False


def check_version():
    """检查当前版本"""
    try:
        import lumina
        print(f"当前版本: {lumina.__version__}")
        
        # 检查最新版本（通过 git）
        install_dir = get_install_dir()
        if (install_dir / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=install_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                current_commit = result.stdout.strip()[:7]
                print(f"当前 commit: {current_commit}")
                
                # 获取远程最新 commit
                subprocess.run(
                    ["git", "fetch", "origin", "release-ripple"],
                    cwd=install_dir,
                    capture_output=True
                )
                result = subprocess.run(
                    ["git", "rev-parse", "origin/release-ripple"],
                    cwd=install_dir,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    remote_commit = result.stdout.strip()[:7]
                    print(f"远程最新: {remote_commit}")
                    
                    if current_commit != remote_commit:
                        print("⚠️  有新版本可用，运行 `python install.py --update` 更新")
                    else:
                        print("✅ 已是最新版本")
                        
    except ImportError:
        print("❌ Lumina 未安装")


def uninstall_lumina(remove_config: bool = False):
    """卸载 Lumina"""
    print("\n🗑️  卸载 Lumina...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "uninstall", "-y", "lumina"
        ])
        print("✅ Lumina 已卸载")

        config_file = Path.home() / ".lumina" / "lumina.yaml"
        if remove_config and config_file.exists():
            config_file.unlink()
            print(f"✅ 已删除配置文件: {config_file}")
        elif config_file.exists():
            print(f"ℹ️  保留用户配置: {config_file}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 卸载失败: {e}")
        return False


def create_config():
    """创建空白用户配置文件 ~/.lumina/lumina.yaml"""
    config_file = Path.home() / ".lumina" / "lumina.yaml"
    
    if config_file.exists():
        print(f"⚠️  配置文件已存在: {config_file}")
        return True

    print("\n⚙️  创建空白配置文件...")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    # 空白 YAML 文件，实际字段由用户按需填写。
    config_file.write_text("", encoding='utf-8')
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
    parser = argparse.ArgumentParser(description="Lumina 安装工具")
    parser.add_argument("--update", action="store_true", help="更新到最新版本")
    parser.add_argument("--version", action="store_true", help="检查版本")
    parser.add_argument("--uninstall", action="store_true", help="卸载 Lumina")
    parser.add_argument("--remove-config", action="store_true", help="卸载时删除 ~/.lumina/lumina.yaml")
    args = parser.parse_args()
    
    if args.version:
        check_version()
        return
    
    if args.update:
        print_banner()
        update_lumina()
        return

    if args.uninstall:
        print_banner()
        if not uninstall_lumina(remove_config=args.remove_config):
            sys.exit(1)
        return
    
    # 默认：安装
    print_banner()
    
    print(f"\n🔍 系统信息:")
    print(f"   平台: {platform.system()} {platform.release()}")
    print(f"   架构: {platform.machine()}")
    
    if not check_python():
        sys.exit(1)
    
    if not install_dependencies():
        sys.exit(1)

    if not ensure_runtime_dependencies():
        sys.exit(1)
    
    create_config()
    setup_shell_completion()
    
    print("\n" + "="*50)
    print("🎉 Lumina 安装完成!")
    print("="*50)
    print("\n快速开始:")
    print("   lumina serve")
    print("\n配置文件:")
    print(f"   {Path.home() / '.lumina' / 'lumina.yaml'}")
    print("\n更新命令:")
    print("   python install.py --update")
    print("\n卸载命令:")
    print("   python install.py --uninstall")
    print("\n更多帮助:")
    print("   lumina --help")
    print()


if __name__ == "__main__":
    main()