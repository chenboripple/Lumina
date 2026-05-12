# Lumina 高级功能

这份文档描述当前代码里已经落地、并且仍在主流程中生效的高级能力。凡是尚未真正打通的能力，这里会明确标注，不再按“已完成”口径描述。

## 1. Web 管理界面

核心文件：

- [src/lumina/web_interface.py](../../src/lumina/web_interface.py)
- [src/lumina/web/templates/dashboard.html](../../src/lumina/web/templates/dashboard.html)
- [src/lumina/web/static/js/react-app.jsx](../../src/lumina/web/static/js/react-app.jsx)（React 主界面，浏览器内 Babel 实时转译）
- [src/lumina/web/static/js/app.js](../../src/lumina/web/static/js/app.js)（共享 utils / `luminaTranslate` 等全局函数）
- [src/lumina/web/static/css/style.css](../../src/lumina/web/static/css/style.css)

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
- 提示词模板在线编辑（变量预览、版本回滚）

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
| `GET /api/templates` | 提示词模板列表（可按 `tag` 过滤） |
| `GET /api/templates/<name>` | 模板详情（含内容、变量） |
| `POST /api/templates` | 新建模板（已存在返回 409） |
| `PUT /api/templates/<name>` | 更新模板内容（自动 bump 版本） |
| `DELETE /api/templates/<name>` | 删除模板 |
| `GET /api/templates/<name>/versions` | 历史版本列表 |
| `POST /api/templates/<name>/rollback` | 回滚到指定版本 |
| `POST /api/templates/<name>/preview` | 用给定变量预览渲染结果 |

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

文档场景检测与模板位于 [src/lumina/scene_detector.py](../../src/lumina/scene_detector.py)。

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

说明：这里的“文档场景”是 Executor 用来选择提取模板和输出格式的能力；它和 `output.note_organization.scenes` 的目录分层不是同一件事。

## 4. 内容过滤与内容策略

核心文件：

- [src/lumina/content_filter.py](../../src/lumina/content_filter.py)
- [src/lumina/executor.py](../../src/lumina/executor.py)

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

- [src/lumina/document_cluster.py](../../src/lumina/document_cluster.py)
- [src/lumina/planner.py](../../src/lumina/planner.py)
- [src/lumina/harness.py](../../src/lumina/harness.py)

当前聚合能力：

- 短文档目录聚合
- 项目目录总览
- 与已有笔记的 append 模式
- 全局知识地图任务

这意味着当前产品逻辑已经不是“一文件一笔记”，而是“单文件 + 聚合簇 + 总览任务”的混合模式。

## 6. 多格式输出

核心文件：

- [src/lumina/plugins.py](../../src/lumina/plugins.py)

当前支持三种输出格式：

### Obsidian（默认）

- YAML frontmatter：`status`、`para`、`aliases`、`up`、`related`
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

### Notion

- Properties 表格（Notion 导入时自动识别为页面属性）
- 标准 Markdown 链接 `[text](url)`
- 标签使用反引号包裹
- 适合直接导入 Notion

### Plain Markdown

- 通用 Markdown 格式
- 无特定工具依赖
- 可在任何 Markdown 编辑器中使用

## 7. 向量搜索与知识图谱

当前 CLI 与 Web 都可以调用向量能力：

- 语义搜索
- 关联笔记
- 图谱构建
- 向量统计

前提是处理时启用了向量数据库，并且已经有成功写入的笔记被索引。

## 8. 提示词模板管理

核心文件：

- [src/lumina/prompt_manager.py](../../src/lumina/prompt_manager.py)
- [src/lumina/executor.py](../../src/lumina/executor.py)

当前可用能力：

- **YAML 持久化**：用户自定义模板保存到 `~/.lumina/prompts/`，每个模板一个 `.yaml` 文件
- **变量占位**：`{{var}}` / `{{var:default}}` 语法，自动从内容提取变量列表
- **版本管理**：每次保存自动生成新版本号，保留全部历史快照
- **一键回滚**：通过 `lumina template rollback` 或 Web UI 选择历史版本恢复
- **内置模板**：默认/Markdown/文本/代码/PDF/图片/修复 等 Executor 场景模板会自动落地，可被用户覆盖
- **导入导出**：`lumina template export/import` 支持跨设备迁移
- **变量预览**：Web UI 提供实时填值预览，避免上线后再发现变量缺漏

入口方式：

- CLI：`lumina template list / show / edit / create / delete / versions / rollback / render / export / import`
- Web UI：导航栏「提示词」页面，左侧列表 + 右侧编辑器 + 底部变量预览 / 版本历史
- REST API：见上文 `/api/templates/*` 接口表
- 代码：`from lumina.prompt_manager import get_prompt_manager; pm.render("default", file_name="x.md")`

## 9. 仍需谨慎看待的能力

下面这些接口或模块存在，但不应被文档表述为“成熟可用产品能力”：

- `/api/batch-repair`：接口存在，但低质量笔记扫描逻辑仍是占位实现
- 多设备同步：模块存在，但当前主流程和手册没有把它作为默认运行路径

文档里如果需要提到这些能力，应该明确写成“已预留/可继续开发”，而不是“已完整交付”。