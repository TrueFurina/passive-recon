"""R4 三级审批 + 断点续跑 API。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from passive_agent.approval.model import ApprovalEvent, ApprovalTask
from passive_agent.approval.service import ApprovalService
from passive_agent.approval.snapshot import SnapshotStore
from passive_agent.common.enums import RiskLevel
from passive_agent.common.result import fail, ok

router = APIRouter(tags=["approval"])
_svc = ApprovalService()
_snap = SnapshotStore()


class CreateBody(BaseModel):
    task_id: str
    biz_type: str = "COLLECT_RESULT"
    subject_id: str = ""
    risk_level: str = "LOW"
    payload_ref: str = ""


@router.get("/approval/queue")
def queue(risk: Optional[str] = None):
    r = RiskLevel(risk) if risk else None
    tasks = _svc.queue(r)
    return ok([t.model_dump() for t in tasks])


@router.post("/approval/create")
def create(body: CreateBody):
    try:
        rl = RiskLevel(body.risk_level)
    except ValueError:
        return fail("400001", f"未知风险等级: {body.risk_level}")
    task = ApprovalTask(
        task_id=body.task_id, biz_type=body.biz_type,
        subject_id=body.subject_id, risk_level=rl, payload_ref=body.payload_ref,
    )
    created = _svc.create(task)
    return ok(created.model_dump())


@router.post("/approval/decide")
def decide(ev: ApprovalEvent):
    try:
        updated = _svc.decide(ev)
    except ValueError as e:
        return fail("400001", str(e))
    return ok(updated.model_dump())


@router.post("/approval/resume")
def resume(task_id: str):
    snap = _snap.load(task_id)
    if not snap:
        return fail("400001", f"无快照: {task_id}")
    offset, state = snap
    return ok({"task_id": task_id, "offset": offset, "state": state})
