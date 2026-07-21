"""AI 风险评分与误报过滤 — 替代 _detect_risks 的硬编码规则。

对每个风险项，AI 评分 0-100，只输出 >= 60 的高置信风险。
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from passive_agent.ai.client import ai_chat, ai_chat_json


def score_risks(risks: List[str], domain: str) -> List[Tuple[str, int, str]]:
    """AI 风险评分与误报过滤。

    Args:
        risks: 风险描述列表，如 ["[P1] VPN 入口暴露: vpn.pku.edu.cn"]
        domain: 目标域名，如 "pku.edu.cn"

    Returns:
        [(风险描述, 评分0-100, 建议), ...]，按评分降序排列，仅保留 >= 60 的
    """
    if not risks:
        return []

    # 如果风险太多，取前 10 个让 AI 评分
    sample = risks[:10]

    prompt = (
        "你是一个网络安全专家。请对以下每个安全风险进行评分（0-100）并给出简短建议。\n\n"
        f"评分标准：\n"
        f"- 90-100: 严重风险，立即修复（如 VPN 暴露、一卡通系统、远程代码执行）\n"
        f"- 70-89: 高风险，尽快修复（如 OA 系统暴露、邮件系统、弱密码）\n"
        f"- 60-69: 中风险，计划修复（如非标准端口、信息泄露）\n"
        f"- 0-59: 低风险或误报，可以忽略\n\n"
        f"请只输出 JSON 数组，格式：\n"
        f'[{{"risk": "风险描述", "score": 85, "advice": "修复建议"}}]\n\n'
        f"风险列表：\n" + "\n".join(f"- {r}" for r in sample)
    )

    result = ai_chat_json(
        [{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.1,
    )

    if not result or not isinstance(result, list):
        # AI 失败，返回原始风险（不加分不降级）
        return [(r, 50, "AI 评分不可用，请人工判断") for r in risks]

    # 解析 AI 评分结果
    scored: List[Tuple[str, int, str]] = []
    for item in result:
        risk_text = item.get("risk", "")
        score = item.get("score", 50)
        advice = item.get("advice", "")
        if isinstance(score, (int, float)) and score >= 60:
            scored.append((risk_text, int(score), advice))

    # 按评分降序排列
    scored.sort(key=lambda x: -x[1])
    return scored


def filter_risks(risks: List[str], domain: str, min_score: int = 60) -> List[str]:
    """过滤风险，仅保留评分 >= min_score 的。"""
    scored = score_risks(risks, domain)
    return [r for r, s, _ in scored if s >= min_score]