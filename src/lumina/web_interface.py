"""
Web Management Interface - Web管理界面
提供可视化操作、知识图谱展示、搜索界面、重新生成笔记
"""

import os
import json
import time
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
            if not self.harness or not self.harness.vector_store:
                return jsonify({"error": "Vector store not available"}), 503
            
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
                
                if not source_path or not Path(source_path).exists():
                    return jsonify({"error": "Source file not found"}), 404

                source_file = Path(source_path).expanduser().resolve()
                allowed_source = self._resolve_allowed_source(source_file)
                if not allowed_source:
                    return jsonify({"error": "Source file is not allowed by current input.sources configuration"}), 400

                source_root, source_filter = allowed_source
                scanned = self.harness.planner.scan(
                    str(source_file),
                    recursive=False,
                    file_filter=source_filter,
                    supported_extensions=self.harness.config.supported_extensions,
                )
                if not scanned:
                    return jsonify({"error": "Source file is filtered out by current filter or supported_extensions settings"}), 400
                
                file_info = scanned[0]
                
                plan = {"strategy": "direct", "batches": [[file_info]]}
                result = self.harness._process_single(file_info, plan)
                
                return jsonify({
                    "success": result.get("success", False),
                    "score": result.get("best_score", 0),
                    "iterations": result.get("iterations", 0),
                    "message": "Note regenerated successfully" if result.get("success") else "Failed to regenerate"
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # API: 批量修复
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
            "recent_activity": []
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
