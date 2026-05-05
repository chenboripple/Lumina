# Lumina

> 🌟 用 AI 自动整理你的本地文件，轻松生成结构化知识笔记

---

## ✨ 核心价值

Lumina 帮你：

- **📁 自动整理**：把散落的文档、笔记、邮件、会议记录转换成结构化的知识笔记
- **🤖 AI 驱动**：支持本地模型 (Ollama/llama.cpp) 或云端 API (OpenAI/Anthropic/DeepSeek/国内大模型)
- **🔗 双向链接**：自动识别文件关系，生成 Obsidian 风格的笔记
- **🎯 场景感知**：自动识别会议纪要、学术论文、PRD、邮件、聊天记录等
- **⚡ 增量更新**：只重新处理变化的文件
- **🌐 Web 界面**：可视化查看进度、搜索、管理知识图谱

---

## 🚀 快速开始

### 一键安装 (推荐)

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.ps1 | iex
```

安装脚本会自动：
- ✅ 检查 Python 3.8+
- ✅ 安装 Lumina
- ✅ 可选安装 Ollama (本地模型，无需 API Key)
- ✅ 运行 `lumina init` 交互式配置

### 配置 & 运行

```bash
# 1. 交互式配置向导
lumina init

# 2. 后台启动常驻服务
lumina start

# 3. 打开 Web 界面 (浏览器会自动打开)
# http://127.0.0.1:5088

# 4. 立即处理目录
lumina process ~/Documents
```

### 常用命令

```bash
# 后台服务
lumina start    # 启动
lumina status   # 查看状态
lumina stop     # 停止

# 一次性处理
lumina process ~/Documents

# 向量搜索
lumina search "关键词"
lumina related "某篇笔记"

# 查看帮助
lumina --help
```

---

## 🌟 主要功能

### 📄 文件处理

- **批量扫描**：自动识别知识文件
- **📊 智能筛选**：过滤低价值文件、去重、敏感信息脱敏
- **📝 自动摘要**：自动生成标题、摘要、标签
- **🔄 增量更新**：只重跑内容变化的文件
- **📂 文档聚合**：短文档按目录合并，项目目录生成总览
- **🌍 全局知识地图**：生成全局知识图谱

### 🎬 场景模板

Lumina 会自动识别并适配：

- 📋 **会议纪要**：自动提取议题、决策、行动项
- 📄 **学术论文**：整理摘要、方法、结果、结论
- 📐 **PRD/设计文档**：结构化产品需求、设计方案
- 🧪 **测试报告**：提取测试结果、问题清单
- 🖥️ **运维文档**：整理系统信息、故障处理
- 📧 **邮件/聊天记录**：提取关键信息、行动项

### 🎨 Obsidian 增强输出

生成的笔记包含：
- `frontmatter`: `title`、`status`、`para`、`aliases`、`up`、`related`、`tags`、`source`
- 场景感知的 `callout`
- 层级标签：`lumina/scene/meeting_notes`
- `[[双向链接]]` 自动识别相关文件

### 🤖 多 LLM Provider 支持

| Provider | 特点 |
|---------|------|
| **Ollama** | 本地模型，完全免费，无需 API Key |
| **llama.cpp** | 本地轻量模型 |
| **OpenAI** | GPT-4/GPT-3.5 |
| **Anthropic** | Claude 系列 |
| **DeepSeek** | 深度求索 |
| **百炼/Qwen** | 阿里云通义千问 |
| **火山引擎** | 火山方舟 |
| **Kimi** | 月之暗面 |
| **智谱 GLM** | 智谱 AI |

### 🔍 向量能力

- 语义搜索：自然语言找笔记
- 关联笔记：找相关的知识
- 知识图谱：可视化知识关联
- 向量统计：查看知识覆盖

### 🎛️ Web 仪表盘

- 扫描队列、实时进度、速度、ETA
- 最近一次运行结果
- 失败项批量操作（重试/打标签/删除）
- 语义搜索、知识图谱可视化
- 向量统计

---

## 📖 详细文档

- [安装指南](docs/deployment/installation.md)
- [配置参考](docs/deployment/config-reference.md)
- [用户手册](docs/user-guide/manual.md)
- [功能说明](docs/product/features.md)
- [架构设计](docs/design/architecture/planner.md)
- [设计思路](docs/design/architecture/harness.md)

---

## 🛠️ 手动安装

```bash
# 方式 1: git clone
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py

# 方式 2: pip install
pip install "git+https://github.com/chenboripple/Lumina.git@release-ripple"
```

## 配置

所有运行配置来自 `~/.lumina/lumina.yaml`，包括：
- `input.sources`：输入目录、递归策略、glob 过滤规则
- `supported_extensions`：允许处理的扩展名
- `output.base_dir` / `output.plugin`：输出目录和格式
- `output.note_organization`：统一管理 scene/PARA 层级、场景规则和分类映射
- `harness.max_iterations` / `harness.quality_threshold`
- `llm` 以及 `llm_planner` / `llm_executor` / `llm_validator`

## 技术说明

### Planner
- 同时执行 `supported_extensions` 和 `input.sources[].filter` 两层过滤
- 为文件分配 `note_subdir`
- 短文档会按目录聚合
- 项目型目录会生成「项目总览」簇
- 文件数量足够多时会插入「全局知识地图」任务

### Executor
- 先做内容过滤，再做场景识别和 LLM 生成
- 对低价值文件直接跳过，不进入验证与保存
- 对生成结果执行标题归一化，避免落回原始文件名或占位标题

### Harness
Planner → Executor → Validator → Harness 完整链路

## 开发与验证

```bash
/usr/bin/python3 -m unittest tests.unit.test_content_policy tests.unit.test_planning_optimizations
/usr/bin/python3 -m py_compile src/lumina/web_interface.py
node --check src/lumina/web/static/js/app.js
```
