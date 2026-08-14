"""AI 子域名预测 — 根据已知资产推测可能的子域名并验证。

策略：
1. 收集已知子域名（如 vpn.example.com, mail.example.com）
2. 调用 DeepSeek AI 推测该目标可能存在的其他子域名
3. 对预测结果做纯被动 DNS 验证（仅解析，不连接）
4. 返回验证通过的新子域名（供采集流程补充）

命令：python cli.py predict-subdomains "目标"
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Set

from passive_agent.ai.client import ai_chat
from passive_agent.common import logging as clog

_logger = clog.get_logger("ai-subdomain")


# 常见子域名前缀（作为 AI 提示的参考种子）
COMMON_PREFIXES = [
    "www", "mail", "vpn", "webvpn", "oa", "sso", "cas", "api", "app",
    "admin", "portal", "login", "git", "gitlab", "jenkins", "ftp", "cdn",
    "static", "img", "test", "dev", "staging", "prod", "docs", "blog",
    "shop", "pay", "m", "mobile", "wx", "mini", "h5", "erp", "crm", "hr",
]


def predict_subdomains(domain: str, known: Optional[List[str]] = None,
                       count: int = 20) -> List[str]:
    """AI 推测目标可能存在的子域名（未验证）。

    Args:
        domain: 主域名，如 "pku.edu.cn"
        known: 已知子域名列表（供 AI 参考）
        count: 期望预测数量

    Returns:
        预测的子域名列表（未验证）
    """
    known_str = ", ".join(known[:30]) if known else "无"
    prompt = (
        f"你是网络安全资产枚举专家。目标主域名是「{domain}」。\n"
        f"已发现的子域名：{known_str}\n\n"
        f"请推测该目标可能还存在但未发现的 {count} 个子域名。\n"
        "要求：\n"
        "- 只输出域名本身（每行一个，带主域后缀，如 vpn.example.com）\n"
        "- 优先考虑中国高校/企业常见系统：vpn, webvpn, oa, mail, sso, cas, "
        "ecard, onecard, lib, jwc, graduate, cwc, ict, itc, idc, bi, "
        "data, cloud, iot, api, openapi, gateway, monitor, zabbix, "
        "gitlab, jenkins, wiki, confluence, jira, nextcloud, 网盘相关\n"
        "- 不要输出已存在的子域名\n"
        "- 不要输出任何解释文字，只输出域名列表"
    )
    result = ai_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.5,
    )
    if not result:
        return []

    predicted: Set[str] = set()
    for line in result.splitlines():
        line = line.strip().lower().strip("-").strip("*").strip(".")
        # 清理可能的序号/引号
        line = re.sub(r"^\d+[.)、\s]+", "", line)
        line = line.strip("`'\"")
        if line.endswith(f".{domain}") and line != domain:
            predicted.add(line)
    return list(predicted)[:count]


def verify_dns(hostname: str, timeout: float = 2.0) -> Optional[str]:
    """纯被动 DNS 验证（仅 A 记录解析，绝不连接目标）。

    Returns:
        解析到的 IP；失败返回 None
    """
    try:
        import socket
        addrs = socket.getaddrinfo(hostname, 80, socket.AF_INET, socket.SOCK_STREAM)
        ips = list(set(a[4][0] for a in addrs))
        return ips[0] if ips else None
    except Exception:
        return None


def predict_and_verify(domain: str, known: Optional[List[str]] = None,
                       count: int = 20, max_workers: int = 10) -> List[Dict]:
    """AI 预测 + 纯被动验证，返回确认存在的子域名。

    Args:
        domain: 主域名
        known: 已知子域名
        count: 预测数量
        max_workers: DNS 并发验证线程数

    Returns:
        [{"subdomain": ..., "ip": ...}, ...]
    """
    predicted = predict_subdomains(domain, known, count)
    if not predicted:
        return []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {pool.submit(verify_dns, s): s for s in predicted}
        for fut in as_completed(fut_map, timeout=30):
            sub = fut_map[fut]
            ip = fut.result()
            if ip:
                results.append({"subdomain": sub, "ip": ip})
    _logger.info(f"AI 子域名预测: {domain} 预测 {len(predicted)} 个，验证存活 {len(results)} 个")
    return results