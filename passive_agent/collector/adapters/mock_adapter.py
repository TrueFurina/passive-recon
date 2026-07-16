"""通用 mock 回退适配器（蓝图 T20）。

所有集群缺凭证/失败时的回退源。确定性 mock 数据，保证闭环不中断。
mock 回退视为"源可用"，不计入全源不可用挂起（V-R8-4）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult

_logger = clog.get_logger("mock-adapter")


class MockAdapter(SourceAdapter):
    """通用 mock 回退源（确定性数据，保证闭环不中断）。

    每个集群实例化一个 MockAdapter，设置不同 cluster 属性。
    """

    name = "mock"
    cluster = CollectorCluster.WEB
    requires_credential = False
    priority = 999  # 最低优先（仅作为回退）

    def __init__(self, cluster: CollectorCluster | None = None,
                 name: str | None = None) -> None:
        if cluster is not None:
            self.cluster = cluster
        if name is not None:
            self.name = name
        elif type(self) is MockAdapter:
            # Only set default cluster-specific name for MockAdapter itself;
            # subclasses keep their class-level name attribute.
            self.name = f"mock-{self.cluster.value.lower()}"

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """返回确定性 mock 采集数据。"""
        # mock 源不出站，但为保持接口一致性仍记录合规关隘调用
        # （不实际出站网络，故不触发 R1 真实拦截）

        items = self._generate_mock_items(query)
        _logger.info(
            f"Mock 适配器返回 {len(items)} 项 "
            f"cluster={query.cluster.value} enterprise={query.enterprise}"
        )

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=True,
            error="",
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _generate_mock_items(self, query: CollectQuery) -> List[CollectItem]:
        """根据集群类型生成确定性 mock 数据。"""
        # 用企业名做哈希种子，保证同一企业结果确定性
        seed = hashlib.md5(f"{query.enterprise}-{query.cluster.value}".encode()).hexdigest()[:8]
        cluster = query.cluster

        if cluster == CollectorCluster.WEB:
            return [
                CollectItem(
                    item_type="domain",
                    value=f"www.{query.enterprise[:4].lower()}.com",
                    source_name=self.name,
                    raw={"mock": True, "seed": seed},
                ),
                CollectItem(
                    item_type="domain",
                    value=f"mail.{query.enterprise[:4].lower()}.com",
                    source_name=self.name,
                    raw={"mock": True, "seed": seed},
                ),
            ]
        elif cluster == CollectorCluster.WECHAT:
            return [
                CollectItem(
                    item_type="wechat_account",
                    value=f"{query.enterprise[:4]}官方公众号",
                    source_name=self.name,
                    raw={"mock": True, "seed": seed},
                ),
            ]
        elif cluster == CollectorCluster.MINIAPP:
            return [
                CollectItem(
                    item_type="mini_program",
                    value=f"{query.enterprise[:4]}小程序",
                    source_name=self.name,
                    raw={"mock": True, "seed": seed},
                ),
            ]
        elif cluster == CollectorCluster.EQUITY:
            return [
                CollectItem(
                    item_type="equity_relation",
                    value=f"{query.enterprise}-控股子公司",
                    source_name=self.name,
                    raw={"mock": True, "seed": seed, "relation": "控股子公司"},
                ),
            ]
        else:
            return []
