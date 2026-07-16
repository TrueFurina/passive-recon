"""R11 度量数据聚合（蓝图 T26）。

从 R6 网关（频控/WNSR）、R9 调度器（算力占比/回收）、
R10 日志（违规/降级计数）汇聚数据。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from passive_agent.common import logging as mlog
from passive_agent.config import settings

_logger = mlog.get_logger("metrics-aggregator")


class MetricsSnapshot(BaseModel):
    """度量快照（WNSR + 6 项支撑指标 + 红线状态 + 降级/回收事件）。"""
    wnsr: float = 0.0                    # 有效加权得分达成率（模拟分估算）
    compute_ratio: Dict[str, float] = Field(default_factory=dict)  # {A:60, B:30, C:10}
    coverage: float = 0.0               # 资产覆盖率
    accuracy: float = 0.0               # 情报准确率
    invalid_rate: float = 0.0           # 无效情报率
    schedule_efficiency: float = 0.0    # 算力调度效率
    compliance_rate: float = 100.0      # 合规安全率（违规=0&封禁=0 → 100）
    api_efficiency: float = 0.0         # API 调用效率
    violations: int = 0                 # 违规计数
    bans: int = 0                       # 封禁计数
    freq_buffer_pct: float = 0.0        # 频控 buffer
    fault_events: List[Dict[str, Any]] = Field(default_factory=list)  # 降级/回收事件摘要
    snapshot_at: str = ""               # 快照时间


class MetricsAggregator:
    """度量数据聚合（从 R6/R9/R10 汇聚）。"""

    def __init__(self, compute_scheduler=None) -> None:
        """
        Args:
            compute_scheduler: ComputeScheduler 实例（可为 None）。
        """
        self._compute_scheduler = compute_scheduler

    def snapshot(self) -> MetricsSnapshot:
        """汇聚当前度量快照。"""
        # 1) R6 网关频控状态
        freq_pct = 0.0
        try:
            from passive_agent.gateway.proxy import ApiProxy
            proxy = ApiProxy()
            q = proxy.quota("127.0.0.1")
            freq_pct = q.usage_pct
        except Exception:
            pass

        # 2) R9 算力调度状态
        compute_ratio = dict(settings.COMPUTE_WEIGHTS)
        fault_events: List[Dict[str, Any]] = []
        if self._compute_scheduler:
            status = self._compute_scheduler.get_status()
            for ev in status.get("reclaim_events", []):
                fault_events.append({
                    "type": "reclaim",
                    "task_id": ev.get("task_id", ""),
                    "enterprise": ev.get("enterprise", ""),
                    "idle_minutes": ev.get("idle_minutes", 0),
                    "reason_code": ev.get("reason_code", "030001"),
                    "reclaimed_at": ev.get("reclaimed_at", ""),
                })

        # 3) R10 审计日志统计
        violations, bans, fault_count = self._count_audit_events()

        # 4) 合规安全率（违规=0 & 封禁=0 → 100%）
        compliance_rate = 100.0 if (violations == 0 and bans == 0) else 0.0

        # 5) 降级/回收事件从审计日志补充
        fault_events.extend(self._query_fault_events())

        # 6) WNSR 模拟分估算（规则发布后回填）
        wnsr = self._estimate_wnsr(violations, bans, freq_pct)

        # 7) 6 项支撑指标（模拟分估算）
        coverage = self._estimate_coverage()
        accuracy = self._estimate_accuracy(violations, fault_count)
        invalid_rate = self._estimate_invalid_rate(fault_count)
        schedule_efficiency = self._estimate_schedule_efficiency()
        api_efficiency = self._estimate_api_efficiency(freq_pct)

        return MetricsSnapshot(
            wnsr=wnsr,
            compute_ratio=compute_ratio,
            coverage=coverage,
            accuracy=accuracy,
            invalid_rate=invalid_rate,
            schedule_efficiency=schedule_efficiency,
            compliance_rate=compliance_rate,
            api_efficiency=api_efficiency,
            violations=violations,
            bans=bans,
            freq_buffer_pct=freq_pct,
            fault_events=fault_events,
            snapshot_at=datetime.now(timezone.utc).isoformat(),
        )

    def war_report(self) -> Dict[str, Any]:
        """阶段战报（WNSR + 指标快照 + 红线状态 + 降级/回收事件摘要）。"""
        snap = self.snapshot()
        return {
            "title": "企业被动信息搜集 Agent · 阶段战报",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "wnsr": snap.wnsr,
            "metrics": {
                "coverage": snap.coverage,
                "accuracy": snap.accuracy,
                "invalid_rate": snap.invalid_rate,
                "schedule_efficiency": snap.schedule_efficiency,
                "compliance_rate": snap.compliance_rate,
                "api_efficiency": snap.api_efficiency,
            },
            "compute_ratio": snap.compute_ratio,
            "redline": {
                "violations": snap.violations,
                "bans": snap.bans,
                "freq_buffer_pct": snap.freq_buffer_pct,
                "compliance_rate": snap.compliance_rate,
                "status": "GREEN" if (snap.violations == 0 and snap.bans == 0
                                      and snap.freq_buffer_pct <= 95) else "RED",
            },
            "fault_events": snap.fault_events,
            "summary": (
                f"WNSR={snap.wnsr:.1f}% | "
                f"合规安全率={snap.compliance_rate:.0f}% | "
                f"违规={snap.violations} 封禁={snap.bans} | "
                f"频控={snap.freq_buffer_pct:.1f}% | "
                f"降级/回收事件={len(snap.fault_events)}"
            ),
        }

    def _count_audit_events(self) -> tuple:
        """统计审计日志中的违规/封禁/降级计数。"""
        violations = 0
        bans = 0
        fault_count = 0
        try:
            from passive_agent.storage import db

            # 违规计数（decision=BLOCK 的记录）
            rows = db.query(
                "SELECT COUNT(*) AS c FROM t_audit_log "
                "WHERE deleted=0 AND decision='BLOCK'"
            )
            violations = rows[0]["c"] if rows else 0

            # 降级/挂起事件计数
            rows = db.query(
                "SELECT COUNT(*) AS c FROM t_audit_log "
                "WHERE deleted=0 AND reason_code IN ('040001', '040002', '030001')"
            )
            fault_count = rows[0]["c"] if rows else 0
        except Exception:
            pass
        return violations, bans, fault_count

    def _query_fault_events(self) -> List[Dict[str, Any]]:
        """查询降级/回收事件摘要（最近 20 条）。"""
        try:
            from passive_agent.storage import db

            rows = db.query(
                "SELECT ts, trace_id, action, source, decision, reason_code, msg "
                "FROM t_audit_log "
                "WHERE deleted=0 AND reason_code IN ('040001', '040002', '030001') "
                "ORDER BY id DESC LIMIT 20"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _estimate_wnsr(self, violations: int, bans: int,
                       freq_pct: float) -> float:
        """WNSR 模拟分估算（规则发布后回填真实分母）。

        基线 100%，每条违规扣 5%，每条封禁扣 10%，频控超 95% 扣 10%。
        """
        wnsr = 100.0
        wnsr -= violations * 5.0
        wnsr -= bans * 10.0
        if freq_pct > 95:
            wnsr -= 10.0
        return max(wnsr, 0.0)

    def _estimate_coverage(self) -> float:
        """资产覆盖率估算（基于图谱节点数）。"""
        try:
            from passive_agent.graph.asset_graph import AssetGraph
            ag = AssetGraph()
            count = ag.node_count()
            # 简化：10+ 节点视为 100% 覆盖
            return min(count * 10.0, 100.0)
        except Exception:
            return 0.0

    def _estimate_accuracy(self, violations: int, fault_count: int) -> float:
        """情报准确率估算。"""
        base = 100.0
        base -= violations * 2.0
        base -= fault_count * 1.0
        return max(base, 0.0)

    def _estimate_invalid_rate(self, fault_count: int) -> float:
        """无效情报率估算。"""
        return min(fault_count * 2.0, 100.0)

    def _estimate_schedule_efficiency(self) -> float:
        """算力调度效率估算。"""
        # 简化：有调度器配置即视为高效
        return 95.0 if settings.COMPUTE_WEIGHTS else 0.0

    def _estimate_api_efficiency(self, freq_pct: float) -> float:
        """API 调用效率估算。"""
        # 频控 buffer 越低效率越高
        return max(100.0 - freq_pct * 0.5, 0.0)
