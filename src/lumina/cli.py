"""
Lumina CLI - 命令行入口
连接配置系统，支持配置文件和命令行参数
"""

import click
from pathlib import Path
import json

from .harness import Harness, HarnessConfig
from .config import LuminaConfig


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Lumina - 知识萃取 Agent"""
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--recursive', '-r', is_flag=True, default=None, help='递归扫描')
@click.option('--output', '-o', default=None, help='输出目录')
@click.option('--threshold', '-t', default=None, type=float, help='质量阈值')
@click.option('--max-rounds', '-m', default=None, type=int, help='最大迭代轮数')
@click.option('--plugin', '-p', default=None, help='输出插件')
def scan(path, config, recursive, output, threshold, max_rounds, plugin):
    """扫描文件并生成笔记"""
    
    # 加载配置
    lumina_config = LuminaConfig.load(config)
    
    # 命令行参数覆盖配置文件
    if recursive is not None:
        pass  # 通过命令行传入
    else:
        recursive = True  # 默认
    
    # 构建 Harness 配置
    harness_config = HarnessConfig(
        output_dir=output or str(lumina_config.output.resolve_base_dir()),
        quality_threshold=threshold or lumina_config.harness.get("quality_threshold", 0.8),
        max_iterations=max_rounds or lumina_config.harness.get("max_iterations", 3),
        plugin=plugin or lumina_config.output.plugin,
        vault_path=lumina_config.output.vault_path,
    )
    
    # 传递 LLM 配置到 Executor
    harness = Harness(harness_config)
    harness.executor.llm_config = lumina_config.llm.to_dict()
    
    # 执行
    report = harness.run(path, recursive)
    
    # 打印报告
    click.echo("\n" + "="*50)
    click.echo("📊 Generation Report")
    click.echo("="*50)
    click.echo(f"Total files: {report['total_files']}")
    click.echo(f"Avg iterations: {report['avg_iterations']:.1f}")
    click.echo(f"Avg score: {report['avg_score']:.2f}")
    click.echo(f"Threshold: {report['threshold']}")
    
    # 保存报告
    report_path = Path(harness_config.output_dir) / "lumina_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    click.echo(f"\n📄 Report saved: {report_path}")


@cli.command()
@click.argument('config_path', type=click.Path(exists=True))
def config(config_path):
    """加载配置文件运行"""
    lumina_config = LuminaConfig.load(config_path)
    errors = lumina_config.validate()
    if errors:
        for err in errors:
            click.echo(f"❌ Config error: {err}", err=True)
        raise SystemExit(1)

    harness_config = HarnessConfig(
        max_iterations=lumina_config.harness.get("max_iterations", 3),
        quality_threshold=lumina_config.harness.get("quality_threshold", 0.8),
        output_dir=str(lumina_config.output.resolve_base_dir()),
        vault_path=lumina_config.output.vault_path,
        plugin=lumina_config.output.plugin,
    )
    harness = Harness(harness_config)
    harness.executor.llm_config = lumina_config.llm.to_dict()

    for source in lumina_config.input_sources:
        report = harness.run(str(source.resolve_path()), source.recursive)
        click.echo(f"✅ {source.path}: {report['total_files']} files processed")


@cli.command()
def init():
    """初始化用户配置"""
    config = LuminaConfig()
    config.save_user_config()
    click.echo(f"✅ 配置文件已创建: {Path.home() / '.lumina' / 'config.yaml'}")
    click.echo("请编辑配置文件设置您的 LLM API Key")


if __name__ == '__main__':
    cli()