"""R9 算力调度数据模型（蓝图 §3.5）。"""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ComputeQuota(BaseModel):
    """A:B:C 三类算力配额。"""
    cluster_a_pct: float = 60.0    # A 类算力占比（工控/政务/能源高价值）
    cluster_b_pct: float = 30.0    # B 类算力占比（主站/公众号）
    cluster_c_pct: float = 10.0    # C 类算力占比（长尾旁站）
    total_slots: int = 100         # 总算力槽位


class LeaderboardSnapshot(BaseModel):
    """看榜快照（每 5 分钟读一次）。"""
    snapshot_at: str = ""                           # 快照时间 ISO8601
    task_scores: List[Dict[str, Any]] = Field(default_factory=list)
    # [{task_id, marginal_score, cluster, new_count}]


class ReclaimEvent(BaseModel):
    """算力回收事件。"""
    task_id: str = ""
    enterprise: str = ""
    idle_minutes: int = 0                           # 空闲时长
    reason_code: str = "030001"                     # 回收原因码
    snapshot_saved: bool = False                    # 回收前是否已存快照
    reclaimed_at: str = ""                          # 回收时间 ISO8601
