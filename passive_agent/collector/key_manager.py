"""多 Key 自动轮询与限频协同管理器。

核心能力：
1. 多 Key 存储与智能轮询（基于历史成功率）
2. 429 限频自动切换 Key
3. Key 冷却机制（429 后自动冷却指定时间）
4. 成功率统计（用于选择最优 Key）

专利方向：多 API Key 自动轮询与限频协同方法
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Tuple


class KeyState:
    """单个 API Key 的状态。"""

    def __init__(self, key: str):
        self.key = key
        self.success_count = 0
        self.fail_count = 0
        self.rate_limited_count = 0
        self.last_rate_limited_at: float = 0.0  # 最后一次 429 的时间戳
        self.cooldown_until: float = 0.0        # 冷却到期时间
        self.last_used_at: float = 0.0

    @property
    def is_available(self) -> bool:
        """Key 是否可用（未在冷却期）。"""
        return time.time() >= self.cooldown_until

    @property
    def success_rate(self) -> float:
        """成功率。"""
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0

    def record_success(self) -> None:
        self.success_count += 1
        self.last_used_at = time.time()

    def record_failure(self, is_rate_limit: bool = False) -> None:
        self.fail_count += 1
        if is_rate_limit:
            self.rate_limited_count += 1
            self.last_rate_limited_at = time.time()
            # 冷却时间随限频次数递增：30s, 60s, 120s, 240s...
            cooldown = 30 * (2 ** min(self.rate_limited_count - 1, 5))
            self.cooldown_until = time.time() + cooldown

    def __repr__(self) -> str:
        return (f"KeyState(key={self.key[:8]}..., avail={self.is_available}, "
                f"succ={self.success_count}, fail={self.fail_count}, "
                f"rl={self.rate_limited_count})")


class MultiKeyManager:
    """多 Key 自动轮询与限频协同管理器（线程安全）。"""

    def __init__(self, keys: List[str], name: str = "default"):
        """初始化。

        Args:
            keys: API Key 列表
            name: 数据源名称（用于日志）
        """
        self.name = name
        self._keys = [KeyState(k) for k in keys if k]
        self._lock = threading.Lock()
        self._index = 0  # 轮询指针

    @property
    def available_count(self) -> int:
        """可用 Key 数量。"""
        return sum(1 for k in self._keys if k.is_available)

    @property
    def total_count(self) -> int:
        return len(self._keys)

    def get_key(self) -> Optional[str]:
        """获取最优可用 Key。

        策略：
        1. 优先选择可用（非冷却期）的 Key
        2. 在可用 Key 中轮询
        3. 优先选择成功率最高的 Key
        4. 如果没有可用 Key，返回冷却时间最短的 Key

        Returns:
            API Key 字符串，无 Key 时返回 None
        """
        with self._lock:
            if not self._keys:
                return None

            now = time.time()
            # 找出所有可用 Key
            available = [k for k in self._keys if k.cooldown_until <= now]

            if available:
                # 按成功率排序，取最优
                best = max(available, key=lambda k: k.success_rate)
                best.last_used_at = now
                return best.key
            else:
                # 全部冷却中，返回冷却时间最短的
                soonest = min(self._keys, key=lambda k: k.cooldown_until)
                return soonest.key

    def report_success(self, key: str) -> None:
        """报告 Key 调用成功。"""
        with self._lock:
            for ks in self._keys:
                if ks.key == key:
                    ks.record_success()
                    break

    def report_failure(self, key: str, is_rate_limit: bool = False) -> None:
        """报告 Key 调用失败。"""
        with self._lock:
            for ks in self._keys:
                if ks.key == key:
                    ks.record_failure(is_rate_limit)
                    break

    def get_stats(self) -> Dict:
        """获取所有 Key 的状态统计。"""
        with self._lock:
            return {
                "name": self.name,
                "total": self.total_count,
                "available": self.available_count,
                "keys": [
                    {
                        "key": k.key[:12] + "...",
                        "available": k.is_available,
                        "success_rate": round(k.success_rate * 100, 1),
                        "rate_limited": k.rate_limited_count,
                        "cooldown_remaining": round(max(0, k.cooldown_until - time.time()), 1),
                    }
                    for k in self._keys
                ],
            }

    def __repr__(self) -> str:
        return (f"MultiKeyManager(name={self.name}, "
                f"available={self.available_count}/{self.total_count})")


# 全局管理器注册表（按数据源名称索引）
_registry: Dict[str, MultiKeyManager] = {}
_registry_lock = threading.Lock()


def get_manager(name: str, keys: Optional[List[str]] = None) -> MultiKeyManager:
    """获取或创建全局 Key 管理器。

    同一数据源共享同一个管理器，实现跨实例的 Key 轮询。
    """
    with _registry_lock:
        if name not in _registry:
            _registry[name] = MultiKeyManager(keys or [], name)
        return _registry[name]


def list_all_managers() -> Dict[str, Dict]:
    """列出所有管理器的状态。"""
    with _registry_lock:
        return {name: mgr.get_stats() for name, mgr in _registry.items()}