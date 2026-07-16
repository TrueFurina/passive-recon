"""R9 加权算力调度控制器（蓝图 T23）。

- 权重分配器：A:B:C=60:30:10 配额（可配置 COMPUTE_WEIGHTS）。
- 看榜倾斜器：每 5min 读榜单快照，向高边际贡献任务倾斜。
- 回收控制器：25min 零新增回收，回收前调 SnapshotStore.save() 存断点快照。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from passive_agent.common import logging as slog
from passive_agent.config import settings
from passive_agent.scheduler.model import ComputeQuota, LeaderboardSnapshot, ReclaimEvent

_logger = slog.get_logger("compute-scheduler")


class ComputeScheduler:
    """加权算力调度控制器（R9）。

    A:B:C=60:30:10 权重 + 看榜倾斜 + 25min 零新增回收。
    """

    def __init__(self, snapshot_store=None) -> None:
        """
        Args:
            snapshot_store: SnapshotStore 实例（R4 断点续跑快照）。
                           为 None 时内部创建（用于测试）。
        """
        if snapshot_store is None:
            from passive_agent.approval.snapshot import SnapshotStore
            snapshot_store = SnapshotStore()
        self.snapshot_store = snapshot_store
        self._task_idle: Dict[str, float] = {}           # task_id → 首次零新增时间戳
        self._last_leaderboard: Optional[LeaderboardSnapshot] = None
        self._allocations: Dict[str, ComputeQuota] = {}  # task_id → quota
        self._tilt_factors: Dict[str, float] = {}        # task_id → 倾斜系数
        self._reclaim_events: List[ReclaimEvent] = []     # 回收事件历史

    def allocate(self, tasks: List[Dict[str, Any]]) -> Dict[str, ComputeQuota]:
        """按 A:B:C 权重分配算力配额。

        Args:
            tasks: [{task_id, enterprise, cluster(A/B/C)}]

        Returns:
            {task_id: ComputeQuota}
        """
        weights = settings.COMPUTE_WEIGHTS  # {"A":60,"B":30,"C":10}
        total_slots = 100
        a_pct = float(weights.get("A", 60))
        b_pct = float(weights.get("B", 30))
        c_pct = float(weights.get("C", 10))

        result: Dict[str, ComputeQuota] = {}
        for task in tasks:
            task_id = task.get("task_id", "")
            cluster = task.get("cluster", "B")
            if cluster == "A":
                pct_a, pct_b, pct_c = a_pct, 0.0, 0.0
                slots = int(total_slots * a_pct / 100)
            elif cluster == "C":
                pct_a, pct_b, pct_c = 0.0, 0.0, c_pct
                slots = int(total_slots * c_pct / 100)
            else:  # B
                pct_a, pct_b, pct_c = 0.0, b_pct, 0.0
                slots = int(total_slots * b_pct / 100)

            quota = ComputeQuota(
                cluster_a_pct=a_pct,
                cluster_b_pct=b_pct,
                cluster_c_pct=c_pct,
                total_slots=slots,
            )
            result[task_id] = quota
            self._allocations[task_id] = quota

        _logger.info(f"算力分配完成: {len(result)} 个任务, A:B:C={a_pct}:{b_pct}:{c_pct}")
        return result

    def tilt_by_leaderboard(self, leaderboard: LeaderboardSnapshot) -> Dict[str, float]:
        """读榜单快照，计算各任务边际贡献，返回倾斜系数。

        边际贡献 A:B:C≈36:9:1 作为倾斜依据（规划建议值）。
        高边际任务获得更高倾斜系数。
        """
        self._last_leaderboard = leaderboard
        tilt_factors: Dict[str, float] = {}

        # 边际贡献基准（A:B:C≈36:9:1）
        marginal_base = {"A": 36.0, "B": 9.0, "C": 1.0}

        for score in leaderboard.task_scores:
            task_id = score.get("task_id", "")
            cluster = score.get("cluster", "B")
            marginal_score = float(score.get("marginal_score", 0.0))
            new_count = int(score.get("new_count", 0))

            # 倾斜系数 = 边际贡献基准 × 任务边际得分 × (1 + 新增加成)
            base = marginal_base.get(cluster, 1.0)
            new_bonus = 1.0 + min(new_count * 0.01, 0.5)  # 新增多则倾斜多
            tilt = base * (1.0 + marginal_score * 0.01) * new_bonus
            tilt_factors[task_id] = round(tilt, 4)
            self._tilt_factors[task_id] = tilt

        _logger.info(f"看榜倾斜计算完成: {len(tilt_factors)} 个任务")
        return tilt_factors

    def check_reclaim(self, task_id: str, enterprise: str,
                      has_new: bool) -> Optional[ReclaimEvent]:
        """检查是否需要回收（25min 零新增）。

        回收前调 SnapshotStore.save() 存断点快照（进度零丢失）。
        回收事件写 t_audit_log(reason_code=030001)。

        Args:
            task_id: 任务 ID
            enterprise: 企业名
            has_new: 本轮是否有新增资产

        Returns:
            ReclaimEvent 或 None（未触发回收）
        """
        now = time.time()
        reclaim_minutes = settings.IDLE_RECLAIM_MINUTES

        if has_new:
            # 有新增：重置空闲计时
            self._task_idle.pop(task_id, None)
            return None

        # 无新增：记录/检查空闲时长
        if task_id not in self._task_idle:
            self._task_idle[task_id] = now
            return None

        idle_seconds = now - self._task_idle[task_id]
        idle_minutes = int(idle_seconds / 60)

        if idle_minutes < reclaim_minutes:
            return None

        # 达到回收阈值：回收前存断点快照
        snapshot_saved = False
        try:
            self.snapshot_store.save(task_id, -1, {
                "phase": "reclaim",
                "enterprise": enterprise,
                "idle_minutes": idle_minutes,
                "reclaimed_at": datetime.now(timezone.utc).isoformat(),
            })
            snapshot_saved = True
        except Exception as exc:
            _logger.error(f"回收前快照保存失败 task_id={task_id}: {exc}")

        event = ReclaimEvent(
            task_id=task_id,
            enterprise=enterprise,
            idle_minutes=idle_minutes,
            reason_code="030001",
            snapshot_saved=snapshot_saved,
            reclaimed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._reclaim_events.append(event)

        # 清除空闲计时
        self._task_idle.pop(task_id, None)

        # 回收事件写审计日志
        try:
            from passive_agent import audit

            audit.log(
                action="COMPUTE_RECLAIM",
                source="compute-scheduler",
                decision="RECLAIM",
                reason_code="030001",
                msg=f"算力回收 task_id={task_id} enterprise={enterprise} "
                    f"idle={idle_minutes}min snapshot_saved={snapshot_saved}",
                subject_id=enterprise,
            )
        except Exception:
            pass

        _logger.info(
            f"算力回收: task_id={task_id} idle={idle_minutes}min "
            f"snapshot_saved={snapshot_saved}"
        )
        return event

    def get_status(self) -> Dict[str, Any]:
        """返回当前算力分配/倾斜/回收状态（供 R11 M6 面板）。"""
        return {
            "allocations": {
                tid: q.model_dump() for tid, q in self._allocations.items()
            },
            "tilt_factors": dict(self._tilt_factors),
            "reclaim_events": [e.model_dump() for e in self._reclaim_events],
            "idle_tasks": list(self._task_idle.keys()),
            "compute_weights": settings.COMPUTE_WEIGHTS,
            "idle_reclaim_minutes": settings.IDLE_RECLAIM_MINUTES,
            "leaderboard_interval": settings.LEADERBOARD_INTERVAL,
        }

    def get_reclaim_events(self) -> List[ReclaimEvent]:
        """返回回收事件历史。"""
        return list(self._reclaim_events)
