"""Webhook 通知推送 — 定时采集完成后推送报告摘要到企业微信/钉钉。

支持：
- 企业微信群机器人 Webhook
- 钉钉群机器人 Webhook
- 通用 Webhook（Markdown 文本）

通过环境变量配置：
- NOTIFY_WECHAT_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
- NOTIFY_DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
- NOTIFY_WEBHOOK=https://example.com/hook  （通用 Webhook）
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

from passive_agent.common.compliance_client import check as _r1_pass
from passive_agent.common import logging as clog

_logger = clog.get_logger("notify")


def _get_webhooks() -> List[str]:
    """读取配置的 Webhook 地址列表。"""
    hooks = []
    for key in ("NOTIFY_WECHAT_WEBHOOK", "NOTIFY_DINGTALK_WEBHOOK", "NOTIFY_WEBHOOK"):
        url = os.environ.get(key, "")
        if url:
            hooks.append(url)
    return hooks


def has_webhook() -> bool:
    """是否配置了任何 Webhook。"""
    return bool(_get_webhooks())


def send_summary(results: List[dict], targets: Optional[List[dict]] = None) -> bool:
    """推送定时采集结果摘要到所有配置的 Webhook。

    Args:
        results: run_once() 返回的结果列表
        targets: 目标列表（可选，用于统计）

    Returns:
        是否至少成功推送一个 Webhook
    """
    hooks = _get_webhooks()
    if not hooks:
        return False

    total = len(results)
    ok_count = sum(1 for r in results if r.get("status") == "success")
    fail_count = total - ok_count
    new_assets = sum(r.get("new", 0) for r in results)
    risk_count = sum(r.get("risks", 0) for r in results)

    # 构建摘要文本
    lines = [
        f"📡 Passive Recon 定时采集报告",
        f"━━━━━━━━━━━━━━━━━━",
        f"目标数: {total} | 成功: {ok_count} | 失败: {fail_count}",
        f"新增资产: {new_assets} | 风险: {risk_count}",
    ]
    # 每个目标一行
    for r in results:
        status = "✅" if r.get("status") == "success" else "❌"
        lines.append(f"{status} {r.get('name', '?')} ({r.get('domain', '?')}) "
                     f"资产={r.get('total', 0)} 新增={r.get('new', 0)} 风险={r.get('risks', 0)}")

    text = "\n".join(lines)

    sent = False
    for url in hooks:
        try:
            if "qyapi.weixin" in url:
                payload = {"msgtype": "markdown", "markdown": {"content": text}}
            elif "oapi.dingtalk" in url:
                payload = {"msgtype": "markdown", "markdown": {"title": "Passive Recon 采集报告", "text": text}}
            else:
                payload = {"text": text, "type": "markdown"}

            _r1_pass(source="webhook-notify")
            resp = httpx.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                sent = True
                _logger.info(f"Webhook 推送成功: {url[:50]}...")
            else:
                _logger.warn(f"Webhook 推送失败 HTTP {resp.status_code}: {url[:50]}...")
        except Exception as e:
            _logger.warn(f"Webhook 推送异常: {e}")

    return sent