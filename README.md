# Lumina

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)](#-roadmap)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> 🌟 **本地优先的 AI 笔记管道** — 把你散落的文档 / 邮件 / 会议纪要，自动转成 **Obsidian 友好**的结构化笔记。**文件不出本机**，**自带 LLM Key**，**提示词可改**。

📖 Read this in [English](README.en.md)

---

## 🎯 30 秒了解 Lumina

**你已经在用 Obsidian / Notion 管理笔记 —— 但还有 90% 的「半成品知识」散落在 Documents、Downloads、聊天截图里。**

Lumina 是一根「整理管道」，把这些散文件喂进去，吐出**直接能落地到你已有笔记体系**的 Markdown：

```
   ~/Documents/ 散文件          Lumina             ~/Obsidian/Vault/
   meeting_0412.txt    ───▶    [AI 处理]   ───▶   工作/Projects/发版规划.md
   research_notes.pdf                              学习/Resources/论文摘要.md
   ChatLog.png                                     工作/Areas/团队沟通.md
                                                   含 frontmatter + 双链 + 标签
```

它**不替代** Obsidian，它**喂养**你的 Obsidian。

---

## 🆚 为什么选 Lumina

| 维度 | **Lumina** | Reflect / Mem / Notion AI | Logseq + AI 插件 | Quivr |
|---|---|---|---|---|
| 数据存储 | ✅ 本地 | ❌ 云端锁定 | ✅ 本地 | 🔧 自托管 |
| LLM 自由选 | ✅ OpenAI / Claude / Ollama / 国内大模型 | ❌ 内置不可换 | ⚠️ 依赖插件 | ✅ 你自己的 Key |
| 输出格式 | ✅ Obsidian / Notion / Plain MD | ❌ 私有格式 | ✅ Markdown | ❌ 聊天界面 |
| 提示词可改 | ✅ YAML + 版本回滚 | ❌ 黑盒 | ❌ 一般不行 | ⚠️ 改代码 |
| 适用场景 | **批量整理** 已有散文件 | 新笔记输入 | 笔记编辑 + 检索 | RAG 问答 |
| 价格 | ✅ 开源免费 + 你的 LLM 用量 | ❌ $10–20/月订阅 | ✅ 免费 | ✅ 开源 |

**一句话**：如果你 **已经有一个 Vault**、**已经有一堆没整理的旧文件**、**不想把它们交给云端服务**，Lumina 就是为这个场景做的。

---

## 🚀 快速开始

### 一键安装

**macOS / Linux：**

```bash
curl -fsSL https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.sh | bash
```

**Windows (PowerShell)：**

```powershell
irm https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.ps1 | iex
```

安装脚本会自动：检查 Python 3.8+ → 安装 Lumina → 可选装 Ollama（本地模型免 Key） → 运行 `lumina init`。

### 三行起步

```bash
lumina init                          # 1) 交互式配置（选输入目录 / LLM / 输出格式）
lumina start                         # 2) 后台启动常驻服务（自带 Web UI）
open http://127.0.0.1:5088           # 3) 浏览器查看进度、搜索、改提示词
```

立即处理一个目录而不启常驻服务：

```bash
lumina process ~/Documents
```

---

## ✨ 看一个真实的转换效果

**输入** `~/Documents/meeting_2026-04-12.txt`：

```
今天和小李、小王对了一下下周发版计划，
决定先做 OAuth 改造再做支付重构，
小李负责 OAuth，预计周五前出 demo。
风险点：移动端 OAuth SDK 还没选定。
```

**输出** `~/Obsidian/Vault/工作/Projects/发版规划与-OAuth-重构会议.md`：

```markdown
---
title: 发版规划与 OAuth 重构会议
status: stable
para: Projects
aliases: [发版会议, OAuth 改造]
up: "[[工作 Map]]"
related: ["[[支付重构方案]]", "[[OAuth SDK 调研]]"]
tags: [lumina/scene/meeting_notes, lumina/para/Projects]
source: meeting_2026-04-12.txt
---

> [!info] 会议纪要
> 2026-04-12 与小李、小王讨论发版计划

## 决策
- 先做 OAuth 改造，再做支付重构

## 行动项
- [ ] 小李：周五前出 OAuth demo
- [ ] 待定：选定移动端 OAuth SDK

## 风险
- 移动端 OAuth SDK 还没选定
```

Lumina 自动完成：场景识别（会议纪要）→ 内容提取 → frontmatter 生成 → 双链推断 → 层级标签 → PARA 分类。

---

## 🌟 主要功能

### 📄 文件处理
- **批量扫描**：自动识别 `.md / .txt / .pdf / .py / .png / .jpg ...` 等知识文件
- **智能筛选**：过滤低价值文件、去重、敏感信息脱敏（手机号 / 邮箱 / 身份证）
- **场景感知**：会议纪要 / 学术论文 / PRD / 设计文档 / 测试报告 / 运维文档 / 邮件 / 聊天记录 / 日记 / 任务清单 共 15 种内置场景
- **增量更新**：基于内容哈希，只重跑变化的文件
- **文档聚合**：短文档按目录合并、项目目录生成总览、批次级全局知识地图

### 🎨 多格式输出

| 格式 | 适用 |
|---|---|
| **Obsidian** | YAML frontmatter + 场景 callout + 层级标签 + `[[双向链接]]` |
| **Notion** | Properties 表格 + 标准 MD 链接，直接 `Import → Markdown` |
| **Plain Markdown** | 通用，无工具依赖 |

### 🤖 LLM 自由选择

云端：OpenAI · Anthropic · DeepSeek · 阿里百炼 · 火山引擎 · Kimi · 智谱 GLM
本地：Ollama · llama.cpp（完全离线、零 API 费）

各 Agent 可独立配置：Planner 用便宜模型，Executor 用强模型，Validator 用快速模型。

### 🔍 向量能力
- 语义搜索：自然语言找笔记
- 关联笔记：找相关知识点
- 知识图谱：可视化笔记之间的连接
- 向量统计：查看知识覆盖度

### ✍️ 提示词可热改

不用改代码就能调整 LLM 行为：

```bash
lumina template list                  # 列出所有模板
lumina template edit markdown         # 用 $EDITOR 改 Markdown 提取模板
lumina template versions markdown     # 看版本历史
lumina template rollback markdown 1   # 一键回滚
```

或在 Web UI 「提示词」页面在线编辑，左侧列表、右侧编辑器、底部实时变量预览。模板每次保存自动生成新版本，旧版本永远在 `~/.lumina/prompts/` 中可回滚。

### 🎛️ Web 仪表盘

- 扫描队列 / 实时进度 / ETA
- 失败项批量重试、打标签、导出、删除
- 语义搜索 + 知识图谱可视化
- 提示词模板在线编辑器

---

## ❓ 常见问题

**Q1：我的文件会上传到云端吗？**
不会。Lumina 只把**单个文件的内容片段**发给你**自己配置的 LLM**。如果用 Ollama / llama.cpp，文件**完全不出本机**。

**Q2：能不能完全离线运行？**
能。`provider: ollama` + `model: llama3`（或 `mistral`、`qwen` 等），不需要任何 API Key，所有处理在你机器上完成。

**Q3：处理 100 个文件大概多少成本？**
用 GPT-4 全跑大约 $1–3，用 GPT-3.5 / DeepSeek 约 $0.05–0.2。Lumina 内置 LLM 响应缓存，第二次重跑同样文件不再花钱。

**Q4：会覆盖我现有的 Obsidian Vault 吗？**
不会。Lumina 默认输出到 `output.base_dir`（你自己配的目录），并按 `source` 字段匹配是否更新已有笔记，新文件直接走配置的 PARA + scene 路径，**不会动你手写的笔记**。

**Q5：不用 Obsidian，可以吗？**
可以。设置 `output.plugin: notion`（导 Notion 友好）或 `output.plugin: plain`（通用 Markdown），任何 MD 编辑器都能打开。

**Q6：支持哪些文件类型？**
内置支持 `.md / .txt / .pdf / .py / .js / .ts / .json / .yaml / .yml / .png / .jpg`，可在 `~/.lumina/lumina.yaml` 的 `supported_extensions` 里调整。

**Q7：处理速度？**
依赖 LLM 速度。本地 Ollama 大约 5–30 秒/文件；云端 API 1–5 秒/文件；重跑命中缓存 < 50ms/文件。

---

## 🗺️ Roadmap

✅ **已完成**：Planner（智能扫描）/ Executor（缓存 + 分块 + 流式）/ Harness（增量处理）/ PromptManager（YAML + 版本化）/ CacheManager / HistoryManager / 多 LLM Provider / Web UI（React）

🔄 **进行中**：增强 Validator（历史对比 + 质量趋势）/ 关键路径单测补全 / 多设备同步 / 批量低质量笔记重处理

详见 [升级路线图](docs/development/upgrade-guide.md)。

---

## 📖 文档

- 📘 [安装指南](docs/deployment/installation.md)
- ⚙️ [配置参考](docs/deployment/config-reference.md)
- 📚 [用户手册](docs/user-guide/manual.md)
- 🧩 [功能说明](docs/product/features.md)
- 🏗️ [架构设计](docs/design/architecture/planner.md)
- 🛠️ [贡献指南](CONTRIBUTING.md)
- 📄 全部文档索引：[docs/index.md](docs/index.md)

---

## 🤝 贡献

PR / Issue / 提示词模板分享都欢迎，参见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📄 许可证

双许可：
- **源代码**：[MIT](LICENSE) — 允许商用，保留版权声明
- **生成的笔记内容**：CC BY 4.0 — 你拥有产出，仅需署名

意味着你可以：自由商用 / 修改 / 分发 Lumina，用它处理商业文件并产出知识库，唯一要求是保留版权与署名。
