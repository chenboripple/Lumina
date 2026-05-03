# Harness 模块文档

## 模块定位

Harness 是 Lumina 的主编排层，负责把 Planner、Executor、Validator、Cache、History、VectorStore 和输出插件连接起来。

它不只是“调用几个模块”，还承担了：

- 增量过滤
- 单文件/文档簇处理
- 迭代修复
- 输出保存与去重
- 历史记录
- 向量索引

## 主流程

当前 `run()` 的实际流程是：

```text
scan -> optional incremental filter -> plan -> process batches -> save outputs -> record history -> final report
```

更细一点：

```text
Planner.scan
  -> Harness._filter_incremental
  -> Planner.plan
  -> Harness._process_batches
  -> Harness._save_outputs
  -> Harness._record_history
  -> Harness._generate_final_report
```

## 核心配置

`HarnessConfig` 当前包含这些重要字段：

```python
@dataclass
class HarnessConfig:
    max_iterations: int = 3
    quality_threshold: float = 0.8
    output_dir: str = "./output"
    vault_path: Optional[str] = None
    plugin: str = "obsidian"
    use_cache: bool = True
    incremental: bool = True
    parallel: bool = True
    max_workers: int = 4
    stream_output: bool = False
    enable_history: bool = True
    quick_validation_first: bool = True
    allow_partial: bool = True
    metadata_prefix: str = "lumina_"
    enable_vector_store: bool = True
    supported_extensions: List[str] = field(default_factory=list)
    output_structure: Dict[str, bool] = field(default_factory=dict)
    note_organization: Dict[str, Any] = field(default_factory=dict)
    enable_clustering: bool = True
    enable_content_filter: bool = True
    enable_scene_detection: bool = True
```

补充说明：

- 增量开关在 Harness，而不是 Planner
- `llm_config_planner` / `llm_config_executor` / `llm_config_validator` 支持三套独立 LLM 配置
- `write_permission_rules` 与敏感内容检查会在保存阶段生效

## 单文件处理逻辑

`_process_single()` 是最关键的控制点。

### 普通文件

执行顺序：

1. 查处理结果缓存
2. 调用 Executor 生成内容
3. 如果被 `ContentFilter` 标记为 filtered，直接返回跳过
4. 快速验证
5. 完整验证
6. 根据建议迭代修复，直到达标或达到最大轮数
7. 缓存结果
8. 只有产出了结果，才会把文件标记为 processed

这最后一点很重要：失败或无输出文件不会被错误标记为已处理。

### 文档簇

当 `file_info.metadata["is_cluster"] = True` 时：

- 进入 `_execute_cluster()`
- 文档簇默认只处理一轮
- 不走普通文件那套多轮验证/修复链路

因此 cluster 是“Planner 预先决定好的聚合任务”，不是简单把多个文件塞进普通单文件流程。

## 增量处理

`_filter_incremental()` 使用 `FileChangeTracker` 判断内容是否发生变化。

当前策略：

- 内容未变：跳过并增加 `skipped_files`
- 检测异常：保守起见，仍继续处理

这和旧文档中“Planner 增量扫描”是两回事。

## 输出保存

`_save_outputs()` 当前有几条重要行为：

### 1. 追加模式

如果输出 metadata 中有 `is_append`：

- 优先写回 `append_to_path`
- 路径不存在时尝试按标题匹配已有笔记
- 直接把新内容追加到原笔记后面

### 2. 结构化目录写入

普通笔记会根据 Planner 写入的 `note_subdir` 落盘，例如：

- `工作/Projects`
- `学习/Resources`
- `Archive`

### 3. 去重与迁移

写入前会先尝试复用已有笔记：

- 先按 `source` 匹配 frontmatter 或内容
- 再按标题相似度兜底

如果找到的是旧平铺路径，而新规划已有 `note_subdir`，Harness 会迁移到新结构路径。

### 4. 输出插件

真正渲染 Markdown 的是插件系统：

- `obsidian`
- `plain`

Harness 会先补全 metadata，例如：

- `para`
- `lumina_score`
- `lumina_iterations`
- `lumina_best_round`
- `lumina_source`
- `lumina_processed_at`

## 历史记录与向量索引

### 历史记录

`_record_history()` 只记录真正产出 `final_output` 的结果。

### 向量索引

`_index_to_vector_store()` 同样只在存在 `final_output` 时执行，因此 filtered/no-output 结果不会污染向量库。

## 最终报告

`_generate_final_report()` 会汇总：

- `session_id`
- `status`
- `config`
- `statistics`
- `results`
- `errors`

其中 `statistics` 包括：

- `total_files`
- `processed_files`
- `skipped_files`
- `failed_files`
- `total_iterations`
- `cache_hits`
- `cache_misses`
- `cache_hit_rate`
- `avg_score`
- `score_distribution`

## 和旧文档容易冲突的点

- 主流程里没有“Planner 内部增量扫描”这一步
- cluster 不走完整多轮验证链路
- 只有成功产出笔记才会 mark processed
- 保存阶段会做 source 级去重、结构迁移和 append 回写，这些不是单纯的 `write file`

## 相关文件

- [src/lumina/harness.py](../../../src/lumina/harness.py)
- [src/lumina/executor.py](../../../src/lumina/executor.py)
- [src/lumina/planner.py](../../../src/lumina/planner.py)
- [src/lumina/plugins.py](../../../src/lumina/plugins.py)