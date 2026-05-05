#!/usr/bin/env bash
# Lumina 一键安装脚本 (macOS/Linux)
# 支持通过 curl | bash 直接运行

set -e

# 颜色输出
if command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1 2>/dev/null || true)
    GREEN=$(tput setaf 2 2>/dev/null || true)
    YELLOW=$(tput setaf 3 2>/dev/null || true)
    BLUE=$(tput setaf 4 2>/dev/null || true)
    BOLD=$(tput bold 2>/dev/null || true)
    RESET=$(tput sgr0 2>/dev/null || true)
else
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    BOLD=""
    RESET=""
fi

# 符号
CHECK="${GREEN}✓${RESET}"
CROSS="${RED}✗${RESET}"
ARROW="${BLUE}➜${RESET}"
INFO="${BLUE}ℹ${RESET}"
STAR="${YELLOW}★${RESET}"

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)  echo "linux" ;;
        *)      echo "unknown" ;;
    esac
}

# 检测包管理器
detect_package_manager() {
    if command -v brew >/dev/null 2>&1; then
        echo "brew"
    elif command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v yum >/dev/null 2>&1; then
        echo "yum"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

# 打印标题
print_header() {
    echo ""
    echo "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo "${BOLD}${BLUE}║${RESET}  ${BOLD}✨ Lumina - 智能知识萃取 Agent${RESET}                              ${BOLD}${BLUE}║${RESET}"
    echo "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

# 检查 Python
check_python() {
    echo "${ARROW} 检查 Python 版本..."

    # 寻找可用的 Python
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD=python
    else
        echo "${CROSS} 未找到 Python"
        return 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>/dev/null || true)
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        echo "${CROSS} Python 版本过低: $PYTHON_VERSION (需要 3.8+)"
        echo "  请安装 Python 3.8 或更高版本:"
        OS=$(detect_os)
        if [ "$OS" = "macos" ]; then
            echo "    brew install python3"
        else
            echo "    sudo apt-get install python3 python3-pip"
        fi
        return 1
    fi

    echo "${CHECK} Python $PYTHON_VERSION 可用"
    export PYTHON_CMD
    return 0
}

# 检查 pip
check_pip() {
    echo "${ARROW} 检查 pip..."

    if ! $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
        echo "${CROSS} pip 不可用"
        echo "  请先安装 pip:"
        echo "    $PYTHON_CMD -m ensurepip --upgrade"
        return 1
    fi

    echo "${CHECK} pip 可用"
    return 0
}

# 安装 Lumina
install_lumina() {
    echo ""
    echo "${ARROW} 安装 Lumina..."

    # 检查是否在 git 仓库根目录中
    if [ -f "pyproject.toml" ] && [ -f "src/lumina/cli.py" ] && [ -d ".git" ]; then
        echo "${INFO} 检测到在 Lumina 仓库中，使用开发模式安装"
        $PYTHON_CMD -m pip install -e .
    else
        echo "${INFO} 从 GitHub 克隆并安装..."
        REPO_URL="https://github.com/chenboripple/Lumina.git"
        TEMP_DIR=$(mktemp -d)

        echo "  克隆仓库..."
        if git clone --depth 1 --branch release-ripple "$REPO_URL" "$TEMP_DIR" 2>/dev/null; then
            cd "$TEMP_DIR"
            $PYTHON_CMD -m pip install .
            cd - >/dev/null
            rm -rf "$TEMP_DIR"
        else
            echo "${YELLOW}  克隆失败，尝试直接从 pip 安装"
            $PYTHON_CMD -m pip install "git+$REPO_URL@release-ripple"
        fi
    fi

    if command -v lumina >/dev/null 2>&1; then
        echo "${CHECK} Lumina 安装成功"
        return 0
    elif $PYTHON_CMD -m lumina --help >/dev/null 2>&1; then
        echo "${CHECK} Lumina 安装成功 (使用 python -m lumina)"
        return 0
    else
        echo "${CROSS} Lumina 安装可能失败，请尝试手动安装"
        return 1
    fi
}

# 检查 Ollama
check_ollama() {
    echo ""
    echo "${ARROW} 检测 Ollama..."

    if command -v ollama >/dev/null 2>&1; then
        echo "${CHECK} Ollama 已安装"
        return 0
    fi

    echo "${INFO} 未检测到 Ollama"
    return 1
}

# 安装 Ollama
install_ollama() {
    OS=$(detect_os)
    PKG_MANAGER=$(detect_package_manager)

    echo ""
    echo "${STAR} Ollama 是本地模型运行工具，无需 API Key 即可使用 LLM"
    echo "${STAR} 建议安装 Ollama 以获得最佳体验"
    echo ""

    read -p "是否安装 Ollama? [Y/n] " -r
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        echo "${ARROW} 正在安装 Ollama..."

        if [ "$OS" = "macos" ]; then
            if [ "$PKG_MANAGER" = "brew" ]; then
                echo "  使用 Homebrew 安装..."
                brew install ollama
            else
                echo "  请手动从 https://ollama.com 下载安装"
                return 1
            fi
        else
            echo "  使用官方脚本安装..."
            curl -fsSL https://ollama.com/install.sh | sh
        fi

        echo "${CHECK} Ollama 安装完成"
        return 0
    fi

    return 1
}

# 启动 Ollama 并拉取模型
setup_ollama_model() {
    echo ""
    echo "${ARROW} 设置 Ollama 模型..."

    # 检查 Ollama 是否在运行
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "  启动 Ollama 服务..."
        if [ "$(detect_os)" = "macos" ]; then
            open -a Ollama 2>/dev/null || true
        fi
        # 后台启动 ollama serve
        ollama serve >/dev/null 2>&1 &
        OLLAMA_PID=$!

        # 等待服务启动
        for _ in {1..30}; do
            if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi

    # 检查是否已有 llama3 模型
    if curl -s http://localhost:11434/api/tags | grep -q "llama3"; then
        echo "${CHECK} llama3 模型已存在"
    else
        echo "  拉取 llama3 模型..."
        ollama pull llama3 || echo "${YELLOW}  拉取模型失败，请稍后手动运行: ollama pull llama3"
    fi

    echo "${CHECK} Ollama 准备就绪"
    return 0
}

# 运行 lumina init
run_init() {
    echo ""
    echo "${ARROW} 运行 Lumina 配置向导..."
    echo ""

    if command -v lumina >/dev/null 2>&1; then
        lumina init
    else
        $PYTHON_CMD -m lumina init
    fi
}

# 完成
print_complete() {
    echo ""
    echo "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo "${BOLD}${GREEN}║${RESET}  ${BOLD}✅ Lumina 安装完成!${RESET}                                         ${BOLD}${GREEN}║${RESET}"
    echo "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo "快速开始:"
    echo "  ${BOLD}lumina start${RESET}        - 启动后台服务"
    echo "  ${BOLD}lumina process${RESET}      - 处理文件"
    echo "  ${BOLD}lumina serve${RESET}        - 前台启动 Web 界面"
    echo "  ${BOLD}lumina --help${RESET}       - 查看帮助"
    echo ""
    echo "访问 Web 界面:"
    echo "  http://127.0.0.1:5088"
    echo ""
}

# 主函数
main() {
    print_header

    # 检查 Python
    if ! check_python; then
        exit 1
    fi

    # 检查 pip
    if ! check_pip; then
        exit 1
    fi

    # 安装 Lumina
    install_lumina

    # 检查并可选安装 Ollama
    if ! check_ollama; then
        if install_ollama; then
            setup_ollama_model
        fi
    else
        setup_ollama_model
    fi

    # 运行配置向导
    run_init

    # 完成
    print_complete
}

# 运行主函数
main "$@"
