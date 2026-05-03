"""
Web Management Interface - Web管理界面
提供可视化操作、知识图谱展示、搜索界面、重新生成笔记
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps

# 尝试导入 Flask

try:
    from flask import Flask, render_template, jsonify, request, send_from_directory
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


from .planner import Planner
from .executor import Executor
from .validator import Validator
from .plugins import get_plugin
from .config_core import LuminaConfig, USER_CONFIG_FILE


class WebInterface:
    """
    Lumina Web管理界面
    
    功能：
    1. 📊 仪表板 - 处理统计、质量趋势
    2. 🔍 语义搜索 - 向量搜索界面
    3. 🕸️ 知识图谱 - 可视化展示
    4. 📝 笔记管理 - 查看、编辑、重新生成
    5. ⚙️ 配置管理 - 热加载配置
    6. 📈 实时监控 - 处理进度、日志
    """
    
    def __init__(self, harness=None, host='0.0.0.0', port=5088, lumina_config=None):
        self.harness = harness
        self.host = host
        self.port = port
        self.app = None
        self.lumina_config = lumina_config
        self._scan_state: Dict[str, Any] = {
            "running": False,
            "phase": "idle",
            "started_at": None,
            "last_event_at": None,
            "last_completed_at": None,
            "last_status": "idle",
            "message": "",
            "current_source": "",
            "current_source_index": -1,
            "sources_total": 0,
            "progress_percent": 0.0,
            "elapsed_seconds": 0.0,
            "eta_seconds": None,
            "rate_per_minute": 0.0,
            "source_counts": {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            },
            "file_counts": {
                "total": 0,
                "completed": 0,
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "pending": 0,
            },
            "failed_items": [],
            "queue": [],
            "_failure_counter": 0,
            "_scan_baseline": {
                "processed_files": 0,
                "failed_files": 0,
                "skipped_files": 0,
            },
            "_source_baseline": {
                "processed_files": 0,
                "failed_files": 0,
                "skipped_files": 0,
            },
        }
        self._scan_state_lock = threading.Lock()
        self._bootstrap_scan_state_from_history()
        
        if not FLASK_AVAILABLE:
            raise ImportError(
                "Flask not installed. Install with: pip install flask flask-cors"
            )
        
        self._init_app()
    
    def _init_app(self):
        """初始化 Flask 应用"""
        self.app = Flask(__name__, 
                        template_folder=self._get_template_dir(),
                        static_folder=self._get_static_dir())
        CORS(self.app)
        
        self._register_routes()
    
    def _get_template_dir(self) -> str:
        """获取模板目录"""
        return str(Path(__file__).parent / 'web' / 'templates')
    
    def _get_static_dir(self) -> str:
        """获取静态文件目录"""
        return str(Path(__file__).parent / 'web' / 'static')
    
    def _register_routes(self):
        """注册路由"""
        
        # 仪表板
        @self.app.route('/')
        def dashboard():
            """主仪表板"""
            stats = self._get_dashboard_stats()
            return render_template('dashboard.html', stats=stats)
        
        # API: 获取统计信息
        @self.app.route('/api/stats')
        def api_stats():
            """获取处理统计"""
            return jsonify(self._get_dashboard_stats())
        
        # API: 搜索
        @self.app.route('/api/search', methods=['POST'])
        def api_search():
            """语义搜索"""
            data = request.get_json()
            query = data.get('query', '')
            n_results = data.get('n_results', 10)
            
            if not self.harness or not self.harness.vector_store:
                return jsonify({"error": "Vector store not available"}), 503
            
            try:
                results = self.harness.search_notes(query, n_results)
                return jsonify({
                    "query": query,
                    "results": results,
                    "total": len(results)
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 知识图谱
        @self.app.route('/api/graph')
        def api_graph():
            """获取知识图谱数据"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503
            
            try:
                min_similarity = request.args.get('min_similarity', 0.7, type=float)
                graph = self.harness.build_knowledge_graph(min_similarity)
                return jsonify(graph)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 笔记列表
        @self.app.route('/api/notes')
        def api_notes():
            """获取笔记列表"""
            try:
                output_dir = Path(self.harness.config.output_dir) if self.harness else Path("./output")
                notes = []
                
                if output_dir.exists():
                    for md_file in output_dir.rglob("*.md"):
                        stat = md_file.stat()
                        notes.append({
                            "id": str(md_file.relative_to(output_dir)),
                            "path": str(md_file),
                            "title": md_file.stem,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        })
                
                return jsonify({
                    "notes": notes,
                    "total": len(notes)
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 获取单个笔记
        @self.app.route('/api/notes/<path:note_id>')
        def api_note_detail(note_id):
            """获取笔记详情"""
            try:
                output_dir = Path(self.harness.config.output_dir) if self.harness else Path("./output")
                note_path = output_dir / note_id
                
                if not note_path.exists():
                    return jsonify({"error": "Note not found"}), 404
                
                content = note_path.read_text(encoding='utf-8')
                
                # 解析 frontmatter
                metadata = {}
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        import yaml
                        metadata = yaml.safe_load(parts[1]) or {}
                        content = parts[2].strip()
                
                return jsonify({
                    "id": note_id,
                    "title": metadata.get('title', note_path.stem),
                    "content": content,
                    "metadata": metadata,
                    "source_path": metadata.get('source'),
                    "tags": metadata.get('tags', []),
                    "links": metadata.get('links', [])
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # API: 按源文件路径获取笔记
        @self.app.route('/api/notes/by-source')
        def api_note_detail_by_source():
            """按 source 路径查找并返回笔记详情。"""
            try:
                source_path = (request.args.get('source') or '').strip()
                if not source_path:
                    return jsonify({"error": "source query is required"}), 400

                output_dir = Path(self.harness.config.output_dir) if self.harness else Path("./output")
                if not output_dir.exists():
                    return jsonify({"error": "Note not found"}), 404

                source_normalized = str(Path(source_path).expanduser().resolve())

                for md_file in output_dir.rglob("*.md"):
                    try:
                        content = md_file.read_text(encoding='utf-8')
                    except Exception:
                        continue

                    metadata = {}
                    body = content
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            try:
                                import yaml
                                metadata = yaml.safe_load(parts[1]) or {}
                                body = parts[2].strip()
                            except Exception:
                                metadata = {}

                    candidate_source = str(metadata.get('source', '')).strip()
                    if not candidate_source:
                        continue

                    try:
                        candidate_normalized = str(Path(candidate_source).expanduser().resolve())
                    except Exception:
                        candidate_normalized = candidate_source

                    if candidate_normalized != source_normalized:
                        continue

                    note_id = str(md_file.relative_to(output_dir))
                    return jsonify({
                        "id": note_id,
                        "title": metadata.get('title', md_file.stem),
                        "content": body,
                        "metadata": metadata,
                        "source_path": metadata.get('source'),
                        "tags": metadata.get('tags', []),
                        "links": metadata.get('links', [])
                    })

                return jsonify({"error": "Note not found"}), 404
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 重新生成笔记
        @self.app.route('/api/notes/<path:note_id>/regenerate', methods=['POST'])
        def api_regenerate_note(note_id):
            """重新生成笔记"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503
            
            try:
                data = request.get_json() or {}
                source_path = data.get('source_path')

                if not source_path:
                    return jsonify({"error": "source_path is required"}), 400

                source_file = Path(source_path).expanduser().resolve()
                if not source_file.exists():
                    return jsonify({"error": "Source file not found"}), 404
                return jsonify(self._regenerate_source_file(source_file))
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # API: 按指定源文件重新生成
        @self.app.route('/api/regenerate-source', methods=['POST'])
        def api_regenerate_source():
            """按源文件路径重新生成笔记"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503

            try:
                data = request.get_json() or {}
                source_path = data.get('source_path')

                if not source_path:
                    return jsonify({"error": "source_path is required"}), 400

                source_file = Path(source_path).expanduser().resolve()
                if not source_file.exists():
                    return jsonify({"error": "Source file not found"}), 404

                return jsonify(self._regenerate_source_file(source_file))
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 批量修复
        @self.app.route('/api/scan', methods=['POST'])
        def api_scan():
            """触发全量扫描并在后台处理所有配置的输入源"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503
            if not self.lumina_config:
                return jsonify({"error": "Config not available"}), 503
            if self._scan_state["running"]:
                return jsonify({"error": "扫描已在进行中，请稍后再试"}), 409

            data = request.get_json() or {}
            incremental = data.get("incremental", True)

            sources = list(self.lumina_config.input_sources or [])
            queue = []
            for source in sources:
                queue.append({
                    "source": str(source.resolve_path()),
                    "status": "pending",
                    "total_files": 0,
                    "processed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "completed": 0,
                    "progress_percent": 0.0,
                })

            baseline = self.harness.get_state() if self.harness else {}
            self._scan_state.update({
                "running": False,
                "phase": "queued",
                "started_at": None,
                "last_event_at": datetime.now().isoformat(),
                "message": "准备扫描...",
                "current_source": "",
                "current_source_index": -1,
                "sources_total": len(queue),
                "progress_percent": 0.0,
                "elapsed_seconds": 0.0,
                "eta_seconds": None,
                "rate_per_minute": 0.0,
                "source_counts": {
                    "pending": len(queue),
                    "processing": 0,
                    "completed": 0,
                    "failed": 0,
                },
                "file_counts": {
                    "total": 0,
                    "completed": 0,
                    "processed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "pending": 0,
                },
                "failed_items": [],
                "queue": queue,
                "_failure_counter": 0,
                "_scan_baseline": {
                    "processed_files": baseline.get("processed_files", 0),
                    "failed_files": baseline.get("failed_files", 0),
                    "skipped_files": baseline.get("skipped_files", 0),
                },
                "_source_baseline": {
                    "processed_files": baseline.get("processed_files", 0),
                    "failed_files": baseline.get("failed_files", 0),
                    "skipped_files": baseline.get("skipped_files", 0),
                },
            })

            def _do_scan():
                self._scan_state["running"] = True
                self._scan_state["phase"] = "running"
                self._scan_state["started_at"] = datetime.now().isoformat()
                self._scan_state["last_event_at"] = self._scan_state["started_at"]
                self._scan_state["message"] = "扫描中..."
                try:
                    for idx, source in enumerate(self.lumina_config.input_sources):
                        target_path = source.resolve_path()
                        recursive = getattr(source, "recursive", True)
                        file_filter = getattr(source, "filter", None)
                        self._scan_state["current_source"] = str(target_path)
                        self._scan_state["current_source_index"] = idx
                        if idx < len(self._scan_state["queue"]):
                            self._scan_state["queue"][idx]["status"] = "processing"

                        source_baseline = self.harness.get_state() if self.harness else {}
                        self._scan_state["_source_baseline"] = {
                            "processed_files": source_baseline.get("processed_files", 0),
                            "failed_files": source_baseline.get("failed_files", 0),
                            "skipped_files": source_baseline.get("skipped_files", 0),
                        }
                        source_error_index = len(getattr(self.harness.state, "errors", [])) if self.harness else 0

                        if not incremental:
                            orig = self.harness.config.incremental
                            self.harness.config.incremental = False
                        try:
                            report = self.harness.run(str(target_path), recursive=recursive, file_filter=file_filter)

                            stats = report.get("statistics", {}) if isinstance(report, dict) else {}
                            after_state = self.harness.get_state() if self.harness else {}
                            total_files = int(stats.get("total_files", 0) or after_state.get("total_files", 0) or 0)
                            processed_files = max(0, int(after_state.get("processed_files", 0)) - int(source_baseline.get("processed_files", 0)))
                            failed_files = max(0, int(after_state.get("failed_files", 0)) - int(source_baseline.get("failed_files", 0)))
                            skipped_files = max(0, int(after_state.get("skipped_files", 0)) - int(source_baseline.get("skipped_files", 0)))

                            if idx < len(self._scan_state["queue"]):
                                item = self._scan_state["queue"][idx]
                                item["total_files"] = total_files
                                item["processed"] = processed_files
                                item["failed"] = failed_files
                                item["skipped"] = skipped_files
                                item["completed"] = processed_files + failed_files + skipped_files
                                item["progress_percent"] = (
                                    (item["completed"] / total_files) * 100.0 if total_files > 0 else 100.0
                                )
                                item["status"] = "failed" if str(report.get("status", "")).lower() == "failed" else "completed"

                            current_errors = list(getattr(self.harness.state, "errors", [])) if self.harness else []
                            for error in current_errors[source_error_index:]:
                                self._append_failed_item(
                                    source=str(target_path),
                                    file=error.get("file", str(target_path)),
                                    message=error.get("message") or error.get("error") or str(error),
                                )
                        finally:
                            if not incremental:
                                self.harness.config.incremental = orig
                    self._scan_state["phase"] = "completed"
                    self._scan_state["last_status"] = "completed"
                    self._scan_state["last_completed_at"] = datetime.now().isoformat()
                    self._scan_state["last_event_at"] = self._scan_state["last_completed_at"]
                    self._scan_state["message"] = "扫描完成"
                except Exception as exc:
                    idx = self._scan_state.get("current_source_index", -1)
                    if isinstance(idx, int) and idx >= 0 and idx < len(self._scan_state["queue"]):
                        self._scan_state["queue"][idx]["status"] = "failed"
                    self._append_failed_item(
                        source=self._scan_state.get("current_source") or "",
                        file=self._scan_state.get("current_source") or "",
                        message=str(exc),
                    )
                    self._scan_state["phase"] = "failed"
                    self._scan_state["last_status"] = "failed"
                    self._scan_state["last_event_at"] = datetime.now().isoformat()
                    self._scan_state["message"] = f"扫描出错: {exc}"
                finally:
                    self._scan_state["current_source"] = ""
                    self._scan_state["current_source_index"] = -1
                    self._scan_state["running"] = False
                    self._refresh_scan_state_runtime()

            t = threading.Thread(target=_do_scan, daemon=True)
            t.start()
            return jsonify({"success": True, "message": "扫描已在后台启动"})

        @self.app.route('/api/scan/status')
        def api_scan_status():
            """获取当前扫描状态"""
            self._refresh_scan_state_runtime()
            public = {k: v for k, v in self._scan_state.items() if not k.startswith("_")}
            return jsonify(public)

        @self.app.route('/api/scan/failures/regenerate', methods=['POST'])
        def api_scan_failures_regenerate():
            """批量重生成失败项对应的源文件。"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503

            data = request.get_json() or {}
            ids = set(data.get("ids", []))
            if not ids:
                return jsonify({"error": "ids is required"}), 400

            details = []
            success_count = 0
            failed_count = 0

            for item in self._scan_state.get("failed_items", []):
                if item.get("id") not in ids:
                    continue

                file_path = Path(str(item.get("file", ""))).expanduser()
                if not file_path.exists() or not file_path.is_file():
                    item["status"] = "retry_failed"
                    item["last_error"] = "File not found or not a file"
                    details.append({"id": item.get("id"), "success": False, "message": item["last_error"]})
                    failed_count += 1
                    continue

                result = self._regenerate_source_file(file_path)
                ok = bool(result.get("success"))
                item["status"] = "resolved" if ok else "retry_failed"
                item["last_retry_at"] = datetime.now().isoformat()
                item["last_error"] = "" if ok else str(result.get("message", "Failed to regenerate"))
                details.append({
                    "id": item.get("id"),
                    "success": ok,
                    "message": result.get("message", ""),
                    "source": result.get("source", str(file_path)),
                })
                if ok:
                    success_count += 1
                else:
                    failed_count += 1

            return jsonify({
                "total": success_count + failed_count,
                "success": success_count,
                "failed": failed_count,
                "details": details,
            })

        @self.app.route('/api/scan/failures/delete', methods=['POST'])
        def api_scan_failures_delete():
            """从失败列表中批量删除失败项记录。"""
            data = request.get_json() or {}
            ids = set(data.get("ids", []))
            if not ids:
                return jsonify({"error": "ids is required"}), 400

            before = len(self._scan_state.get("failed_items", []))
            self._scan_state["failed_items"] = [
                item for item in self._scan_state.get("failed_items", [])
                if item.get("id") not in ids
            ]
            deleted = before - len(self._scan_state.get("failed_items", []))
            return jsonify({"deleted": deleted, "remaining": len(self._scan_state.get("failed_items", []))})

        @self.app.route('/api/scan/failures/tag', methods=['POST'])
        def api_scan_failures_tag():
            """为失败项批量打标签。"""
            data = request.get_json() or {}
            ids = set(data.get("ids", []))
            tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
            if not ids:
                return jsonify({"error": "ids is required"}), 400
            if not tags:
                return jsonify({"error": "tags is required"}), 400

            updated = 0
            for item in self._scan_state.get("failed_items", []):
                if item.get("id") not in ids:
                    continue
                existing = set(item.get("tags", []))
                existing.update(tags)
                item["tags"] = sorted(existing)
                updated += 1

            return jsonify({"updated": updated, "tags": tags})

        @self.app.route('/api/batch-repair', methods=['POST'])
        def api_batch_repair():
            """批量修复低质量笔记"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503
            
            try:
                data = request.get_json() or {}
                min_score = data.get('min_score', 0.6)
                
                # 获取历史记录中低质量的笔记
                low_quality_notes = self._get_low_quality_notes(min_score)
                
                repaired = []
                for note in low_quality_notes:
                    # 重新处理
                    result = self._reprocess_note(note)
                    repaired.append({
                        "note_id": note["id"],
                        "old_score": note["score"],
                        "new_score": result.get("best_score", 0),
                        "success": result.get("success", False)
                    })
                
                return jsonify({
                    "total": len(low_quality_notes),
                    "repaired": len([r for r in repaired if r["success"]]),
                    "failed": len([r for r in repaired if not r["success"]]),
                    "details": repaired
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 配置管理
        @self.app.route('/api/config', methods=['GET', 'POST'])
        def api_config():
            """获取/更新配置"""
            if request.method == 'GET':
                return jsonify(self._build_grouped_config_response())
            
            else:  # POST
                data = request.get_json() or {}
                try:
                    applied = self._apply_grouped_config_updates(data)
                    return jsonify({"message": "Config updated", "changes": applied})
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
                except Exception as exc:
                    return jsonify({"error": str(exc)}), 500
        
        # API: 处理状态
        @self.app.route('/api/status')
        def api_status():
            """获取当前处理状态"""
            if not self.harness:
                return jsonify({"status": "idle"})
            
            state = self.harness.get_state()
            return jsonify(state)
        
        # API: 向量统计
        @self.app.route('/api/vector-stats')
        def api_vector_stats():
            """获取向量数据库统计"""
            if not self.harness:
                return jsonify({"error": "Harness not available"}), 503
            
            stats = self.harness.get_vector_stats()
            return jsonify(stats)
        
        # 静态文件服务
        @self.app.route('/static/<path:filename>')
        def serve_static(filename):
            """提供静态文件"""
            return send_from_directory(self._get_static_dir(), filename)

    def _resolve_allowed_source(self, source_path: Path):
        """根据当前配置判断源文件是否允许重新生成，并返回匹配到的输入源规则。"""
        if not self.lumina_config:
            return None

        if not Planner.is_supported_extension(source_path, self.lumina_config.supported_extensions):
            return None

        for source in self.lumina_config.input_sources:
            source_root = source.resolve_path().resolve()
            if source_root.is_file():
                matches_root = source_root == source_path
            else:
                matches_root = source_path == source_root or source_root in source_path.parents

            if not matches_root:
                continue

            filter_root = source_root.parent if source_root.is_file() else source_root
            if Planner.matches_file_filter(source_path, filter_root, source.filter):
                return source_root, source.filter

        return None

    def _regenerate_source_file(self, source_file: Path) -> Dict[str, Any]:
        """按单个源文件重新生成并保存笔记。"""
        allowed_source = self._resolve_allowed_source(source_file)
        if not allowed_source:
            return {
                "success": False,
                "message": "Source file is not allowed by current input.sources configuration",
            }

        _, source_filter = allowed_source
        scanned = self.harness.planner.scan(
            str(source_file),
            recursive=False,
            file_filter=source_filter,
            supported_extensions=self.harness.config.supported_extensions,
        )
        if not scanned:
            return {
                "success": False,
                "message": "Source file is filtered out by current filter or supported_extensions settings",
            }

        file_info = scanned[0]
        plan = {"strategy": "direct", "batches": [[file_info]]}
        result = self.harness._process_single(file_info, plan)

        if result.get("processed") and result.get("final_output"):
            # 复用 Harness 保存逻辑，确保按插件规则写回目标目录
            self.harness._save_outputs([result])

        return {
            "success": result.get("success", False),
            "processed": result.get("processed", False),
            "score": result.get("best_score", 0),
            "iterations": result.get("iterations", 0),
            "source": str(source_file),
            "message": "Note regenerated successfully" if result.get("success") else "Failed to regenerate",
        }

    def _sanitize_llm_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cfg = dict(config or {})
        cfg.pop("api_key", None)
        return cfg

    def _mask_secret(self, value: Optional[str]) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if len(text) <= 10:
            return "*" * len(text)
        return f"{text[:4]}...{text[-4:]}"

    def _read_user_config_text(self) -> str:
        try:
            if USER_CONFIG_FILE.exists():
                return USER_CONFIG_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    def _build_full_llm_config(self, config_obj: Any) -> Dict[str, Any]:
        if config_obj is None:
            return {}
        if isinstance(config_obj, dict):
            return dict(config_obj)
        return {
            "provider": getattr(config_obj, "provider", None),
            "base_url": getattr(config_obj, "base_url", None),
            "api_key": getattr(config_obj, "api_key", None),
            "model": getattr(config_obj, "model", None),
            "temperature": getattr(config_obj, "temperature", None),
            "max_tokens": getattr(config_obj, "max_tokens", None),
            "timeout": getattr(config_obj, "timeout", None),
            "max_retries": getattr(config_obj, "max_retries", None),
            "retry_delay": getattr(config_obj, "retry_delay", None),
        }

    def _reload_runtime_from_lumina_config(self):
        if not self.harness or not self.lumina_config:
            return

        cfg = self.lumina_config
        harness_cfg = self.harness.config

        harness_cfg.max_iterations = int(cfg.harness.get("max_iterations", harness_cfg.max_iterations))
        harness_cfg.quality_threshold = float(cfg.harness.get("quality_threshold", harness_cfg.quality_threshold))
        harness_cfg.output_dir = str(cfg.output.resolve_base_dir())
        harness_cfg.vault_path = str(cfg.output.resolve_vault_path()) if cfg.output.vault_path else None
        harness_cfg.plugin = cfg.output.plugin
        harness_cfg.supported_extensions = list(cfg.supported_extensions)
        harness_cfg.output_structure = dict(cfg.output.structure)
        harness_cfg.note_organization = dict(cfg.output.note_organization)
        harness_cfg.llm_config = self._build_full_llm_config(cfg.llm)
        harness_cfg.llm_config_planner = dict(cfg.llm_planner or {}) if cfg.llm_planner else None
        harness_cfg.llm_config_executor = dict(cfg.llm_executor or {}) if cfg.llm_executor else None
        harness_cfg.llm_config_validator = dict(cfg.llm_validator or {}) if cfg.llm_validator else None

        self.harness.plugin = get_plugin(str(harness_cfg.plugin))
        self.harness.planner = Planner(
            cache_manager=self.harness.cache,
            history_manager=self.harness.history,
            llm_config=harness_cfg.get_llm_config_for('planner'),
            enable_clustering=harness_cfg.enable_clustering,
            output_structure=harness_cfg.output_structure,
            note_organization=harness_cfg.note_organization,
        )
        self.harness.executor = Executor(
            llm_config=harness_cfg.get_llm_config_for('executor'),
            cache_manager=self.harness.cache,
            history_manager=self.harness.history,
            enable_content_filter=harness_cfg.enable_content_filter,
            enable_scene_detection=harness_cfg.enable_scene_detection,
        )
        self.harness.validator = Validator(
            history_manager=self.harness.history,
            llm_config=harness_cfg.get_llm_config_for('validator')
        )

    def _build_grouped_config_response(self) -> Dict[str, Any]:
        harness_cfg = self.harness.config if self.harness else None
        state = self.harness.get_state() if self.harness else {}

        system_fixed = {
            "config_schema_version": "v2-grouped-config",
            "supported_agents": ["planner", "executor", "validator", "harness"],
            "planner_defaults": {
                "para_categories": dict(Planner.PARA_CATEGORY_MAP),
                "batch_sizes": dict(Planner.BATCH_SIZES),
                "type_priority": dict(Planner.TYPE_PRIORITY),
            },
        }

        system_runtime = {
            "status": state.get("status", "idle"),
            "session_id": state.get("session_id", ""),
            "output_dir": str(harness_cfg.output_dir) if harness_cfg else "",
            "vector_store_enabled": bool(getattr(harness_cfg, "enable_vector_store", False)) if harness_cfg else False,
        }

        service_cfg = {}
        if self.lumina_config:
            service_cfg = dict(self.lumina_config.service or {})

        agent_user = {
            "harness": {
                "max_iterations": getattr(harness_cfg, "max_iterations", 3) if harness_cfg else 3,
                "quality_threshold": getattr(harness_cfg, "quality_threshold", 0.8) if harness_cfg else 0.8,
                "incremental": bool(getattr(harness_cfg, "incremental", True)) if harness_cfg else True,
                "parallel": bool(getattr(harness_cfg, "parallel", True)) if harness_cfg else True,
                "max_workers": int(getattr(harness_cfg, "max_workers", 4)) if harness_cfg else 4,
                "enable_vector_store": bool(getattr(harness_cfg, "enable_vector_store", True)) if harness_cfg else True,
            },
            "llm_shared": self.lumina_config.llm.to_dict() if self.lumina_config else {},
            "llm_planner": self._sanitize_llm_config(self.lumina_config.llm_planner if self.lumina_config else None),
            "llm_executor": self._sanitize_llm_config(self.lumina_config.llm_executor if self.lumina_config else None),
            "llm_validator": self._sanitize_llm_config(self.lumina_config.llm_validator if self.lumina_config else None),
        }

        user_preferences = {
            "input": {
                "default_recursive": bool(self.lumina_config.default_recursive) if self.lumina_config else True,
                "supported_extensions": list(self.lumina_config.supported_extensions) if self.lumina_config else [],
                "sources": [
                    {
                        "path": src.path,
                        "recursive": bool(src.recursive),
                        "filter": src.filter,
                    }
                    for src in (self.lumina_config.input_sources if self.lumina_config else [])
                ],
            },
            "output": {
                "plugin": self.lumina_config.output.plugin if self.lumina_config else "obsidian",
                "base_dir": self.lumina_config.output.base_dir if self.lumina_config else "",
                "vault_path": self.lumina_config.output.vault_path if self.lumina_config else "",
                "structure": dict(self.lumina_config.output.structure) if self.lumina_config else {},
                "naming": dict(self.lumina_config.output.naming) if self.lumina_config else {},
                "note_organization": dict(self.lumina_config.output.note_organization) if self.lumina_config else {},
            },
        }

        current_snapshot = {
            "input": user_preferences["input"],
            "output": user_preferences["output"],
            "harness": dict(self.lumina_config.harness or {}) if self.lumina_config else {},
            "service": service_cfg,
            "llm": {
                **(self.lumina_config.llm.to_dict() if self.lumina_config else {}),
                "api_key_masked": self._mask_secret(self.lumina_config.llm.api_key if self.lumina_config else ""),
            },
            "llm_planner": {
                **self._sanitize_llm_config(self.lumina_config.llm_planner if self.lumina_config else None),
                "api_key_masked": self._mask_secret((self.lumina_config.llm_planner or {}).get("api_key", "") if self.lumina_config else ""),
            } if (self.lumina_config and self.lumina_config.llm_planner) else {},
            "llm_executor": {
                **self._sanitize_llm_config(self.lumina_config.llm_executor if self.lumina_config else None),
                "api_key_masked": self._mask_secret((self.lumina_config.llm_executor or {}).get("api_key", "") if self.lumina_config else ""),
            } if (self.lumina_config and self.lumina_config.llm_executor) else {},
            "llm_validator": {
                **self._sanitize_llm_config(self.lumina_config.llm_validator if self.lumina_config else None),
                "api_key_masked": self._mask_secret((self.lumina_config.llm_validator or {}).get("api_key", "") if self.lumina_config else ""),
            } if (self.lumina_config and self.lumina_config.llm_validator) else {},
        }

        return {
            "system_config": {
                "fixed": system_fixed,
                "runtime": system_runtime,
                "service": service_cfg,
            },
            "agent_config": {
                "user_defined": agent_user,
            },
            "user_preferences": user_preferences,
            "current_snapshot": current_snapshot,
            "raw_user_config": self._read_user_config_text(),
        }

    def _apply_grouped_config_updates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.harness:
            raise ValueError("Harness not available")
        if not self.lumina_config:
            raise ValueError("Lumina config not available")

        raw_user_config = payload.get("raw_user_config") if isinstance(payload, dict) else None
        if isinstance(raw_user_config, str) and raw_user_config.strip():
            USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            USER_CONFIG_FILE.write_text(raw_user_config, encoding="utf-8")
            self.lumina_config = LuminaConfig.load(str(USER_CONFIG_FILE))
            self._reload_runtime_from_lumina_config()
            return {"raw_user_config": "updated"}

        applied: Dict[str, Any] = {"system_config": {}, "agent_config": {}, "user_preferences": {}}

        # System/service config
        system_cfg = payload.get("system_config", {}) if isinstance(payload, dict) else {}
        service_cfg = system_cfg.get("service", {}) if isinstance(system_cfg, dict) else {}
        if isinstance(service_cfg, dict) and "log_retention_days" in service_cfg:
            days = int(service_cfg.get("log_retention_days", 15))
            days = max(0, days)
            self.lumina_config.service["log_retention_days"] = days
            applied["system_config"]["service"] = {"log_retention_days": days}

        # Agent user config
        agent_cfg = payload.get("agent_config", {}) if isinstance(payload, dict) else {}
        agent_user = agent_cfg.get("user_defined", {}) if isinstance(agent_cfg, dict) else {}
        harness_user = agent_user.get("harness", {}) if isinstance(agent_user, dict) else {}
        if isinstance(harness_user, dict):
            field_map = {
                "max_iterations": int,
                "quality_threshold": float,
                "incremental": bool,
                "parallel": bool,
                "max_workers": int,
                "enable_vector_store": bool,
            }
            changed = {}
            for key, caster in field_map.items():
                if key not in harness_user:
                    continue
                value = caster(harness_user.get(key))
                if key == "max_iterations":
                    value = max(1, min(10, value))
                if key == "quality_threshold":
                    value = max(0.0, min(1.0, value))
                setattr(self.harness.config, key, value)
                self.lumina_config.harness[key] = value
                changed[key] = value
            if changed:
                applied["agent_config"]["harness"] = changed

        llm_shared = agent_user.get("llm_shared", {}) if isinstance(agent_user, dict) else {}
        if isinstance(llm_shared, dict) and llm_shared:
            for key in ["provider", "base_url", "model", "temperature", "max_tokens", "timeout", "max_retries", "retry_delay"]:
                if key in llm_shared:
                    setattr(self.lumina_config.llm, key, llm_shared[key])
            applied["agent_config"]["llm_shared"] = self.lumina_config.llm.to_dict()

        for agent_key in ["llm_planner", "llm_executor", "llm_validator"]:
            update_val = agent_user.get(agent_key, {}) if isinstance(agent_user, dict) else {}
            if not isinstance(update_val, dict):
                continue
            base_cfg = dict(getattr(self.lumina_config, agent_key) or {})
            for key in ["provider", "base_url", "model", "temperature", "max_tokens", "timeout", "max_retries", "retry_delay"]:
                if key in update_val:
                    base_cfg[key] = update_val[key]
            setattr(self.lumina_config, agent_key, base_cfg if base_cfg else None)
            if base_cfg:
                applied["agent_config"][agent_key] = self._sanitize_llm_config(base_cfg)

        # User preferences
        user_pref = payload.get("user_preferences", {}) if isinstance(payload, dict) else {}
        input_pref = user_pref.get("input", {}) if isinstance(user_pref, dict) else {}
        if isinstance(input_pref, dict):
            changed_input = {}
            if "default_recursive" in input_pref:
                value = bool(input_pref.get("default_recursive"))
                self.lumina_config.default_recursive = value
                changed_input["default_recursive"] = value
            if "supported_extensions" in input_pref and isinstance(input_pref.get("supported_extensions"), list):
                value = [str(ext) for ext in input_pref.get("supported_extensions", []) if str(ext).strip()]
                self.lumina_config.supported_extensions = value
                self.harness.config.supported_extensions = value
                changed_input["supported_extensions"] = value
            if "sources" in input_pref and isinstance(input_pref.get("sources"), list):
                new_sources = []
                for item in input_pref.get("sources", []):
                    if not isinstance(item, dict) or not str(item.get("path", "")).strip():
                        continue
                    source = {
                        "path": str(item.get("path")).strip(),
                        "recursive": bool(item.get("recursive", True)),
                        "filter": item.get("filter"),
                    }
                    new_sources.append(source)
                if new_sources:
                    from .config_core import InputSource
                    self.lumina_config.input_sources = [
                        InputSource(path=s["path"], recursive=s["recursive"], filter=s["filter"])
                        for s in new_sources
                    ]
                    changed_input["sources"] = new_sources
            if changed_input:
                applied["user_preferences"]["input"] = changed_input

        output_pref = user_pref.get("output", {}) if isinstance(user_pref, dict) else {}
        if isinstance(output_pref, dict):
            changed_output = {}
            for key in ["plugin", "base_dir", "vault_path"]:
                if key in output_pref:
                    value = output_pref.get(key)
                    setattr(self.lumina_config.output, key, value)
                    if key == "plugin":
                        self.harness.config.plugin = value
                        self.harness.plugin = get_plugin(str(value))
                    if key == "base_dir":
                        self.harness.config.output_dir = str(value)
                    changed_output[key] = value
            for key in ["structure", "naming", "note_organization"]:
                if key in output_pref and isinstance(output_pref.get(key), dict):
                    value = dict(output_pref.get(key, {}))
                    setattr(self.lumina_config.output, key, value)
                    if key == "structure":
                        self.harness.config.output_structure = value
                    if key == "note_organization":
                        self.harness.config.note_organization = value
                        self.harness.planner.note_organization = self.harness.planner._normalize_note_organization(value)
                        self.harness.planner.categories = {
                            **self.harness.planner.PARA_CATEGORY_MAP,
                            **self.harness.planner.note_organization.get("categories", {}),
                        }
                        self.harness.planner.scenes = self.harness.planner.note_organization.get("scenes", [])
                        self.harness.planner.default_scene = self.harness.planner.note_organization.get("default_scene", "")
                    changed_output[key] = value
            if changed_output:
                applied["user_preferences"]["output"] = changed_output

        self.lumina_config.save_user_config()
        self._reload_runtime_from_lumina_config()
        return applied
    
    def _get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表板统计数据"""
        stats = {
            "total_notes": 0,
            "total_files_processed": 0,
            "avg_score": 0.0,
            "pass_rate": 0.0,
            "vector_store": {
                "available": False,
                "total_documents": 0
            },
            "recent_activity": [],
            "recent_processed_files": []
        }
        
        try:
            if self.harness:
                state = self.harness.get_state()
                stats.update({
                    "total_files_processed": state.get("processed_files", 0),
                    "avg_score": state.get("avg_score", 0.0),
                    "status": state.get("status", "unknown")
                })
                
                # 向量存储统计
                try:
                    vector_stats = self.harness.get_vector_stats()
                    stats["vector_store"] = {
                        "available": vector_stats.get("available", False),
                        "total_documents": vector_stats.get("total_documents", 0),
                    }
                except Exception:
                    pass

                # 最近标记为已处理的文件（来自增量指纹）
                try:
                    source_roots = []
                    if self.lumina_config:
                        for source in self.lumina_config.input_sources:
                            source_roots.append(source.resolve_path())

                    recent_files = self.harness.change_tracker.get_recent_processed_files(
                        limit=10000,
                        roots=source_roots or None,
                    )
                    stats["recent_processed_files"] = [
                        {
                            "file_path": item["file_path"],
                            "file_name": Path(item["file_path"]).name,
                            "last_processed_time": datetime.fromtimestamp(item["last_processed_time"]).isoformat(),
                            "processing_version": item.get("processing_version", 0),
                        }
                        for item in recent_files
                    ]
                except Exception:
                    pass
        except Exception:
            pass
        
        # 统计笔记数量
        try:
            output_dir = Path(self.harness.config.output_dir) if self.harness else Path("./output")
            if output_dir.exists():
                stats["total_notes"] = len(list(output_dir.rglob("*.md")))
        except Exception:
            pass
        
        return stats

    def _bootstrap_scan_state_from_history(self):
        """在服务启动时为扫描状态提供最近一次运行的回显。"""
        if not self.harness:
            return

        try:
            state = self.harness.get_state()
            output_dir = Path(self.harness.config.output_dir).expanduser() if self.harness else None
            total_notes = len(list(output_dir.rglob("*.md"))) if output_dir and output_dir.exists() else 0
            total_processed = int(state.get("processed_files", 0) or 0)
            total_failed = int(state.get("failed_files", 0) or 0)
            total_skipped = int(state.get("skipped_files", 0) or 0)

            if total_notes <= 0 and total_processed <= 0 and total_failed <= 0 and total_skipped <= 0:
                self._scan_state.update({
                    "phase": "idle",
                    "last_status": "idle",
                    "message": "尚未开始扫描",
                })
                return

            completed = total_processed + total_failed + total_skipped
            self._scan_state.update({
                "phase": "completed" if total_failed == 0 else "failed",
                "last_status": "completed" if total_failed == 0 else "failed",
                "message": "最近一次生成已完成" if total_failed == 0 else "最近一次生成包含失败项",
                "progress_percent": 100.0 if completed > 0 else 0.0,
                "file_counts": {
                    "total": completed,
                    "completed": completed,
                    "processed": total_processed,
                    "failed": total_failed,
                    "skipped": total_skipped,
                    "pending": 0,
                },
                "source_counts": {
                    "pending": 0,
                    "processing": 0,
                    "completed": 0 if completed == 0 else 1,
                    "failed": 1 if total_failed > 0 else 0,
                },
                "last_event_at": datetime.now().isoformat(),
                "last_completed_at": datetime.now().isoformat(),
            })
        except Exception:
            pass

    def report_runtime_activity(self, target_path: str, mode: str = "processing"):
        """让非 /api/scan 触发的后台任务也能在仪表盘上显示当前处理目标。"""
        now = datetime.now().isoformat()
        mode_text = {
            "initial_sync": "后台初始化同步中...",
            "incremental": "增量更新中...",
            "processing": "后台处理中...",
        }.get(mode, "后台处理中...")

        with self._scan_state_lock:
            self._scan_state.update({
                "running": True,
                "phase": "running",
                "last_status": "running",
                "started_at": self._scan_state.get("started_at") or now,
                "last_event_at": now,
                "current_source": str(target_path or ""),
                "current_source_index": -1,
                "message": mode_text,
            })

    def clear_runtime_activity(self, target_path: Optional[str] = None):
        """清理当前后台任务显示，避免旧路径残留在仪表盘。"""
        with self._scan_state_lock:
            current_source = str(self._scan_state.get("current_source") or "")
            if target_path and current_source and current_source != str(target_path):
                return
            self._scan_state["current_source"] = ""
            self._scan_state["current_source_index"] = -1
            self._scan_state["last_event_at"] = datetime.now().isoformat()

    def _refresh_scan_state_runtime(self):
        """根据当前 queue 与 harness 状态刷新扫描进度。"""
        queue = self._scan_state.get("queue", [])
        if not isinstance(queue, list):
            queue = []

        live = self.harness.get_state() if self.harness else {}
        harness_running = str(live.get("status", "")).lower() == "running"

        # `serve` 的初始化同步和目录监听会直接调用 harness.run，
        # 这条路径不会显式设置 _scan_state.running，但用户仍需要看到“正在处理”。
        previous_phase = str(self._scan_state.get("phase", "")).lower()
        previous_message = str(self._scan_state.get("message", "")).strip()

        if harness_running:
            if not self._scan_state.get("running"):
                started_at = self._scan_state.get("started_at") or datetime.now().isoformat()
                self._scan_state.update({
                    "running": True,
                    "phase": "running",
                    "started_at": started_at,
                    "last_status": "running",
                    "last_event_at": datetime.now().isoformat(),
                })
            if (not previous_message) or previous_phase in {"completed", "failed", "idle"}:
                self._scan_state["message"] = "后台处理中..."
        elif self._scan_state.get("running") and self._scan_state.get("phase") == "running":
            self._scan_state["running"] = False

        # 扫描运行中：把当前 source 的实时文件进度映射到 queue
        if self._scan_state.get("running") and self.harness:
            idx = self._scan_state.get("current_source_index", -1)
            if isinstance(idx, int) and 0 <= idx < len(queue):
                try:
                    baseline = self._scan_state.get("_source_baseline", {})
                    processed = max(0, int(live.get("processed_files", 0)) - int(baseline.get("processed_files", 0)))
                    failed = max(0, int(live.get("failed_files", 0)) - int(baseline.get("failed_files", 0)))
                    skipped = max(0, int(live.get("skipped_files", 0)) - int(baseline.get("skipped_files", 0)))
                    completed = processed + failed + skipped
                    total = max(int(queue[idx].get("total_files", 0)), int(live.get("total_files", 0)), completed)

                    queue[idx]["processed"] = processed
                    queue[idx]["failed"] = failed
                    queue[idx]["skipped"] = skipped
                    queue[idx]["completed"] = completed
                    queue[idx]["total_files"] = total
                    queue[idx]["progress_percent"] = (completed / total) * 100.0 if total > 0 else 0.0
                    queue[idx]["status"] = "processing"
                except Exception:
                    pass

        # 聚合 source 级状态
        source_counts = {
            "pending": len([q for q in queue if q.get("status") == "pending"]),
            "processing": len([q for q in queue if q.get("status") == "processing"]),
            "completed": len([q for q in queue if q.get("status") == "completed"]),
            "failed": len([q for q in queue if q.get("status") == "failed"]),
        }

        # 聚合文件级状态
        total_files = sum(int(q.get("total_files", 0) or 0) for q in queue)
        processed_files = sum(int(q.get("processed", 0) or 0) for q in queue)
        failed_files = sum(int(q.get("failed", 0) or 0) for q in queue)
        skipped_files = sum(int(q.get("skipped", 0) or 0) for q in queue)
        completed_files = processed_files + failed_files + skipped_files
        pending_files = max(0, total_files - completed_files)

        # 若仍未知 total_files，退化为 source 级进度
        if total_files > 0:
            progress_percent = (completed_files / total_files) * 100.0
        else:
            done_sources = source_counts["completed"] + source_counts["failed"]
            sources_total = max(1, int(self._scan_state.get("sources_total", 0) or 0))
            progress_percent = (done_sources / sources_total) * 100.0 if self._scan_state.get("sources_total", 0) else 0.0

        started_at = self._scan_state.get("started_at")
        elapsed_seconds = 0.0
        eta_seconds = None
        rate_per_minute = 0.0
        if started_at:
            try:
                start_dt = datetime.fromisoformat(str(started_at))
                elapsed_seconds = max(0.0, (datetime.now() - start_dt).total_seconds())
            except Exception:
                elapsed_seconds = 0.0

        if elapsed_seconds > 0:
            progress_units_total = total_files if total_files > 0 else int(self._scan_state.get("sources_total", 0) or 0)
            progress_units_done = completed_files if total_files > 0 else (source_counts["completed"] + source_counts["failed"])
            if progress_units_done > 0:
                rate_per_minute = (progress_units_done / elapsed_seconds) * 60.0
                remaining = max(0, progress_units_total - progress_units_done)
                eta_seconds = (remaining / progress_units_done) * elapsed_seconds if remaining > 0 else 0.0

        self._scan_state["queue"] = queue
        self._scan_state["source_counts"] = source_counts
        self._scan_state["file_counts"] = {
            "total": total_files,
            "completed": completed_files,
            "processed": processed_files,
            "failed": failed_files,
            "skipped": skipped_files,
            "pending": pending_files,
        }
        self._scan_state["progress_percent"] = round(progress_percent, 2)
        self._scan_state["elapsed_seconds"] = round(elapsed_seconds, 1)
        self._scan_state["eta_seconds"] = round(eta_seconds, 1) if eta_seconds is not None else None
        self._scan_state["rate_per_minute"] = round(rate_per_minute, 2)

        if self._scan_state.get("running"):
            self._scan_state["last_status"] = "running"
        elif queue:
            if any(q.get("status") == "failed" for q in queue):
                self._scan_state["last_status"] = "failed"
                self._scan_state["phase"] = "failed"
            elif any(q.get("status") == "completed" for q in queue):
                self._scan_state["last_status"] = "completed"
                self._scan_state["phase"] = "completed"

    def _append_failed_item(self, source: str, file: str, message: str, tags: Optional[List[str]] = None):
        """向失败列表追加标准化失败项。"""
        self._scan_state["_failure_counter"] = int(self._scan_state.get("_failure_counter", 0)) + 1
        self._scan_state.setdefault("failed_items", []).append({
            "id": f"failure_{self._scan_state['_failure_counter']}",
            "source": str(source or ""),
            "file": str(file or source or ""),
            "message": str(message or "Unknown error"),
            "tags": list(tags or []),
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "last_error": str(message or "Unknown error"),
        })
    
    def _get_low_quality_notes(self, min_score: float) -> List[Dict]:
        """获取低质量笔记"""
        low_quality = []
        
        if self.harness and self.harness.history:
            # 从历史记录获取
            sessions = self.harness.history.get_all_sessions(limit=100)
            for session in sessions:
                # 这里需要实现从历史记录获取低质量笔记的逻辑
                pass
        
        return low_quality
    
    def _reprocess_note(self, note: Dict) -> Dict:
        """重新处理笔记"""
        # 实现重新处理逻辑
        return {"success": False, "best_score": 0}
    
    def run(self, debug=False):
        """启动 Web 服务器"""
        print(f"🌐 Starting Lumina Web Interface on http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug)
    
    def get_app(self):
        """获取 Flask 应用实例（用于测试或嵌入）"""
        return self.app


class WebInterfaceConfig:
    """Web界面配置"""
    
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 5088
        self.debug = False
        self.auth_enabled = False
        self.auth_username = 'admin'
        self.auth_password = 'lumina'
        self.enable_cors = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "auth_enabled": self.auth_enabled,
            "enable_cors": self.enable_cors
        }
