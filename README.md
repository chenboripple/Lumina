# Lumina

> 从本地文件萃取知识，生成结构化笔记的 AI Agent

Lumina 是一个**本地常驻知识整理服务**。它从 `~/.lumina/lumina.yaml` 读取输入目录与输出规则，启动后常驻运行，提供 Web 管理界面、目录变化监听、自动增量更新，以及手动重生成笔记能力。

```
本地文件 ──► Planner ──► Executor ──► Validator ──► Obsidian / Markdown
             (扫描规划)   (AI 生成)    (质量验证)
                              ▲            │
                              └── 迭代修复 ┘
```

## 安装

```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py
```

更多安装方式见 [docs/installation.md](docs/installation.md)。

## 配置

所有配置通过 `~/.lumina/lumina.yaml` 管理，**不读取环境变量**。

**最小配置：**

```yaml
llm:
  provider: openai
  api_key: "sk-..."
  model: gpt-4
```

完整字段说明和各 Agent 独立 LLM 配置见 [docs/lumina-yaml-demo.md](docs/lumina-yaml-demo.md)。

## 使用

```bash
# 后台启动常驻服务（推荐）
lumina start

# 查看服务状态
lumina status

# 停止后台服务
lumina stop

# 打开 Web 界面
# http://127.0.0.1:5000

# 前台调试模式（保留）
lumina serve

# 一次性手动处理（可选）
lumina process
lumina process ~/Documents

# 调试模式
lumina debug
```

服务模式下：

1. 启动时会先按 `~/.lumina/lumina.yaml` 执行一次初始化处理
2. 随后持续监听 `input.sources` 中的目录变化
3. 检测到文件新增/修改后自动增量更新对应笔记
4. 也可以在页面中手动触发单篇笔记重新生成
5. 后台服务会维护 `~/.lumina/service.pid` 与 `~/.lumina/service.log`

## 核心架构

Lumina 基于 **Harness Engineering** 设计，分离生成与评估，建立迭代修复循环：

| 组件 | 职责 |
|---|---|
| **Planner** | 扫描目录，分析文件类型，制定处理策略 |
| **Executor** | 调用 LLM，提取核心信息，生成 Markdown 笔记 |
| **Validator** | 质量评分，发现问题，驱动 Executor 迭代修复 |
| **Harness** | 协调三者，控制迭代轮数和质量阈值 |

每篇笔记在质量得分超过 `quality_threshold`（默认 0.8）或达到 `max_iterations`（默认 3）前会持续迭代。

## 输出格式

内置两种输出插件，通过 `output.plugin` 切换：

| 插件 | 说明 |
|---|---|
| `obsidian`（默认） | 含 frontmatter、`[[双向链接]]`、标签，兼容 Obsidian |
| `plain` | 纯 Markdown，无工具依赖 |

## 目录结构

```
Lumina/
├── src/lumina/          # 核心包
│   ├── harness.py       # 主流程协调
│   ├── planner.py       # 文件扫描与规划
│   ├── executor.py      # 笔记生成
│   ├── validator.py     # 质量验证
│   └── llm.py           # LLM Provider 抽象
├── tests/
│   ├── unit/            # 单元测试（pytest）
│   ├── integration/     # 集成测试（pytest）
│   └── manual/          # 手动验证脚本
├── docs/
│   ├── lumina-yaml-demo.md   # 配置文件完整示例
│   ├── installation.md       # 安装指南
│   └── usage/manual.md       # 详细使用手册
└── README.md
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/unit tests/integration -v

# 手动验证
python tests/manual/run_all_manual_checks.py
```

## 许可证

[CC BY-NC 4.0](LICENSE) — 可自由分享和修改，不可用于商业目的。如需商业授权请联系作者。

