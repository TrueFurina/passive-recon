"""R9 算力调度测试（蓝图 T29）。

覆盖：
- A:B:C=60:30:10 权重分配
- 25min 回收触发 + 快照保存
- 看榜倾斜计算
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from passive_agent.scheduler.compute_scheduler import ComputeScheduler
from passive_agent.scheduler.model import ComputeQuota, LeaderboardSnapshot, ReclaimEvent
from passive_agent.config import settings


class TestComputeAllocation:
    """权重分配测试。"""

    def test_abc_weights(self):
        """A:B:C=60:30:10 权重分配（V-R9-1）。"""
        sched = ComputeScheduler()
        tasks = [
            {"task_id": "T1", "enterprise": "企业A", "cluster": "A"},
            {"task_id": "T2", "enterprise": "企业B", "cluster": "B"},
            {"task_id": "T3", "enterprise": "企业C", "cluster": "C"},
        ]
        quotas = sched.allocate(tasks)
        assert "T1" in quotas
        assert "T2" in quotas
        assert "T3" in quotas

        # 验证权重
        q = quotas["T1"]
        assert q.cluster_a_pct == 60.0
        assert q.cluster_b_pct == 30.0
        assert q.cluster_c_pct == 10.0

    def test_configurable_weights(self):
        """权重可配置（通过 COMPUTE_WEIGHTS 配置项）。"""
        weights = settings.COMPUTE_WEIGHTS
        assert weights["A"] == 60
        assert weights["B"] == 30
        assert weights["C"] == 10

    def test_allocation_slots(self):
        """A 类任务分配 60 槽位。"""
        sched = ComputeScheduler()
        tasks = [{"task_id": "T1", "enterprise": "企业A", "cluster": "A"}]
        quotas = sched.allocate(tasks)
        assert quotas["T1"].total_slots == 60  # 100 * 60%


class TestReclaimController:
    """回收控制器测试。"""

    def test_reclaim_after_idle(self):
        """25min 零新增回收（V-R9-3）。"""
        mock_snapshot = MagicMock()
        sched = ComputeScheduler(snapshot_store=mock_snapshot)

        # 模拟空闲超过 25 分钟
        task_id = "TASK-test"
        sched._task_idle[task_id] = time.time() - (26 * 60)  # 26 分钟前

        event = sched.check_reclaim(task_id, "测试企业", has_new=False)
        assert event is not None
        assert event.task_id == task_id
        assert event.idle_minutes >= 25
        assert event.reason_code == "030001"
        assert event.snapshot_saved  # 快照已保存

        # 验证快照保存调用
        mock_snapshot.save.assert_called_once()

    def test_no_reclaim_with_new(self):
        """有新增时不回收。"""
        mock_snapshot = MagicMock()
        sched = ComputeScheduler(snapshot_store=mock_snapshot)

        # 先记录空闲
        sched._task_idle["TASK-test"] = time.time() - (30 * 60)
        event = sched.check_reclaim("TASK-test", "测试企业", has_new=True)
        assert event is None
        # 空闲计时被重置
        assert "TASK-test" not in sched._task_idle

    def test_no_reclaim_within_threshold(self):
        """未达 25min 不回收。"""
        mock_snapshot = MagicMock()
        sched = ComputeScheduler(snapshot_store=mock_snapshot)

        sched._task_idle["TASK-test"] = time.time() - (10 * 60)  # 10 分钟
        event = sched.check_reclaim("TASK-test", "测试企业", has_new=False)
        assert event is None

    def test_reclaim_logs_audit(self):
        """回收事件写 t_audit_log(reason_code=030001)（V-R9-4）。"""
        mock_snapshot = MagicMock()
        sched = ComputeScheduler(snapshot_store=mock_snapshot)

        task_id = "TASK-audit-test"
        sched._task_idle[task_id] = time.time() - (26 * 60)
        sched.check_reclaim(task_id, "审计测试企业", has_new=False)

        from passive_agent.audit.logger import search
        logs = search(reason_code="030001", limit=5)
        assert len(logs) > 0
        assert any("回收" in (l.get("msg", "") or "") for l in logs)


class TestLeaderboardTilt:
    """看榜倾斜测试。"""

    def test_tilt_calculation(self):
        """看榜倾斜计算（V-R9-2）。"""
        sched = ComputeScheduler()
        leaderboard = LeaderboardSnapshot(
            snapshot_at="2026-07-13T10:00:00Z",
            task_scores=[
                {"task_id": "T1", "marginal_score": 10.0, "cluster": "A", "new_count": 5},
                {"task_id": "T2", "marginal_score": 5.0, "cluster": "B", "new_count": 3},
                {"task_id": "T3", "marginal_score": 1.0, "cluster": "C", "new_count": 1},
            ],
        )
        tilt = sched.tilt_by_leaderboard(leaderboard)
        assert "T1" in tilt
        assert "T2" in tilt
        assert "T3" in tilt
        # A 类任务倾斜系数应高于 C 类（边际贡献 A:B:C≈36:9:1）
        assert tilt["T1"] > tilt["T3"]

    def test_get_status(self):
        """get_status 返回算力分配/倾斜/回收状态。"""
        sched = ComputeScheduler()
        sched.allocate([{"task_id": "T1", "enterprise": "企业", "cluster": "A"}])
        status = sched.get_status()
        assert "allocations" in status
        assert "tilt_factors" in status
        assert "reclaim_events" in status
        assert "compute_weights" in status
        assert status["compute_weights"] == {"A": 60, "B": 30, "C": 10}
