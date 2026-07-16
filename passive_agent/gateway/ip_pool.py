"""R6 多出口 IP 轮询（蓝图 T08）。

从 config.EGRESS_IPS 读取；默认单占位，逻辑就绪待真实 IP 池回填。
"""
from __future__ import annotations

import threading
from typing import List

from passive_agent.config import settings


class IpPool:
    def __init__(self, ips: List[str] | None = None) -> None:
        self._ips = list(ips) if ips else list(settings.EGRESS_IPS)
        if not self._ips:
            self._ips = ["127.0.0.1"]
        self._idx = 0
        self._lock = threading.Lock()

    def next(self) -> str:
        with self._lock:
            ip = self._ips[self._idx % len(self._ips)]
            self._idx += 1
            return ip

    def size(self) -> int:
        return len(self._ips)
