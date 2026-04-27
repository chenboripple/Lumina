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
from lumina.debug import run_debug_mode


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
@click.argument('path', type=click.Path(exists=True))
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
    
    # 运行
    harness = Harness(harness_config)
    report = harness.run(path, recursive=recursive)
    
    # 输出简要报告
    click.echo(f"\n✅ 处理完成!")
    click.echo(f"总文件数: {report['statistics']['total_files']}")
    click.echo(f"已处理: {report['statistics']['processed_files']}")
    click.echo(f"平均得分: {report['statistics']['avg_score']:.2f}")
    
    if vector and harness.vector_store:
        vector_stats = harness.get_vector_stats()
        click.echo(f"向量索引数: {vector_stats['total_documents']}")


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
