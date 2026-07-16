"""R10 全链路审计日志检索（企业/时间/违规三维组合，蓝图 T24）。

扩展 P0 audit/logger.py 的检索能力。
"""
from __future__ import annotations

from typing import List, Optional

from passive_agent.common import logging as aqlog
from passive_agent.storage import db

_logger = aqlog.get_logger("audit-query")


class AuditQuery:
    """全链路审计日志检索（企业/时间/违规三维组合）。"""

    def search(
        self,
        enterprise: Optional[str] = None,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None,
        decision: Optional[str] = None,
        reason_code: Optional[str] = None,
        trace_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """按企业/时间范围/违规类型三维组合检索 t_audit_log。

        Args:
            enterprise: 企业名（匹配 subject_id 字段）
            start_ts: 起始时间（ISO8601 或 SQLite datetime 格式）
            end_ts: 结束时间
            decision: 合规判定（ALLOW/BLOCK/SUSPEND/DEGRADE/FAIL/RECLAIM）
            reason_code: 错误码
            trace_id: 全链路追踪 ID
            subject_id: 直接匹配 subject_id 字段
            limit: 返回上限

        Returns:
            审计记录列表
        """
        sql = (
            "SELECT ts, trace_id, subject_id, action, source, "
            "decision, reason_code, msg FROM t_audit_log WHERE deleted=0"
        )
        params: list = []

        # 企业维度：优先用 enterprise 匹配 subject_id
        if enterprise:
            sql += " AND subject_id=?"
            params.append(enterprise)
        elif subject_id:
            sql += " AND subject_id=?"
            params.append(subject_id)

        # 时间维度
        if start_ts:
            sql += " AND ts>=?"
            params.append(start_ts)
        if end_ts:
            sql += " AND ts<=?"
            params.append(end_ts)

        # 违规类型维度
        if decision:
            sql += " AND decision=?"
            params.append(decision)
        if reason_code:
            sql += " AND reason_code=?"
            params.append(reason_code)
        if trace_id:
            sql += " AND trace_id=?"
            params.append(trace_id)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        try:
            return [dict(r) for r in db.query(sql, tuple(params))]
        except Exception as exc:
            _logger.error(f"审计检索失败: {exc}")
            return []

    def count_by_type(self, start_ts: Optional[str] = None) -> dict:
        """按 action 维度统计计数（采集/校验/提交/调度四类事件）。

        Args:
            start_ts: 起始时间（可选，不传则统计全部）

        Returns:
            {action: count}
        """
        sql = "SELECT action, COUNT(*) AS c FROM t_audit_log WHERE deleted=0"
        params: list = []
        if start_ts:
            sql += " AND ts>=?"
            params.append(start_ts)
        sql += " GROUP BY action"

        try:
            rows = db.query(sql, tuple(params))
            return {r["action"]: r["c"] for r in rows}
        except Exception as exc:
            _logger.error(f"审计统计失败: {exc}")
            return {}
