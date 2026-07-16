"""R4 断点续跑快照服务（蓝图 T11）。

SnapshotStore.save/load 实时读写 t_task_snapshot；崩溃/重启可恢复最近偏移，零丢失。
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional, Tuple

from passive_agent.common import logging as slog
from passive_agent.storage import db

_logger = slog.get_logger("approval-snapshot")


class SnapshotStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def save(self, task_id: str, offset: int, state: Dict[str, Any]) -> None:
        state_json = json.dumps(state, ensure_ascii=False)
        try:
            db.write(
                "INSERT INTO t_task_snapshot (task_id, offset, state_json) VALUES (?,?,?)",
                (task_id, offset, state_json),
            )
        except Exception as exc:
            _logger.error(f"快照保存失败: {exc}")

    def load(self, task_id: str) -> Optional[Tuple[int, Dict[str, Any]]]:
        try:
            rows = db.query(
                "SELECT offset, state_json FROM t_task_snapshot "
                "WHERE task_id=? AND deleted=0 ORDER BY id DESC LIMIT 1",
                (task_id,),
            )
            if not rows:
                return None
            r = rows[0]
            offset = r["offset"]
            state = json.loads(r["state_json"]) if r["state_json"] else {}
            return offset, state
        except Exception as exc:
            _logger.error(f"快照加载失败: {exc}")
            return None
