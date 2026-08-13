"""资产变化告警 — 对比本次与历史采集，识别新增高风险资产并推送通知。

策略：
1. 提取本次采集的资产
2. 与数据库中已有的历史资产对比，找出「新增」资产
3. 对新增资产进行高风险判定（子域名关键词 / 高危端口 / 高风险技术栈）
4. 若有新增高风险资产 → 通过 Webhook 推送告警

高风险子域名关键词（与 scorer.py 保持一致口径）：
  vpn / webvpn / oa / mail / ecard / pay / sso / cas / admin / jenkins /
  gitlab / phpmyadmin / erp / crm / db / redis / mysql
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from passive_agent.collector.model import AssetRecord, AssetType, CollectReport
from passive_agent.common import logging as clog
from passive_agent.storage import db

_logger = clog.get_logger("asset-alert")

# 高风险子域名关键词
HIGH_RISK_KEYWORDS = [
    "vpn", "webvpn", "sslvpn", "oa", "mail", "coremail", "exchange",
    "ecard", "pay", "sso", "cas", "login", "admin", "manage", "console",
    "jenkins", "gitlab", "phpmyadmin", "erp", "crm", "db", "redis",
    "mysql", "monitor", "grafana", "zabbix", "ftp",
]

# 高危端口（与 manager._detect_risks 保持一致）
HIGH_RISK_PORTS = {
    21, 23, 3306, 3389, 5432, 6379, 8080, 8443, 9090, 27017, 9200,
}

# 高风险技术栈
HIGH_RISK_TECH = ["wordpress", "joomla", "通达oa", "致远oa", "phpmyadmin", "coremail"]


def _get_history_assets(enterprise: str) -> set:
    """获取该企业已入库的历史资产集合（用于判断新增）。"""
    try:
        rows = db.query(
            "SELECT asset_value FROM t_collect_asset WHERE enterprise=?",
            (enterprise,),
        )
        return {r["asset_value"] for r in rows}
    except Exception:
        return set()


def _is_high_risk(record: AssetRecord) -> Optional[str]:
    """判定单条资产是否为高风险，返回原因；非高风险返回 None。"""
    val = record.value.lower()

    # 1. 子域名关键词
    if record.asset_type in (AssetType.SUBDOMAIN, AssetType.DOMAIN):
        for kw in HIGH_RISK_KEYWORDS:
            if kw in val:
                return f"高风险关键词「{kw}」"

    # 2. 高危端口
    if record.port and record.port in HIGH_RISK_PORTS:
        return f"高危端口 {record.port}"

    # 3. 高风险技术栈
    for tech in record.tech_stack:
        ts = tech.lower() if isinstance(tech, str) else str(tech).lower()
        for hk in HIGH_RISK_TECH:
            if hk in ts:
                return f"高风险技术栈「{tech}」"

    return None


def detect_new_high_risk(report: CollectReport) -> List[Dict]:
    """对比历史采集，找出本次新增的高风险资产。

    Args:
        report: 本次采集报告

    Returns:
        新增高风险资产列表：[{"asset": ..., "type": ..., "ip": ..., "reason": ...}]
    """
    history = _get_history_assets(report.enterprise)
    new_high_risk: List[Dict] = []

    for r in report.records:
        # 跳过已在库中的资产（非新增）
        if r.value in history:
            continue
        reason = _is_high_risk(r)
        if reason:
            new_high_risk.append({
                "asset": r.value,
                "type": r.asset_type.value,
                "ip": r.ip or "",
                "reason": reason,
            })

    if new_high_risk:
        _logger.info(f"资产告警: {report.enterprise} 新增 {len(new_high_risk)} 个高风险资产")
    return new_high_risk


def send_alert(report: CollectReport) -> bool:
    """检测新增高风险资产并通过 Webhook 推送告警。

    Args:
        report: 本次采集报告

    Returns:
        是否推送了告警（无新增高风险或未配置 Webhook 时返回 False）
    """
    new_high_risk = detect_new_high_risk(report)
    if not new_high_risk:
        return False

    try:
        from passive_agent.scheduler.notify import has_webhook
        if not has_webhook():
            _logger.info("资产告警: 未配置 Webhook，跳过推送")
            return False

        lines = [
            f"🚨 资产变化告警",
            f"━━━━━━━━━━━━━━━━━━",
            f"目标: {report.enterprise} ({report.domain})",
            f"新增高风险资产: {len(new_high_risk)} 个",
            f"━━━━━━━━━━━━━━━━━━",
        ]
        for item in new_high_risk[:10]:
            lines.append(f"• {item['asset']} [{item['type']}] {item['reason']}")

        text = "\n".join(lines)

        # 复用 notify 的推送逻辑（企业微信 markdown）
        import os
        import httpx
        from passive_agent.common.compliance_client import check as _r1_pass

        sent = False
        for key in ("NOTIFY_WECHAT_WEBHOOK", "NOTIFY_DINGTALK_WEBHOOK", "NOTIFY_WEBHOOK"):
            url = os.environ.get(key, "")
            if not url:
                continue
            try:
                if "qyapi.weixin" in url:
                    payload = {"msgtype": "markdown", "markdown": {"content": text}}
                elif "oapi.dingtalk" in url:
                    payload = {"msgtype": "markdown", "markdown": {"title": "Passive Recon 资产告警", "text": text}}
                else:
                    payload = {"text": text, "type": "markdown"}
                _r1_pass(source="asset-alert-webhook")
                resp = httpx.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    sent = True
            except Exception:
                pass

        return sent
    except Exception:
        return False