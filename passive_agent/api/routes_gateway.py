"""R6 赛事网关 API（频控 / 分片提交）。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from passive_agent.approval.service import ApprovalService
from passive_agent.common.result import ok, fail
from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy

router = APIRouter(tags=["gateway"])
_proxy = ApiProxy()
_approval = ApprovalService()


class SubmitBody(BaseModel):
    biz_req_no: str
    batch_id: str
    shard_index: int = 0
    shard_total: int = 1
    payload: dict = {}


@router.get("/gateway/quota")
def quota(ip: str = "127.0.0.1"):
    return ok(_proxy.quota(ip).model_dump())


@router.post("/gateway/submit")
def submit(body: SubmitBody):
    # 合规闸门：手动出站提交也须关联审批任务已通过（REVIEWING/REJECTED 严禁出站）
    # biz_req_no 形如 "{result_id}-{idx}"，关联审批 task_id = "AP-{result_id}"
    result_id = body.biz_req_no.rsplit("-", 1)[0] if "-" in body.biz_req_no else body.biz_req_no
    task = _approval.get(f"AP-{result_id}")
    # F-4 修复：fail-closed——无匹配审批任务（task is None）或状态非放行态，一律拦截。
    # 原逻辑 `task is not None` 会在无关联任务时直接放行，构成审批绕过。
    if task is None or task.status not in ("APPROVED", "REMINDING"):
        return fail(
            "020002",
            f"出站被审批闸门拦截 task_id=AP-{result_id} status={task.status if task else 'NONE'}",
        )
    req = SubmitProxyRequest(**body.model_dump())
    vo = _proxy.submit(req)
    return ok(vo.model_dump())
