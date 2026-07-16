"""R11 度量看板 API（蓝图 T26）。

路由：
  GET /api/v1/metrics/snapshot     → 当前度量快照
  GET /api/v1/metrics/war-report   → 阶段战报导出
  GET /api/v1/metrics/fault-events → 降级/回收事件流
"""
from __future__ import annotations

from fastapi import APIRouter

from passive_agent.common.result import ok
from passive_agent.metrics.aggregator import MetricsAggregator

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/snapshot")
def snapshot():
    """当前度量快照（WNSR + 6 项指标 + 红线状态 + 降级/回收事件）。"""
    agg = MetricsAggregator()
    snap = agg.snapshot()
    return ok(snap.model_dump())


@router.get("/war-report")
def war_report():
    """阶段战报导出（WNSR + 指标快照 + 红线状态 + 降级/回收事件摘要）。"""
    agg = MetricsAggregator()
    report = agg.war_report()
    return ok(report)


@router.get("/fault-events")
def fault_events():
    """降级/回收事件流（最近 20 条）。"""
    agg = MetricsAggregator()
    snap = agg.snapshot()
    return ok(snap.fault_events)
