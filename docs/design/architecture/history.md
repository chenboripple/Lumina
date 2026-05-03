# 操作历史与审计追踪系统文档

## 🎯 模块定位

HistoryManager 是 Lumina 的**记忆与审计系统**，负责记录完整的处理流程，支持版本回滚、质量趋势分析、可解释性展示。

## ✨ 核心能力

### 1. 完整处理记录
- 记录每个文件的完整处理流程（扫描→规划→执行→验证→输出）
- 记录每次迭代的详细数据（得分、问题、修复建议）
- 记录最终输出内容和质量评分
- 支持按文件、按会话、按时间维度查询

### 2. 版本管理
- 支持笔记的版本回滚（回到之前的生成版本）
- 版本对比（查看不同版本的差异）
- 版本标签（标记重要版本）

### 3. 质量趋势分析
- 追踪单个文件的质量变化趋势
- 分析整体处理质量的提升/下降
- 识别质量瓶颈和改进点

### 4. 审计追踪
- 记录谁、何时、为什么修改了笔记
- 完整的决策链记录（为什么这样处理）
- 支持合规性审计

### 5. 可解释性
- 展示 Agent 的完整决策过程
- 解释为什么生成这样的笔记
- 展示迭代优化的具体步骤

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│              HistoryManager                  │
├─────────────────────────────────────────────┤
│  📊 SQLite 数据库                             │
│     - processing_records 表                  │
│       * session_id, file_path, file_hash     │
│       * iterations, best_score              │
│       * final_output, full_history            │
│       * created_at, metadata                  │
│                                             │
│     - sessions 表                             │
│       * session_id, start_time, end_time      │
│       * total_files, avg_score, status         │
│                                             │
│  📈 查询接口                                 │
│     - 文件历史查询                           │
│     - 会话统计查询                           │
│     - 质量趋势分析                           │
│     - 可解释性生成                           │
└─────────────────────────────────────────────┘
```

## 🚀 快速使用

### 基础用法
```python
from lumina.history import HistoryManager, ProcessingRecord

# 初始化
history = HistoryManager()

# 开始新会话
session_id = "session_123"
history.start_session(session_id)

# 记录文件处理
record = ProcessingRecord(
    session_id=session_id,
    file_path="/path/to/file.md",
    file_hash="abc123",
    file_type="markdown",
    file_size=1024,
    iterations=3,
    best_score=0.85,
    final_output="生成的笔记内容...",
    full_history='[{"round":1,"score":0.6,"issues":5},...]',
    created_at="2026-04-25T10:00:00",
    metadata={"model": "gpt-4", "temperature": 0.3}
)
history.record_file_processing(record)

# 结束会话
history.end_session(session_id, total_files=100, avg_score=0.82)

# 查询文件历史
file_history = history.get_file_history("/path/to/file.md", limit=5)
for record in file_history:
    print(f"处理时间: {record['created_at']}, 得分: {record['best_score']}")

# 获取质量趋势
trend = history.get_quality_trend("/path/to/file.md", days=30)
for point in trend:
    print(f"{point['created_at']}: {point['best_score']}")

# 获取可解释性说明
explanation = history.get_explanation("/path/to/file.md")
print(explanation)
```

### 输出示例
```
📄 文件: /path/to/file.md
🕐 处理时间: 2026-04-25 10:00:00
📊 最终得分: 0.85
🔄 迭代次数: 3

📋 迭代详情:
  第1轮: 得分=0.60, 通过=False, 问题数=5
    修复建议: 内容太短,缺少标题,标签不足...
  第2轮: 得分=0.75, 通过=False, 问题数=2
    修复建议: 结构不清晰,缺少关键信息...
  第3轮: 得分=0.85, 通过=True, 问题数=0
    修复建议: 无
```

## 📊 数据库结构

### processing_records 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| session_id | TEXT | 会话ID |
| file_path | TEXT | 文件路径 |
| file_hash | TEXT | 文件哈希 |
| file_type | TEXT | 文件类型 |
| file_size | INTEGER | 文件大小 |
| iterations | INTEGER | 迭代次数 |
| best_score | REAL | 最佳得分 |
| final_output | TEXT | 最终输出 |
| full_history | TEXT | 完整历史（JSON） |
| created_at | TEXT | 创建时间 |
| metadata | TEXT | 元数据（JSON） |

### sessions 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| session_id | TEXT | 会话ID |
| start_time | TEXT | 开始时间 |
| end_time | TEXT | 结束时间 |
| total_files | INTEGER | 总文件数 |
| avg_score | REAL | 平均得分 |
| status | TEXT | 状态 |

## 🔧 高级用法

### 批量查询
```python
# 获取最近50个会话
sessions = history.get_all_sessions(limit=50)
for session in sessions:
    print(f"{session['session_id']}: {session['total_files']} files, score={session['avg_score']}")

# 获取会话统计
stats = history.get_session_stats("session_123")
print(f"状态: {stats['status']}, 文件数: {stats['total_files']}")
```

### 质量趋势分析
```python
import matplotlib.pyplot as plt

# 获取质量趋势
trend = history.get_quality_trend("/path/to/file.md", days=30)

# 绘制趋势图
dates = [p['created_at'] for p in trend]
scores = [p['best_score'] for p in trend]

plt.plot(dates, scores)
plt.title("Quality Trend")
plt.xlabel("Date")
plt.ylabel("Score")
plt.show()
```

## 🎯 应用场景

### 1. 质量监控
- 监控笔记质量是否持续提升
- 识别质量下降的文件，及时干预
- 分析质量瓶颈，优化处理策略

### 2. 版本回滚
- 发现新版本质量不如旧版本时回滚
- A/B 测试不同处理策略的效果
- 对比不同 LLM 模型的输出质量

### 3. 审计合规
- 记录完整的处理决策链
- 证明处理过程的透明性和可解释性
- 满足合规性审计要求

### 4. 用户反馈
- 向用户展示 Agent 的决策过程
- 解释为什么生成这样的笔记
- 增强用户对 Agent 的信任

## 📈 性能特性

- **SQLite 存储**：轻量级，无需额外数据库服务
- **索引优化**：file_path 和 session_id 已建立索引
- **查询速度**：单次查询 < 10ms（10万条记录）
- **存储效率**：每条记录约 1~5KB

## 🔒 安全特性

- 数据库文件存储在用户目录（~/.lumina/history/）
- 默认权限 0700，只有用户可访问
- 敏感内容自动脱敏（可配置）
- 支持数据库加密（可选）

## 🎯 配置参数

```python
# 默认配置
DEFAULT_HISTORY_DIR = "~/.lumina/history"
MAX_HISTORY_RECORDS = 100000  # 最多保留10万条记录
HISTORY_RETENTION_DAYS = 365  # 保留365天的记录
```

## 🔧 扩展开发

### 自定义存储后端
```python
class PostgreSQLHistoryManager(HistoryManager):
    def __init__(self, db_url):
        self.db = psycopg2.connect(db_url)
    
    def record_file_processing(self, record):
        # 自定义 PostgreSQL 存储逻辑
        pass
```

### 添加新的查询维度
```python
def get_files_by_score_range(self, min_score, max_score, limit=100):
    """按得分范围查询文件"""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            """
            SELECT * FROM processing_records 
            WHERE best_score BETWEEN ? AND ?
            ORDER BY best_score DESC
            LIMIT ?
            """,
            (min_score, max_score, limit)
        )
        return [dict(row) for row in cursor.fetchall()]
```

## 📋 常见问题

### Q: 历史记录会占用太多空间吗？
A: 默认保留10万条记录，每条约1~5KB，总大小约100~500MB。超过部分会自动清理最旧的记录。

### Q: 可以导出历史数据吗？
A: 可以，SQLite 数据库可以直接导出为 CSV、JSON 等格式。

### Q: 历史数据可以迁移吗？
A: 可以，直接复制 ~/.lumina/history/ 目录即可。

### Q: 如何清理历史记录？
A: 删除 ~/.lumina/history/lumina_history.db 文件即可。
