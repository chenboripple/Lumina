# Lumina

> 从本地文件萃取知识，生成结构化笔记的 AI Agent

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

- 🗂️ **本地文件扫描** - 自动发现文档、图片、代码等
- 🤖 **AI 内容理解** - 基于 LLM 提取核心信息
- 📝 **结构化笔记生成** - Markdown 格式，兼容 Obsidian
- 🔗 **自动关联发现** - 识别内容关联，建议双向链接
- 🔄 **迭代优化** - Harness 验证-修复循环，确保输出质量

## 快速开始

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
