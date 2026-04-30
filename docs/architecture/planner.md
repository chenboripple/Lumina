# Planner 模块文档

## 模块定位

Planner 负责三件事：

1. 扫描输入路径，产出 `FileInfo`
2. 在处理前做结构化规划和聚合
3. 为输出阶段准备目录结构和批次策略

它不负责真正调用 LLM，也不负责验证结果质量，但它决定了“哪些东西会被处理、怎样组合、落到什么目录”。

## 公开接口

### `scan(input_path, recursive=True, file_filter=None, supported_extensions=None)`

行为：

- 支持扫描单文件或目录
- 同时应用 `supported_extensions` 与 glob `file_filter`
- 为每个文件计算：类型、大小、修改时间、内容哈希、预估成本、能力需求

说明：当前 `scan` 没有 `incremental` 参数。增量过滤发生在 Harness 层。

### `plan(files, existing_notes=None)`

行为：

- 将输入文件做聚合和批次规划
- 为每个任务分配 `note_subdir`
- 在文件足够多时插入全局知识地图任务
- 返回 `ProcessingPlan`

## 关键数据结构

### `FileInfo`

```python
@dataclass
class FileInfo:
    path: Path
    type: str
    size: int
    modified: float
    hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_priority: int = 0
    estimated_cost: float = 0.0
    estimated_time: float = 0.0
    required_capabilities: List[str] = field(default_factory=list)
```

`metadata` 在当前版本里非常关键，常见字段包括：

- `note_subdir`
- `is_cluster`
- `cluster_id`
- `cluster_files`
- `cluster_strategy`
- `cluster_title`
- `overview_scope`
- `title_hint`
- `para`

### `ProcessingPlan`

```python
@dataclass
class ProcessingPlan:
    total_files: int
    total_estimated_cost: float
    total_estimated_time: float
    strategy: str
    batches: List[List[FileInfo]]
    summary: str
```

## 当前规划逻辑

### 1. 基础扫描

Planner 会先根据扩展名和 glob 规则筛选文件，然后调用 `_analyze_file()` 生成 `FileInfo`。

类型优先级当前是：

- `markdown`
- `text`
- `code`
- `pdf`
- `image`
- `data`
- `unknown`

### 2. 文档聚合

当前通过 `DocumentClusterer` 插入三类聚合任务。

#### 项目目录聚合

当目录同时满足这些特征时，Planner 会优先把它视作项目而不是零散资料：

- 文件数量达到阈值
- 代码/文档比例较高
- 目录名或内容特征接近 project/repo/module/service/app 等

产物是一个 `SUMMARIZE_MULTIPLE` 簇，标题通常为“`目录名项目总览`”。

#### 短文档目录聚合

短文档会按目录分组：

- 普通目录：倾向 `COMBINE_SHORT_DOCS`
- 泛化目录名或文件较多：倾向 `SUMMARIZE_MULTIPLE`

标题由目录名自动生成，例如：

- `xxx资料汇总`
- `xxx主题总结`

#### 追加到已有笔记

如果传入了 `existing_notes`，DocumentClusterer 会按标题和文件名做近似匹配，命中后会生成 `APPEND_TO_EXISTING` 类型的簇。

## 全局知识地图

当本轮输入文件足够多时，Planner 会在批次前插入一个 synthetic cluster：

- `cluster_id = global_overview`
- `overview_scope = global`
- `title_hint = 全局知识地图`

它会选取代表性文件，并生成一份 overview catalog，包括：

- domain counts
- PARA counts
- type counts
- top directories

这个任务不是普通目录聚合，而是批次级总览任务。

## 目录结构分配

Planner 会在 `_assign_note_structure()` 中写入 `note_subdir`。

规则如下：

- `flat=true`：不分目录
- 配置了 `output.scenes`：输出为 `场景/PARA`
- 未配置 `output.scenes`：输出为 `PARA`

### PARA 推断

`_infer_para()` 的优先级：

1. `metadata["para"]` 显式值
2. cluster 默认归到 `Resources`
3. 文件名关键词命中 `Archive` / `Projects` / `Areas`
4. 场景到 PARA 的兜底映射

### 场景层推断

`output.scenes` 是用户自定义的目录组织规则，不等同于 `SceneDetector` 的文档场景模板。

- 这里是按文件名关键词匹配场景目录
- 匹配不到时用 `default_scene`
- 仍匹配不到时回退到第一个场景名

## 批次策略

Planner 目前只使用简单、稳定的分批逻辑：

- 小文件 `< 100KB`：每批 5 个
- 中等文件 `< 1MB`：每批 3 个
- 大文件 `>= 1MB`：每批 1 个

策略名由平均文件大小决定：

- `batch_parallel`
- `sequential`
- `resource_aware`

## 和旧文档最容易混淆的点

- `scan()` 没有 `incremental=True/False` 参数
- `ProcessingPlan` 没有 `plan_id`、`created_at`、`priorities` 这些字段
- 增量过滤不在 Planner，而在 Harness `_filter_incremental()`
- 当前 Planner 已经负责插入“项目总览”和“全局知识地图”任务，不再只是基础扫描器

## 相关文件

- [src/lumina/planner.py](/Users/ripple/work%20space/Lumina/src/lumina/planner.py)
- [src/lumina/document_cluster.py](/Users/ripple/work%20space/Lumina/src/lumina/document_cluster.py)
- [src/lumina/config_core.py](/Users/ripple/work%20space/Lumina/src/lumina/config_core.py)