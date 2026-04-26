"""
HistoryManager - 操作历史与审计追踪系统
记录完整的处理流程，支持版本管理、质量趋势分析
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProcessingRecord:
    """处理记录"""
    session_id: str
    file_path: str
    file_hash: str
    file_type: str
    file_size: int
    iterations: int
    best_score: float
    final_output: str
    full_history: str  # JSON 序列化的迭代历史
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class HistoryManager:
    """
    历史管理器
    
    职责：
    1. 记录完整处理流程（SQLite）
    2. 版本管理（支持回滚）
    3. 质量趋势分析
    4. 审计追踪（谁、何时、为什么修改）
    5. 可解释性（展示 Agent 决策过程）
    """
    
    def __init__(self, history_dir: str = "~/.lumina/history"):
        self.history_dir = Path(history_dir).expanduser()
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.history_dir / "lumina_history.db"
        self._init_db()
    
    def _init_db(self):
        """初始化 SQLite 数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    iterations INTEGER,
                    best_score REAL,
                    final_output TEXT,
                    full_history TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # 数据库迁移：添加缺失字段
            cursor = conn.execute("PRAGMA table_info(processing_records)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "file_type" not in columns:
                conn.execute("ALTER TABLE processing_records ADD COLUMN file_type TEXT")
            if "file_size" not in columns:
                conn.execute("ALTER TABLE processing_records ADD COLUMN file_size INTEGER")
            if "final_output" not in columns:
                conn.execute("ALTER TABLE processing_records ADD COLUMN final_output TEXT")
            if "full_history" not in columns:
                conn.execute("ALTER TABLE processing_records ADD COLUMN full_history TEXT")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    start_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    end_time TEXT,
                    total_files INTEGER,
                    avg_score REAL,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path ON processing_records(file_path)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session ON processing_records(session_id)
            """)
    
    def start_session(self, session_id: str):
        """开始新会话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, status) VALUES (?, ?)",
                (session_id, "running")
            )
    
    def end_session(self, session_id: str, total_files: int, avg_score: float):
        """结束会话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET end_time = CURRENT_TIMESTAMP, total_files = ?, avg_score = ?, status = ? WHERE session_id = ?",
                (total_files, avg_score, "completed", session_id)
            )
    
    def record_file_processing(self, record: ProcessingRecord):
        """记录文件处理"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO processing_records 
                (session_id, file_path, file_hash, file_type, file_size, iterations, best_score, final_output, full_history, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.session_id,
                record.file_path,
                record.file_hash,
                record.file_type,
                record.file_size,
                record.iterations,
                record.best_score,
                record.final_output,
                record.full_history,
                json.dumps(record.metadata)
            ))
    
    def get_file_history(self, file_path: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取文件处理历史"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM processing_records 
                WHERE file_path = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (file_path, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_quality_trend(self, file_path: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取质量趋势"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT created_at, best_score, iterations 
                FROM processing_records 
                WHERE file_path = ? AND created_at > datetime('now', '-{} days')
                ORDER BY created_at
                """.format(days),
                (file_path,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取所有会话列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_explanation(self, file_path: str) -> str:
        """获取处理过程的可解释性说明"""
        history = self.get_file_history(file_path, limit=1)
        if not history:
            return f"未找到 {file_path} 的处理记录"
        
        record = history[0]
        try:
            full_history = json.loads(record["full_history"])
        except (json.JSONDecodeError, KeyError):
            full_history = []
        
        explanation = [
            f"📄 文件: {file_path}",
            f"🕐 处理时间: {record['created_at']}",
            f"📊 最终得分: {record['best_score']:.2f}",
            f"🔄 迭代次数: {record['iterations']}",
            "",
            "📋 迭代详情:",
        ]
        
        for i, iteration in enumerate(full_history, 1):
            explanation.append(
                f"  第{i}轮: 得分={iteration['validation']['score']:.2f}, "
                f"通过={iteration['validation']['passed']}, "
                f"问题数={iteration['validation']['issues']}"
            )
            if iteration['validation']['issues'] > 0:
                explanation.append(f"    修复建议: {', '.join(iteration.get('validation', {}).get('suggestions', []))[:100]}")
        
        return "\n".join(explanation)
