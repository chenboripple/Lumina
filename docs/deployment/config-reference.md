# ~/.lumina/lumina.yaml 配置参考

Lumina 的所有配置通过用户主目录下的 `~/.lumina/lumina.yaml` 文件管理，不在项目目录内存放任何配置。

> 本文件为完整配置示例，包含所有可用字段和说明。实际使用时只需保留需要修改的字段，其余字段会使用代码默认值。

---

## 最小配置（快速上手）

方式一：配置文件中直接写入 API Key

```yaml
llm:
  provider: openai
  api_key: "sk-..."
  model: gpt-4
```

方式二：使用环境变量（推荐，更安全）

```bash
export OPENAI_API_KEY="sk-..."
```

```yaml
llm:
  provider: openai
  model: gpt-4
  # api_key 留空，自动从 OPENAI_API_KEY 环境变量读取
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
  plugin: obsidian               # 输出插件：obsidian | notion | plain
  base_dir: "~/Lumina/Notes"    # 笔记根目录
  vault_path: "~/Obsidian/Vault" # Obsidian Vault 路径（使用 obsidian 插件时）

  structure:
    by_date: false               # 按日期分子目录（PARA 模式下建议关闭）
    by_type: false               # 按文件类型分子目录（PARA 模式下建议关闭）
    flat: false                  # 平铺（不分子目录）

  # ── 笔记目录组织（统一配置块）──────────────────
  # scenes/categories/levels 都放在 note_organization 下。
  note_organization:
    # levels 仅支持 scene / para，最多两层。
    # 默认：scene -> para，例如 工作/Projects
    # 可改成：para -> scene，例如 Projects/工作
    levels: ["scene", "para"]
    default_scene: "工作"         # scene 匹配失败时的兜底值

    # 生活场景层
    scenes:
      - name: "工作"
        keywords: ["需求", "会议", "项目", "技术", "代码", "方案", "报告", "排期", "季度"]
        # 可选：按 scene 限制可用 PARA 分类
        # 例如工作场景不希望出现 Resources
        enabled_categories: ["projects", "areas", "archive"]
        fallback_category: "areas"
      - name: "生活"
        keywords: ["日记", "健康", "家庭", "购物", "账单", "旅行"]
      - name: "学习"
        keywords: ["读书", "笔记", "课程", "学习", "摘录", "论文"]

    # PARA 分类层
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
# api_key 可写入配置，或留空让 Lumina 从环境变量自动读取
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

## 更多 LLM 配置示例

### 使用 DeepSeek

```yaml
llm:
  provider: deepseek
  api_key: "sk-..."
  model: deepseek-chat  # 或 deepseek-coder
```

### 使用阿里云百炼（通义千问）

```yaml
llm:
  provider: bailian
  api_key: "sk-..."
  model: qwen-max  # 或 qwen-plus、qwen-turbo
```

### 使用 Kimi（月之暗面）

```yaml
llm:
  provider: kimi
  api_key: "sk-..."
  model: moonshot-v1-8k  # 或 moonshot-v1-32k、moonshot-v1-128k
```

### 使用智谱 GLM

```yaml
llm:
  provider: glm
  api_key: "sk-..."
  model: glm-4  # 或 glm-3-turbo
```

### 使用火山引擎（火山方舟）

```yaml
llm:
  provider: volcengine
  api_key: "sk-..."
  base_url: "https://ark.cn-beijing.volces.com/api/v3"
  model: "ep-..."  # 需在火山方舟创建自己的 endpoint
```

### 使用 Ollama 本地模型

```yaml
# 先启动 ollama 服务
# ollama serve
# ollama pull llama3

llm:
  provider: ollama
  model: llama3  # 或 mistral、gemma 等已 pull 的模型
  base_url: "http://localhost:11434/v1"
  # 不需要 api_key
```

### 使用 llama.cpp 本地模型

```yaml
# 先启动 llama.cpp 服务
# ./server -m ./models/llama-3-8b-instruct.Q4_K_M.gguf --port 8080

llm:
  provider: llamacpp
  model: "llama-3-8b-instruct"  # 实际使用的模型由 server 启动参数决定
  base_url: "http://localhost:8080/v1"
  # 不需要 api_key
```

### 混合使用（Planner 用本地模型，Executor 用 DeepSeek）

```yaml
llm:
  provider: deepseek
  api_key: "sk-..."
  model: deepseek-chat

# Planner 用 ollama 降低成本
llm_planner:
  provider: ollama
  model: llama3
```

---

## 字段说明

### `llm.provider`

| 值 | 说明 | 默认 base_url | 默认模型 |
|---|---|---|---|
| `openai` | OpenAI 或兼容 OpenAI 协议的服务（默认） | `https://api.openai.com/v1` | `gpt-4` |
| `anthropic` | Anthropic Claude 系列 | `https://api.anthropic.com` | `claude-3-opus-20240229` |
| `deepseek` | DeepSeek - 深度求索 | `https://api.deepseek.com/v1` | `deepseek-chat` |
| `bailian` | 百炼 - 阿里云通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| `volcengine` | 火山引擎 - 火山方舟 | `https://ark.cn-beijing.volces.com/api/v3` | 需创建 endpoint |
| `kimi` | Kimi - 月之暗面 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| `glm` | 智谱 GLM - 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| `ollama` | Ollama 本地模型（无需 api_key） | `http://localhost:11434/v1` | `llama3` |
| `llamacpp` | llama.cpp 本地模型（无需 api_key） | `http://localhost:8080/v1` | `llama-3-8b-instruct` |

> **api_key 说明**：`ollama` 和 `llamacpp` 不需要 api_key；其他 provider 可通过 `~/.lumina/lumina.yaml` 配置，或从对应环境变量自动读取（`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`VOLCENGINE_API_KEY`、`MOONSHOT_API_KEY`、`ZHIPU_API_KEY`）。

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
| `notion` | 生成 Notion 导入友好的 Markdown，使用 Properties 表格替代 YAML frontmatter，标准 Markdown 链接 |
| `plain` | 纯 Markdown，无特定工具依赖，可在任何 Markdown 编辑器中使用 |

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

当 `output.plugin = notion` 时，输出使用 Notion 友好的格式：

- Properties 表格（Notion 导入时会自动识别为页面属性）
- 标准 Markdown 链接 `[text](url)`
- 标签使用反引号包裹，便于 Notion 识别
- 适合直接导入 Notion（选择 Import → Markdown）

### `output.note_organization.scenes` 与文档 scene 模板的区别

`output.note_organization.scenes` 只决定输出目录中的 scene 层如何组织，例如 `工作/Projects`、`学习/Resources`。

它和 Executor 里的文档 scene 模板不是同一件事：

- `output.note_organization.scenes`：用户配置的目录分层规则
- 文档 scene 模板：代码里的内容识别与提取策略

当前内置文档 scene 已覆盖会议纪要、学术论文、PRD、设计文档、测试报告、运维文档、邮件、聊天记录等类型，即使你没有配置 `output.note_organization.scenes`，这些模板也依然会参与内容提取。

### `output.note_organization.levels`

用于定义目录层级顺序，决定 scene 与 PARA 谁在前。

- `levels: ["scene", "para"]` -> `工作/Projects`
- `levels: ["para", "scene"]` -> `Projects/工作`

当 `levels` 包含 `scene` 但没有配置 `output.note_organization.scenes` 时，会自动降级为仅输出 PARA 层。

### `output.note_organization.scenes[].enabled_categories`

可选字段，用于限制某个 scene 可用的 PARA 分类键：

- `projects`
- `areas`
- `resources`
- `archive`

若推断结果不在白名单里，使用 `fallback_category`，未设置则回退到白名单首项。

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
