"""Web 集群 — crt.sh 真实免凭证源适配器（蓝图 T20）。

crt.sh 是公开的证书透明度日志查询服务，无需凭证。
用 httpx 调 crt.sh JSON API 查域名/子域名。
出站前经 compliance_client.check(PASSIVE_QUERY) + 白名单打标。
超时回退 mock。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("crtsh-adapter")


class CrtshAdapter(SourceAdapter):
    """crt.sh 证书透明度查询适配器（真实免凭证源）。"""

    name = "crtsh"
    cluster = CollectorCluster.WEB
    requires_credential = False
    priority = 10  # 高优先（免凭证可用）

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """调 crt.sh JSON API 查询域名/子域名。"""
        # 1) 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        items: List[CollectItem] = []
        error_msg = ""
        timeout = settings.SOURCE_TIMEOUT

        try:
            import httpx

            url = settings.CRTSH_API_URL.format(query.enterprise)
            _logger.info(f"crt.sh 查询 enterprise={query.enterprise} trace_id={trace_id}")

            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data_list: List[Any] = resp.json()

            # 去重提取域名
            seen: set = set()
            for entry in data_list:
                if isinstance(entry, dict):
                    name_val = entry.get("name_value", "")
                    if name_val and name_val not in seen:
                        seen.add(name_val)
                        items.append(CollectItem(
                            item_type="domain",
                            value=name_val,
                            source_name=self.name,
                            raw=entry,
                        ))
            _logger.info(f"crt.sh 返回 {len(items)} 个域名 enterprise={query.enterprise}")
        except Exception as exc:
            error_msg = f"crt.sh 查询失败: {exc}"
            _logger.warn(error_msg)

        # 无结果时返回 success=False 以触发 mock 回退（与 DnsAdapter 一致）
        success = len(error_msg) == 0 and len(items) > 0
        if not success and not error_msg:
            error_msg = "crt.sh 返回 0 条结果，触发 mock 回退"

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=success,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
