"""最小面板控制台 API（聚合态势 / 单企业闭环触发 / P1 度量概览）。"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from passive_agent.common.result import ok
from passive_agent.compliance.engine import get_engine
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.inventory.registry import InventoryRegistry
from passive_agent.orchestrator.loop import run_company

router = APIRouter(tags=["console"])

# 进程内任务状态表（单实例；多 worker 需外置共享，见部署 Runbook）。
# value = {"status": PENDING|DONE|ERROR, "summary": Optional[dict], "error": Optional[str]}
_run_tasks: Dict[str, Dict[str, Any]] = {}


class RunBody(BaseModel):
    enterprise: str
    max_depth: int = 3


@router.get("/console/overview")
def overview():
    eng = get_engine()
    reg = InventoryRegistry()
    proof = reg.export_proof()
    q = ApiProxy().quota("127.0.0.1")
    return ok({
        "compliance": {"fail_closed": True, "rules": len(eng._rules)},
        "inventory": proof.ratio,
        "quota": q.model_dump(),
    })


@router.post("/console/run-company")
async def run(body: RunBody):
    """派发企业闭环到后台线程，立即返回 task_id；结果经 /console/run-status/{task_id} 查询。

    解决原同步实现：run_company 在请求线程内跑完整采集闭环（分钟级），
    并发即耗尽 worker 线程池导致网关/客户端超时（P0-6）。
    """
    task_id = f"RUN-{uuid.uuid4().hex[:12]}"
    _run_tasks[task_id] = {"status": "PENDING", "summary": None, "error": None}
    asyncio.create_task(_dispatch_run(task_id, body.enterprise, body.max_depth))
    return ok({
        "task_id": task_id,
        "status": "PENDING",
        "poll": f"/console/run-status/{task_id}",
    })


async def _dispatch_run(task_id: str, enterprise: str, max_depth: int) -> None:
    try:
        # run_company 是同步重活（多源网络采集 + DB）；丢到线程池，不阻塞事件循环
        summary = await asyncio.to_thread(run_company, enterprise, max_depth=max_depth)
        _run_tasks[task_id] = {"status": "DONE", "summary": summary, "error": None}
    except Exception as exc:  # 后台任务异常需捕获，否则成为未处理 task 异常
        _run_tasks[task_id] = {"status": "ERROR", "summary": None, "error": str(exc)}


@router.get("/console/run-status/{task_id}")
async def run_status(task_id: str):
    """查询后台企业闭环任务进度/结果。"""
    task = _run_tasks.get(task_id)
    if not task:
        return ok({"task_id": task_id, "status": "NOT_FOUND"})
    return ok(task)


@router.get("/console/metrics-overview")
def metrics_overview():
    """聚合 R7/R9/R10/R11/R12 全景概览（P1 T32 新增）。

    返回合规态势 + 频控 + 度量快照 + 图谱统计 + 源健康状态。
    """
    # R1 合规态势 + R6 频控
    eng = get_engine()
    q = ApiProxy().quota("127.0.0.1")

    # R11 度量快照
    from passive_agent.metrics.aggregator import MetricsAggregator
    agg = MetricsAggregator()
    snap = agg.snapshot()

    # R12 图谱统计
    from passive_agent.graph.asset_graph import AssetGraph
    ag = AssetGraph()
    graph_stats = {
        "node_count": ag.node_count(),
        "edge_count": ag.edge_count(),
    }

    # R10 审计统计
    from passive_agent.audit.query import AuditQuery
    aq = AuditQuery()
    action_counts = aq.count_by_type()

    return ok({
        "compliance": {
            "fail_closed": True,
            "rules": len(eng._rules),
            "violations": snap.violations,
            "bans": snap.bans,
        },
        "quota": q.model_dump(),
        "metrics": snap.model_dump(),
        "graph": graph_stats,
        "audit_counts": action_counts,
        "redline_status": "GREEN" if (
            snap.violations == 0 and snap.bans == 0 and snap.freq_buffer_pct <= 95
        ) else "RED",
    })
