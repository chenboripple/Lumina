# ~/.lumina/lumina.yaml 配置参考

Lumina 的所有配置通过用户主目录下的 `~/.lumina/lumina.yaml` 文件管理，不在项目目录内存放任何配置。

> 本文件为完整配置示例，包含所有可用字段和说明。实际使用时只需保留需要修改的字段，其余字段会使用代码默认值。

---

## 最小配置（快速上手）

```yaml
llm:
  provider: openai
  api_key: "sk-..."
  model: gpt-4
```

---

## 完整配置示例

```yaml
# ──────────────────────────────────────────────
# 输入配置：告诉 Lumina 去哪里读取原始文件
# ──────────────────────────────────────────────
input:
  sources:
    - path: "~/Documents"        # 支持 ~ 展开
      recursive: true            # 是否递归子目录
      filter: "*.md"             # 文件过滤规则（glob 格式）
    - path: "~/Downloads"
      recursive: false
      filter: "*.pdf"

  default_recursive: true
  supported_extensions:
    - ".md"
    - ".txt"
    - ".pdf"
    - ".py"
    - ".js"
    - ".ts"
    - ".json"
    - ".yaml"
    - ".yml"
    - ".png"
    - ".jpg"

# ──────────────────────────────────────────────
# 输出配置：整理后的笔记存放位置和格式
# ──────────────────────────────────────────────
output:
  plugin: obsidian               # 输出插件：obsidian | plain
  base_dir: "~/Lumina/Notes"    # 笔记根目录
  vault_path: "~/Obsidian/Vault" # Obsidian Vault 路径（使用 obsidian 插件时）

  structure:
    by_date: false               # 按日期分子目录（PARA 模式下建议关闭）
    by_type: false               # 按文件类型分子目录（PARA 模式下建议关闭）
    flat: false                  # 平铺（不分子目录）

  # ── 第一层目录：生活场景 ──────────────────────
  # 按关键词将笔记归入不同生活场景。未匹配则归入 default_scene。
  # 不配置 scenes 时直接使用单层 PARA 目录。
  scenes:
    - name: "工作"
      keywords: ["需求", "会议", "项目", "技术", "代码", "方案", "报告", "排期", "季度"]
    - name: "生活"
      keywords: ["日记", "健康", "家庭", "购物", "账单", "旅行"]
    - name: "学习"
      keywords: ["读书", "笔记", "课程", "学习", "摘录", "论文"]
  default_scene: "工作"           # 关键词匹配失败时的兜底场景

  # ── 第二层目录：PARA 分类 ─────────────────────
  # 每个场景内按 PARA 方法论自动分入四个子目录：
  #   Projects  — 有明确截止目标的临时项目（完成后可划掉）
  #   Areas     — 需长期维护的责任/兴趣领域（无明确完成日期）
  #   Resources — 仅供参考的资料（不需完成任务）
  #   Archive   — 已完成或不再关注的材料
  # 最终路径示例：~/obsidian/工作/Projects/海思科差旅需求.md
  # 留空则使用内置英文默认值；只需覆盖想自定义的项
  categories:
    projects:  "Projects"
    areas:     "Areas"
    resources: "Resources"
    archive:   "Archive"

  naming:
    prefix_date: false           # 文件名加日期前缀
    slugify: true                # 文件名 URL 友好化

# ──────────────────────────────────────────────
# Harness 核心配置
# ──────────────────────────────────────────────
harness:
  max_iterations: 3              # 每篇笔记最多修复轮数
  quality_threshold: 0.8         # 质量达标阈值（0.0 ~ 1.0）

# ──────────────────────────────────────────────
# 服务配置
# ──────────────────────────────────────────────
service:
  log_retention_days: 15         # 日志保留天数（按天分文件）

# ──────────────────────────────────────────────
# LLM 配置
# api_key 必填，不从环境变量读取
# ──────────────────────────────────────────────
llm:
  provider: openai               # openai | anthropic
  api_key: "sk-..."              # API 密钥
  base_url: "https://api.openai.com/v1"  # 可替换为代理地址
  model: gpt-4
  temperature: 0.3
  max_tokens: 2000
  timeout: 60                    # 单次请求超时（秒）
  max_retries: 3
  retry_delay: 1.0               # 重试间隔（秒）

# ──────────────────────────────────────────────
# 各 Agent 独立 LLM 配置（可选）
# 未配置则继承上方 llm 配置
# ──────────────────────────────────────────────
llm_planner:
  provider: openai
  api_key: "sk-..."
  model: gpt-3.5-turbo           # 规划阶段用快速模型，降低成本
  temperature: 0.2

llm_executor:
  provider: anthropic
  api_key: "sk-ant-..."
  model: claude-3-sonnet-20240229  # 笔记生成用最强模型
  temperature: 0.4

llm_validator:
  provider: openai
  api_key: "sk-..."
  model: gpt-3.5-turbo           # 质量验证用快速模型
  temperature: 0.1
```

---

## 字段说明

### `llm.provider`

| 值 | 说明 |
|---|---|
| `openai` | OpenAI 或兼容 OpenAI 协议的服务（默认） |
| `anthropic` | Anthropic Claude 系列 |

### `llm.base_url`

可替换为任意兼容 OpenAI/Anthropic 协议的代理地址，例如：

```yaml
llm:
  provider: openai
  base_url: "https://your-proxy.example.com/v1"
  api_key: "your-proxy-key"
  model: gpt-4
```

### `output.plugin`

| 值 | 说明 |
|---|---|
| `obsidian` | 生成 Obsidian 兼容格式，含增强 frontmatter、callouts、层级标签和 `[[双向链接]]` |
| `plain` | 纯 Markdown，无特定工具依赖 |

当 `output.plugin = obsidian` 时，当前版本默认会写出这些字段：

- `title`
- `status`
- `para`
- `aliases`
- `up`
- `related`
- `tags`
- `source`

同时会根据检测到的 scene 选择不同 callout 类型，并自动补齐层级标签，例如 `lumina/scene/meeting_notes`、`lumina/para/Projects`。

### `output.scenes` 与文档 scene 模板的区别

`output.scenes` 只决定输出目录第一层如何组织，例如 `工作/Projects`、`学习/Resources`。

它和 Executor 里的文档 scene 模板不是同一件事：

- `output.scenes`：用户配置的目录分层规则
- 文档 scene 模板：代码里的内容识别与提取策略

当前内置文档 scene 已覆盖会议纪要、学术论文、PRD、设计文档、测试报告、运维文档、邮件、聊天记录等类型，即使你没有配置 `output.scenes`，这些模板也依然会参与内容提取。

### `harness.quality_threshold`

笔记质量评分由 Validator 给出（0.0 ~ 1.0）。低于阈值时 Harness 会触发 Executor 重新生成，直到达标或到达 `max_iterations`。

---

## 配置生效方式

```bash
# 使用默认路径 ~/.lumina/lumina.yaml
lumina start

# 指定配置文件路径
lumina start --config /path/to/custom.yaml
```
