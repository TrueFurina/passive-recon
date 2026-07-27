"""资产重要性评分 — 结合资产类型、暴露面、业务价值进行综合评分。

参考安恒零日雷达的"资产重要性"维度，对每个资产打分 0-100：
- 90-100: 核心资产（VPN、邮件、OA、一卡通）
- 70-89: 重要资产（主站、API、管理后台）
- 50-69: 普通资产（子域名、CDN、开发环境）
- 0-49: 低价值资产（测试环境、静态资源）
"""
from __future__ import annotations

from typing import Dict, List

from passive_agent.collector.model import AssetRecord, AssetType, CollectReport


# 资产类型 → 基础分
TYPE_SCORES = {
    AssetType.SUBDOMAIN: 50,
    AssetType.DOMAIN: 60,
    AssetType.IP: 40,
    AssetType.ORGANIZATION: 70,
}

# 子域名关键词 → 加分（关键词越重要得分越高）
KEYWORD_BONUS: Dict[str, int] = {
    "vpn": 40, "webvpn": 40, "sslvpn": 40,
    "mail": 35, "email": 35, "coremail": 35, "exchange": 35, "webmail": 35,
    "oa": 35, "oaoffice": 35,
    "ecard": 40, "card": 30, "pay": 30,
    "sso": 30, "cas": 30, "login": 25, "passport": 25, "auth": 25,
    "api": 25, "openapi": 25, "gateway": 25,
    "erp": 35, "crm": 30, "hr": 25,
    "admin": 30, "manage": 25, "console": 30, "dashboard": 25,
    "jenkins": 30, "jira": 25, "gitlab": 25, " confluence": 25,
    "db": 25, "database": 25, "mysql": 25, "redis": 25,
    "monitor": 20, "grafana": 20, "prometheus": 20, "zabbix": 20,
    "test": 10, "dev": 10, "staging": 10, "uat": 10,
    "cdn": 15, "static": 10, "assets": 10, "img": 10,
}

# 端口 → 加分（高危端口暴露 = 更高重要性）
PORT_BONUS = {
    21: 20,    # FTP
    22: 15,    # SSH
    23: 25,    # Telnet
    3306: 30,  # MySQL
    3389: 25,  # RDP
    5432: 25,  # PostgreSQL
    6379: 30,  # Redis
    8080: 20,  # Tomcat/管理后台
    8443: 20,  # 管理后台 HTTPS
    9090: 20,  # 管理控制台
    27017: 30, # MongoDB
    9200: 20,  # Elasticsearch
    5601: 15,  # Kibana
    3000: 15,  # Grafana
}


def score_asset(record: AssetRecord) -> int:
    """对单条资产进行重要性评分。

    Args:
        record: 资产记录

    Returns:
        评分 0-100
    """
    score = TYPE_SCORES.get(record.asset_type, 30)

    # 子域名关键词加分
    if record.asset_type in (AssetType.SUBDOMAIN, AssetType.DOMAIN):
        val = record.value.lower()
        for keyword, bonus in KEYWORD_BONUS.items():
            if keyword in val:
                score += bonus

    # 端口加分
    if record.port and record.port in PORT_BONUS:
        score += PORT_BONUS[record.port]

    # IP 公网暴露加分（有 IP 且不是内网 = 更暴露）
    if record.ip:
        score += 5

    # 技术栈加分（有技术栈说明资产更成熟、更值得关注）
    if record.tech_stack:
        score += min(len(record.tech_stack) * 3, 10)

    # 标题信息加分（有标题说明页面有内容）
    if record.title:
        score += 5

    return min(score, 100)  # 上限 100


def score_report(report: CollectReport) -> None:
    """对报告中的所有资产进行评分，结果注入 tags。

    Args:
        report: 采集报告（原地修改）
    """
    for r in report.records:
        score = score_asset(r)
        # 清除旧的 importance 标签
        r.tags = [t for t in r.tags if not t.startswith("importance:")]
        r.tags.append(f"importance:{score}")

    # 按评分排序（高到低）
    report.records.sort(key=lambda r: _get_importance(r), reverse=True)


def _get_importance(record: AssetRecord) -> int:
    """从 tags 中提取重要性评分。"""
    for t in record.tags:
        if t.startswith("importance:"):
            try:
                return int(t.split(":")[1])
            except ValueError:
                return 0
    return 0


def importance_label(score: int) -> str:
    """评分 → 文字标签。"""
    if score >= 90:
        return "🔴 核心"
    elif score >= 70:
        return "🟠 重要"
    elif score >= 50:
        return "🟡 普通"
    else:
        return "🟢 低值"