"""数据源健康度监测 — 记录每个数据源的成功率/延迟/故障，自动降级。

核心能力：
1. 每个数据源记录：成功次数、失败次数、平均延迟、连续失败数、上次调用时间
2. 健康状态判定：HEALTHY / DEGRADED / UNAVAILABLE
3. 自动降级：连续失败超过阈值 → 标记不可用，采集时跳过
4. 冷却恢复：不可用源经过冷却时间后自动恢复
5. 状态落 t_source_health 表 + 可查询
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from passive_agent.common import logging as clog
from passive_agent.storage import db

_logger = clog.get_logger("source-health")

# 健康阈值
DEGRADE_THRESHOLD = 2          # 连续失败 2 次 → DEGRADED
UNAVAILABLE_THRESHOLD = 5      # 连续失败 5 次 → UNAVAILABLE
COOLDOWN_SECONDS = 300         # 不可用源冷却 5 分钟后恢复
SUCCESS_RATE_WINDOW = 20       # 统计最近 20 次调用的成功率


class SourceHealthState:
    """单个数据源的健康状态。"""

    def __init__(self, name: str):
        self.name = name
        self.success_count = 0
        self.fail_count = 0
        self.consecutive_failures = 0
        self.last_latency_ms = 0.0
        self.avg_latency_ms = 0.0
        self._latency_samples: List[float] = []
        self.last_called_at: Optional[str] = None
        self.last_error: str = ""
        self.cooldown_until: float = 0.0
        self._recent: List[bool] = []  # 最近调用的成功/失败记录

    @property
    def status(self) -> str:
        """健康状态：HEALTHY / DEGRADED / UNAVAILABLE。"""
        if time.time() < self.cooldown_until:
            return "UNAVAILABLE"
        if self.consecutive_failures >= UNAVAILABLE_THRESHOLD:
            return "UNAVAILABLE"
        if self.consecutive_failures >= DEGRADE_THRESHOLD:
            return "DEGRADED"
        return "HEALTHY"

    @property
    def is_available(self) -> bool:
        return self.status != "UNAVAILABLE"

    @property
    def success_rate(self) -> float:
        """最近窗口内的成功率（0-100）。"""
        if not self._recent:
            return 100.0
        return round(sum(self._recent) / len(self._recent) * 100, 1)

    def record(self, success: bool, latency_ms: float = 0.0, error: str = "") -> None:
        """记录一次调用结果。"""
        if success:
            self.success_count += 1
            self.consecutive_failures = 0
            self.last_error = ""
        else:
            self.fail_count += 1
            self.consecutive_failures += 1
            self.last_error = error[:200]
            # 连续失败达到阈值 → 进入冷却
            if self.consecutive_failures >= UNAVAILABLE_THRESHOLD:
                self.cooldown_until = time.time() + COOLDOWN_SECONDS
                _logger.warn(f"数据源 {self.name} 连续失败 {self.consecutive_failures} 次，"
                             f"冷却 {COOLDOWN_SECONDS}s")

        self.last_latency_ms = latency_ms
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 20:
            self._latency_samples.pop(0)
        self.avg_latency_ms = round(
            sum(self._latency_samples) / len(self._latency_samples), 1
        ) if self._latency_samples else 0.0
        self.last_called_at = datetime.now(timezone.utc).isoformat()[:19]

        self._recent.append(success)
        if len(self._recent) > SUCCESS_RATE_WINDOW:
            self._recent.pop(0)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "success_rate": self.success_rate,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency_ms": self.avg_latency_ms,
            "last_called_at": self.last_called_at,
            "last_error": self.last_error[:100],
            "cooldown_remaining": round(max(0, self.cooldown_until - time.time()), 1),
        }


class SourceHealthMonitor:
    """数据源健康监测器（线程安全单例）。"""

    def __init__(self) -> None:
        self._states: Dict[str, SourceHealthState] = {}
        self._lock = threading.Lock()

    def get_state(self, name: str) -> SourceHealthState:
        with self._lock:
            if name not in self._states:
                self._states[name] = SourceHealthState(name)
            return self._states[name]

    def record_success(self, name: str, latency_ms: float = 0.0) -> None:
        self.get_state(name).record(True, latency_ms)
        self._persist(name)

    def record_failure(self, name: str, error: str = "", latency_ms: float = 0.0) -> None:
        self.get_state(name).record(False, latency_ms, error)
        self._persist(name)

    def is_available(self, name: str) -> bool:
        return self.get_state(name).is_available

    def status(self, name: str) -> str:
        return self.get_state(name).status

    def snapshot(self) -> List[Dict]:
        """获取所有数据源的健康快照（按状态排序：UNAVAILABLE → DEGRADED → HEALTHY）。"""
        with self._lock:
            states = [s.to_dict() for s in self._states.values()]
        order = {"UNAVAILABLE": 0, "DEGRADED": 1, "HEALTHY": 2}
        states.sort(key=lambda d: order.get(d["status"], 9))
        return states

    def summary(self) -> Dict:
        """汇总统计。"""
        snap = self.snapshot()
        return {
            "total": len(snap),
            "healthy": sum(1 for s in snap if s["status"] == "HEALTHY"),
            "degraded": sum(1 for s in snap if s["status"] == "DEGRADED"),
            "unavailable": sum(1 for s in snap if s["status"] == "UNAVAILABLE"),
            "sources": snap,
        }

    def _persist(self, name: str) -> None:
        """落 t_source_health 表（看板数据源）。best-effort。"""
        try:
            s = self.get_state(name)
            db.write(
                "INSERT OR REPLACE INTO t_source_health "
                "(source_name, status, success_rate, success_count, fail_count, "
                "consecutive_failures, avg_latency_ms, last_error, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
                (name, s.status, s.success_rate, s.success_count, s.fail_count,
                 s.consecutive_failures, s.avg_latency_ms, s.last_error[:100]),
            )
        except Exception:
            pass


# 全局单例
_monitor: Optional[SourceHealthMonitor] = None
_monitor_lock = threading.Lock()


def get_health_monitor() -> SourceHealthMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = SourceHealthMonitor()
    return _monitor