# Lumina 使用手册

## 运行模式

Lumina 有两种主模式：

- 常驻服务：Web 界面 + 目录监听 + 后台初始化同步
- 一次性处理：处理一个路径或按配置批量处理一组输入源

## 常驻服务

### 启动

```bash
lumina start
lumina start --port 5088 --no-watch
```

常用参数：

- `--watch/--no-watch`：是否监听输入目录变化
- `--initial-sync/--no-initial-sync`：启动后是否自动跑一次初始化处理
- `--parallel/--no-parallel`：是否并行处理
- `--vector/--no-vector`：是否启用向量数据库
- `--threshold`：覆盖质量阈值

### 查看状态与停止

```bash
lumina status
lumina stop
```

### 前台调试

```bash
lumina serve
lumina serve --no-watch --no-initial-sync
```

前台模式适合看日志、调试异常和验证页面行为。

## 一次性处理

### 处理配置中的全部输入源

```bash
lumina process
```

### 处理指定目录或文件

```bash
lumina process ~/Desktop/bymonth
lumina process ~/Desktop/bymonth --no-incremental
lumina process ~/Desktop/bymonth --no-vector --parallel
```

实际行为：

- 未传路径时，遍历 `input.sources`
- 传路径时，只处理该路径
- `--incremental` 开启时，只处理内容发生变化的文件
- `--recursive` 可以覆盖配置里的递归设置

## Web 仪表盘

默认地址：`http://127.0.0.1:5088`

当前页面能力：

- 扫描队列与实时进度条
- 最近一次扫描状态回显
- 失败详情查看
- 失败项批量重生成、导出、删除、打标签
- 已生成笔记浏览与单篇重生成
- 向量搜索与知识图谱

### 扫描状态语义

仪表盘顶部状态卡片不是简单的“是否正在运行”。当前逻辑会区分：

- `idle`：尚未开始
- `queued`：已排队，等待后台线程执行
- `running`：正在处理输入源队列
- `completed`：最近一次运行完成
- `failed`：最近一次运行含失败项或运行中断

对应接口是 `/api/scan/status`，其中会返回：

- `queue`
- `source_counts`
- `file_counts`
- `progress_percent`
- `elapsed_seconds`
- `eta_seconds`
- `rate_per_minute`
- `failed_items`
- `last_status`
- `last_completed_at`

## 实际处理逻辑

### 1. 文件选择

每个输入文件必须同时满足：

- 扩展名在 `supported_extensions` 中
- 路径匹配对应输入源的 `filter` glob

这条规则同时用于：

- 正常扫描
- 页面里的按源文件重生成
- 单笔记重生成

### 2. 增量处理

Harness 会基于 `FileChangeTracker` 判断文件内容是否变化。只有真的产出笔记的文件才会被标记为已处理；失败或没有输出的文件不会被错误标记成“已完成”。

### 3. 内容过滤与脱敏

在调用 LLM 之前，Executor 会通过 `ContentFilter` 做前置策略判断：

- 空白文件、模板文件
- 重复内容
- 几乎不可读的扫描 PDF
- 低知识密度文档
- 大量样本事实、清单、映射表、客观流水
- 敏感字段脱敏

结果可能是：

- 直接跳过
- 降级保留抽象结论，不保留细节样本
- 允许处理，但输出阶段继续兜底脱敏

### 4. 文档聚合

Planner 不再是“一文件一笔记”的朴素模型。当前会插入三类聚合任务：

- 同目录短文档聚合
- 项目目录总览
- 批次级全局知识地图

另外，如果检测到和已有笔记标题匹配，也可能进入追加模式。

### 5. 输出落盘

Harness 保存结果时会：

- 根据 `note_subdir` 落入场景/PARA 子目录
- 先按 `source` 匹配已有笔记，避免重复生成
- source 不命中时按标题相似度兜底
- 命中旧平铺路径时迁移到新结构路径

## Obsidian 输出

当 `output.plugin = obsidian` 时，生成内容会包含：

- YAML frontmatter：`title`、`status`、`para`、`aliases`、`up`、`related`、`tags`、`source`
- Scene 对应的 callout 类型
- `[[link]]` 链接语法
- 层级标签，例如 `#lumina/scene/academic_paper`

`status` 由质量分决定：

- `stable`：分数 >= 0.85
- `draft`：分数 >= 0.65 且 < 0.85
- `review`：分数 < 0.65

## 向量能力

```bash
lumina search "差旅"
lumina related "Projects/差旅报销设计说明.md"
lumina graph --output graph.json
lumina stats
```

说明：`search`、`related`、`graph`、`stats` 都依赖向量数据库。未索引过内容时，这些命令不会返回有效结果。

## 常见操作

### 全量重跑

```bash
lumina stop
rm -rf ~/obsidian/Archive ~/obsidian/Areas ~/obsidian/Projects ~/obsidian/Resources
rm -rf ~/.lumina/cache ~/.lumina/fingerprints ~/.lumina/history
lumina start
```

### 手动验证 Web 层

```bash
curl http://127.0.0.1:5088/api/stats
curl http://127.0.0.1:5088/api/scan/status
```

## 故障排查

### 页面一直显示等待处理

优先检查：

```bash
lumina status
curl http://127.0.0.1:5088/api/scan/status
```

说明：当前版本的状态卡片会保留最近一次完成或失败状态。如果这里仍然长期停在 `idle`，通常说明服务刚启动且还没有扫描历史，或前端没有连到当前服务实例。

### 重生成提示文件不允许

这通常不是 bug，而是当前源文件不满足当前配置：

- 不在 `input.sources` 范围内
- 扩展名不在 `supported_extensions`
- 不匹配 `filter`

### 向量命令不可用

先确认处理时没有关闭向量：

```bash
lumina process --vector
lumina start --vector
```