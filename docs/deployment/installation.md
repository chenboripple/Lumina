# Lumina 安装指南

## 快速安装

### macOS / Linux (推荐)

```bash
curl -fsSL https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.sh | bash
```

一键脚本会自动:
- ✅ 检查 Python 3.8+
- ✅ 安装 Lumina
- ✅ 可选安装 Ollama (本地模型)
- ✅ 运行 `lumina init` 交互式配置

### Windows (推荐)

在 PowerShell 中运行:

```powershell
irm https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.ps1 | iex
```

PowerShell 脚本会自动:
- ✅ 检查 Python 3.8+
- ✅ 安装 Lumina
- ✅ 提示安装 Ollama
- ✅ 运行 `lumina init` 交互式配置

## 使用 lumina init 配置

安装后，运行 `lumina init` 进入交互式配置向导:

```bash
lumina init
```

配置向导会帮你:
1. 📁 选择输入源目录
2. 📁 选择输出目录
3. 🎨 选择输出格式（Obsidian / Notion / Plain Markdown）
4. 🤖 自动检测可用的 LLM Provider
5. ✅ 生成最小可用的 `~/.lumina/lumina.yaml`

**自动检测:**
- 环境变量: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, `VOLCENGINE_API_KEY`, `MOONSHOT_API_KEY`, `ZHIPU_API_KEY`, `ANTHROPIC_API_KEY`
- 本地 Ollama (http://localhost:11434)

## 手动安装

### 方式 A: git clone + python install.py

```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py
```

### 方式 B: pip install

```bash
pip install "git+https://github.com/chenboripple/Lumina.git@release-ripple"
```

### 方式 C: 开发安装

```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
pip install -e ".[dev]"
```

## 系统要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows 10/11、macOS 10.15+、Linux

## 配置

### 使用环境变量 (推荐)

你可以通过环境变量设置 API Key，无需写入配置文件:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# DeepSeek
export DEEPSEEK_API_KEY="sk-..."

# 百炼 / Qwen
export DASHSCOPE_API_KEY="sk-..."

# 火山引擎
export VOLCENGINE_API_KEY="..."

# Kimi
export MOONSHOT_API_KEY="sk-..."

# 智谱 GLM
export ZHIPU_API_KEY="..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 手动编辑配置文件

配置文件位于: `~/.lumina/lumina.yaml`

```yaml
input:
  sources:
    - path: ~/Documents
      recursive: true
  default_recursive: true

output:
  plugin: obsidian
  base_dir: ~/Lumina/Notes

llm:
  provider: ollama    # openai | anthropic | deepseek | bailian | volcengine | kimi | glm | llamacpp
  model: llama3
  # api_key: xxx      # 可选，推荐使用环境变量

harness:
  max_iterations: 3
  quality_threshold: 0.8
```

详细配置文档见 [config-reference.md](config-reference.md)。

## 验证安装

```bash
# 查看版本和帮助
lumina --version
lumina --help

# 运行配置向导
lumina init

# 快速测试
lumina process /path/to/some/documents
```

## Ollama (本地模型)

如果你希望使用本地模型（不依赖云服务），推荐安装 Ollama:

### 安装 Ollama

- **macOS**: `brew install ollama` 或从 https://ollama.com 下载
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`
- **Windows**: 从 https://ollama.com/download 下载

### 拉取模型

```bash
ollama pull llama3
```

### 使用 Ollama

在 `~/.lumina/lumina.yaml` 中配置:

```yaml
llm:
  provider: ollama
  model: llama3
```

## 快速开始

```bash
# 后台启动常驻服务 (推荐)
lumina start

# 查看状态
lumina status

# 停止后台服务
lumina stop

# 默认打开 Web 管理界面
# http://127.0.0.1:5088

# 前台调试模式 (保留)
lumina serve

# 一次性处理任务 (可选)
lumina process
```

后台模式会自动管理:
- PID 文件: `~/.lumina/service.pid`
- 日志文件: `~/.lumina/service-YYYY-MM-DD.log`
- 元数据: `~/.lumina/service.json`

日志默认只保留最近 15 天。可在 `~/.lumina/lumina.yaml` 中配置:

```yaml
service:
   log_retention_days: 30
```

## 更新

### 使用安装脚本 (推荐)

```bash
# 重新运行一键脚本
curl -fsSL https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.sh | bash
```

### 手动更新

```bash
cd Lumina
git pull origin release-ripple
pip install -e .
```

## 卸载

```bash
# 方式 1: pip
pip uninstall lumina

# 可选: 删除配置
rm -rf ~/.lumina
```

## 故障排除

### 安装失败

1. **检查 Python 版本**
   ```bash
   python --version  # 需要 3.8+
   ```

2. **升级 pip**
   ```bash
   python -m pip install --upgrade pip
   ```

3. **使用虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或 .\venv\Scripts\activate  # Windows
   pip install lumina
   ```

### lumina init 报错

如果 `lumina init` 命令找不到，尝试:

```bash
python -m lumina init
```

或者确保 pip 安装的脚本在 PATH 中:

```bash
# 查看安装位置
pip show lumina | grep Location
# 检查该位置下的 bin/Scripts 目录是否在 PATH
```

### Ollama 连接失败

确保 Ollama 服务正在运行:

```bash
ollama serve
```

然后测试 API:

```bash
curl http://localhost:11434/api/tags
```

### API Key 问题

- 确保已设置环境变量或在配置文件中写入 `api_key`
- 检查 API Key 是否有效且有额度
- 确认 `base_url` 是否正确（如果使用代理）

## 获取帮助

- GitHub Issues: https://github.com/chenboripple/Lumina/issues
- 文档: https://github.com/chenboripple/Lumina#readme
