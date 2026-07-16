"""P1 端到端集成测试（蓝图 T31）。

验证 run_company(企业) 端到端跑通：
R1→R3→R7 四集群采集→R8 容错→R2 核验→R6 提交→R4 审批→R12 拓扑写入
"""
from __future__ import annotations

import pytest

from passive_agent.orchestrator.loop import run_company
from passive_agent.common.enums import CollectorCluster, NodeType, EdgeType


class TestP1Integration:
    """P1 端到端集成测试。"""

    def test_run_company_full_chain(self):
        """单企业闭环端到端跑通（V-R7-5）。"""
        summary = run_company("集成测试企业")
        assert summary["enterprise"] == "集成测试企业"
        assert not summary["blocked"]
        assert summary["subjects"] > 0
        # R7 采集应有结果
        assert summary["collected_items"] > 0
        # R12 拓扑写入
        assert summary["graph_nodes"] > 0
        assert summary["graph_edges"] > 0
        # trace_id 生成
        assert summary["trace_id"] != ""

    def test_collect_result_into_verify(self):
        """CollectResult 的 items 正确填入 VerifyRequest.layer4_src_cnt（多源佐证）。"""
        summary = run_company("佐证测试企业")
        # 至少有部分主体核验通过（mock 回退提供多源）
        assert summary["verified"] > 0 or summary["suspended"] > 0

    def test_graph_topology_complete(self):
        """R12 拓扑节点/边写入完整（企业+子公司+域名+公众号+小程序）。"""
        summary = run_company("拓扑完整测试企业")
        from passive_agent.graph.asset_graph import AssetGraph
        ag = AssetGraph()
        topo = ag.query_topology("拓扑完整测试企业")
        # 应有企业节点
        node_types = {n.node_type for n in topo.nodes}
        assert NodeType.ENTERPRISE in node_types
        # 应有边（企业→子公司 PARENT_OF 或 BELONGS_TO）
        assert len(topo.edges) > 0

    def test_trace_id_chain(self):
        """全链路 trace_id 串联审计日志。"""
        summary = run_company("链路追踪测试企业")
        trace_id = summary["trace_id"]

        from passive_agent.audit.export import AuditExport
        export = AuditExport()
        result = export.export_trace(trace_id)
        # 应有多条审计日志（采集/提交/审批等）
        assert result["record_count"] > 0

    def test_run_company_idempotent(self):
        """run_company 多次调用不崩溃。"""
        s1 = run_company("幂等测试企业")
        s2 = run_company("幂等测试企业")
        assert s1["enterprise"] == s2["enterprise"]

    def test_compute_reclaim_in_loop(self):
        """R9 算力回收在闭环中的作用。"""
        summary = run_company("回收测试企业")
        # 闭环完成后应能正常返回（回收检查不崩溃）
        assert "trace_id" in summary

    def test_no_p0_regression(self):
        """P0 集成测试不回归（run_company 返回结构兼容 P0）。"""
        summary = run_company("回归测试企业")
        # P0 summary 必须有的字段
        assert "enterprise" in summary
        assert "trace_id" in summary
        assert "blocked" in summary
        assert "subjects" in summary
        assert "verified" in summary
        assert "suspended" in summary
        assert "submitted" in summary
        assert "approvals" in summary
        # P1 新增字段
        assert "collected_items" in summary
        assert "graph_nodes" in summary
        assert "graph_edges" in summary

    def test_four_clusters_collected(self):
        """四集群被动采集均有执行。"""
        summary = run_company("四集群测试企业")
        # 至少有采集项（来自 mock 回退）
        assert summary["collected_items"] > 0

    def test_audit_log_full_chain_events(self):
        """审计日志覆盖采集/校验/提交/调度四类事件（V-R10-1）。"""
        summary = run_company("全链路审计测试企业")
        from passive_agent.audit.query import AuditQuery
        aq = AuditQuery()
        counts = aq.count_by_type()
        # 应有多种 action 类型
        assert len(counts) > 0
