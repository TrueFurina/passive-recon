"""R1 合规态势 API。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from passive_agent.common.enums import ActionType
from passive_agent.common.result import fail, ok
from passive_agent.compliance.engine import get_engine

router = APIRouter(tags=["compliance"])


@router.get("/compliance/status")
def compliance_status():
    engine = get_engine()
    return ok({"fail_closed": True, "rules_count": len(engine._rules)})


class CheckBody(BaseModel):
    action_type: str
    source_name: str = "api"
    target_url: Optional[str] = None


@router.post("/compliance/check")
def compliance_check(body: CheckBody):
    from passive_agent.common.compliance_client import check

    try:
        # 仅做语义校验提示；引擎接受任意字符串（未知动作默认拦截）
        ActionType(body.action_type)
    except ValueError:
        pass
    decision = check(body.action_type, target_url=body.target_url, source_name=body.source_name)
    return ok(decision.model_dump())
