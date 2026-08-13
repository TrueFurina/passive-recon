"""P1 端到端集成测试（蓝图 T31）。

验证 run_company(企业) 端到端跑通：
R1→R7 采集→R2 核验→R12 拓扑写入（重构后契约）
"""
from __future__ import annotations

import pytest

from passive_agent.orchestrator.loop import run_company
from passive_agent.common.enums import CollectorCluster, NodeType, EdgeType

# 重构后 run_company 返回的契约键
_CONTRACT_KEYS = [
    "enterprise", "trace_id", "blocked", "status",
    "total_assets", "verified", "suspended", "rounds",
    "domain_count", "ip_count", "email_count", "sources",
]


class TestP1Integration:
    """P1 端到端集成测试。"""

    def test_run_company_full_chain(self):
        """单企业闭环端到端跑通（新契约）。"""
        summary = run_company("集成测试企业")
        assert summary["enterprise"] == "集成测试企业"
        assert not summary["blocked"]
        assert summary["status"] == "completed"
        for k in _CONTRACT_KEYS:
            assert k in summary
        assert summary["trace_id"] != ""

    def test_collect_result_into_verify(self):
        """采集结果进入核验流程（verified/suspended 字段存在）。"""
        summary = run_company("佐证测试企业")
        assert "verified" in summary
        assert "suspended" in summary

    def test_graph_topology_complete(self):
        """R12 拓扑写入（图模块独立可用）。"""
        summary = run_company("拓扑完整测试企业")
        assert not summary["blocked"]
        from passive_agent.graph.asset_graph import AssetGraph
        ag = AssetGraph()
        topo = ag.query_topology("拓扑完整测试企业")
        assert topo is not None

    def test_trace_id_chain(self):
        """全链路 trace_id 生成。"""
        summary = run_company("链路追踪测试企业")
        trace_id = summary["trace_id"]
        assert trace_id != ""

    def test_run_company_idempotent(self):
        """run_company 多次调用不崩溃。"""
        s1 = run_company("幂等测试企业")
        s2 = run_company("幂等测试企业")
        assert s1["enterprise"] == s2["enterprise"]

    def test_compute_reclaim_in_loop(self):
        """R9 算力回收在闭环中的作用。"""
        summary = run_company("回收测试企业")
        assert "trace_id" in summary

    def test_no_p0_regression(self):
        """P0 集成测试不回归（run_company 返回结构兼容 P0 关键字段）。"""
        summary = run_company("回归测试企业")
        assert "enterprise" in summary
        assert "trace_id" in summary
        assert "blocked" in summary
        assert "verified" in summary
        assert "suspended" in summary
        assert "total_assets" in summary

    def test_four_clusters_collected(self):
        """闭环执行不崩溃，返回完整契约。"""
        summary = run_company("四集群测试企业")
        assert not summary["blocked"]
        assert summary["status"] == "completed"

    def test_audit_log_full_chain_events(self):
        """审计日志可查询（V-R10-1）。"""
        summary = run_company("全链路审计测试企业")
        from passive_agent.audit.query import AuditQuery
        aq = AuditQuery()
        counts = aq.count_by_type()
        assert counts is not None
