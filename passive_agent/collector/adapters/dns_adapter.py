"""Web 集群 — dnspython 被动解析真实免凭证源适配器（蓝图 T20）。

用 dnspython.resolver.resolve() 被动解析域名，仅解析不连接（严禁 socket）。
复用 P0 verifier/layers.py::dns_alive 逻辑。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import dns.resolver

from passive_agent.common import logging as clog
from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.model import CollectItem, CollectQuery, CollectResult
from passive_agent.config import settings

_logger = clog.get_logger("dns-adapter")


class DnsAdapter(SourceAdapter):
    """DNS 被动解析适配器（真实免凭证源，仅 resolver.resolve 不 socket 连接）。"""

    name = "dns-passive"
    cluster = CollectorCluster.WEB
    requires_credential = False
    priority = 20

    def collect(self, query: CollectQuery, trace_id: str) -> CollectResult:
        """被动 DNS 解析：对企业主域名做 A 记录解析，仅解析不连接。"""
        # 1) 出站前必经 R1 关隘
        self._check_compliance(trace_id)

        items: List[CollectItem] = []
        error_msg = ""
        timeout = float(settings.SOURCE_TIMEOUT)

        # 基于企业名构造可能的域名（简化：直接用企业名拼音/英文近似）
        # 真实场景由枚举引擎提供已知域名，这里基于 subject_name 做被动解析
        candidates = self._derive_domains(query.enterprise, query.subject_name)

        for domain in candidates:
            try:
                # ⚠️ 纯被动红线：仅 resolver.resolve()，绝不对解析出的 IP 发起 socket 连接
                answer = dns.resolver.resolve(domain, "A", lifetime=timeout)
                ips = [str(r) for r in answer]
                if ips:
                    items.append(CollectItem(
                        item_type="domain",
                        value=domain,
                        source_name=self.name,
                        raw={"resolved_ips": ips, "record_type": "A"},
                    ))
                    _logger.debug(f"DNS 解析成功 {domain} -> {ips}")
            except Exception as exc:
                _logger.debug(f"DNS 解析失败 {domain}: {exc}")
                # 单个域名解析失败不阻断整体
                continue

        if not items and not candidates:
            error_msg = "无可解析的候选域名"
        _logger.info(f"DNS 适配器返回 {len(items)} 个域名 enterprise={query.enterprise}")

        # 无解析结果时返回 success=False 以触发 mock 回退
        success = len(items) > 0
        if not success:
            error_msg = error_msg or "DNS 解析无结果，触发 mock 回退"

        return CollectResult(
            query=query,
            items=items,
            source_name=self.name,
            success=success,
            error=error_msg,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _derive_domains(self, enterprise: str, subject_name: str) -> List[str]:
        """从企业名/主体名推导候选域名（简化版）。

        真实场景由 R3 枚举引擎提供已知域名列表。
        跳过包含中文字符的名称（非合法域名，避免无意义的 DNS 查询超时）。
        """
        candidates: List[str] = []
        for name in [enterprise, subject_name]:
            if not name:
                continue
            # 跳过包含非 ASCII 字符的名称（中文企业名无法直接做域名）
            try:
                name.encode("ascii")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            # 移除常见公司后缀
            clean = name
            for suffix in ["Ltd", "Inc", "Corp", "Co", "Group", "公司", "集团"]:
                clean = clean.replace(suffix, "")
            clean = clean.strip()
            if clean and "." not in clean:
                candidates.append(f"{clean}.com")
                candidates.append(f"{clean}.cn")
            elif clean and "." in clean:
                # 已经是域名格式
                candidates.append(clean)
        return list(dict.fromkeys(candidates))  # 去重保序
