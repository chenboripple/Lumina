# Lumina 本地开发指南

## 快速开始

### 1. 安装依赖

```bash
cd Lumina
pip install -e .
```

### 2. 运行调试模式

```bash
# 方式一：使用启动脚本（推荐）
python lumina.py --debug

# 方式二：使用 CLI 命令
python -m lumina debug

# 方式三：直接运行调试模块
python -m lumina.debug
```

## 调试模式功能

### 单文件调试

```bash
# 调试单个文件
python lumina.py --debug test.md
```

调试模式会显示：
- 📄 文件分析
- 🎯 处理计划
- 📝 生成内容预览
- ⭐ 质量验证
- ⏱️ 各阶段耗时

### 交互式调试

```bash
python lumina.py --debug --interactive
```

交互式命令：
- `test_llm` - 测试 LLM 连接
- `test_file` - 测试文件处理
- `test_config` - 验证配置
- `show_logs` - 显示调试日志
- `clear_logs` - 清除日志

### 配置和 LLM 测试

```bash
# 验证配置
python lumina.py --debug --validate-config --config my_config.yaml

# 测试 LLM
python lumina.py --debug --test-llm
```

## VS Code 调试

项目已包含 `.vscode/launch.json`，提供以下调试配置：

1. **Lumina: CLI Debug** - 调试 CLI 命令
2. **Lumina: Interactive Debug** - 启动交互式调试
3. **Lumina: Single File Debug** - 调试当前打开的文件
4. **Lumina: Test Suite** - 运行测试套件

使用方法：
1. 按 `F5` 或点击「运行和调试」
2. 选择配置
3. 设置断点
4. 开始调试

## 项目结构

```
Lumina/
├── src/
│   └── lumina/
│       ├── harness.py          # 核心协调器
│       ├── planner.py          # 规划器
│       ├── executor.py         # 执行器
│       ├── validator.py        # 验证器
│       ├── llm.py             # LLM 集成
│       ├── config.py          # 配置管理
│       ├── cli.py             # 命令行接口
│       ├── debug.py           # 调试模式（新增）
│       ├── core/              # 核心模块
│       ├── tools/             # 工具模块
│       ├── utils/             # 工具函数
│       └── plugins/           # 输出插件
├── tests/
│   └── test_debug.py          # 调试模式测试（新增）
├── docs/
│   └── example_config_with_separate_llm.yaml
├── lumina.py                  # 快速启动脚本（新增）
├── install.py
├── pyproject.toml
└── README.md
```

## 开发流程

### 1. 代码修改流程

```bash
# 1. 调试修改
python lumina.py --debug test_file.md

# 2. 运行测试
python -m pytest tests/ -v

# 3. 提交更改
git status
git add .
git commit -m "描述你的更改"
```

### 2. 测试策略

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行调试模式测试
python -m pytest tests/integration/test_debug.py -v

# 运行特定文件测试
python -m pytest tests/integration/test_integration.py -v
```

### 3. 代码格式化

```bash
# 使用 black
black src/ tests/

# 使用 flake8
flake8 src/
```

## 常见问题

### Q: 调试模式看不到 LLM 响应？
A: 确保在 `~/.lumina/lumina.yaml` 中配置了 API key：
```yaml
llm:
  provider: openai
  api_key: "sk-..."
```

### Q: 如何测试多个 Agent 的不同 LLM 配置？
A: 创建 `lumina.yaml` 配置文件：
```yaml
llm_planner:
  provider: openai
  model: gpt-3.5-turbo

llm_executor:
  provider: anthropic
  model: claude-3-sonnet-20240229

llm_validator:
  provider: anthropic
  model: claude-3-haiku-20240307
```

然后运行：
```bash
python lumina.py --debug --validate-config --config lumina.yaml
```

### Q: 如何在 VS Code 中调试？
A: 
1. 打开 `.py` 文件
2. 设置断点（点击行号左侧）
3. 按 `F5` 选择「Lumina: Single File Debug」
4. 观察变量和调用栈

### Q: 调试模式太慢？
A: 
- 使用更快的模型：`llm_config.model = "gpt-3.5-turbo"`
- 禁用向量存储：`enable_vector_store = False`
- 减少迭代次数：`max_iterations = 1`

## 高级调试

### 使用调试器类直接编程

```python
from lumina.debug import LuminaDebugger
from lumina.harness import Harness, HarnessConfig

# 初始化调试器
config = HarnessConfig(
    max_iterations=1,
    quality_threshold=0.0,
)
debugger = LuminaDebugger(Harness(config))

# 调试单个文件
report = debugger.debug_single_file("test.md")

# 访问调试日志
for log in debugger.debug_logs:
    print(f"Step {log['step']}: {log['action']}")
```

### 集成到你的测试

```python
def test_integration():
    from lumina.debug import LuminaDebugger
    
    debugger = LuminaDebugger()
    report = debugger.debug_single_file("test.md")
    
    assert report.get("success", False) is True
    assert "validation" in report
    assert report["validation"]["score"] > 0.5
```
