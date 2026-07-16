"""小程序集群适配器（蓝图 T20）。

凭证源适配器 + mock 回退。小程序数据需通过微信开放平台获取。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("miniapp-adapter")


class MiniappAdapter(SourceAdapter):
    """小程序集群凭证源适配器（缺凭证回退 mock）。"""

    name = "miniapp-api"
    cluster = CollectorCluster.MINIAPP
    requires_credential = True
    priority = 60

    def is_available(self) -> bool:
        """检查小程序 API 凭证是否就绪。"""
        miniapp_token = getattr(settings, "MINIAPP_TOKEN", None)
        return bool(miniapp_token)

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """调小程序 API 查询。缺凭证时返回失败结果。"""
        if not self.is_available():
            return CollectResult(
                query=query,
                items=[],
                source_name=self.name,
                success=False,
                error="小程序 API 凭证未配置，触发 mock 回退",
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        # 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        # 小程序 API 调用（接口已实现，凭证到位后填充真实逻辑）
        items: List[CollectItem] = []
        error_msg = "小程序 API 暂未接入真实源"

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=False,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
