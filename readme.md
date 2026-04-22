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
