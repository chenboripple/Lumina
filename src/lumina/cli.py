"""
Lumina CLI - 命令行入口
"""

import click
from pathlib import Path
import json

from .harness import Harness, HarnessConfig


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Lumina - 知识萃取 Agent"""
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, default=True, help='递归扫描')
@click.option('--output', '-o', default='./output', help='输出目录')
@click.option('--threshold', '-t', default=0.8, help='质量阈值')
@click.option('--max-rounds', '-m', default=3, help='最大迭代轮数')
def scan(path, recursive, output, threshold, max_rounds):
    """扫描文件并生成笔记"""
    
    config = HarnessConfig(
        output_dir=output,
        quality_threshold=threshold,
        max_iterations=max_rounds
    )
    
    harness = Harness(config)
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
    report_path = Path(output) / "lumina_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    click.echo(f"\n📄 Report saved: {report_path}")


@cli.command()
@click.argument('config_path', type=click.Path(exists=True))
def config(config_path):
    """加载配置文件运行"""
    import yaml
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    harness_config = HarnessConfig(**config_data.get('harness', {}))
    harness = Harness(harness_config)
    
    for source in config_data.get('sources', []):
        harness.run(source['path'], source.get('recursive', True))


if __name__ == '__main__':
    cli()