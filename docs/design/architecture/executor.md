# Executor 模块 (Agent 增强版) 文档

## 🎯 模块定位

Executor 是 Lumina 的**智能执行引擎**，负责调用 LLM 生成结构化笔记，支持缓存、分块、多策略执行、流式输出等 Agent 核心能力。

## ✨ 核心能力

### 1. 🧠 智能内容读取
- **自动类型识别**：根据文件类型选择最佳读取策略
- **大文件分块**：超过 4000 字符自动分块处理，避免超出 LLM 上下文限制
- **图片支持**：支持图片文件（返回描述信息，可扩展视觉模型）
- **PDF 解析**：支持 PDF 文件自动提取文本（需要 PyPDF2）
- **安全读取**：自动处理编码错误、权限问题

### 2. 💾 LLM 响应缓存
- **基于内容哈希**：相同文件内容不会重复调用 LLM
- **TTL 过期机制**：默认 7 天过期，避免缓存过时内容
- **成本降低**：重复处理相同文件时成本降低 **90%+**
- **速度提升**：缓存命中时速度提升 **10~100x**

### 3. 📝 多策略提示词
- **类型感知**：根据文件类型（Markdown、代码、PDF、图片等）选择不同提示词策略
- **单块处理**：小文件直接处理，简单高效
- **分块汇总**：大文件分块处理 + 汇总，确保内容完整性
- **修复模式**：基于验证反馈自动修复内容

### 4. 🔄 迭代修复支持
- **上下文感知**：修复时保留原始内容和验证反馈
- **问题定位**：精确修复 Validator 指出的问题
- **质量提升**：通过迭代修复持续提升笔记质量

### 5. 📊 执行过程记录
- **完整记录**：记录每次调用的参数、结果、成本
- **统计分析**：统计总调用次数、缓存命中率、总成本
- **可解释性**：记录处理策略、分块数、迭代次数

### 6. ⚡ 流式输出支持
- **实时进度**：实时展示读取、处理、生成的进度
- **增量输出**：LLM 生成内容实时返回，无需等待完整响应
- **用户体验**：提升用户等待时的体验

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│                  Executor                     │
├─────────────────────────────────────────────┤
│  1. 内容读取器 (ContentReader)               │
│     - 智能分块                               │
│     - 类型识别                               │
│     - 安全读取                               │
│                                             │
│  2. 缓存管理器 (CacheManager)                │
│     - LLM 响应缓存                           │
│     - 基于内容哈希                           │
│     - TTL 过期                               │
│                                             │
│  3. 提示词构建器 (PromptBuilder)             │
│     - 类型感知策略                           │
│     - 单块/分块模式                          │
│     - 修复模式                               │
│                                             │
│  4. LLM 调用器 (LLMCaller)                   │
│     - 同步调用                               │
│     - 流式调用                               │
│     - 统计记录                               │
│                                             │
│  5. 输出解析器 (OutputParser)                │
│     - JSON 提取                              │
│     - Markdown 转换                          │
│     - 错误处理                               │
└─────────────────────────────────────────────┘
```

## 📋 数据结构

### NoteOutput（笔记输出）
```python
@dataclass
class NoteOutput:
    title: str                    # 笔记标题
    content: str                  # Markdown 内容
    tags: List[str]               # 标签列表
    links: List[str]             # 建议的链接
    source: str                   # 源文件路径
    metadata: Dict[str, Any]      # 元数据（复杂度、置信度等）
    processing_info: Dict[str, Any]  # 处理过程信息
```

### ExecutionContext（执行上下文）
```python
@dataclass
class ExecutionContext:
    session_id: str               # 会话ID
    file_info: Any                # 文件信息
    plan: Dict[str, Any]          # 处理计划
    iteration: int = 0            # 当前迭代次数
    previous_output: Optional[NoteOutput] = None  # 上一次输出（用于修复）
    previous_validation: Optional[Any] = None     # 上一次验证结果（用于修复）
```

## 🚀 快速使用

### 基础用法
```python
from lumina.executor import Executor, ExecutionContext
from lumina.planner import Planner
from lumina.cache import CacheManager

# 初始化
executor = Executor(
    llm_config={"provider": "openai", "model": "gpt-4"},
    cache_manager=CacheManager()
)

# 创建执行上下文
context = ExecutionContext(
    session_id="session_123",
    file_info=file_info,  # 从 Planner 获取
    plan=plan,            # 从 Planner 获取
)

# 执行笔记生成
note = executor.execute(context)

print(f"标题: {note.title}")
print(f"标签: {note.tags}")
print(f"内容长度: {len(note.content)}")
```

### 流式执行
```python
# 流式执行，实时展示进度
for progress in executor.execute_with_stream(context):
    print(progress, end="")
```

### 迭代修复
```python
# 第一次执行
context.iteration = 0
note = executor.execute(context)

# 验证（假设 validation 是 Validator 的输出）
validation = validator.validate(note)

if not validation.passed:
    # 修复
    context.iteration = 1
    context.previous_output = note
    context.previous_validation = validation
    
    fixed_note = executor.revise(context)
    print(f"修复后得分: {validation.score}")
```

## 🎛️ 配置参数

### 文件大小阈值
| 阈值 | 默认值 | 说明 |
|------|--------|------|
| SMALL_FILE_THRESHOLD | 100KB | 小文件阈值 |
| MEDIUM_FILE_THRESHOLD | 1MB | 中等文件阈值 |
| LARGE_FILE_THRESHOLD | 10MB | 大文件阈值 |

### 分块配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| CHUNK_SIZE | 4000 | 每块最大字符数 |
| MAX_CHUNKS | 5 | 最多处理块数 |

### 提示词策略
| 文件类型 | 策略 | 说明 |
|----------|------|------|
| markdown | markdown_extractor | Markdown 文件提取 |
| text | text_extractor | 文本文件提取 |
| code | code_extractor | 代码文件提取 |
| pdf | document_extractor | PDF 文档提取 |
| image | image_extractor | 图片文件提取 |
| data | data_extractor | 数据文件提取 |
| default | default_extractor | 默认提取策略 |

## 📊 输出示例

### 执行统计
```python
stats = executor.get_stats()
print(f"总调用次数: {stats['total_calls']}")
print(f"缓存命中率: {stats['cache_hit_rate']:.1%}")
print(f"总 Token 数: {stats['total_tokens']:.0f}")
print(f"总成本: ${stats['total_cost']:.4f}")
print(f"平均每次成本: ${stats['avg_cost_per_call']:.4f}")
```

### 处理过程信息
```python
print(note.processing_info)
# {
#     "session_id": "session_123",
#     "iteration": 0,
#     "prompt_strategy": "markdown_extractor",
#     "chunks_processed": 1,
#     "cache_key": "abc123",
#     "timestamp": "2026-04-25T10:00:00",
#     "cached": False
# }
```

## 🔧 扩展开发

### 添加新的提示词策略
```python
class CustomExecutor(Executor):
    PROMPT_TEMPLATES = {
        **Executor.PROMPT_TEMPLATES,
        "custom": "custom_extractor",
    }
    
    def _build_prompt_custom(self, file_info, content, context):
        return f"""Custom prompt for {file_info.type}..."""
```

### 自定义缓存键生成
```python
def _generate_cache_key(self, file_info, content_chunks):
    # 自定义缓存键逻辑
    return hashlib.md5(
        (file_info.hash + str(self.llm_config) + str(datetime.now().date())).encode()
    ).hexdigest()
```

### 添加新的文件类型支持
```python
def _read_file_smart(self, path):
    if path.suffix == '.docx':
        return self._read_docx(path)
    return super()._read_file_smart(path)

def _read_docx(self, path):
    # 使用 python-docx 读取 Word 文档
    from docx import Document
    doc = Document(path)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    return [text]
```

## 🎯 性能特性

- **O(1) 缓存查询**：基于哈希的缓存查找
- **流式处理**：大文件分块处理，避免内存溢出
- **智能分块**：按段落分块，保持语义完整性
- **并行处理**：支持多文件并行处理（需配合 Harness）

## 🔒 安全特性

- **输入长度限制**：自动截断超长内容
- **编码安全**：自动处理编码错误
- **路径安全**：使用 Path 对象避免路径注入
- **错误降级**：LLM 调用失败时返回错误信息，不崩溃

## 📈 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|----------|----------|
| 0.1.0 | 2026-04-21 | 初始版本，基础 LLM 调用 |
| 0.2.0 | 2026-04-25 | Agent 增强版，缓存、分块、流式、修复 |

---

## 🤝 贡献指南

1. 新文件类型支持需要附带测试文件
2. 提示词策略修改需要 A/B 测试验证效果
3. 性能敏感代码需要基准测试
4. 所有新功能需要附带单元测试
