"""R12 图谱数据模型（蓝图 §3.8）。

节点/边字段设计便于后续 Neo4j 迁移：
  node_type → label, edge_type → relationship type, properties_json → properties
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from passive_agent.common.enums import EdgeType, NodeType


def _make_id(*parts: str) -> str:
    """根据多部分生成确定性唯一 ID（type:name 哈希）。"""
    raw = ":".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


class GraphNode(BaseModel):
    """图谱节点。"""
    node_id: str = ""                        # 唯一 ID（自动生成）
    node_type: NodeType = NodeType.ENTERPRISE
    name: str = ""
    enterprise: str = ""                     # 所属企业
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context) -> None:
        if not self.node_id:
            self.node_id = _make_id(self.node_type.value, self.name, self.enterprise)


class GraphEdge(BaseModel):
    """图谱边/关系。"""
    edge_id: str = ""                        # 唯一 ID（自动生成）
    from_node: str = ""                      # 源节点 ID
    to_node: str = ""                        # 目标节点 ID
    edge_type: EdgeType = EdgeType.BELONGS_TO
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context) -> None:
        if not self.edge_id:
            self.edge_id = _make_id(self.from_node, self.to_node, self.edge_type.value)


class AssetTopology(BaseModel):
    """按企业查询的关联拓扑。"""
    enterprise: str = ""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
