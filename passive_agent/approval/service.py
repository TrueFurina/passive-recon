"""R4 三级审批后端服务（蓝图 T10）。

- create() 三级分流：LOW 自动入库 / MID 入库+提醒 / HIGH 高价值人工复核（置顶队列）。
- decide()：AUTO_PASS/APPROVE/REJECT/REVIEW 状态机（HIGH 不可被自动跳过）。
- 状态落 t_approval_task。
"""
from __future__ import annotations

import threading
from typing import List, Optional

from passive_agent.approval.model import ApprovalEvent, ApprovalTask
from passive_agent.common import logging as alog
from passive_agent.common.enums import RiskLevel
from passive_agent.config import settings
from passive_agent.storage import db

_logger = alog.get_logger("approval")


class ApprovalService:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _elevate_risk(self, task: ApprovalTask) -> RiskLevel:
        """命中高价值关键词强制 HIGH 人工复核（合规底线）。"""
        hay = f"{task.subject_id} {task.payload_ref}"
        for kw in settings.HIGH_VALUE_KEYWORDS:
            if kw and kw in hay:
                return RiskLevel.HIGH
        return task.risk_level

    def create(self, task: ApprovalTask) -> ApprovalTask:
        risk = self._elevate_risk(task)
        task.risk_level = risk
        if risk == RiskLevel.LOW:
            task.status = "APPROVED"           # 低危：自动入库
        elif risk == RiskLevel.MID:
            task.status = "REMINDING"          # 中危：入库 + 提醒
        else:
            task.status = "REVIEWING"          # 高价值：人工复核（置顶）
        self._persist(task)
        _logger.info(f"审批任务创建 task_id={task.task_id} risk={risk.value} status={task.status}")
        return task

    def decide(self, ev: ApprovalEvent) -> ApprovalTask:
        row = db.query(
            "SELECT * FROM t_approval_task WHERE task_id=? AND deleted=0", (ev.task_id,)
        )
        if not row:
            raise ValueError(f"审批任务不存在: {ev.task_id}")
        r = row[0]
        task = ApprovalTask(
            task_id=r["task_id"],
            biz_type=r["biz_type"] or "COLLECT_RESULT",
            subject_id=r["subject_id"] or "",
            risk_level=RiskLevel(r["risk_level"]),
            status=r["status"] or "PENDING",
            payload_ref=r["payload_ref"] or "",
        )
        action = (ev.action or "AUTO_PASS").upper()
        if action == "APPROVE":
            task.status = "APPROVED"
        elif action == "REJECT":
            task.status = "REJECTED"
        elif action == "REVIEW":
            task.status = "REVIEWING"
        elif action == "AUTO_PASS":
            # HIGH 不可被 AUTO_PASS 跳过人工
            if task.risk_level == RiskLevel.HIGH:
                task.status = "REVIEWING"
            else:
                task.status = "APPROVED"
        else:
            raise ValueError(f"未知审批动作: {ev.action}")
        self._persist(task)
        _logger.info(f"审批决策 task_id={ev.task_id} action={action} -> {task.status}")
        return task

    def queue(self, risk: Optional[RiskLevel] = None) -> List[ApprovalTask]:
        sql = "SELECT * FROM t_approval_task WHERE deleted=0"
        params: tuple = ()
        if risk is not None:
            sql += " AND risk_level=?"
            params = (risk.value,)
        sql += (" ORDER BY CASE risk_level WHEN 'HIGH' THEN 0 WHEN 'MID' THEN 1 "
                "ELSE 2 END, id ASC")
        rows = db.query(sql, params)
        return [self._row_to_task(r) for r in rows]

    def get(self, task_id: str) -> Optional[ApprovalTask]:
        """按 task_id 查询审批任务；不存在返回 None（供手动出站闸门判定）。"""
        row = db.query(
            "SELECT * FROM t_approval_task WHERE task_id=? AND deleted=0", (task_id,)
        )
        if not row:
            return None
        return self._row_to_task(row[0])

    def _row_to_task(self, r) -> ApprovalTask:
        return ApprovalTask(
            task_id=r["task_id"],
            biz_type=r["biz_type"] or "COLLECT_RESULT",
            subject_id=r["subject_id"] or "",
            risk_level=RiskLevel(r["risk_level"]),
            status=r["status"] or "PENDING",
            payload_ref=r["payload_ref"] or "",
        )

    def _persist(self, task: ApprovalTask) -> None:
        try:
            db.write(
                """
                INSERT INTO t_approval_task
                (task_id, biz_type, subject_id, risk_level, status, payload_ref, updated_at)
                VALUES (?,?,?,?,?,?,datetime('now'))
                ON CONFLICT(task_id) DO UPDATE SET
                    status=excluded.status, risk_level=excluded.risk_level,
                    payload_ref=excluded.payload_ref, updated_at=datetime('now')
                """,
                (task.task_id, task.biz_type, task.subject_id,
                 task.risk_level.value, task.status, task.payload_ref),
            )
        except Exception as exc:
            _logger.error(f"审批任务落库失败: {exc}")
