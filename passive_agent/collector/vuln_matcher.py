"""资产-漏洞关联引擎 — 将采集到的资产技术与 NVD CVE 数据库关联。

采集完成后，提取资产的技术栈/端口/关键词，查询 NVD API 获取关联漏洞，
结果注入到报告中。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from passive_agent.collector.model import AssetRecord, AssetSourceEnum, AssetType, CollectReport
from passive_agent.collector.sources import NvdCollector
from passive_agent.common import logging as clog

_logger = clog.get_logger("vuln-matcher")

# 端口 → 技术关键词映射
PORT_TECH_MAP: Dict[int, str] = {
    80: "http",
    443: "https",
    3306: "mysql",
    5432: "postgresql",
    6379: "redis",
    27017: "mongodb",
    8080: "tomcat",
    8443: "tomcat",
    22: "ssh",
    21: "ftp",
    3389: "rdp",
    1433: "mssql",
    9200: "elasticsearch",
    5601: "kibana",
    9090: "prometheus",
    3000: "grafana",
}


def match_vulnerabilities(report: CollectReport) -> int:
    """对采集报告中的资产进行漏洞关联。

    策略：
    1. 提取资产的技术栈（tech_stack）
    2. 根据端口推断技术关键词
    3. 根据子域名关键词（mail, vpn, oa 等）推断
    4. 去重后查询 NVD API
    5. 将 CVE 结果注入报告

    Args:
        report: 采集报告（原地修改，注入 CVE 结果）

    Returns:
        关联到的 CVE 数量
    """
    keywords = _extract_keywords(report)
    if not keywords:
        return 0

    collector = NvdCollector(timeout=20)
    # 并不真的需要 domain，但 collect 签名需要
    cve_records = collector.collect("", tech_stacks=keywords)

    if cve_records:
        report.records.extend(cve_records)
        # 在报告头部添加漏洞摘要
        for cve in cve_records:
            score_tag = [t for t in cve.tags if t.startswith("score:")]
            score = score_tag[0].split(":")[1] if score_tag else "?"
            tech = cve.ip or ""
            report.errors.append(
                f"🔴 [CVE] {cve.value} (CVSS:{score}) — {tech}: {cve.title[:80]}"
            )
        _logger.info(f"漏洞关联: 发现 {len(cve_records)} 个关联 CVE")
    else:
        _logger.info("漏洞关联: 未发现关联 CVE")

    return len(cve_records)


def _extract_keywords(report: CollectReport) -> List[str]:
    """从报告中提取技术关键词（去重）。"""
    keywords: Set[str] = set()

    for r in report.records:
        # 1. 技术栈
        for tech in r.tech_stack:
            if isinstance(tech, str) and tech:
                keywords.add(tech.lower().strip())

        # 2. 端口推断
        if r.port and r.port in PORT_TECH_MAP:
            keywords.add(PORT_TECH_MAP[r.port])

        # 3. 子域名关键词
        if r.asset_type in (AssetType.SUBDOMAIN, AssetType.DOMAIN):
            val = r.value.lower()
            for kw in ["nginx", "apache", "tomcat", "iis", "wordpress",
                        "joomla", "drupal", "php", "python", "java",
                        "coremail", "exchange", "openssh", "openssl"]:
                if kw in val:
                    keywords.add(kw)

    # 过滤通用词
    common = {"http", "https", "www", "mail", "web", "admin", "api"}
    return [k for k in keywords if k not in common][:10]  # 最多 10 个关键词