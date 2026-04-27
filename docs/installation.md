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

安装脚本会自动检查 `~/.lumina/lumina.yaml`：
- 如果不存在：自动创建一个空白 YAML 文件
- 如果已存在：保持原文件不覆盖

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

安装完成后，在主目录创建配置文件 `~/.lumina/lumina.yaml`（Windows 用户为 `%USERPROFILE%\.lumina\lumina.yaml`）。

### 配置 LLM

Lumina 通过 `~/.lumina/lumina.yaml` 管理所有配置，**不读取环境变量**，api_key 需在配置文件中显式填写。

创建 `~/.lumina/lumina.yaml`：

```yaml
llm:
  provider: openai
  api_key: "sk-..."   # 必填
  model: gpt-4
```

完整配置字段和说明见 [docs/lumina-yaml-demo.md](lumina-yaml-demo.md)。

## 验证安装

```bash
lumina --version
lumina --help
```

## 快速开始

```bash
# 后台启动常驻服务（推荐）
lumina start

# 查看状态
lumina status

# 停止后台服务
lumina stop

# 默认打开 Web 管理界面
# http://127.0.0.1:5088

# 前台调试模式（保留）
lumina serve

# 一次性处理任务（可选）
lumina process
```

后台模式会自动管理：

- PID 文件: `~/.lumina/service.pid`
- 日志文件: `~/.lumina/service-YYYY-MM-DD.log`
- 元数据: `~/.lumina/service.json`

日志默认只保留最近 15 天。可在 `~/.lumina/lumina.yaml` 中配置：

```yaml
service:
   log_retention_days: 30
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
# 方式 1：通过安装脚本卸载
python install.py --uninstall

# 可选：卸载时同时删除 ~/.lumina/lumina.yaml
python install.py --uninstall --remove-config

# 方式 2：使用 pip
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

- 确保已在 `~/.lumina/lumina.yaml` 中填写 `llm.api_key`
- 检查 Key 是否有额度
- 确认 `base_url` 是否正确（如果使用代理）

## 获取帮助

- GitHub Issues: https://github.com/chenboripple/Lumina/issues
- 文档: https://github.com/chenboripple/Lumina#readme