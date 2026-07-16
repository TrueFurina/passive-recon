"""R10 审计日志导出（答辩溯源，蓝图 T24）。

支持导出 JSON 文件 + 按 trace_id 导出完整链路轨迹。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from passive_agent.audit.query import AuditQuery
from passive_agent.common import logging as aelog
from passive_agent.storage import db

_logger = aelog.get_logger("audit-export")


class AuditExport:
    """审计日志导出（答辩溯源）。"""

    def __init__(self) -> None:
        self.query = AuditQuery()

    def export_json(self, path: str, **filters: Any) -> str:
        """导出检索结果为 JSON 文件。

        Args:
            path: 导出文件路径
            **filters: 传递给 AuditQuery.search() 的过滤参数

        Returns:
            实际写入的文件路径
        """
        records = self.query.search(**filters)
        export_data = {
            "exported_at": _now_iso(),
            "count": len(records),
            "records": records,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(export_data, fh, ensure_ascii=False, indent=2)
        _logger.info(f"审计日志导出: {len(records)} 条 → {path}")
        return path

    def export_trace(self, trace_id: str,
                     path: Optional[str] = None) -> dict:
        """按 trace_id 导出完整链路轨迹（采集→核验→提交→调度）。

        Args:
            trace_id: 全链路追踪 ID
            path: 可选导出路径（不传则只返回字典不写文件）

        Returns:
            {trace_id, records, timeline}
        """
        records: List[Dict[str, Any]] = []
        try:
            rows = db.query(
                "SELECT ts, trace_id, subject_id, action, source, "
                "decision, reason_code, msg FROM t_audit_log "
                "WHERE deleted=0 AND trace_id=? ORDER BY id ASC",
                (trace_id,),
            )
            records = [dict(r) for r in rows]
        except Exception as exc:
            _logger.error(f"trace 轨迹查询失败 trace_id={trace_id}: {exc}")

        # 按时间排序构建轨迹时间线
        timeline = []
        for r in records:
            timeline.append({
                "ts": r.get("ts", ""),
                "action": r.get("action", ""),
                "source": r.get("source", ""),
                "decision": r.get("decision", ""),
                "reason_code": r.get("reason_code", ""),
                "msg": r.get("msg", ""),
            })

        result = {
            "trace_id": trace_id,
            "record_count": len(records),
            "records": records,
            "timeline": timeline,
            "exported_at": _now_iso(),
        }

        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
            _logger.info(f"trace 轨迹导出: {len(records)} 条 → {path}")

        return result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
