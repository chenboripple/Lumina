# Lumina

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)](#-roadmap)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> 🌟 **Local-first AI note pipeline** — turn your scattered docs, emails, and meeting notes into **Obsidian-friendly** structured Markdown. **Files stay on your machine.** **Bring your own LLM key.** **Prompts are editable.**

📖 中文版：[README.md](README.md)

---

## 🎯 What Lumina Is in 30 Seconds

You already use Obsidian or Notion to manage notes — but 90% of your half-baked knowledge is scattered across `~/Documents`, `~/Downloads`, and chat screenshots.

Lumina is a **pipeline**: feed those raw files in, get back Markdown that drops cleanly into your existing notes system.

```
   ~/Documents/ raw files          Lumina             ~/Obsidian/Vault/
   meeting_0412.txt    ───▶    [AI processing] ───▶  Work/Projects/release-plan.md
   research_notes.pdf                                 Study/Resources/paper-summary.md
   ChatLog.png                                        Work/Areas/team-comms.md
                                                      with frontmatter + backlinks + tags
```

It **doesn't replace** Obsidian — it **feeds** Obsidian.

---

## 🆚 Why Lumina

| | **Lumina** | Reflect / Mem / Notion AI | Logseq + AI plugins | Quivr |
|---|---|---|---|---|
| Storage | ✅ Local | ❌ Cloud-locked | ✅ Local | 🔧 Self-hosted |
| LLM choice | ✅ OpenAI / Claude / Ollama / etc. | ❌ Built-in only | ⚠️ Plugin-dependent | ✅ Bring your own |
| Output format | ✅ Obsidian / Notion / Plain MD | ❌ Proprietary | ✅ Markdown | ❌ Chat UI |
| Editable prompts | ✅ YAML + versioning | ❌ Black box | ❌ Usually no | ⚠️ Edit source |
| Sweet spot | **Bulk organize** existing files | Capture new notes | Edit & retrieve | RAG Q&A |
| Pricing | ✅ Open source + your LLM usage | ❌ $10–20/mo SaaS | ✅ Free | ✅ Open source |

**Bottom line**: if you **already have a Vault**, **already have a pile of unorganized old files**, and **don't want to hand them to a cloud service**, that's the gap Lumina fills.

---

## 🚀 Quick Start

### One-line install

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/chenboripple/Lumina/release-ripple/install.ps1 | iex
```

Installer checks Python 3.8+, installs Lumina, optionally installs Ollama (key-free local model), and runs `lumina init`.

### Three commands to running

```bash
lumina init                          # 1) Interactive config (input dir / LLM / output format)
lumina start                         # 2) Start daemon (auto-opens web UI)
open http://127.0.0.1:5088           # 3) Watch progress, search, edit prompts in browser
```

Or one-shot:

```bash
lumina process ~/Documents
```

---

## ✨ Before / After

**Input** `~/Documents/meeting_2026-04-12.txt`:

```
Synced with Li and Wang on next week's release.
Decided to do OAuth refactor first, then payment refactor.
Li owns OAuth, demo by Friday.
Risk: mobile OAuth SDK not yet selected.
```

**Output** `~/Obsidian/Vault/Work/Projects/Release-Plan-and-OAuth-Refactor.md`:

```markdown
---
title: Release Plan and OAuth Refactor Meeting
status: stable
para: Projects
aliases: [Release Meeting, OAuth Refactor]
up: "[[Work Map]]"
related: ["[[Payment Refactor Proposal]]", "[[OAuth SDK Research]]"]
tags: [lumina/scene/meeting_notes, lumina/para/Projects]
source: meeting_2026-04-12.txt
---

> [!info] Meeting Notes
> 2026-04-12 — sync with Li and Wang on release plan

## Decisions
- Do OAuth refactor first, payment refactor second

## Action Items
- [ ] Li: OAuth demo by Friday
- [ ] TBD: select mobile OAuth SDK

## Risks
- Mobile OAuth SDK not yet selected
```

Lumina automatically: detects scene (meeting notes) → extracts structure → generates frontmatter → infers backlinks → adds hierarchical tags → assigns PARA category.

---

## 🌟 Core Features

- **Smart file selection** — 15 built-in scenes (meeting notes, papers, PRDs, design docs, test reports, ops docs, emails, chat logs, diaries, task lists, etc.)
- **Incremental processing** — content hash–based, only reprocess what changed
- **LLM caching** — second run costs 90%+ less, 10–100× faster
- **Doc aggregation** — short docs merged by directory, project folders get auto-overview, batch-level knowledge map
- **Editable prompts** — YAML-based, versioned, rollback support, no code changes needed
- **Multi-format output** — Obsidian (frontmatter + callouts + backlinks), Notion (properties table), or plain Markdown
- **Vector search** — semantic search, related notes, knowledge graph
- **Web dashboard** — scan queue, ETA, failure retry, search, graph view, prompt editor

---

## 🤖 LLM Support

**Cloud**: OpenAI · Anthropic · DeepSeek · Alibaba Bailian · Volcengine · Kimi · Zhipu GLM
**Local (key-free)**: Ollama · llama.cpp

Each agent (Planner / Executor / Validator) can use a different model: cheap model for planning, strong model for note generation, fast model for validation.

---

## ❓ FAQ

**Will my files be uploaded?**
Only individual file content goes to **the LLM you configure**. With Ollama / llama.cpp, files **never leave your machine**.

**Can it run fully offline?**
Yes. Set `provider: ollama` + `model: llama3` (or `mistral`, `qwen`, etc.) — no API key, everything local.

**Cost for 100 files?**
~$1–3 with GPT-4, ~$0.05–0.2 with GPT-3.5 / DeepSeek. Re-runs hit the cache and cost nothing.

**Will it overwrite my existing Vault?**
No. Output goes to your configured `output.base_dir`, matched by `source` field. Hand-written notes are never touched.

**Required Obsidian?**
No. `output.plugin: notion` or `plain` works in any Markdown editor.

**Supported file types?**
`.md / .txt / .pdf / .py / .js / .ts / .json / .yaml / .yml / .png / .jpg` out of the box; configurable.

---

## 🗺️ Roadmap

**Done**: Planner (smart scan) / Executor (cache + chunking + streaming) / Harness (incremental) / PromptManager (YAML + versioning) / Cache / History / Multi-LLM / Web UI (React)

**In progress**: enhanced Validator (history compare, quality trend) / unit test coverage / multi-device sync / batch repair of low-quality notes

See [upgrade-guide.md](docs/development/upgrade-guide.md) for details.

---

## 📖 Documentation

Most docs are in Chinese for now. Index: [docs/index.md](docs/index.md). Contributions to translate are very welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

Dual-licensed:
- **Source code**: [MIT](LICENSE) — commercial use allowed, keep the copyright notice.
- **Generated notes**: CC BY 4.0 — you own the output, just attribute.

You can freely use, modify, and distribute Lumina (commercial or personal), use it to process business files and build commercial knowledge bases — just keep the copyright and attribution.
