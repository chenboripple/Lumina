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
            "started_at": None,
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
                "started_at": None,
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
                self._scan_state["started_at"] = datetime.now().isoformat()
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
                if not self.harness:
                    return jsonify({"error": "Harness not available"}), 503
                
                config = {
                    "max_iterations": self.harness.config.max_iterations,
                    "quality_threshold": self.harness.config.quality_threshold,
                    "output_dir": self.harness.config.output_dir,
                    "plugin": self.harness.config.plugin,
                    "incremental": self.harness.config.incremental,
                    "parallel": self.harness.config.parallel,
                    "enable_vector_store": self.harness.config.enable_vector_store,
                }
                return jsonify(config)
            
            else:  # POST
                data = request.get_json()
                # 更新配置（需要实现配置热加载）
                return jsonify({"message": "Config updated", "changes": data})
        
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

    def _refresh_scan_state_runtime(self):
        """根据当前 queue 与 harness 状态刷新扫描进度。"""
        queue = self._scan_state.get("queue", [])
        if not isinstance(queue, list):
            queue = []

        # 扫描运行中：把当前 source 的实时文件进度映射到 queue
        if self._scan_state.get("running") and self.harness:
            idx = self._scan_state.get("current_source_index", -1)
            if isinstance(idx, int) and 0 <= idx < len(queue):
                try:
                    live = self.harness.get_state()
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
