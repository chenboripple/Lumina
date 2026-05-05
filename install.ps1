# Lumina 一键安装脚本 (Windows)
# 使用方法: irm https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.ps1 | iex
# 或本地运行: .\install.ps1

$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-Step($msg) { Write-Host "`n➜ $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warning($msg) { Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Error($msg) { Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "ℹ $msg" -ForegroundColor Blue }
function Write-Star($msg) { Write-Host "★ $msg" -ForegroundColor Yellow }

# 打印标题
function Write-Header {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  ✨ Lumina - 智能知识萃取 Agent                               ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

# 打印完成
function Write-Complete {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  ✅ Lumina 安装完成!                                          ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "快速开始:"
    Write-Host "  lumina start        - 启动后台服务"
    Write-Host "  lumina process      - 处理文件"
    Write-Host "  lumina serve        - 前台启动 Web 界面"
    Write-Host "  lumina --help       - 查看帮助"
    Write-Host ""
    Write-Host "访问 Web 界面:"
    Write-Host "  http://127.0.0.1:5088"
    Write-Host ""
}

# 检查 Python
function Test-Python {
    Write-Step "检查 Python 版本..."

    $pythonCmd = $null
    foreach ($cmd in @("python3", "python")) {
        try {
            $version = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pythonCmd = $cmd
                break
            }
        } catch {
            continue
        }
    }

    if (-not $pythonCmd) {
        Write-Error "未找到 Python"
        Write-Host "  请从 https://www.python.org/downloads/ 下载并安装 Python 3.8+"
        return $false
    }

    try {
        $versionInfo = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
        $major, $minor = $versionInfo -split '\.' | ForEach-Object { [int]$_ }

        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 8)) {
            Write-Error "Python 版本过低: $versionInfo (需要 3.8+)"
            Write-Host "  请从 https://www.python.org/downloads/ 下载并安装 Python 3.8+"
            return $false
        }

        Write-Success "Python $versionInfo 可用"
        Set-Variable -Name "PYTHON_CMD" -Value $pythonCmd -Scope Script
        return $true
    } catch {
        Write-Error "检查 Python 版本失败"
        return $false
    }
}

# 检查 pip
function Test-Pip {
    Write-Step "检查 pip..."

    try {
        & $PYTHON_CMD -m pip --version | Out-Null
        Write-Success "pip 可用"
        return $true
    } catch {
        Write-Error "pip 不可用"
        Write-Host "  请尝试: $PYTHON_CMD -m ensurepip --upgrade"
        return $false
    }
}

# 安装 Lumina
function Install-Lumina {
    Write-Step "安装 Lumina..."

    # 检查是否在 git 仓库根目录中
    $inRepo = (Test-Path "pyproject.toml") -and (Test-Path "src/lumina/cli.py") -and (Test-Path ".git")

    if ($inRepo) {
        Write-Info "检测到在 Lumina 仓库中，使用开发模式安装"
        & $PYTHON_CMD -m pip install -e .
    } else {
        Write-Info "从 GitHub 安装..."
        $repoUrl = "https://github.com/chenboripple/Lumina.git"
        & $PYTHON_CMD -m pip install "git+$repoUrl@release-ripple"
    }

    # 验证安装
    try {
        lumina --help | Out-Null
        Write-Success "Lumina 安装成功"
        return $true
    } catch {
        try {
            & $PYTHON_CMD -m lumina --help | Out-Null
            Write-Success "Lumina 安装成功 (使用 python -m lumina)"
            return $true
        } catch {
            Write-Warning "Lumina 安装可能失败，请尝试手动安装"
            return $false
        }
    }
}

# 检查 Ollama
function Test-Ollama {
    Write-Step "检测 Ollama..."

    try {
        $ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaPath) {
            Write-Success "Ollama 已安装"
            return $true
        }
    } catch {}

    Write-Info "未检测到 Ollama"
    return $false
}

# 安装 Ollama
function Install-Ollama {
    Write-Host ""
    Write-Star "Ollama 是本地模型运行工具，无需 API Key 即可使用 LLM"
    Write-Star "建议安装 Ollama 以获得最佳体验"
    Write-Host ""

    $response = Read-Host "是否安装 Ollama? [Y/n]"
    if ($response -match "^[Nn]") {
        return $false
    }

    Write-Host ""
    Write-Step "正在安装 Ollama..."

    # Windows 上 Ollama 官方推荐手动下载
    Write-Host ""
    Write-Info "Windows 上推荐手动安装 Ollama:"
    Write-Host "  1. 访问 https://ollama.com/download"
    Write-Host "  2. 下载 Windows 版本"
    Write-Host "  3. 运行安装程序"
    Write-Host ""
    Write-Info "安装完成后，运行: ollama pull llama3"
    Write-Host ""

    $continue = Read-Host "是否已了解? [Y]"
    return $true
}

# 启动 Ollama 并拉取模型
function Setup-OllamaModel {
    Write-Step "设置 Ollama 模型..."

    # 检查 Ollama 是否在运行
    $ollamaRunning = $false
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
        $ollamaRunning = ($response.StatusCode -eq 200)
    } catch {}

    if (-not $ollamaRunning) {
        Write-Host "  启动 Ollama 服务..."
        try {
            Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
            Start-Sleep -Seconds 3
        } catch {
            Write-Warning "启动 Ollama 失败，请手动启动 Ollama"
        }
    }

    # 检查是否已有 llama3 模型
    $hasModel = $false
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing
        if ($response.Content -match "llama3") {
            $hasModel = $true
        }
    } catch {}

    if ($hasModel) {
        Write-Success "llama3 模型已存在"
    } else {
        Write-Host "  拉取 llama3 模型..."
        try {
            ollama pull llama3
        } catch {
            Write-Warning "拉取模型失败，请稍后手动运行: ollama pull llama3"
        }
    }

    Write-Success "Ollama 准备就绪"
}

# 运行 lumina init
function Run-Init {
    Write-Step "运行 Lumina 配置向导..."
    Write-Host ""

    try {
        lumina init
    } catch {
        & $PYTHON_CMD -m lumina init
    }
}

# 主函数
function Main {
    Write-Header

    # 检查 Python
    if (-not (Test-Python)) {
        exit 1
    }

    # 检查 pip
    if (-not (Test-Pip)) {
        exit 1
    }

    # 安装 Lumina
    Install-Lumina

    # 检查并可选安装 Ollama
    if (-not (Test-Ollama)) {
        if (Install-Ollama) {
            # 用户确认了解后不自动 setup，等待他们安装完成
        }
    } else {
        Setup-OllamaModel
    }

    # 运行配置向导
    Run-Init

    # 完成
    Write-Complete
}

# 运行主函数
Main
