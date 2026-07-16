"""R7 调度编排内核（蓝图 T21）。

CollectionScheduler：100% 自研。
职责：任务分解（按集群拆子任务）→ 分发（调适配器 collect）→
     汇总（合并 CollectResult）→ 状态机管理。
不依赖任何外部调度框架。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from passive_agent.common import logging as slog
from passive_agent.common.enums import CollectorCluster, TaskState
from passive_agent.common.result import gen_trace_id, now_iso
from passive_agent.collector.fault_tolerance import FaultToleranceManager
from passive_agent.collector.model import CollectQuery, CollectResult
from passive_agent.collector.registry import AdapterRegistry
from passive_agent.config import settings

_logger = slog.get_logger("collector-scheduler")


class CollectionScheduler:
    """调度编排内核（100% 自研）。

    任务分解 → 分发 → 汇总 → 状态机。
    """

    # 四类集群全量
    ALL_CLUSTERS: List[CollectorCluster] = [
        CollectorCluster.WEB,
        CollectorCluster.WECHAT,
        CollectorCluster.MINIAPP,
        CollectorCluster.EQUITY,
    ]

    def __init__(self, registry: Optional[AdapterRegistry] = None,
                 ftm: Optional[FaultToleranceManager] = None) -> None:
        self.registry = registry or AdapterRegistry()
        self.ftm = ftm or FaultToleranceManager(self.registry)
        self._task_states: Dict[str, TaskState] = {}  # task_id → state

    def collect(self, enterprise: str, subject_name: str,
                trace_id: str = "") -> List[CollectResult]:
        """对单个主体执行四集群采集，返回各集群结果列表。

        1) 任务分解：为四类集群各创建 CollectQuery
        2) 分发：对每个集群调用 ftm.execute_with_fallback()
        3) 汇总：合并结果返回
        """
        if not trace_id:
            trace_id = gen_trace_id()

        task_id = f"COLLECT-{enterprise}-{subject_name}"
        self._set_state(task_id, TaskState.RUNNING)
        self._audit(trace_id, task_id, enterprise, "COLLECT_START",
                    f"调度内核启动四集群采集 enterprise={enterprise} subject={subject_name}")

        results: List[CollectResult] = []
        for cluster in self.ALL_CLUSTERS:
            query = CollectQuery(
                enterprise=enterprise,
                subject_name=subject_name,
                cluster=cluster,
                trace_id=trace_id,
            )
            # 分发：经容错管理器执行（含热切换/挂起）
            result = self.ftm.execute_with_fallback(query, trace_id)
            results.append(result)

        # 汇总：检查是否有 SUSPEND
        has_suspend = any(not r.success and "SUSPEND" in r.error for r in results)
        if has_suspend:
            self._set_state(task_id, TaskState.SUSPENDED)
            self._audit(trace_id, task_id, enterprise, "COLLECT_SUSPEND",
                        "部分集群全源不可用，任务挂起（不阻断其他集群）")
        else:
            self._set_state(task_id, TaskState.COMPLETED)
            self._audit(trace_id, task_id, enterprise, "COLLECT_DONE",
                        f"四集群采集完成，成功 {sum(1 for r in results if r.success)}/{len(results)} 集群")

        return results

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """获取任务当前状态。"""
        return self._task_states.get(task_id)

    def _set_state(self, task_id: str, state: TaskState) -> None:
        """设置任务状态（状态机：PENDING→RUNNING→DONE/SUSPENDED）。"""
        self._task_states[task_id] = state

    def _audit(self, trace_id: str, task_id: str, enterprise: str,
               action: str, msg: str) -> None:
        """写全链路审计日志。"""
        try:
            from passive_agent import audit

            audit.log(
                trace_id=trace_id,
                subject_id=enterprise,
                action=action,
                source="collector-scheduler",
                decision="ALLOW",
                reason_code="000000",
                msg=msg,
            )
        except Exception:
            pass

    @staticmethod
    def create_default() -> "CollectionScheduler":
        """创建带默认适配器注册的调度器（工厂方法）。"""
        from passive_agent.collector.adapters import (
            CrtshAdapter, DnsAdapter, FofaAdapter, SubfinderAdapter,
            WechatAdapter, MiniappAdapter, EquityAdapter, MockAdapter,
        )

        registry = AdapterRegistry()
        # Web 集群：crt.sh + DNS（真实免凭证）+ FOFA + Subfinder（凭证）+ Mock（回退）
        registry.register(CrtshAdapter())
        registry.register(DnsAdapter())
        registry.register(FofaAdapter())
        registry.register(SubfinderAdapter())
        registry.register(MockAdapter(cluster=CollectorCluster.WEB))
        # 公众号集群：WechatAdapter（凭证）+ Mock（回退）
        registry.register(WechatAdapter())
        registry.register(MockAdapter(cluster=CollectorCluster.WECHAT))
        # 小程序集群：MiniappAdapter（凭证）+ Mock（回退）
        registry.register(MiniappAdapter())
        registry.register(MockAdapter(cluster=CollectorCluster.MINIAPP))
        # 工商股权集群：EquityAdapter（凭证）+ Mock（回退）
        registry.register(EquityAdapter())
        registry.register(MockAdapter(cluster=CollectorCluster.EQUITY))

        ftm = FaultToleranceManager(registry, max_retries=settings.FAULT_MAX_RETRIES)
        return CollectionScheduler(registry, ftm)
