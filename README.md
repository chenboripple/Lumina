# Lumina

> 从本地文件中提炼知识，生成结构化 Markdown/Obsidian 笔记的常驻服务。

Lumina 会读取 `~/.lumina/lumina.yaml` 中配置的输入源、输出目录、LLM 参数和目录结构规则，然后通过 Planner -> Executor -> Validator -> Harness 这条链路，把原始文件整理成可检索、可链接、可在 Obsidian 中继续使用的笔记。

## 当前能力

- 常驻服务模式：启动 Web 界面、目录监听、后台初始化同步
- 一次性处理模式：按路径或按 `input.sources` 批量处理
- 增量更新：只重跑内容发生变化的文件
- 内容策略：低知识密度过滤、样本事实降级、敏感字段脱敏
- 文档聚合：短文档按目录合并、项目目录总览、全局知识地图
- 场景模板：会议纪要、学术论文、PRD、设计文档、测试报告、运维文档、邮件、聊天记录等
- Obsidian 增强输出：frontmatter、callouts、层级标签、related/up/aliases
- Web 仪表盘：扫描队列、实时进度、最近一次运行结果、失败项批量操作
- 向量能力：语义搜索、关联笔记、知识图谱

## 安装

```bash
git clone https://github.com/chenboripple/Lumina.git
cd Lumina
python install.py
```

更多安装说明见 [docs/installation.md](/Users/ripple/work%20space/Lumina/docs/installation.md)。

## 配置

所有运行配置都来自 `~/.lumina/lumina.yaml`，包括：

- `input.sources`：输入目录、递归策略、glob 过滤规则
- `supported_extensions`：允许处理的扩展名
- `output.base_dir` / `output.plugin`：输出目录和格式
- `output.scenes` / `output.categories`：场景层和 PARA 目录映射
- `harness.max_iterations` / `harness.quality_threshold`
- `llm` 以及 `llm_planner` / `llm_executor` / `llm_validator`

完整示例见 [docs/lumina-yaml-demo.md](/Users/ripple/work%20space/Lumina/docs/lumina-yaml-demo.md)。

## 使用

### 常驻服务

```bash
lumina start
lumina status
lumina stop
```

默认地址是 `http://127.0.0.1:5088`。

`lumina start` 会在后台启动 `lumina serve`，并维护：

- `~/.lumina/service.pid`
- `~/.lumina/service.json`
- `~/.lumina/service-YYYY-MM-DD.log`

### 前台服务

```bash
lumina serve
lumina serve --host 127.0.0.1 --port 5088 --no-watch --no-initial-sync
```

`serve` 会：

1. 启动 Web 界面
2. 可选地监听 `input.sources`
3. 在页面可访问后触发一次后台初始化同步

### 一次性处理

```bash
lumina process
lumina process ~/Documents
lumina process ~/Documents --no-incremental --no-vector
```

- 不传路径时，按 `input.sources` 逐个处理
- 传路径时，只处理指定文件或目录
- `--incremental/--no-incremental` 控制是否跳过未变化文件

### 向量相关命令

```bash
lumina search "差旅报销"
lumina related "Projects/差旅系统设计说明.md"
lumina graph --min-similarity 0.75 --output graph.json
lumina stats
```

## Web 界面

仪表盘覆盖这些能力：

- `/api/scan`：触发按配置输入源的后台扫描
- `/api/scan/status`：返回队列、文件级进度、速度、ETA、最近一次运行状态
- `/api/notes/<id>/regenerate`：按笔记来源重生成
- `/api/regenerate-source`：按源文件路径重生成
- `/api/scan/failures/regenerate`：批量重试失败项
- `/api/scan/failures/tag`：给失败项打标签
- `/api/scan/failures/delete`：删除失败记录
- `/api/search`、`/api/graph`、`/api/vector-stats`：搜索与图谱能力

说明：`/api/status` 返回的是 Harness 运行状态；仪表盘顶部扫描卡片使用的是 `/api/scan/status`。

## 输出行为

### Planner

- 同时执行 `supported_extensions` 和 `input.sources[].filter` 两层过滤
- 为文件分配 `note_subdir`
- 短文档会按目录聚合
- 项目型目录会生成“项目总览”簇
- 文件数量足够多时会插入“全局知识地图”任务

### Executor

- 先做内容过滤，再做场景识别和 LLM 生成
- 对低价值文件直接跳过，不进入验证与保存
- 对生成结果执行标题归一化，避免落回原始文件名或占位标题

### Obsidian 插件

默认输出包含：

- frontmatter：`title`、`status`、`para`、`aliases`、`up`、`related`、`tags`、`source`
- 场景感知 callout
- 层级标签，例如 `lumina/scene/meeting_notes`
- `[[双向链接]]`

## 文档索引

- [docs/start-here.md](/Users/ripple/work%20space/Lumina/docs/start-here.md)
- [docs/usage/manual.md](/Users/ripple/work%20space/Lumina/docs/usage/manual.md)
- [docs/advanced-features.md](/Users/ripple/work%20space/Lumina/docs/advanced-features.md)
- [docs/architecture/planner.md](/Users/ripple/work%20space/Lumina/docs/architecture/planner.md)
- [docs/architecture/harness.md](/Users/ripple/work%20space/Lumina/docs/architecture/harness.md)

## 开发与验证

```bash
/usr/bin/python3 -m unittest tests.unit.test_content_policy tests.unit.test_planning_optimizations
/usr/bin/python3 -m py_compile src/lumina/web_interface.py
node --check src/lumina/web/static/js/app.js
```

说明：这个仓库里根目录的 `lumina.py` 可能会影响临时导入测试；手动跑模块时优先确保 `src` 在 `PYTHONPATH` 前面。