"""R7 适配器抽象基类（ACL 防腐层接口，蓝图 §3.2）。

所有适配器出站前必须经 compliance_client.check(PASSIVE_QUERY)。
白名单被动接口，可注册/发现/可插拔。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from passive_agent.common.enums import ActionType, CollectorCluster
from passive_agent.collector.model import CollectQuery, CollectResult


class SourceAdapter(ABC):
    """被动源适配器抽象基类（ACL 防腐层）。

    子类必须实现 collect()；出站前首行调 _check_compliance()。
    """

    name: str = "base"                          # 适配器唯一名
    cluster: CollectorCluster = CollectorCluster.WEB  # 所属集群
    requires_credential: bool = False           # 是否需要凭证
    priority: int = 100                         # 优先级（小=高优先）

    @abstractmethod
    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """采集入口。出站前必经 R1 关隘。"""
        ...

    def _check_compliance(self, trace_id: str) -> None:
        """出站前必经 R1 fail-closed 关隘。

        未 ALLOW 抛 PermissionError，阻止出站。
        """
        from passive_agent.common.compliance_client import check

        decision = check(
            ActionType.PASSIVE_QUERY,
            source_name=self.name,
            trace_id=trace_id,
        )
        if not decision.allowed:
            raise PermissionError(f"R1 拦截：{decision.reason_code}")

    def is_available(self) -> bool:
        """检查凭证/配置是否就绪。

        缺凭证返回 False 以触发 mock 回退（V-R8-4）。
        """
        return True
