# Lumina 安装指南

## 系统要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows 10/11、macOS 10.15+、Linux

## 安装方式

### 方式 1：使用安装脚本（推荐）

**macOS / Linux:**
```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py
```

**Windows:**
```powershell
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py
```

### 方式 2：使用 pip

```bash
pip install lumina
```

### 方式 3：开发安装

```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
pip install -e ".[dev]"
```

## 配置

### 首次使用

安装后会在用户目录创建配置文件：

- **macOS/Linux**: `~/.lumina/config.yaml`
- **Windows**: `%USERPROFILE%\.lumina\config.yaml`

### 配置 LLM

**方式 1：环境变量（推荐）**

```bash
# macOS/Linux
export OPENAI_API_KEY="your-api-key"

# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key"
```

**方式 2：配置文件**

编辑 `~/.lumina/config.yaml`：

```yaml
llm:
  provider: "openai"
  api_key: "your-api-key"
  model: "gpt-4"
```

## 验证安装

```bash
lumina --version
lumina --help
```

## 快速开始

```bash
# 扫描目录并生成笔记
lumina scan ~/Documents --output ./notes

# 使用配置文件运行
lumina config ~/.lumina/config.yaml
```

## 跨平台注意事项

### Windows
- 路径使用反斜杠或正斜杠均可
- PowerShell 支持最佳

### macOS
- 需要 Xcode Command Line Tools（部分依赖）
- 推荐使用 Homebrew 安装 Python

### Linux
- 可能需要安装 `python3-dev` 包
- Ubuntu/Debian: `sudo apt-get install python3-dev`

## 更新

### 使用 install.py 更新（推荐）

```bash
# 进入 Lumina 目录
cd Lumina

# 检查版本
python install.py --version

# 更新到最新
python install.py --update
```

### 使用 pip 更新

```bash
pip install --upgrade lumina
```

### 手动更新

```bash
cd Lumina
git pull origin release-ripple
pip install -e ".[dev]"
```

## 卸载

```bash
pip uninstall lumina
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
   # 或 venv\Scripts\activate  # Windows
   pip install lumina
   ```

### API Key 问题

- 确保设置了 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`
- 检查 Key 是否有额度
- 确认 base_url 是否正确（如果使用代理）

## 获取帮助

- GitHub Issues: https://github.com/chenboripple/Lumina/issues
- 文档: https://github.com/chenboripple/Lumina#readme