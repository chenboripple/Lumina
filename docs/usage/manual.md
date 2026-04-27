# Lumina 使用手册 (Agent 增强版)

## 🚀 快速开始

### 安装
```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
pip install -r requirements.txt
```

### 初始化配置
```bash
# 安装后会自动创建 ~/.lumina/lumina.yaml（若不存在）
# 手动编辑配置文件
vim ~/.lumina/lumina.yaml
```

### 基础使用
```bash
# 启动常驻服务（推荐）
python -m lumina serve

# 服务启动后访问 Web 界面
# http://127.0.0.1:5000

# 一次性执行处理
python -m lumina process

# 停止服务
# Ctrl+C
```

## 📖 高级功能

### 1. 增量处理

**场景**：每天自动更新笔记库，只处理新增/修改的文件。

```bash
# 启动常驻模式后自动监听 input.sources
python -m lumina serve
```

**效果**：
- 启动时先执行一次初始化整理
- 后续只处理变化的文件，速度提升 **10~50x**
- 用户可在 Web 页面手动重生成指定笔记

### 2. 缓存管理

**场景**：避免重复处理相同内容，降低 API 成本。

```bash
# 查看缓存统计
python -m lumina cache-stats

# 清理缓存
python -m lumina cache-clear

# 查看缓存大小
python -m lumina cache-size
```

**效果**：
- 重复文件处理速度提升 **10~100x**
- LLM API 成本降低 **90%+**

### 3. 历史查询

**场景**：查看文件处理历史、质量趋势、可解释性。

```bash
# 查看文件处理历史
python -m lumina history ~/Documents/important.md

# 查看质量趋势
python -m lumina history --trend ~/Documents/important.md

# 查看可解释性
python -m lumina history --explain ~/Documents/important.md
```

**输出示例**：
```
📄 文件: ~/Documents/important.md
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

### 4. 批量处理

**场景**：处理大量文件，需要分批次、优先级控制。

```bash
# 自动分批次处理
python -m lumina scan ~/Documents --batch-size 20

# 只处理高优先级文件
python -m lumina scan ~/Documents --priority high

# 限制处理数量
python -m lumina scan ~/Documents --limit 100
```

### 5. 成本预估

**场景**：提前了解处理成本，避免意外费用。

```bash
# 预估处理成本
python -m lumina scan ~/Documents --dry-run

# 输出示例
📋 处理计划 #a1b2c3d4
📂 总文件数: 126
💰 预估成本: $0.2450
⏱️  预估时间: 125.3s
📦 批次数: 14
⚡ 缓存命中: 42 个文件
🔄 增量文件: 84 个文件
```

## ⚙️ 配置文件

### 完整配置示例
```yaml
# ~/.lumina/lumina.yaml

# LLM 配置
llm:
  provider: openai
  model: gpt-4
  temperature: 0.3
  max_tokens: 2000
  timeout: 60
  max_retries: 3

# Harness 配置
harness:
  max_iterations: 3
  quality_threshold: 0.8
  output_dir: "./output"

# 缓存配置
cache:
  enabled: true
  dir: "~/.lumina/cache"
  max_size_gb: 10
  llm_ttl_days: 7

# 历史配置
history:
  enabled: true
  dir: "~/.lumina/history"
  max_records: 100000
  retention_days: 365

# 输入配置
input:
  sources:
    - path: "~/Documents"
      recursive: true
      filter: "*.md"
    - path: "~/Downloads"
      recursive: false
      filter: "*.pdf"

# 输出配置
output:
  plugin: obsidian
  base_dir: "~/Lumina/Notes"
  vault_path: "~/Obsidian/Vault"
  
  structure:
    by_date: false
    by_type: true
    flat: false
  
  naming:
    prefix_date: false
    slugify: true
```

## 🔧 最佳实践

### 1. 日常增量更新
```bash
# 创建定时任务（crontab）
0 9 * * * lumina scan ~/Documents --output ~/Obsidian/Vault >> ~/logs/lumina.log 2>&1
```

### 2. 监控处理质量
```bash
# 生成质量报告
lumina quality-report --output report.html

# 查看质量趋势
lumina history --trend-all --days 30
```

### 3. 优化处理速度
```bash
# 使用缓存（默认开启）
lumina scan ~/Documents --cache

# 调整批量大小
lumina scan ~/Documents --batch-size 50

# 使用更快的模型（调试时）
lumina scan ~/Documents --model gpt-3.5-turbo
```

### 4. 处理大文件
```bash
# 跳过超大文件
lumina scan ~/Documents --max-size 10MB

# 分段处理大文件
lumina scan ~/Documents --chunk-size 4000
```

## 🐛 故障排查

### 问题1：处理速度很慢
**原因**：
- 首次扫描，没有缓存
- 文件数量太多
- 使用了昂贵的模型

**解决**：
```bash
# 检查缓存状态
lumina cache-stats

# 使用增量模式
lumina scan ~/Documents --incremental

# 使用更快的模型
lumina scan ~/Documents --model gpt-3.5-turbo
```

### 问题2：API 成本太高
**原因**：
- 没有启用缓存
- 重复处理相同文件
- 使用了昂贵的模型

**解决**：
```bash
# 启用缓存
lumina scan ~/Documents --cache

# 使用增量模式
lumina scan ~/Documents --incremental

# 预估成本
lumina scan ~/Documents --dry-run
```

### 问题3：处理结果质量差
**原因**：
- 质量阈值设置太低
- 迭代次数不够
- 提示词模板不合适

**解决**：
```bash
# 提高质量阈值
lumina scan ~/Documents --threshold 0.9

# 增加迭代次数
lumina scan ~/Documents --max-rounds 5

# 查看历史，分析质量问题
lumina history --explain ~/Documents/problematic.md
```

### 问题4：缓存不命中
**原因**：
- 文件内容变化
- 提示词模板变化
- 模型参数变化

**解决**：
```bash
# 查看缓存统计
lumina cache-stats

# 清理缓存，重新生成
lumina cache-clear

# 检查提示词模板是否稳定
```

## 📊 性能优化

### 缓存命中率优化
| 场景 | 命中率 | 优化建议 |
|------|--------|----------|
| 首次扫描 | 0% | 无需优化 |
| 二次扫描无变化 | 95%+ | 保持现状 |
| 二次扫描10%变化 | 85% | 检查文件变化原因 |
| 日常增量更新 | 70%~90% | 优化文件组织 |

### 批量大小优化
| 文件大小 | 推荐批量 | 说明 |
|----------|----------|------|
| <100KB | 20~50 | 小文件批量大 |
| 100KB~1MB | 10~20 | 中等文件批量适中 |
| >1MB | 3~5 | 大文件批量小 |

## 🎯 典型工作流

### 工作流1：个人知识库维护
```bash
# 1. 初始化
lumina init

# 2. 首次全量扫描
lumina scan ~/Documents --output ~/Obsidian/Vault --full-scan

# 3. 设置定时增量更新
crontab -e
# 添加：0 9 * * * lumina scan ~/Documents --output ~/Obsidian/Vault

# 4. 每周查看质量报告
lumina quality-report --week
```

### 工作流2：项目文档整理
```bash
# 1. 扫描项目文档
lumina scan ./docs --output ./notes

# 2. 查看处理计划（预估成本）
lumina scan ./docs --dry-run

# 3. 执行处理
lumina scan ./docs --output ./notes

# 4. 查看处理历史
lumina history --trend ./docs/README.md
```

### 工作流3：批量文件处理
```bash
# 1. 扫描大量文件
lumina scan ~/Downloads --batch-size 50

# 2. 监控处理进度
lumina scan ~/Downloads --progress

# 3. 查看处理统计
lumina stats

# 4. 清理缓存
lumina cache-clear
```

## 📞 获取帮助

### 命令行帮助
```bash
# 查看所有命令
lumina --help

# 查看具体命令帮助
lumina scan --help
lumina history --help
lumina cache --help
```

### 文档资源
- [架构文档](../architecture/planner.md)
- [缓存系统](../architecture/cache.md)
- [历史系统](../architecture/history.md)
- [升级指南](../develop/upgrade-guide.md)

### 社区支持
- GitHub Issues: https://github.com/chenboripple/Lumina/issues
- 邮件: chenboripple@gmail.com
