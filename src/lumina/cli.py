"""
CLI 命令行增强
添加向量搜索相关命令
"""

import json
from pathlib import Path
from typing import Optional
import click
from pprint import pprint

from lumina.harness import Harness, HarnessConfig
from lumina.config import LuminaConfig
from lumina.core.directory_monitor import DirectoryMonitor
from lumina.debug import run_debug_mode
from lumina.web_interface import WebInterface


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """Lumina - 知识萃取 Agent"""
    pass


@cli.command()
def debug():
    """进入 Lumina 调试模式（交互式）"""
    run_debug_mode()


@cli.command()
@click.argument('path', required=False, type=click.Path())
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--recursive', '-r', is_flag=True, default=None, help='递归扫描')
@click.option('--output', '-o', default=None, help='输出目录')
@click.option('--threshold', '-t', default=None, type=float, help='质量阈值')
@click.option('--incremental/--no-incremental', default=True, help='增量处理')
@click.option('--parallel/--no-parallel', default=True, help='并行处理')
@click.option('--vector/--no-vector', default=True, help='启用向量数据库')
@click.option('--planner-llm', default=None, help='Planner 的 LLM 配置 (JSON)')
@click.option('--executor-llm', default=None, help='Executor 的 LLM 配置 (JSON)')
@click.option('--validator-llm', default=None, help='Validator 的 LLM 配置 (JSON)')
def process(path, config, recursive, output, threshold, incremental, parallel, vector,
            planner_llm, executor_llm, validator_llm):
    """处理文件/目录，生成结构化笔记"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 解析各 Agent 的 LLM 配置（JSON 格式）
    import json
    planner_llm_config = json.loads(planner_llm) if planner_llm else None
    executor_llm_config = json.loads(executor_llm) if executor_llm else None
    validator_llm_config = json.loads(validator_llm) if validator_llm else None
    
    # 构建 Harness 配置
    harness_config = HarnessConfig(
        max_iterations=lumina_config.harness.get("max_iterations", 3),
        quality_threshold=threshold or lumina_config.harness.get("quality_threshold", 0.8),
        output_dir=output or str(lumina_config.output.resolve_base_dir()),
        vault_path=str(lumina_config.output.resolve_vault_path()) if lumina_config.output.vault_path else None,
        plugin=lumina_config.output.plugin,
        incremental=incremental,
        parallel=parallel,
        enable_vector_store=vector,
        llm_config=lumina_config.llm.to_dict(),  # 默认配置
        llm_config_planner=planner_llm_config or lumina_config.llm_planner,
        llm_config_executor=executor_llm_config or lumina_config.llm_executor,
        llm_config_validator=validator_llm_config or lumina_config.llm_validator,
    )
    
    # 构建待处理目标：优先使用命令行 path，否则从配置 input.sources 读取
    targets = []
    if path:
        target_path = Path(path).expanduser()
        if not target_path.exists():
            raise click.ClickException(f"路径不存在: {target_path}")
        effective_recursive = recursive if recursive is not None else lumina_config.default_recursive
        targets.append((str(target_path), effective_recursive))
    else:
        if not lumina_config.input_sources:
            raise click.ClickException(
                "未提供 path，且 ~/.lumina.yaml 中未配置 input.sources。"
                "请传入目录路径或先配置 input.sources。"
            )
        for source in lumina_config.input_sources:
            source_path = source.resolve_path()
            if not source_path.exists():
                click.echo(f"⚠️  跳过不存在的输入源: {source_path}")
                continue
            effective_recursive = recursive if recursive is not None else source.recursive
            targets.append((str(source_path), effective_recursive))

    if not targets:
        raise click.ClickException("没有可用的输入源可处理。")

    # 运行并汇总结果
    total_files = 0
    processed_files = 0
    failed_files = 0
    score_sum = 0.0
    score_count = 0
    last_harness = None

    for idx, (target_path, target_recursive) in enumerate(targets, start=1):
        if len(targets) > 1:
            click.echo(f"\n[{idx}/{len(targets)}] 处理: {target_path}")

        harness = Harness(harness_config)
        report = harness.run(target_path, recursive=target_recursive)
        last_harness = harness

        stats = report["statistics"]
        total_files += stats["total_files"]
        processed_files += stats["processed_files"]
        failed_files += stats["failed_files"]
        score_sum += stats["avg_score"] * max(stats["processed_files"], 1)
        score_count += max(stats["processed_files"], 1)

    avg_score = score_sum / score_count if score_count else 0.0

    click.echo(f"\n✅ 处理完成!")
    click.echo(f"总文件数: {total_files}")
    click.echo(f"已处理: {processed_files}")
    click.echo(f"失败数: {failed_files}")
    click.echo(f"平均得分: {avg_score:.2f}")

    if vector and last_harness and last_harness.vector_store:
        vector_stats = last_harness.get_vector_stats()
        click.echo(f"向量索引数: {vector_stats['total_documents']}")


@cli.command()
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--host', default='127.0.0.1', show_default=True, help='Web 服务监听地址')
@click.option('--port', default=5000, show_default=True, type=int, help='Web 服务端口')
@click.option('--watch/--no-watch', default=True, help='是否监听输入目录变化并自动更新')
@click.option('--initial-sync/--no-initial-sync', default=True, help='启动时是否先按配置执行一次全量/增量处理')
@click.option('--recursive', '-r', is_flag=True, default=None, help='覆盖配置中的递归设置')
@click.option('--output', '-o', default=None, help='覆盖输出目录')
@click.option('--threshold', '-t', default=None, type=float, help='质量阈值')
@click.option('--parallel/--no-parallel', default=True, help='并行处理')
@click.option('--vector/--no-vector', default=True, help='启用向量数据库')
def serve(config, host, port, watch, initial_sync, recursive, output, threshold, parallel, vector):
    """启动常驻服务：Web 界面 + 目录监听 + 自动整理"""

    lumina_config = LuminaConfig.load(config)

    if not lumina_config.input_sources:
        raise click.ClickException(
            "~/.lumina.yaml 中未配置 input.sources，无法启动常驻服务。"
        )

    harness_config = HarnessConfig(
        max_iterations=lumina_config.harness.get("max_iterations", 3),
        quality_threshold=threshold or lumina_config.harness.get("quality_threshold", 0.8),
        output_dir=output or str(lumina_config.output.resolve_base_dir()),
        vault_path=str(lumina_config.output.resolve_vault_path()) if lumina_config.output.vault_path else None,
        plugin=lumina_config.output.plugin,
        incremental=True,
        parallel=parallel,
        enable_vector_store=vector,
        llm_config=lumina_config.llm.to_dict(),
        llm_config_planner=lumina_config.llm_planner,
        llm_config_executor=lumina_config.llm_executor,
        llm_config_validator=lumina_config.llm_validator,
    )

    harness = Harness(harness_config)

    targets = []
    watch_dirs = []
    for source in lumina_config.input_sources:
        source_path = source.resolve_path()
        if not source_path.exists():
            click.echo(f"⚠️  跳过不存在的输入源: {source_path}")
            continue
        effective_recursive = recursive if recursive is not None else source.recursive
        targets.append((source_path, effective_recursive))
        if source_path.is_dir():
            watch_dirs.append(source_path)

    if not targets:
        raise click.ClickException("没有可用的 input.sources 可启动服务。")

    def run_target(target_path: Path, target_recursive: bool):
        click.echo(f"🔄 处理: {target_path}")
        return harness.run(str(target_path), recursive=target_recursive)

    if initial_sync:
        click.echo("🚀 启动初始化同步...")
        for target_path, target_recursive in targets:
            run_target(target_path, target_recursive)

    monitor = None
    if watch and watch_dirs:
        recursive_watch = recursive if recursive is not None else any(source.recursive for source in lumina_config.input_sources)

        def on_files_changed(files):
            click.echo(f"\n👀 检测到 {len(files)} 个文件变化，开始增量更新...")
            for changed_file in files:
                changed_path = Path(changed_file)
                if changed_path.exists() and changed_path.is_file():
                    try:
                        run_target(changed_path, False)
                    except Exception as exc:
                        click.echo(f"❌ 增量更新失败: {changed_path} -> {exc}")

        monitor = DirectoryMonitor(
            directories=watch_dirs,
            callback=on_files_changed,
            recursive=recursive_watch,
            debounce_seconds=2.0,
        )
        monitor.start()

    click.echo(f"🌐 Lumina 常驻服务已启动: http://{host}:{port}")
    click.echo("💡 停止服务请按 Ctrl+C")

    web = WebInterface(harness=harness, host=host, port=port)
    try:
        web.run(debug=False)
    finally:
        if monitor:
            monitor.stop()


@cli.command()
@click.argument('query')
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--n', '-n', default=5, type=int, help='返回结果数量')
@click.option('--output', '-o', default=None, help='输出文件路径')
def search(query, config, n, output):
    """语义搜索笔记"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 初始化 Harness
    harness_config = HarnessConfig(
        enable_vector_store=True,
        vector_store_persist_dir=lumina_config.output.base_dir + "/.lumina/vector_store",
    )
    
    harness = Harness(harness_config)
    
    if not harness.vector_store:
        click.echo("❌ 向量数据库不可用，请先运行 process 命令索引内容")
        return
    
    # 执行搜索
    results = harness.search_notes(query, n_results=n)
    
    if not results:
        click.echo("❌ 未找到相关结果")
        return
    
    # 输出结果
    click.echo(f"\n🔍 搜索结果 (共 {len(results)} 条):\n")
    
    for i, result in enumerate(results, 1):
        click.echo(f"{i}. 📄 {result['title']} (score: {result['score']:.2%})")
        click.echo(f"   🔗 {result['source']}")
        click.echo(f"   🏷️  Tags: {', '.join(result['tags'])}")
        click.echo(f"   📝 {result['content_preview']}")
        click.echo()
    
    # 保存到文件
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        click.echo(f"💾 结果已保存到: {output}")


@cli.command()
@click.argument('note_id')
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--min-score', '-s', default=0.7, type=float, help='最小相似度阈值')
@click.option('--n', '-n', default=5, type=int, help='返回结果数量')
def related(note_id, config, min_score, n):
    """查找关联笔记"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 初始化 Harness
    harness_config = HarnessConfig(
        enable_vector_store=True,
        vector_store_persist_dir=lumina_config.output.base_dir + "/.lumina/vector_store",
    )
    
    harness = Harness(harness_config)
    
    if not harness.vector_store:
        click.echo("❌ 向量数据库不可用，请先运行 process 命令索引内容")
        return
    
    # 查找关联
    results = harness.find_related_notes(note_id, min_score=min_score)
    
    if not results:
        click.echo("❌ 未找到关联笔记")
        return
    
    # 输出结果
    click.echo(f"\n🔗 关联笔记 (共 {len(results)} 条):\n")
    
    for i, result in enumerate(results, 1):
        click.echo(f"{i}. 📄 {result['title']} (score: {result['score']:.2%})")
        click.echo(f"   🔗 {result['source']}")
        click.echo(f"   🏷️  Tags: {', '.join(result['tags'])}")
        click.echo()


@cli.command()
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--output', '-o', default=None, help='输出文件路径')
@click.option('--min-similarity', '-s', default=0.7, type=float, help='最小相似度阈值')
def graph(config, output, min_similarity):
    """构建知识图谱"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 初始化 Harness
    harness_config = HarnessConfig(
        enable_vector_store=True,
        vector_store_persist_dir=lumina_config.output.base_dir + "/.lumina/vector_store",
    )
    
    harness = Harness(harness_config)
    
    if not harness.vector_store:
        click.echo("❌ 向量数据库不可用，请先运行 process 命令索引内容")
        return
    
    # 构建图谱
    graph_data = harness.build_knowledge_graph(min_similarity)
    
    stats = graph_data['stats']
    click.echo(f"\n📊 知识图谱构建完成:")
    click.echo(f"节点数: {stats['total_nodes']}")
    click.echo(f"边数: {stats['total_edges']}")
    click.echo(f"平均度数: {stats['avg_degree']:.2f}")
    
    # 保存到文件
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        click.echo(f"💾 图谱数据已保存到: {output}")


@cli.command()
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
def stats(config):
    """显示向量数据库统计信息"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 初始化 Harness
    harness_config = HarnessConfig(
        enable_vector_store=True,
        vector_store_persist_dir=lumina_config.output.base_dir + "/.lumina/vector_store",
    )
    
    harness = Harness(harness_config)
    
    if not harness.vector_store:
        click.echo("❌ 向量数据库不可用")
        return
    
    stats = harness.get_vector_stats()
    
    click.echo("\n📊 向量数据库统计:")
    for key, value in stats.items():
        click.echo(f"   {key}: {value}")
