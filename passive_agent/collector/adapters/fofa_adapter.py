"""Web 集群 — FOFA 凭证源适配器（蓝图 T20）。

requires_credential=True，缺凭证时 is_available() 返回 False，触发 mock 回退。
凭证由用户后续填入 config（FOFA_EMAIL / FOFA_KEY）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("fofa-adapter")


class FofaAdapter(SourceAdapter):
    """FOFA 凭证源适配器（缺凭证回退 mock）。"""

    name = "fofa"
    cluster = CollectorCluster.WEB
    requires_credential = True
    priority = 30

    def is_available(self) -> bool:
        """检查 FOFA 凭证是否就绪。"""
        fofa_email = getattr(settings, "FOFA_EMAIL", None)
        fofa_key = getattr(settings, "FOFA_KEY", None)
        return bool(fofa_email and fofa_key)

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """调 FOFA API 查询域名/子域名。缺凭证时返回失败结果。"""
        if not self.is_available():
            return CollectResult(
                query=query,
                items=[],
                source_name=self.name,
                success=False,
                error="FOFA 凭证未配置，触发 mock 回退",
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        # 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        items: List[CollectItem] = []
        error_msg = ""
        timeout = settings.SOURCE_TIMEOUT

        try:
            import httpx

            fofa_email = getattr(settings, "FOFA_EMAIL", "")
            fofa_key = getattr(settings, "FOFA_KEY", "")
            # FOFA API 查询（base64 编码查询语句）
            import base64
            qbase64 = base64.b64encode(f'cert="{query.enterprise}"'.encode()).decode()
            url = f"https://fofa.info/api/v1/search/all?email={fofa_email}&key={fofa_key}&qbase64={qbase64}&size=100"

            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            for row in results:
                if isinstance(row, list) and len(row) > 1:
                    host = row[0]
                    items.append(CollectItem(
                        item_type="domain",
                        value=host,
                        source_name=self.name,
                        raw={"host": host, "port": row[1] if len(row) > 1 else ""},
                    ))
            _logger.info(f"FOFA 返回 {len(items)} 个域名 enterprise={query.enterprise}")
        except Exception as exc:
            error_msg = f"FOFA 查询失败: {exc}"
            _logger.warn(error_msg)

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=len(error_msg) == 0,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
