"""AI 对话查询 — 用自然语言查询资产数据库。

用法：
    python cli.py ask "北京大学的 VPN 有哪些？"
    python cli.py ask "列出所有发现的邮件服务器"
"""
from __future__ import annotations

import json
from typing import List

from passive_agent.ai.client import ai_chat
from passive_agent.storage import db


def ask(query: str, limit: int = 20) -> str:
    """用自然语言查询资产数据库。

    Args:
        query: 自然语言问题，如 "北京大学的 VPN 有哪些"
        limit: 返回结果上限

    Returns:
        AI 生成的回答（含数据）
    """
    # 1. 查询数据库获取上下文
    assets = _query_assets(query, limit)
    enterprises = _get_enterprises()

    # 2. 构建 prompt
    context = f"数据库中共有 {len(enterprises)} 个目标的资产数据：\n"
    for e in enterprises:
        context += f"- {e['enterprise']} ({e['domain']}): {e['count']} 条资产\n"

    if assets:
        context += f"\n查询到以下相关资产：\n"
        for a in assets:
            context += f"- [{a['asset_type']}] {a['asset_value']}"
            if a['ip']:
                context += f" ({a['ip']})"
            if a['source_name']:
                context += f" [来源: {a['source_name']}]"
            context += "\n"

    prompt = (
        "你是一个网络安全资产分析助手。请根据以下数据库信息回答用户的问题。\n\n"
        f"数据库信息：\n{context}\n"
        f"用户问题：{query}\n\n"
        "请用中文回答，列出相关资产，并给出简短分析。如果数据库中没有相关信息，请如实说明。"
    )

    result = ai_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.3,
    )

    if result:
        return result
    return "❌ AI 暂时无法回答，请稍后重试。"


def _query_assets(query: str, limit: int = 20) -> List[dict]:
    """根据自然语言查询，搜索资产数据库。"""
    # 提取可能的企业名
    enterprises = _get_enterprises()
    matched_enterprise = None
    for e in enterprises:
        if e['enterprise'] in query or e['domain'] in query:
            matched_enterprise = e['enterprise']
            break

    try:
        if matched_enterprise:
            rows = db.query(
                "SELECT asset_value, asset_type, source_name, ip, port, title "
                "FROM t_collect_asset WHERE enterprise=? ORDER BY id DESC LIMIT ?",
                (matched_enterprise, limit),
            )
        else:
            # 全文搜索资产值
            keyword = query.replace("有哪些", "").replace("列出", "").replace("?", "").strip()
            if keyword:
                rows = db.query(
                    "SELECT asset_value, asset_type, source_name, ip, port, title "
                    "FROM t_collect_asset WHERE asset_value LIKE ? OR title LIKE ? "
                    "ORDER BY id DESC LIMIT ?",
                    (f"%{keyword}%", f"%{keyword}%", limit),
                )
            else:
                rows = db.query(
                    "SELECT asset_value, asset_type, source_name, ip, port, title "
                    "FROM t_collect_asset ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_enterprises() -> List[dict]:
    """获取所有已采集的目标列表。"""
    try:
        rows = db.query(
            "SELECT enterprise, domain, COUNT(*) as count "
            "FROM t_collect_asset GROUP BY enterprise ORDER BY count DESC"
        )
        return [dict(r) for r in rows]
    except Exception:
        return []