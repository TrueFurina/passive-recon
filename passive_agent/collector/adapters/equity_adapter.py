"""工商股权集群适配器（蓝图 T20）。

凭证源适配器 + mock 回退。工商股权数据需通过工商 API（爱企查/ENScan_GO）获取。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("equity-adapter")


class EquityAdapter(SourceAdapter):
    """工商股权集群凭证源适配器（缺凭证回退 mock）。"""

    name = "equity-api"
    cluster = CollectorCluster.EQUITY
    requires_credential = True
    priority = 70

    def is_available(self) -> bool:
        """检查工商 API 凭证是否就绪。"""
        equity_token = getattr(settings, "EQUITY_TOKEN", None)
        return bool(equity_token)

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """调工商 API 查询股权关系。缺凭证时返回失败结果。"""
        if not self.is_available():
            return CollectResult(
                query=query,
                items=[],
                source_name=self.name,
                success=False,
                error="工商 API 凭证未配置，触发 mock 回退",
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        # 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        # 工商 API 调用（接口已实现，凭证到位后填充真实逻辑）
        items: List[CollectItem] = []
        error_msg = "工商 API 暂未接入真实源"

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=False,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
