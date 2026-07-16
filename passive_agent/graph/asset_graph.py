"""R12 资产关联图谱（SQLite 关系表，非图数据库，蓝图 T28）。

节点/边 CRUD + 按企业查拓扑。
不做推理补全（V-R12-4）。
"""
from __future__ import annotations

import json
from typing import List, Optional

from passive_agent.common import logging as glog
from passive_agent.common.enums import EdgeType, NodeType
from passive_agent.graph.model import AssetTopology, GraphEdge, GraphNode
from passive_agent.storage import db

_logger = glog.get_logger("asset-graph")


class AssetGraph:
    """资产关联图谱（SQLite 关系表存储邻接拓扑）。

    节点/边字段设计便于后续 Neo4j 迁移。
    """

    def upsert_node(self, node: GraphNode) -> str:
        """节点写入 t_asset_node（幂等，node_id 唯一）。"""
        try:
            db.write(
                """
                INSERT INTO t_asset_node (node_id, node_type, name, enterprise, properties_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_type=excluded.node_type, name=excluded.name,
                    enterprise=excluded.enterprise, properties_json=excluded.properties_json
                """,
                (
                    node.node_id,
                    node.node_type.value,
                    node.name,
                    node.enterprise,
                    json.dumps(node.properties, ensure_ascii=False),
                ),
            )
        except Exception as exc:
            _logger.error(f"节点写入失败 node_id={node.node_id}: {exc}")
        return node.node_id

    def upsert_edge(self, edge: GraphEdge) -> str:
        """边写入 t_asset_relation（幂等，edge_id 唯一）。"""
        try:
            db.write(
                """
                INSERT INTO t_asset_relation (edge_id, from_node, to_node, edge_type, properties_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO UPDATE SET
                    from_node=excluded.from_node, to_node=excluded.to_node,
                    edge_type=excluded.edge_type, properties_json=excluded.properties_json
                """,
                (
                    edge.edge_id,
                    edge.from_node,
                    edge.to_node,
                    edge.edge_type.value,
                    json.dumps(edge.properties, ensure_ascii=False),
                ),
            )
        except Exception as exc:
            _logger.error(f"边写入失败 edge_id={edge.edge_id}: {exc}")
        return edge.edge_id

    def query_topology(self, enterprise: str) -> AssetTopology:
        """按企业查询关联拓扑（节点列表 + 关联关系）。"""
        nodes = self._query_nodes(enterprise)
        node_ids = {n.node_id for n in nodes}
        edges = self._query_edges_for_nodes(node_ids)
        return AssetTopology(
            enterprise=enterprise,
            nodes=nodes,
            edges=edges,
        )

    def node_count(self, enterprise: Optional[str] = None) -> int:
        """节点计数（可按企业过滤）。"""
        try:
            if enterprise:
                rows = db.query(
                    "SELECT COUNT(*) AS c FROM t_asset_node WHERE enterprise=? AND deleted=0",
                    (enterprise,),
                )
            else:
                rows = db.query(
                    "SELECT COUNT(*) AS c FROM t_asset_node WHERE deleted=0"
                )
            return rows[0]["c"] if rows else 0
        except Exception:
            return 0

    def edge_count(self, enterprise: Optional[str] = None) -> int:
        """边计数（可按企业过滤，通过节点 enterprise 关联）。"""
        try:
            if enterprise:
                rows = db.query(
                    """
                    SELECT COUNT(*) AS c FROM t_asset_relation r
                    JOIN t_asset_node n1 ON r.from_node = n1.node_id
                    WHERE n1.enterprise=? AND r.deleted=0 AND n1.deleted=0
                    """,
                    (enterprise,),
                )
            else:
                rows = db.query(
                    "SELECT COUNT(*) AS c FROM t_asset_relation WHERE deleted=0"
                )
            return rows[0]["c"] if rows else 0
        except Exception:
            return 0

    def _query_nodes(self, enterprise: str) -> List[GraphNode]:
        """查询企业下所有节点。"""
        try:
            rows = db.query(
                "SELECT node_id, node_type, name, enterprise, properties_json "
                "FROM t_asset_node WHERE enterprise=? AND deleted=0",
                (enterprise,),
            )
            nodes: List[GraphNode] = []
            for r in rows:
                props = {}
                if r["properties_json"]:
                    try:
                        props = json.loads(r["properties_json"])
                    except Exception:
                        props = {}
                nodes.append(GraphNode(
                    node_id=r["node_id"],
                    node_type=NodeType(r["node_type"]),
                    name=r["name"],
                    enterprise=r["enterprise"],
                    properties=props,
                ))
            return nodes
        except Exception as exc:
            _logger.error(f"节点查询失败 enterprise={enterprise}: {exc}")
            return []

    def _query_edges_for_nodes(self, node_ids: set) -> List[GraphEdge]:
        """查询与给定节点集相关的所有边。"""
        if not node_ids:
            return []
        try:
            # 查询 from_node 或 to_node 在节点集中的边
            placeholders = ",".join("?" * len(node_ids))
            params = tuple(node_ids) + tuple(node_ids)
            rows = db.query(
                f"""
                SELECT DISTINCT edge_id, from_node, to_node, edge_type, properties_json
                FROM t_asset_relation
                WHERE deleted=0 AND (
                    from_node IN ({placeholders}) OR to_node IN ({placeholders})
                )
                """,
                params,
            )
            edges: List[GraphEdge] = []
            for r in rows:
                props = {}
                if r["properties_json"]:
                    try:
                        props = json.loads(r["properties_json"])
                    except Exception:
                        props = {}
                edges.append(GraphEdge(
                    edge_id=r["edge_id"],
                    from_node=r["from_node"],
                    to_node=r["to_node"],
                    edge_type=EdgeType(r["edge_type"]),
                    properties=props,
                ))
            return edges
        except Exception as exc:
            _logger.error(f"边查询失败: {exc}")
            return []
