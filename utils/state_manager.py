"""
EvalStateManager — SQLite 断点续传 (v3.0)
支持精确到子类别级别的增量重跑
"""

import sqlite3
import json
import os
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class EvalStateManager:
    def __init__(self, db_path="eval_state.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                profile TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'running',
                completed_at TEXT,
                overall_score REAL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS task_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                dimension TEXT NOT NULL,
                category TEXT NOT NULL,
                state TEXT DEFAULT 'pending',
                score REAL DEFAULT 0,
                max_score REAL DEFAULT 100,
                error TEXT,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                FOREIGN KEY (run_id) REFERENCES eval_runs(id)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_run ON task_states(run_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_state ON task_states(run_id, state)
        """)
        self.conn.commit()

    def create_run(self, model_id: str, profile: str = "default") -> str:
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{model_id.replace('/', '_')}"
        self.conn.execute(
            "INSERT INTO eval_runs (id, model_id, profile, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (run_id, model_id, profile, datetime.now().isoformat(), "running")
        )
        self.conn.commit()
        return run_id

    def set_task_state(self, run_id: str, dimension: str, category: str,
                       state: TaskState, score: float = 0, max_score: float = 100,
                       error: Optional[str] = None, result_json: Optional[str] = None):
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO task_states (run_id, dimension, category, state, score, max_score, error, started_at, completed_at, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, dimension, category, state.value, score, max_score, error, now, now, result_json)
        )
        self.conn.commit()

    def get_pending_tasks(self, run_id: str) -> List[Dict[str, str]]:
        rows = self.conn.execute(
            "SELECT dimension, category FROM task_states WHERE run_id = ? AND state = ?",
            (run_id, TaskState.PENDING.value)
        ).fetchall()
        return [{"dimension": r["dimension"], "category": r["category"]} for r in rows]

    def get_run_progress(self, run_id: str) -> Dict[str, Any]:
        total = self.conn.execute(
            "SELECT COUNT(*) FROM task_states WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        success = self.conn.execute(
            "SELECT COUNT(*) FROM task_states WHERE run_id = ? AND state = ?",
            (run_id, TaskState.SUCCESS.value)
        ).fetchone()[0]
        failed = self.conn.execute(
            "SELECT COUNT(*) FROM task_states WHERE run_id = ? AND state = ?",
            (run_id, TaskState.FAILED.value)
        ).fetchone()[0]
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": total - success - failed,
            "progress_pct": round(success / total * 100, 1) if total > 0 else 0
        }

    def get_latest_run_id(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT id FROM eval_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def resume_run(self, run_id: str) -> List[Dict[str, str]]:
        """获取上次运行中未完成的任务列表"""
        pending = self.get_pending_tasks(run_id)
        # 将上次 RUNNING 状态的任务重置为 PENDING (可能中断了)
        self.conn.execute(
            "UPDATE task_states SET state = ? WHERE run_id = ? AND state = ?",
            (TaskState.PENDING.value, run_id, TaskState.RUNNING.value)
        )
        self.conn.commit()
        return self.get_pending_tasks(run_id)

    def complete_run(self, run_id: str, overall_score: float = 0):
        self.conn.execute(
            "UPDATE eval_runs SET status = ?, completed_at = ?, overall_score = ? WHERE id = ?",
            ("completed", datetime.now().isoformat(), overall_score, run_id)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
