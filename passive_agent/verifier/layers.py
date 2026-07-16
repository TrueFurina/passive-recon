"""R2 各层实现（含 L2 DNS 仅解析，绝不主动连接解析出的 IP）。

纯被动红线：dnspython 仅 resolver.resolve() 做被动存活校验，
绝不对解析出的 IP 发起 socket 连接 / 主动 HTTP 探测。
"""
from __future__ import annotations

from typing import Optional

import dns.resolver

from passive_agent.common import logging as vlog

_logger = vlog.get_logger("verifier-l2")


def dns_alive(domain: str, timeout: float = 3.0) -> bool:
    """L2 被动存活校验：仅做 DNS 解析（resolver.resolve），绝不对解析出的 IP 发起 socket 连接。"""
    try:
        answer = dns.resolver.resolve(domain, "A", lifetime=timeout)
        return len(answer) > 0
    except Exception as exc:
        _logger.debug(f"DNS 解析失败 {domain}: {exc}")
        return False
