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

### 跨平台支持

Lumina 支持 **Windows、macOS、Linux** 三大平台。

### 快速安装

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

### 使用 pip

```bash
pip install lumina
```

### 验证安装

```bash
lumina --version
```

### 更新

```bash
# 检查版本
python install.py --version

# 更新到最新
python install.py --update
```

更多安装细节见 [docs/installation.md](docs/installation.md)

## 使用

### 使用

```bash
# 扫描目录并生成笔记
python -m lumina scan ~/Documents --output ./notes

# 使用配置文件
python -m lumina config config/lumina.yaml
```

## 输出格式

Lumina 采用**插件化输出架构**，支持多种笔记工具：

### 内置插件

| 插件 | 目标工具 | 状态 |
|------|---------|------|
| `obsidian` | Obsidian | ✅ 默认 |
| `notion` | Notion | 🚧 计划中 |
| `logseq` | Logseq | 🚧 计划中 |
| `plain` | 纯 Markdown | ✅ 内置 |

### 配置方式

```yaml
output:
  plugin: obsidian  # 切换插件即可更换输出格式
  vault_path: ~/Obsidian/Vault
```

### 插件接口

每个插件实现统一接口：
- `format(note)` - 格式化单条笔记
- `frontmatter(metadata)` - 生成前置元数据
- `link_syntax(target)` - 链接语法转换
- `tag_syntax(tags)` - 标签语法转换

### 自定义插件

```python
from lumina.plugins import BasePlugin

class MyPlugin(BasePlugin):
    def format(self, note):
        return f"# {note.title}\n\n{note.content}"
    
    def link_syntax(self, target):
        return f"[{target}]"
```

## 配置

编辑 `config/lumina.yaml`：

### 基础配置

```yaml
harness:
  max_iterations: 3        # 最大迭代轮数
  quality_threshold: 0.8   # 质量阈值
  output_dir: "./output"   # 输出目录

llm:
  provider: openai         # LLM 提供商
  model: gpt-4            # 模型选择

output:
  plugin: plain           # 输出格式插件（obsidian / plain）
  vault_path: ~/Obsidian/Vault  # Obsidian 仓库路径
```

### 高级配置：各 Agent 使用不同 LLM

Lumina 支持为 Planner、Executor、Validator 三个 Agent 分别配置不同的 LLM：

```yaml
# 默认 LLM 配置（所有 Agent 共用）
llm:
  provider: openai
  model: gpt-4
  temperature: 0.3

# Planner 专用配置 - 规划阶段使用更快更便宜的模型
llm_planner:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.2

# Executor 专用配置 - 笔记生成使用最强的模型
llm_executor:
  provider: anthropic
  model: claude-3-sonnet-20240229
  temperature: 0.4

# Validator 专用配置 - 质量检查使用快速模型
llm_validator:
  provider: anthropic
  model: claude-3-haiku-20240307
  temperature: 0.1
```

**配置规则**：
- 如果设置了 `llm_planner`/`llm_executor`/`llm_validator`，对应 Agent 使用专属配置
- 如果没有设置专属配置，Agent 使用默认的 `llm` 配置
- 所有配置项与 `llm` 结构相同，支持 `provider`、`model`、`temperature` 等参数

**使用场景**：
- **Planner**: 使用 GPT-3.5 快速规划，降低成本
- **Executor**: 使用 GPT-4/Claude-3 Sonnet 保证笔记质量
- **Validator**: 使用 Claude-3 Haiku 快速验证

### 完整配置示例

```yaml
input:
  sources:
    - path: "~/Documents"
      recursive: true
      filter: "*.md"

output:
  plugin: obsidian
  base_dir: "~/Lumina/Notes"

harness:
  max_iterations: 3
  quality_threshold: 0.8

llm:
  provider: openai
  model: gpt-4
  temperature: 0.3

llm_planner:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.2

llm_executor:
  provider: anthropic
  model: claude-3-sonnet-20240229
  temperature: 0.4

llm_validator:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.1
```

## 目录结构约定

### 输入（原始文件）
```
~/Documents/          # 可配置
├── 项目A/
│   ├── 需求文档.md
│   └── 会议纪要.txt
├── 项目B/
│   └── 技术方案.pdf
└── 随手记.md
```

### 输出（整理后笔记）
```
~/Lumina/Notes/       # 可配置
├── markdown/         # 按类型分目录（可选）
│   ├── 需求文档.md
│   └── 随手记.md
├── pdf/
│   └── 技术方案.md
└── text/
    └── 会议纪要.md
```

### 配置示例

```yaml
input:
  sources:
    - path: "~/Documents"      # 原始文件位置
      recursive: true
      filter: "*.md"
    - path: "~/Downloads"      # 多个来源
      recursive: false
      filter: "*.pdf"

output:
  plugin: obsidian
  base_dir: "~/Lumina/Notes"   # 整理后存储位置
  vault_path: "~/Obsidian/Vault"  # 可选：直接输出到 Obsidian
  
  structure:
    by_date: false             # 不按日期分目录
    by_type: true              # 按文件类型分目录
    flat: false                # 不平铺
  
  naming:
    prefix_date: false         # 不加日期前缀
    slugify: true              # 转义文件名
```

## 调试模式

Lumina 提供强大的调试模式，帮助开发者排查问题和优化配置：

### 启动调试模式

```bash
# 方式一：使用 CLI 命令
python -m lumina debug

# 方式二：使用启动脚本
python lumina.py --debug

# 方式三：直接运行调试模块
python -m lumina.debug
```

### 调试功能

#### 1. 单文件调试
逐步执行 Planner → Executor → Validator，显示每个阶段的详细输出：

```bash
python lumina.py --debug test.md
```

输出内容：
- 📄 文件分析信息（类型、大小、哈希）
- 🎯 处理计划（策略、预估成本）
- 📝 生成的笔记内容预览
- ⭐ 质量验证结果（得分、问题列表）
- 📄 最终输出预览
- ⏱️ 各阶段耗时统计

#### 2. 交互式调试
进入交互式命令行，手动测试各组件：

```bash
python lumina.py --debug --interactive
```

可用命令：
- `test_llm` - 测试 LLM 连接
- `test_file` - 测试单文件处理
- `test_config` - 验证配置
- `show_logs` - 显示调试日志
- `clear_logs` - 清除调试日志
- `quit` - 退出

#### 3. 测试 LLM 连接
验证 LLM 配置是否正确：

```bash
python lumina.py --debug --test-llm
```

#### 4. 验证配置
检查配置文件是否正确：

```bash
python lumina.py --debug --validate-config --config lumina.yaml
```

### 调试输出示例

```
============================================================
🐛 Lumina 单文件调试模式
============================================================
📄 目标文件: test.md
📏 文件大小: 1234 bytes

🔍 [Step 1] Planner - 扫描文件
🔍 [Step 2] Planner - 文件分析完成
   Data: {
     "type": "markdown",
     "size": 1234,
     "estimated_cost": 308.5,
     "required_capabilities": []
   }

🔍 [Step 3] Planner - 制定处理计划
🔍 [Step 4] Planner - 处理计划
   Data: {
     "strategy": "sequential",
     "total_files": 1,
     "estimated_cost": 308.5
   }

🔍 [Step 5] Executor - 开始生成笔记
🔍 [Step 6] Executor - 笔记生成完成
   Data: {
     "title": "Test Document",
     "content_length": 856,
     "tags": ["test", "markdown"],
     "duration": "2.34s"
   }

📝 生成内容预览:
----------------------------------------
# Test Document

## Summary
This is a test document...
----------------------------------------

🔍 [Step 7] Validator - 开始质量验证
🔍 [Step 8] Validator - 验证完成
   Data: {
     "passed": true,
     "score": 0.85,
     "issues_count": 2
   }

============================================================
📊 调试总结
============================================================
✅ 状态: 成功
⏱️  总耗时: 3.45s
⭐ 质量得分: 0.85
🎯 验证通过: 是
============================================================
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
