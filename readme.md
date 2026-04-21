# Lumina

> 从本地文件萃取知识，生成结构化笔记的 AI Agent
> 
> **专注**：本地文件收集 → 智能整理 → 质量优化 → 格式化输出
> 
> **目标**：为 Obsidian 等笔记工具提供高质量、可查询的知识库素材

## 核心架构：Harness Engineering

基于 **规划-执行-验证** 三元架构：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Planner   │ →  │  Executor   │ →  │  Validator  │
│   (规划)     │    │   (执行)     │    │   (验证)     │
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
  扫描文件            生成笔记            质量检查
  分析结构            提取知识            反馈修复
  制定策略            结构化输出          迭代优化
```

## 特性

- 📁 **本地文件收集** - 自动扫描目录，发现文档、图片、代码等各类文件
- 🧠 **智能整理** - 基于 AI 提取核心信息，去重归类
- 🔄 **迭代优化** - Harness 验证-修复循环，确保输出质量
- 📝 **格式化输出** - 生成标准 Markdown，兼容 Obsidian 等笔记工具
- 🔗 **自动关联** - 识别内容关联，建议双向链接，便于查询
- 🎯 **笔记工具友好** - 默认支持 Obsidian 格式，可扩展其他工具

## 快速开始

### 工作流

```
本地文件 → Lumina 收集整理 → 生成 Markdown → Obsidian 查询使用
    ↑                                              ↓
    └────────────── 持续迭代优化 ──────────────────┘
```

### 安装

```bash
# 克隆仓库
git clone https://github.com/ripple/Lumina.git
cd Lumina

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 使用

```bash
# 扫描目录并生成笔记
python -m lumina scan ~/Documents --output ./notes

# 使用配置文件
python -m lumina config config/lumina.yaml
```

## 输出格式

Lumina 生成的笔记专为**笔记工具查询**优化：

```markdown
---
title: "笔记标题"
tags: ["tag1", "tag2"]
source: "原始文件路径"
lumina_score: 0.95
---

## 摘要

核心内容概述...

## 要点

- 关键点 1
- 关键点 2

## 关联主题

- [[相关笔记 A]]
- [[相关笔记 B]]
```

### 默认支持：Obsidian

- ✅ 标准 Markdown 格式
- ✅ YAML Frontmatter 元数据
- ✅ `[[双向链接]]` 语法
- ✅ 标签系统兼容
- ✅ 可配置 Vault 输出路径

### 可扩展支持

通过自定义模板，可适配：
- Logseq
- Notion（导出）
- 其他 Markdown 笔记工具

## 配置

编辑 `config/lumina.yaml`：

```yaml
harness:
  max_iterations: 3        # 最大迭代轮数
  quality_threshold: 0.8   # 质量阈值
  output_dir: "./output"   # 输出目录

llm:
  provider: openai         # LLM 提供商
  model: gpt-4            # 模型选择

output:
  format: markdown        # 输出格式
  vault_path: ~/Obsidian/Vault  # Obsidian 仓库路径
```

## 项目结构

```
Lumina/
├── src/
│   └── lumina/
│       ├── __init__.py      # 包入口
│       ├── planner.py        # 规划模块
│       ├── executor.py       # 执行模块
│       ├── validator.py      # 验证模块
│       ├── harness.py        # 核心协调器
│       └── cli.py            # 命令行接口
├── tests/                    # 测试套件
├── config/                   # 配置文件
├── docs/                     # 文档
├── examples/                 # 示例
├── README.md
├── requirements.txt
└── pyproject.toml
```

## 核心概念

### 定位：知识的预处理管道

Lumina 不是笔记工具本身，而是**笔记的预处理管道**：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  收集文件    │ →  │  整理优化    │ →  │  格式化输出  │
│  (Planner)  │    │  (Executor) │    │ (Validator) │
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
  扫描本地目录        AI 提取核心        生成标准
  发现各类文件        信息去重归类        Markdown
                                           ↓
                                    Obsidian 等工具
                                    查询使用
```

### Harness Engineering

Lumina 基于 **Harness Engineering** 理念设计：

> **Generator（生成器）+ Evaluator（评估器）+ Feedback Loop（反馈循环）**

通过分离"生成"与"评估"，并建立迭代优化机制，确保 AI 输出质量可控。

### 三元架构

借鉴 "三省六部" 的治理思想，但简化为更高效的 **规划-执行-验证** 三元组：

- **规划（Planner）**：分析输入，制定策略
- **执行（Executor）**：调用 LLM，生成内容
- **验证（Validator）**：质量检查，反馈修复

## 开发

### 运行测试

```bash
pytest tests/ -v
```

### 代码格式化

```bash
black src/ tests/
```

## 许可证

本项目采用 [Creative Commons Attribution-NonCommercial 4.0 International License](https://creativecommons.org/licenses/by-nc/4.0/)

**您可以自由：**
- ✅ **分享** — 在任何媒介或格式中复制、再分发
- ✅ **修改** — 再创作、转换或基于本作品构建

**在以下条件下：**
- ✅ **署名** — 您必须给出适当的署名，提供许可证链接，并标明是否做了修改
- ❌ **非商业性使用** — 您不得将本作品用于商业目的

**附加说明：**
- 本许可证适用于代码和文档内容
- 软件免责声明见 [LICENSE](LICENSE) 文件
- 如果您希望获得商业使用授权，请联系作者

## 致谢

- 灵感来源于 [Harness Engineering](https://www.anthropic.com/) 理念
- 双向链接设计受 [Obsidian](https://obsidian.md/) 启发
