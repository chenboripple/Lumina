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
    by_date: false               # 按日期分子目录
    by_type: true                # 按文件类型分子目录
    flat: false                  # 平铺（不分子目录）

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
| `obsidian` | 生成 Obsidian 兼容格式，含 frontmatter 和 `[[双向链接]]` |
| `plain` | 纯 Markdown，无特定工具依赖 |

### `harness.quality_threshold`

笔记质量评分由 Validator 给出（0.0 ~ 1.0）。低于阈值时 Harness 会触发 Executor 重新生成，直到达标或到达 `max_iterations`。

---

## 配置生效方式

```bash
# 使用默认路径 ~/.lumina/lumina.yaml
lumina scan ~/Documents

# 指定配置文件路径
lumina --config /path/to/custom.yaml scan ~/Documents
```
