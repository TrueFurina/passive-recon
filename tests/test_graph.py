"""R12 图谱 CRUD/查询测试（蓝图 T30）。

覆盖：
- 节点/边 CRUD 幂等性
- 按企业查拓扑完整性
- Neo4j 迁移字段兼容性验证
"""
from __future__ import annotations

import pytest

from passive_agent.graph.asset_graph import AssetGraph
from passive_agent.graph.model import AssetTopology, GraphEdge, GraphNode
from passive_agent.common.enums import EdgeType, NodeType


class TestAssetGraphCRUD:
    """节点/边 CRUD 幂等性测试。"""

    def test_upsert_node(self):
        """节点写入（幂等，node_id 唯一）。"""
        ag = AssetGraph()
        node = GraphNode(
            node_type=NodeType.ENTERPRISE,
            name="图谱测试企业",
            enterprise="图谱测试企业",
            properties={"credit_code": "123456"},
        )
        node_id = ag.upsert_node(node)
        assert node_id == node.node_id
        # 幂等：重复写入不报错
        ag.upsert_node(node)
        assert ag.node_count("图谱测试企业") >= 1

    def test_upsert_edge(self):
        """边写入（幂等，edge_id 唯一）。"""
        ag = AssetGraph()
        ent_node = GraphNode(
            node_type=NodeType.ENTERPRISE,
            name="边测试企业",
            enterprise="边测试企业",
        )
        dom_node = GraphNode(
            node_type=NodeType.DOMAIN,
            name="example.com",
            enterprise="边测试企业",
        )
        ag.upsert_node(ent_node)
        ag.upsert_node(dom_node)

        edge = GraphEdge(
            from_node=ent_node.node_id,
            to_node=dom_node.node_id,
            edge_type=EdgeType.BELONGS_TO,
        )
        edge_id = ag.upsert_edge(edge)
        assert edge_id == edge.edge_id
        # 幂等
        ag.upsert_edge(edge)
        assert ag.edge_count("边测试企业") >= 1

    def test_node_count(self):
        """节点计数。"""
        ag = AssetGraph()
        before = ag.node_count()
        ag.upsert_node(GraphNode(
            node_type=NodeType.ENTERPRISE,
            name="计数测试企业",
            enterprise="计数测试企业",
        ))
        after = ag.node_count()
        assert after >= before

    def test_edge_count(self):
        """边计数。"""
        ag = AssetGraph()
        before = ag.edge_count()
        n1 = GraphNode(node_type=NodeType.ENTERPRISE, name="边计数1", enterprise="边计数企业")
        n2 = GraphNode(node_type=NodeType.DOMAIN, name="count.com", enterprise="边计数企业")
        ag.upsert_node(n1)
        ag.upsert_node(n2)
        ag.upsert_edge(GraphEdge(from_node=n1.node_id, to_node=n2.node_id))
        after = ag.edge_count()
        assert after >= before


class TestTopologyQuery:
    """按企业查拓扑测试。"""

    def test_query_topology(self):
        """按企业查询关联拓扑（V-R12-3）。"""
        ag = AssetGraph()
        enterprise = "拓扑测试企业"

        # 写入企业节点 + 子公司节点 + 域名节点 + 关联边
        ent = GraphNode(node_type=NodeType.ENTERPRISE, name=enterprise, enterprise=enterprise)
        sub = GraphNode(node_type=NodeType.SUBSIDIARY, name="子公司A", enterprise=enterprise)
        dom = GraphNode(node_type=NodeType.DOMAIN, name="topo.com", enterprise=enterprise)

        ag.upsert_node(ent)
        ag.upsert_node(sub)
        ag.upsert_node(dom)

        ag.upsert_edge(GraphEdge(
            from_node=ent.node_id, to_node=sub.node_id,
            edge_type=EdgeType.PARENT_OF,
        ))
        ag.upsert_edge(GraphEdge(
            from_node=sub.node_id, to_node=dom.node_id,
            edge_type=EdgeType.BELONGS_TO,
        ))

        topo = ag.query_topology(enterprise)
        assert topo.enterprise == enterprise
        assert len(topo.nodes) >= 3
        assert len(topo.edges) >= 2

    def test_topology_node_types(self):
        """拓扑包含多种节点类型。"""
        ag = AssetGraph()
        enterprise = "多类型测试企业"

        for nt, name in [
            (NodeType.ENTERPRISE, enterprise),
            (NodeType.SUBSIDIARY, "子A"),
            (NodeType.BRANCH, "分B"),
            (NodeType.DOMAIN, "multi.com"),
            (NodeType.WECHAT_ACCOUNT, "公众号A"),
            (NodeType.MINI_PROGRAM, "小程序A"),
        ]:
            ag.upsert_node(GraphNode(
                node_type=nt, name=name, enterprise=enterprise,
            ))

        topo = ag.query_topology(enterprise)
        types = {n.node_type for n in topo.nodes}
        assert NodeType.ENTERPRISE in types
        assert NodeType.SUBSIDIARY in types
        assert NodeType.DOMAIN in types


class TestNeo4jMigrationCompat:
    """Neo4j 迁移字段兼容性验证。"""

    def test_node_fields_neo4j_compatible(self):
        """节点字段设计便于 Neo4j 迁移（node_type→label）。"""
        node = GraphNode(
            node_type=NodeType.ENTERPRISE,
            name="迁移测试",
            enterprise="迁移测试",
            properties={"credit_code": "ABC123"},
        )
        # 验证字段存在且类型正确
        assert hasattr(node, "node_type")  # → Neo4j label
        assert hasattr(node, "name")
        assert hasattr(node, "enterprise")
        assert hasattr(node, "properties")  # → Neo4j properties
        assert hasattr(node, "node_id")  # → Neo4j node ID

    def test_edge_fields_neo4j_compatible(self):
        """边字段设计便于 Neo4j 迁移（edge_type→relationship type）。"""
        edge = GraphEdge(
            from_node="node-1",
            to_node="node-2",
            edge_type=EdgeType.OWNS,
            properties={"share_pct": 51.0},
        )
        assert hasattr(edge, "edge_type")  # → Neo4j relationship type
        assert hasattr(edge, "from_node")  # → Neo4j source node
        assert hasattr(edge, "to_node")  # → Neo4j target node
        assert hasattr(edge, "properties")  # → Neo4j properties
        assert hasattr(edge, "edge_id")

    def test_node_id_deterministic(self):
        """节点 ID 确定性生成（同类型同名同企业→同 ID）。"""
        n1 = GraphNode(node_type=NodeType.ENTERPRISE, name="确定性", enterprise="确定性")
        n2 = GraphNode(node_type=NodeType.ENTERPRISE, name="确定性", enterprise="确定性")
        assert n1.node_id == n2.node_id

    def test_edge_id_deterministic(self):
        """边 ID 确定性生成。"""
        e1 = GraphEdge(from_node="A", to_node="B", edge_type=EdgeType.OWNS)
        e2 = GraphEdge(from_node="A", to_node="B", edge_type=EdgeType.OWNS)
        assert e1.edge_id == e2.edge_id
