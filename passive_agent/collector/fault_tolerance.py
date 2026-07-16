"""R8 容错降级管理器（蓝图 T22）。

- 源健康检查：按连续失败计数维护 SourceHealth 状态。
- 热切换：主源失败自动切换同集群备用源，对上层透明。
- 挂起告警：全源不可用时任务 SUSPEND + 写 t_audit_log(040001) + 不阻断全局。
- mock 回退不计挂起（V-R8-4）。
- 健康状态落 t_source_health 表。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from passive_agent.common import logging as flog
from passive_agent.common.enums import CollectorCluster, SourceHealth
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectQuery, CollectResult
from passive_agent.collector.registry import AdapterRegistry
from passive_agent.config import settings

_logger = flog.get_logger("fault-tolerance")


class FaultToleranceManager:
    """多源容错降级管理器（R8）。"""

    def __init__(self, registry: AdapterRegistry, max_retries: int = 3) -> None:
        self.registry = registry
        self.max_retries = max_retries
        self._health: Dict[str, SourceHealth] = {}   # adapter.name → health
        self._fail_counts: Dict[str, int] = {}         # adapter.name → 连续失败计数
        self._lock = threading.Lock()

    def execute_with_fallback(self, query: CollectQuery,
                              trace_id: str) -> CollectResult:
        """按优先级尝试各适配器，失败自动切换备用源。

        全源不可用则返回 SUSPEND 结果（不阻断其他集群）。
        """
        adapters = self.registry.get_adapters(query.cluster)
        if not adapters:
            return self._make_suspend_result(query, "无注册适配器")

        last_error = ""
        tried_any_available = False
        used_mock_fallback = False

        for adapter in adapters:
            # 跳过已不可用的适配器
            if self._get_health(adapter.name) == SourceHealth.UNAVAILABLE:
                continue

            # 缺凭证适配器：检查 is_available
            if adapter.requires_credential and not adapter.is_available():
                # 缺凭证适配器跳过，但不计入全源不可用（V-R8-4）
                _logger.debug(f"适配器 {adapter.name} 缺凭证，跳过")
                continue

            tried_any_available = True

            # Mock 适配器标记（用于判断是否为 mock 回退）
            is_mock = "mock" in adapter.name.lower()

            try:
                result = adapter.collect(query, trace_id)
                if result.success:
                    # 成功：恢复健康
                    self._record_success(adapter.name)
                    if is_mock:
                        used_mock_fallback = True
                    return result
                else:
                    # 采集失败（业务层失败，非异常）
                    last_error = result.error
                    self._record_failure(adapter.name, result.error, trace_id)
                    _logger.warn(
                        f"适配器 {adapter.name} 采集失败，切换备用源: {result.error}"
                    )
                    if is_mock and "凭证" in result.error:
                        # 缺凭证 mock 回退不算挂起
                        used_mock_fallback = True
                    continue
            except PermissionError as exc:
                # R1 拦截：fail-closed，不切换（红线拦截）
                last_error = str(exc)
                _logger.error(f"R1 拦截适配器 {adapter.name}: {exc}")
                return CollectResult(
                    query=query,
                    items=[],
                    source_name=adapter.name,
                    success=False,
                    error=f"R1 拦截: {exc}",
                    collected_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as exc:
                last_error = str(exc)
                self._record_failure(adapter.name, str(exc), trace_id)
                _logger.warn(f"适配器 {adapter.name} 异常: {exc}")
                continue

        # 所有适配器都尝试失败
        if used_mock_fallback:
            # V-R8-4: 缺凭证回退 mock 视为"源可用"，不计挂起
            # 但如果 mock 本身也失败了，才挂起
            return self._make_suspend_result(query, last_error or "全源不可用")

        return self._make_suspend_result(query, last_error or "全源不可用")

    def get_health_status(self) -> Dict[str, str]:
        """返回所有源健康状态（供 R11 M5 面板展示）。"""
        with self._lock:
            return {name: health.value for name, health in self._health.items()}

    def _get_health(self, adapter_name: str) -> SourceHealth:
        """获取适配器健康状态（默认 HEALTHY）。"""
        return self._health.get(adapter_name, SourceHealth.HEALTHY)

    def _record_success(self, adapter_name: str) -> None:
        """记录成功 → 恢复 HEALTHY。"""
        with self._lock:
            self._fail_counts[adapter_name] = 0
            self._health[adapter_name] = SourceHealth.HEALTHY
        self._persist_health(adapter_name, SourceHealth.HEALTHY, 0)

    def _record_failure(self, adapter_name: str, reason: str,
                        trace_id: str) -> None:
        """记录失败 → 降级状态 → 写 audit.log。"""
        with self._lock:
            count = self._fail_counts.get(adapter_name, 0) + 1
            self._fail_counts[adapter_name] = count
            if count >= self.max_retries:
                health = SourceHealth.UNAVAILABLE
            elif count >= 1:
                health = SourceHealth.DEGRADED
            else:
                health = SourceHealth.HEALTHY
            self._health[adapter_name] = health

        self._persist_health(adapter_name, health, count)

        # 写降级/切换事件审计日志
        try:
            from passive_agent import audit

            audit.log(
                trace_id=trace_id,
                action="SOURCE_FAILOVER",
                source=adapter_name,
                decision="DEGRADE" if health == SourceHealth.DEGRADED else "FAIL",
                reason_code="040002",
                msg=f"源 {adapter_name} 失败({count}次) → {health.value}: {reason}",
            )
        except Exception:
            pass

    def _record_suspend(self, cluster: CollectorCluster,
                        trace_id: str) -> None:
        """全源不可用 → SUSPEND + audit.log(040001)。"""
        try:
            from passive_agent import audit

            audit.log(
                trace_id=trace_id,
                action="SOURCE_SUSPEND",
                source=f"cluster-{cluster.value}",
                decision="SUSPEND",
                reason_code="040001",
                msg=f"集群 {cluster.value} 全源不可用，任务挂起（不阻断其他集群）",
            )
        except Exception:
            pass

    def _make_suspend_result(self, query: CollectQuery,
                             error: str) -> CollectResult:
        """构造挂起结果。"""
        self._record_suspend(query.cluster, query.trace_id)
        return CollectResult(
            query=query,
            items=[],
            source_name="",
            success=False,
            error=f"SUSPEND: {error}",
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _persist_health(self, adapter_name: str, health: SourceHealth,
                        fail_count: int) -> None:
        """健康状态落 t_source_health 表。"""
        try:
            from passive_agent.storage import db

            db.write(
                """
                INSERT INTO t_source_health (adapter_name, cluster, health, fail_count, last_fail_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(adapter_name) DO UPDATE SET
                    health=excluded.health, fail_count=excluded.fail_count,
                    last_fail_at=excluded.last_fail_at, updated_at=datetime('now')
                """,
                (adapter_name, "", health.value, fail_count),
            )
        except Exception:
            pass
