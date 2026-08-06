#!/usr/bin/env bash
# Lumina 一键安装/更新脚本 (macOS/Linux)
# 支持通过 curl | bash 直接运行
#
# 用法:
#   curl -fsSL <raw_url>/install.sh | bash        # 未安装则安装; 已安装则交互式更新
#   bash install.sh --update                      # 静默更新到云端最新版 (适合 cron)
#   bash install.sh --yes                         # 所有交互问题默认选"是"
#   bash install.sh --branch <branch>             # 指定分支 (默认 release)

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

# 仓库配置
REPO_URL="https://github.com/chenboripple/Lumina.git"
INSTALL_BRANCH="${LUMINA_BRANCH:-release}"    # 安装/更新使用的分支
FORCE_UPDATE="${LUMINA_FORCE_UPDATE:-0}"      # 1 = 静默更新, 不询问 (--update)
ASSUME_YES="${LUMINA_ASSUME_YES:-0}"          # 1 = 所有交互问题默认"是" (--yes)

# 打印用法
usage() {
    cat <<'EOF'
Lumina 一键安装/更新脚本

选项:
  -u, --update          静默更新到云端最新版本 (跳过交互询问)
  -y, --yes             所有交互问题默认回答"是"
      --branch <name>   指定安装分支 (默认: release)
  -h, --help            显示帮助

环境变量:
  LUMINA_BRANCH        等效于 --branch
  LUMINA_FORCE_UPDATE  等效于 --update
  LUMINA_ASSUME_YES    等效于 --yes
EOF
}

# 解析命令行参数
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --update|-u) FORCE_UPDATE=1 ;;
            --yes|-y)    ASSUME_YES=1 ;;
            --branch)
                if [ -z "${2:-}" ]; then
                    echo "${CROSS} --branch 需要指定分支名" >&2
                    exit 1
                fi
                INSTALL_BRANCH="$2"
                shift
                ;;
            -h|--help) usage; exit 0 ;;
            *) echo "${CROSS} 未知参数: $1 (使用 --help 查看用法)" >&2; exit 1 ;;
        esac
        shift
    done
}

# 安全的交互式确认 (兼容 curl | bash 场景, stdin 被脚本占用时回退到 /dev/tty)
# $1=提示语  $2=默认值 (Y 或 n)  返回 0=是 1=否
ask_yes_no() {
    local prompt="$1" default="${2:-Y}" REPLY=""
    if [ -t 0 ]; then
        read -r -p "$prompt" REPLY || REPLY=""
    elif [ -e /dev/tty ]; then
        REPLY=$(read -r -p "$prompt" </dev/tty 2>/dev/null && echo "$REPLY") || REPLY=""
    fi
    [ -z "$REPLY" ] && REPLY="$default"
    [[ ! $REPLY =~ ^[Nn]$ ]]
}

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

# 检查 git
check_git() {
    if ! command -v git >/dev/null 2>&1; then
        echo "${CROSS} 未找到 git, 请先安装 (如: brew install git / apt-get install git)"
        return 1
    fi
    return 0
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

# 获取已安装 Lumina 的调用方式; 未安装时返回空
get_installed_lumina_cmd() {
    if command -v lumina >/dev/null 2>&1; then
        echo "lumina"
    elif [ -n "${PYTHON_CMD:-}" ] && $PYTHON_CMD -m lumina --help >/dev/null 2>&1; then
        echo "$PYTHON_CMD -m lumina"
    else
        echo ""
    fi
}

# 本地已安装版本 (尽力获取, 失败返回空)
get_local_version() {
    local cmd="$1"
    [ -z "$cmd" ] && return 0
    $cmd --version 2>/dev/null | head -1 || true
}

# 云端分支最新提交短 hash (无需 clone)
get_remote_commit() {
    git ls-remote "$REPO_URL" "refs/heads/$INSTALL_BRANCH" 2>/dev/null | cut -c1-7 || true
}

# 若当前目录就是 Lumina git 仓库 (开发模式安装), 输出其路径
get_dev_repo_path() {
    if [ -f "pyproject.toml" ] && [ -f "src/lumina/cli.py" ] && [ -d ".git" ]; then
        pwd
    else
        echo ""
    fi
}

# 从云端更新已安装的 Lumina
# $1 = 开发模式仓库路径 (可为空)
update_lumina() {
    local repo_path="${1:-}"
    if [ -n "$repo_path" ]; then
        echo "  检测到开发模式安装 ($repo_path), 拉取最新代码..."
        (cd "$repo_path" && git pull --ff-only)
        $PYTHON_CMD -m pip install -e "$repo_path"
    else
        echo "  从云端安装最新版本 (分支: $INSTALL_BRANCH)..."
        $PYTHON_CMD -m pip install --upgrade --force-reinstall "git+$REPO_URL@$INSTALL_BRANCH"
    fi
}

# 安装 Lumina (自动检测已有安装并提供更新)
# $1 = 已检测到的 lumina 调用方式 (可为空)
install_lumina() {
    local existing_cmd="${1:-}"
    echo ""
    echo "${ARROW} 安装 Lumina..."

    if [ -n "$existing_cmd" ]; then
        # ---- 已安装: 更新流程 ----
        local local_ver remote_commit dev_repo
        local_ver=$(get_local_version "$existing_cmd")
        remote_commit=$(get_remote_commit)
        dev_repo=$(get_dev_repo_path)

        echo "${INFO} 检测到本机已安装 Lumina"
        [ -n "$local_ver" ]     && echo "  本地版本: $local_ver"
        [ -n "$remote_commit" ] && echo "  云端最新: $INSTALL_BRANCH @ $remote_commit"
        echo ""

        if [ "$FORCE_UPDATE" = "1" ] || [ "$ASSUME_YES" = "1" ]; then
            update_lumina "$dev_repo"
        elif ask_yes_no "是否更新到云端最新版本? [Y/n] " "Y"; then
            update_lumina "$dev_repo"
        else
            echo "${INFO} 跳过更新"
            return 0
        fi
    else
        # ---- 未安装: 全新安装流程 ----
        if [ -f "pyproject.toml" ] && [ -f "src/lumina/cli.py" ] && [ -d ".git" ]; then
            echo "${INFO} 检测到在 Lumina 仓库中, 使用开发模式安装"
            $PYTHON_CMD -m pip install -e .
        else
            echo "${INFO} 从 GitHub 克隆并安装 (分支: $INSTALL_BRANCH)..."
            TEMP_DIR=$(mktemp -d)

            echo "  克隆仓库..."
            if git clone --depth 1 --branch "$INSTALL_BRANCH" "$REPO_URL" "$TEMP_DIR" 2>/dev/null; then
                cd "$TEMP_DIR"
                $PYTHON_CMD -m pip install .
                cd - >/dev/null
                rm -rf "$TEMP_DIR"
            else
                echo "${YELLOW}  克隆失败, 尝试直接从 pip 安装"
                $PYTHON_CMD -m pip install "git+$REPO_URL@$INSTALL_BRANCH"
            fi
        fi
    fi

    if command -v lumina >/dev/null 2>&1; then
        local ver
        ver=$(lumina --version 2>/dev/null || true)
        echo "${CHECK} Lumina 就绪${ver:+ ($ver)}"
        return 0
    elif $PYTHON_CMD -m lumina --help >/dev/null 2>&1; then
        echo "${CHECK} Lumina 就绪 (使用 python -m lumina)"
        return 0
    else
        echo "${CROSS} Lumina 安装可能失败, 请尝试手动安装"
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

    if [ "$ASSUME_YES" = "1" ] || ask_yes_no "是否安装 Ollama? [Y/n] " "Y"; then
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

# 更新完成
print_update_complete() {
    local ver=""
    if command -v lumina >/dev/null 2>&1; then
        ver=$(lumina --version 2>/dev/null || true)
    fi
    echo ""
    echo "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo "${BOLD}${GREEN}║${RESET}  ${BOLD}✅ Lumina 已更新到云端最新版本!${RESET}                             ${BOLD}${GREEN}║${RESET}"
    echo "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
    [ -n "$ver" ] && echo "  当前版本: $ver"
    echo ""
}

# 主函数
main() {
    parse_args "$@"
    print_header

    # 检查 git (克隆/更新都依赖)
    if ! check_git; then
        exit 1
    fi

    # 检查 Python
    if ! check_python; then
        exit 1
    fi

    # 检查 pip
    if ! check_pip; then
        exit 1
    fi

    # 检测已有安装
    local EXISTING_CMD
    EXISTING_CMD=$(get_installed_lumina_cmd)

    # 安装 / 更新 Lumina
    install_lumina "$EXISTING_CMD"

    # 静默更新模式: 更新完成即结束, 不再走 Ollama/init 流程
    if [ -n "$EXISTING_CMD" ] && [ "$FORCE_UPDATE" = "1" ]; then
        print_update_complete
        exit 0
    fi

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
