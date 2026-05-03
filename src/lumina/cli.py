"""
CLI 命令行增强
添加向量搜索相关命令
"""

import json
import importlib.util
import importlib.metadata
import os
import socket
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import click
from pprint import pprint

from lumina.harness import Harness, HarnessConfig
from lumina.config_core import LuminaConfig
from lumina.core.directory_monitor import DirectoryMonitor
from lumina.debug import run_debug_mode
from lumina.web_interface import WebInterface


SERVICE_DIR = Path.home() / ".lumina"
SERVICE_PID_FILE = SERVICE_DIR / "service.pid"
SERVICE_META_FILE = SERVICE_DIR / "service.json"


RUNTIME_DEPENDENCIES_BASE = [
    ("PyPDF2", "PyPDF2"),
    ("pdfplumber", "pdfplumber"),
    ("PyMuPDF", "fitz"),
]

RUNTIME_DEPENDENCIES_VECTOR = [
    ("chromadb<0.5", "chromadb"),
    ("sentence-transformers", "sentence_transformers"),
]


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _is_chromadb_compatible() -> bool:
    """当前项目使用旧版 Chroma 客户端配置，需 chromadb<0.5。"""
    try:
        version = importlib.metadata.version("chromadb")
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        # 0.5+ 与 1.x API 均不兼容当前初始化方式
        if major >= 1:
            return False
        if major == 0 and minor >= 5:
            return False
        return True
    except Exception:
        return False


def _is_numpy_compatible_for_chromadb() -> bool:
    """chromadb 0.4.x 在本项目路径下需要 numpy<2。"""
    try:
        version = importlib.metadata.version("numpy")
        major = int(version.split(".")[0])
        return major < 2
    except Exception:
        return False


def _ensure_runtime_dependencies(enable_vector: bool = False) -> None:
    """运行前检查关键依赖，缺失时自动安装。"""
    deps = list(RUNTIME_DEPENDENCIES_BASE)
    if enable_vector:
        deps.extend(RUNTIME_DEPENDENCIES_VECTOR)

    missing = [pkg for pkg, module in deps if not _module_available(module)]

    # 版本兼容性检查：chromadb 必须 <0.5
    if enable_vector and _module_available("chromadb") and not _is_chromadb_compatible():
        missing.append("chromadb<0.5")

    # 兼容性检查：chromadb 0.4.x 与 numpy 2.x 不兼容
    if enable_vector and _module_available("chromadb") and not _is_numpy_compatible_for_chromadb():
        missing.append("numpy<2")

    if not missing:
        return

    # 去重并保持顺序
    dedup_missing = list(dict.fromkeys(missing))
    click.echo(f"📦 检测到缺失依赖，正在自动安装: {', '.join(dedup_missing)}")

    cmd = [sys.executable, "-m", "pip", "install", *dedup_missing]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(
            "自动安装依赖失败，请手动执行: "
            f"{sys.executable} -m pip install {' '.join(dedup_missing)}"
        )

    still_missing = [pkg for pkg, module in deps if not _module_available(module)]
    if still_missing:
        raise click.ClickException(
            "依赖安装后仍不可用: " + ", ".join(still_missing)
        )

    click.echo("✅ 运行依赖检查通过")


def _ensure_service_dir() -> None:
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)


def _get_service_log_file(ts: Optional[datetime] = None) -> Path:
    dt = ts or datetime.now()
    return SERVICE_DIR / f"service-{dt.strftime('%Y-%m-%d')}.log"


def _get_latest_service_log_file() -> Optional[Path]:
    logs = sorted(SERVICE_DIR.glob("service-*.log"))
    if not logs:
        return None
    return logs[-1]


def _cleanup_old_service_logs(retention_days: int) -> None:
    if retention_days < 0:
        return

    cutoff = datetime.now().date() - timedelta(days=retention_days)
    for log_file in SERVICE_DIR.glob("service-*.log"):
        date_text = log_file.stem.replace("service-", "", 1)
        try:
            log_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            continue

        if log_date < cutoff:
            try:
                log_file.unlink()
            except OSError:
                pass


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_service_meta() -> dict:
    if not SERVICE_META_FILE.exists():
        return {}
    try:
        return json.loads(SERVICE_META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_service_meta(meta: dict) -> None:
    _ensure_service_dir()
    SERVICE_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_service_files() -> None:
    for path in (SERVICE_PID_FILE, SERVICE_META_FILE):
        if path.exists():
            path.unlink()


def _get_running_service_pid() -> Optional[int]:
    if not SERVICE_PID_FILE.exists():
        return None
    try:
        pid = int(SERVICE_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        _clear_service_files()
        return None

    if _is_process_running(pid):
        return pid

    _clear_service_files()
    return None


def _build_serve_command(
    config, host, port, watch, initial_sync, recursive, output, threshold, parallel, vector
):
    command = [sys.executable, "-m", "lumina", "serve", "--host", host, "--port", str(port)]
    if config:
        command.extend(["--config", config])
    command.append("--watch" if watch else "--no-watch")
    command.append("--initial-sync" if initial_sync else "--no-initial-sync")
    if recursive:
        command.append("--recursive")
    if output:
        command.extend(["--output", output])
    if threshold is not None:
        command.extend(["--threshold", str(threshold)])
    command.append("--parallel" if parallel else "--no-parallel")
    command.append("--vector" if vector else "--no-vector")
    return command


def _stop_pid(pid: int) -> bool:
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0

        os.kill(pid, signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline:
            if not _is_process_running(pid):
                return True
            time.sleep(0.2)

        os.kill(pid, signal.SIGKILL)
        return not _is_process_running(pid)
    except OSError:
        return False


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
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--host', default='127.0.0.1', show_default=True, help='Web 服务监听地址')
@click.option('--port', default=5088, show_default=True, type=int, help='Web 服务端口')
@click.option('--watch/--no-watch', default=True, help='是否监听输入目录变化并自动更新')
@click.option('--initial-sync/--no-initial-sync', default=True, help='启动后是否在后台执行一次全量/增量处理')
@click.option('--recursive', '-r', is_flag=True, default=False, help='覆盖配置中的递归设置')
@click.option('--output', '-o', default=None, help='覆盖输出目录')
@click.option('--threshold', '-t', default=None, type=float, help='质量阈值')
@click.option('--parallel/--no-parallel', default=True, help='并行处理')
@click.option('--vector/--no-vector', default=True, help='启用向量数据库')
def start(config, host, port, watch, initial_sync, recursive, output, threshold, parallel, vector):
    """后台启动 Lumina 常驻服务"""

    lumina_config = LuminaConfig.load(config)
    _ensure_runtime_dependencies(enable_vector=vector)
    retention_raw = lumina_config.service.get("log_retention_days", 15) if isinstance(lumina_config.service, dict) else 15
    try:
        retention_days = max(0, int(retention_raw))
    except (TypeError, ValueError):
        raise click.ClickException("service.log_retention_days 必须是非负整数")

    existing_pid = _get_running_service_pid()
    if existing_pid:
        meta = _read_service_meta()
        click.echo(f"⚠️  Lumina 服务已在运行 (PID: {existing_pid})")
        if meta.get("url"):
            click.echo(f"   地址: {meta['url']}")
        return

    _ensure_service_dir()
    _cleanup_old_service_logs(retention_days)
    log_file = _get_service_log_file()
    command = _build_serve_command(
        config, host, port, watch, initial_sync, recursive, output, threshold, parallel, vector
    )

    log_handle = open(log_file, 'a', encoding='utf-8')
    try:
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                close_fds=True,
            )
        else:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
    finally:
        log_handle.close()

    # 启动后短暂自检，避免配置错误导致的秒退被误判为启动成功
    time.sleep(1.0)
    if process.poll() is not None:
        _clear_service_files()
        raise click.ClickException(
            f"后台服务启动失败，请检查日志: {log_file}"
        )

    SERVICE_PID_FILE.write_text(str(process.pid), encoding='utf-8')
    _write_service_meta({
        "pid": process.pid,
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "log_file": str(log_file),
        "log_retention_days": retention_days,
        "started_at": int(time.time()),
        "command": command,
    })

    click.echo(f"✅ Lumina 服务已后台启动 (PID: {process.pid})")
    click.echo(f"🌐 地址: http://{host}:{port}")
    click.echo(f"📝 日志: {log_file}")


@cli.command()
def stop():
    """停止后台 Lumina 服务"""

    pid = _get_running_service_pid()
    if not pid:
        click.echo("ℹ️  Lumina 服务未运行")
        return

    if _stop_pid(pid):
        _clear_service_files()
        click.echo(f"✅ Lumina 服务已停止 (PID: {pid})")
        return

    raise click.ClickException(f"停止服务失败 (PID: {pid})")


@cli.command()
def status():
    """查看 Lumina 服务运行状态"""

    pid = _get_running_service_pid()
    if not pid:
        click.echo("状态: stopped")
        latest_log = _get_latest_service_log_file()
        if latest_log:
            click.echo(f"最近日志: {latest_log}")
        return

    meta = _read_service_meta()
    click.echo("状态: running")
    click.echo(f"PID: {pid}")
    if meta.get("url"):
        click.echo(f"地址: {meta['url']}")
    if meta.get("started_at"):
        click.echo(f"启动时间戳: {meta['started_at']}")
    if meta.get("log_retention_days") is not None:
        click.echo(f"日志保留天数: {meta['log_retention_days']}")
    log_file = meta.get("log_file") or str(_get_service_log_file())
    click.echo(f"日志文件: {log_file}")


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
    _ensure_runtime_dependencies(enable_vector=vector)
    
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
        output_structure=lumina_config.output.structure,
        note_organization=lumina_config.output.note_organization,
        vault_path=str(lumina_config.output.resolve_vault_path()) if lumina_config.output.vault_path else None,
        plugin=lumina_config.output.plugin,
        supported_extensions=lumina_config.supported_extensions,
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
        targets.append((str(target_path), effective_recursive, None))
    else:
        if not lumina_config.input_sources:
            raise click.ClickException(
                "未提供 path，且 ~/.lumina/lumina.yaml 中未配置 input.sources。"
                "请传入目录路径或先配置 input.sources。"
            )
        for source in lumina_config.input_sources:
            source_path = source.resolve_path()
            if not source_path.exists():
                click.echo(f"⚠️  跳过不存在的输入源: {source_path}")
                continue
            effective_recursive = recursive if recursive is not None else source.recursive
            targets.append((str(source_path), effective_recursive, source.filter))

    if not targets:
        raise click.ClickException("没有可用的输入源可处理。")

    # 运行并汇总结果
    total_files = 0
    processed_files = 0
    failed_files = 0
    score_sum = 0.0
    score_count = 0
    last_harness = None

    for idx, (target_path, target_recursive, target_filter) in enumerate(targets, start=1):
        if len(targets) > 1:
            click.echo(f"\n[{idx}/{len(targets)}] 处理: {target_path}")

        harness = Harness(harness_config)
        report = harness.run(target_path, recursive=target_recursive, file_filter=target_filter)
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
@click.option('--port', default=5088, show_default=True, type=int, help='Web 服务端口')
@click.option('--watch/--no-watch', default=True, help='是否监听输入目录变化并自动更新')
@click.option('--initial-sync/--no-initial-sync', default=True, help='启动后是否在后台执行一次全量/增量处理')
@click.option('--recursive', '-r', is_flag=True, default=None, help='覆盖配置中的递归设置')
@click.option('--output', '-o', default=None, help='覆盖输出目录')
@click.option('--threshold', '-t', default=None, type=float, help='质量阈值')
@click.option('--parallel/--no-parallel', default=True, help='并行处理')
@click.option('--vector/--no-vector', default=True, help='启用向量数据库')
def serve(config, host, port, watch, initial_sync, recursive, output, threshold, parallel, vector):
    """启动常驻服务：Web 界面 + 目录监听 + 自动整理"""

    lumina_config = LuminaConfig.load(config)
    _ensure_runtime_dependencies(enable_vector=vector)

    if not lumina_config.input_sources:
        raise click.ClickException(
            "~/.lumina/lumina.yaml 中未配置 input.sources，无法启动常驻服务。"
        )

    harness_config = HarnessConfig(
        max_iterations=lumina_config.harness.get("max_iterations", 3),
        quality_threshold=threshold or lumina_config.harness.get("quality_threshold", 0.8),
        output_dir=output or str(lumina_config.output.resolve_base_dir()),
        vault_path=str(lumina_config.output.resolve_vault_path()) if lumina_config.output.vault_path else None,
        plugin=lumina_config.output.plugin,
        output_structure=lumina_config.output.structure,
        note_organization=lumina_config.output.note_organization,
        supported_extensions=lumina_config.supported_extensions,
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
        targets.append((source_path, effective_recursive, source.filter))
        if source_path.is_dir():
            watch_dirs.append(source_path)

    if not targets:
        raise click.ClickException("没有可用的 input.sources 可启动服务。")

    web = WebInterface(harness=harness, host=host, port=port, lumina_config=lumina_config)

    def run_target(target_path: Path, target_recursive: bool, target_filter: Optional[str] = None, mode: str = "processing"):
        click.echo(f"🔄 处理: {target_path}")
        web.report_runtime_activity(str(target_path), mode=mode)
        try:
            return harness.run(str(target_path), recursive=target_recursive, file_filter=target_filter)
        finally:
            web.clear_runtime_activity(str(target_path))

    def run_initial_sync_in_background():
        click.echo("🚀 后台初始化同步开始...")
        for target_path, target_recursive, target_filter in targets:
            try:
                run_target(target_path, target_recursive, target_filter, mode="initial_sync")
            except Exception as exc:
                click.echo(f"❌ 初始化同步失败: {target_path} -> {exc}")
        click.echo("✅ 后台初始化同步完成")

    def _wait_for_web_ready(timeout_seconds: float = 15.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, int(port))) == 0:
                    return True
            time.sleep(0.2)
        return False

    def run_initial_sync_after_web_ready():
        if not _wait_for_web_ready():
            click.echo("⚠️ Web 服务未在预期时间内就绪，仍继续后台初始化同步")
        run_initial_sync_in_background()

    monitor = None
    if watch and watch_dirs:
        recursive_watch = recursive if recursive is not None else any(source.recursive for source in lumina_config.input_sources)

        def on_files_changed(files):
            click.echo(f"\n👀 检测到 {len(files)} 个文件变化，开始增量更新...")
            for changed_file in files:
                changed_path = Path(changed_file)
                if changed_path.exists() and changed_path.is_file():
                    try:
                        run_target(changed_path, False, mode="incremental")
                    except Exception as exc:
                        click.echo(f"❌ 增量更新失败: {changed_path} -> {exc}")

        monitor = DirectoryMonitor(
            directories=watch_dirs,
            callback=on_files_changed,
            recursive=recursive_watch,
            debounce_seconds=2.0,
        )
        monitor.start()

    # 严格保证先开页面：仅在检测到 Web 端口就绪后才触发初始化同步。
    if initial_sync:
        sync_thread = threading.Thread(target=run_initial_sync_after_web_ready, daemon=True)
        sync_thread.start()

    click.echo(f"🌐 Lumina 常驻服务已启动: http://{host}:{port}")
    click.echo("💡 停止服务请按 Ctrl+C")

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
    _ensure_runtime_dependencies(enable_vector=True)
    
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
    _ensure_runtime_dependencies(enable_vector=True)
    
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
    _ensure_runtime_dependencies(enable_vector=True)
    
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
    _ensure_runtime_dependencies(enable_vector=True)
    
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
