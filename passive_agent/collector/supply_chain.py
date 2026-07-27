"""供应链风险监测 — 递归发现关联企业/资产。

策略：
1. 对已发现资产进行 Whois/ICP 查询，找出同一主体下的其他域名
2. 递归采集关联目标
3. 输出供应链关系图

用法：
    python cli.py collect "目标" --supply-chain
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Set, Tuple

import httpx

from passive_agent.collector.manager import CollectorManager
from passive_agent.collector.model import AssetRecord, AssetSourceEnum, AssetType, CollectReport
from passive_agent.common import logging as clog

_logger = clog.get_logger("supply-chain")

# 缓存已查过的 IP/域名，避免重复
_seen_domains: Set[str] = set()
_seen_ips: Set[str] = set()


def discover_supply_chain(report: CollectReport, max_depth: int = 2) -> CollectReport:
    """对采集结果进行供应链风险监测。

    从已发现的资产 IP 中，反向查询同一 IP 上的其他域名，
    然后递归采集这些关联目标。

    Args:
        report: 初次采集报告
        max_depth: 递归深度（默认 2，避免无限递归）

    Returns:
        扩展后的采集报告（含供应链关联资产）
    """
    supply_chain = CollectReport(
        enterprise=f"{report.enterprise}_供应链",
        domain=report.domain,
    )

    # 收集所有 IP
    ips: Set[str] = set()
    for r in report.records:
        if r.ip and r.ip not in _seen_ips:
            ips.add(r.ip)
            _seen_ips.add(r.ip)

    if not ips:
        _logger.info("供应链: 无 IP 资产，跳过")
        return report

    # 对每个 IP 进行反向查询
    related_domains: Set[str] = set()
    for ip in list(ips)[:10]:  # 最多查 10 个 IP
        domains = _reverse_lookup(ip)
        related_domains.update(domains)
        _logger.info(f"供应链: {ip} → {len(domains)} 个关联域名")

    # 过滤掉主域名本身
    related_domains.discard(report.domain)
    related_domains.discard(f"www.{report.domain}")

    if not related_domains:
        _logger.info("供应链: 未发现关联域名")
        return report

    # 递归采集每个关联域名
    mgr = CollectorManager()
    collected: Set[str] = set()
    for domain in list(related_domains)[:5]:  # 最多采 5 个关联域名
        if domain in _seen_domains or domain in collected:
            continue
        _seen_domains.add(domain)
        collected.add(domain)

        try:
            sub_report = mgr.collect(name=domain, domain=domain)
            supply_chain.merge(sub_report)
            _logger.info(f"供应链: 采集 {domain} → {sub_report.total_records} 条")
        except Exception as e:
            _logger.warn(f"供应链: 采集 {domain} 失败: {e}")

    # 如果有深层次结果，合并到主报告
    if supply_chain.records:
        report.merge(supply_chain)
        report.errors.append(f"🔗 供应链分析: 发现 {len(related_domains)} 个关联域名，新增 {len(supply_chain.records)} 条资产")

    return report


def _reverse_lookup(ip: str) -> List[str]:
    """通过多个免费服务反向查询 IP 上的其他域名。"""
    from passive_agent.common.compliance_client import check as _r1_pass
    _r1_pass(source="supply-chain-reverse")
    domains: Set[str] = set()

    # 1. HackerTarget 反向 DNS
    try:
        resp = httpx.get(
            f"https://api.hackertarget.com/reverseiplookup/?q={ip}",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            for line in resp.text.strip().split("\n"):
                d = line.strip().lower()
                if d and "." in d and not d.startswith("Host") and not d.startswith("API"):
                    domains.add(d)
    except Exception:
        pass

    # 2. YouGetSignal (爬取)
    try:
        resp = httpx.post(
            "https://www.yougetsignal.com/tools/web-sites-on-web-server/",
            data={"remoteAddress": ip},
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if resp.status_code == 200:
            import re
            for m in re.finditer(r'<a[^>]*>([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})</a>', resp.text):
                domains.add(m.group(1).strip().lower())
    except Exception:
        pass

    return list(domains)[:20]  # 最多返回 20 个