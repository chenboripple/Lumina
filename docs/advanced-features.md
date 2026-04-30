# Lumina 高级功能

这份文档描述当前代码里已经落地、并且仍在主流程中生效的高级能力。凡是尚未真正打通的能力，这里会明确标注，不再按“已完成”口径描述。

## 1. Web 管理界面

核心文件：

- [src/lumina/web_interface.py](/Users/ripple/work%20space/Lumina/src/lumina/web_interface.py)
- [src/lumina/web/templates/dashboard.html](/Users/ripple/work%20space/Lumina/src/lumina/web/templates/dashboard.html)
- [src/lumina/web/static/js/app.js](/Users/ripple/work%20space/Lumina/src/lumina/web/static/js/app.js)
- [src/lumina/web/static/css/style.css](/Users/ripple/work%20space/Lumina/src/lumina/web/static/css/style.css)

### 当前可用能力

- 扫描触发与后台执行
- 扫描队列、进度条、速度、ETA
- 最近一次扫描结果回显
- 笔记列表与详情查看
- 单笔记重生成
- 按源文件路径重生成
- 失败项查看与批量操作
- 语义搜索
- 知识图谱
- 向量统计展示

### 关键接口

| 接口 | 说明 |
|---|---|
| `GET /api/stats` | 仪表盘统计 |
| `POST /api/scan` | 按配置输入源启动后台扫描 |
| `GET /api/scan/status` | 队列状态、文件进度、最近一次运行状态 |
| `GET /api/notes` | 笔记列表 |
| `GET /api/notes/<id>` | 笔记详情 |
| `POST /api/notes/<id>/regenerate` | 按笔记来源重生成 |
| `POST /api/regenerate-source` | 按源文件路径重生成 |
| `POST /api/scan/failures/regenerate` | 批量重试失败项 |
| `POST /api/scan/failures/tag` | 给失败项打标签 |
| `POST /api/scan/failures/delete` | 删除失败项记录 |
| `POST /api/search` | 语义搜索 |
| `GET /api/graph` | 知识图谱 |
| `GET /api/vector-stats` | 向量库统计 |
| `GET /api/status` | Harness 原始运行状态 |

### 扫描状态语义

`/api/scan/status` 的 `phase` / `last_status` 当前用于区分：

- `idle`
- `queued`
- `running`
- `completed`
- `failed`

因此仪表盘在没有活动队列时，仍会显示最近一次完成或失败结果，而不是永远回退成“等待处理”。

## 2. 失败项批量操作

失败详情弹窗支持：

- 复制路径
- 复制错误信息
- 批量重生成
- 批量导出 JSON
- 批量删除失败记录
- 批量打标签

失败项当前状态字段：

- `open`
- `resolved`
- `retry_failed`

## 3. 场景模板扩展

文档场景检测与模板位于 [src/lumina/scene_detector.py](/Users/ripple/work%20space/Lumina/src/lumina/scene_detector.py)。

当前内置场景包括：

- `meeting_notes`
- `technical_doc`
- `requirements`
- `academic_paper`
- `prd`
- `design_doc`
- `test_report`
- `ops_doc`
- `email`
- `chat_log`
- `book_notes`
- `code_explanation`
- `diary`
- `task_list`
- `knowledge_essay`
- `generic_notes`

说明：这里的“文档场景”是 Executor 用来选择提取模板和输出格式的能力；它和 `output.scenes` 的目录分层不是同一件事。

## 4. 内容过滤与内容策略

核心文件：

- [src/lumina/content_filter.py](/Users/ripple/work%20space/Lumina/src/lumina/content_filter.py)
- [src/lumina/executor.py](/Users/ripple/work%20space/Lumina/src/lumina/executor.py)

当前已落地的策略包括：

- 空白/模板过滤
- 重复内容过滤
- 低知识密度过滤
- 样本事实降级
- 敏感字段脱敏
- 扫描版/乱码 PDF 跳过
- 客观数据清单、映射表、流水型 SQL 文档过滤

这一层发生在 LLM 调用前，并且输出阶段还会再次兜底脱敏。

## 5. 文档聚合与总览生成

核心文件：

- [src/lumina/document_cluster.py](/Users/ripple/work%20space/Lumina/src/lumina/document_cluster.py)
- [src/lumina/planner.py](/Users/ripple/work%20space/Lumina/src/lumina/planner.py)
- [src/lumina/harness.py](/Users/ripple/work%20space/Lumina/src/lumina/harness.py)

当前聚合能力：

- 短文档目录聚合
- 项目目录总览
- 与已有笔记的 append 模式
- 全局知识地图任务

这意味着当前产品逻辑已经不是“一文件一笔记”，而是“单文件 + 聚合簇 + 总览任务”的混合模式。

## 6. Obsidian 输出增强

核心文件：

- [src/lumina/plugins.py](/Users/ripple/work%20space/Lumina/src/lumina/plugins.py)

当前 Obsidian 输出增强包括：

- frontmatter：`status`、`para`、`aliases`、`up`、`related`
- Scene 感知 callout 类型
- `[[双向链接]]`
- 标签层级化
- `lumina_score` 等处理元数据

默认 callout 类型会按 scene 映射，例如：

- 学术论文 -> `quote`
- 设计文档 -> `example`
- 测试报告 -> `warning`
- 运维文档 -> `danger`
- 邮件 -> `tip`
- 聊天记录 -> `note`

## 7. 向量搜索与知识图谱

当前 CLI 与 Web 都可以调用向量能力：

- 语义搜索
- 关联笔记
- 图谱构建
- 向量统计

前提是处理时启用了向量数据库，并且已经有成功写入的笔记被索引。

## 8. 仍需谨慎看待的能力

下面这些接口或模块存在，但不应被文档表述为“成熟可用产品能力”：

- `/api/batch-repair`：接口存在，但低质量笔记扫描逻辑仍是占位实现
- 多设备同步：模块存在，但当前主流程和手册没有把它作为默认运行路径

文档里如果需要提到这些能力，应该明确写成“已预留/可继续开发”，而不是“已完整交付”。