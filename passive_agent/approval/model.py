"""R4 审批数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from passive_agent.common.enums import RiskLevel


class ApprovalTask(BaseModel):
    task_id: str
    biz_type: str = "COLLECT_RESULT"   # COLLECT_RESULT / SUBMIT
    subject_id: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    status: str = "PENDING"              # PENDING/APPROVED/REJECTED/REVIEWING/REMINDING
    payload_ref: str = ""


class ApprovalEvent(BaseModel):           # R4 审批事件契约
    task_id: str
    offset: int = 0                       # 断点偏移
    action: str = "AUTO_PASS"             # AUTO_PASS/APPROVE/REJECT/REVIEW
    risk_level: RiskLevel = RiskLevel.LOW
    operator: str = "system"
