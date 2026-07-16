"""被动信息采集器模块（P1 增量 + FAFU 实战反哺）。

P1 核心：CollectionScheduler（100% 自研调度内核）+ SourceAdapter（ACL 防腐层）+
        FaultToleranceManager（R8 容错降级）+ AdapterRegistry（注册/发现）。
FAFU 反哺：CollectorManager（实战管理器）+ AssetRecord 模型 + PassivesCollector 实现。
所有适配器出站前必经 compliance_client.check(PASSIVE_QUERY)（fail-closed）。
"""
from __future__ import annotations

from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.domain_db import infer_domain, list_known_enterprises, list_known_universities
from passive_agent.collector.fault_tolerance import FaultToleranceManager
from passive_agent.collector.manager import CollectorManager
from passive_agent.collector.model import (
    AssetRecord,
    AssetSourceEnum,
    AssetType,
    CollectItem,
    CollectQuery,
    CollectReport,
    CollectResult,
)
from passive_agent.collector.registry import AdapterRegistry
from passive_agent.collector.scheduler import CollectionScheduler
from passive_agent.collector.sources import CrtshCollector, FofaCollector, HackerTargetCollector, QichachaCollector

__all__ = [
    "SourceAdapter",
    "AdapterRegistry",
    "CollectionScheduler",
    "FaultToleranceManager",
    "CollectorManager",
    "CollectQuery",
    "CollectItem",
    "CollectResult",
    "AssetRecord",
    "AssetSourceEnum",
    "AssetType",
    "CollectReport",
    "CrtshCollector",
    "FofaCollector",
    "HackerTargetCollector",
    "QichachaCollector",
    "infer_domain",
    "list_known_enterprises",
    "list_known_universities",
]
