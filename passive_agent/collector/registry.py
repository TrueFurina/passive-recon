"""R7 适配器注册/发现机制（蓝图 §3.3）。

按集群分组管理适配器，按优先级排序（小=高优先）。
"""
from __future__ import annotations

import threading
from typing import Dict, List

from passive_agent.common.enums import CollectorCluster
from passive_agent.collector.adapter import SourceAdapter


class AdapterRegistry:
    """适配器注册/发现机制。

    - register(adapter): 注册适配器到对应集群组
    - get_adapters(cluster): 返回该集群下按优先级排序的适配器列表
    - get_clusters(): 返回所有已注册的集群列表
    """

    def __init__(self) -> None:
        self._adapters: Dict[CollectorCluster, List[SourceAdapter]] = {}
        self._lock = threading.Lock()

    def register(self, adapter: SourceAdapter) -> None:
        """注册适配器到对应集群组（按 priority 排序）。"""
        with self._lock:
            lst = self._adapters.setdefault(adapter.cluster, [])
            # 避免重复注册同名适配器
            existing_names = {a.name for a in lst}
            if adapter.name not in existing_names:
                lst.append(adapter)
            lst.sort(key=lambda a: a.priority)

    def get_adapters(self, cluster: CollectorCluster) -> List[SourceAdapter]:
        """返回该集群下按优先级排序的适配器列表（副本）。"""
        with self._lock:
            return list(self._adapters.get(cluster, []))

    def get_clusters(self) -> List[CollectorCluster]:
        """返回所有已注册的集群列表。"""
        with self._lock:
            return list(self._adapters.keys())

    def all_adapters(self) -> List[SourceAdapter]:
        """返回所有已注册的适配器（扁平列表）。"""
        with self._lock:
            result: List[SourceAdapter] = []
            for lst in self._adapters.values():
                result.extend(lst)
            return result
