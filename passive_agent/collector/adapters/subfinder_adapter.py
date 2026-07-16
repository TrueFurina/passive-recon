"""Web 集群 — Subfinder 凭证源适配器（蓝图 T20）。

requires_credential=True，缺凭证时 is_available() 返回 False，触发 mock 回退。
Subfinder 是子域名发现工具，此处封装为适配器接口。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("subfinder-adapter")


class SubfinderAdapter(SourceAdapter):
    """Subfinder 凭证源适配器（缺凭证回退 mock）。"""

    name = "subfinder"
    cluster = CollectorCluster.WEB
    requires_credential = True
    priority = 40

    def is_available(self) -> bool:
        """检查 Subfinder 凭证是否就绪。"""
        subfinder_config = getattr(settings, "SUBFINDER_CONFIG", None)
        return bool(subfinder_config)

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """调 Subfinder 查询子域名。缺凭证时返回失败结果。"""
        if not self.is_available():
            return CollectResult(
                query=query,
                items=[],
                source_name=self.name,
                success=False,
                error="Subfinder 凭证未配置，触发 mock 回退",
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        # 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        # Subfinder 为本地工具调用（非 HTTP），此处接口已实现，
        # 真实场景通过 subprocess 调 subfinder CLI。
        # 当前缺凭证直接返回空结果（由 FTM 回退 mock）
        items: List[CollectItem] = []
        error_msg = "Subfinder 工具未安装或未配置"

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=False,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
