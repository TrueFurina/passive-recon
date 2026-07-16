"""R12 图谱查询 API（蓝图 T28）。

路由：
  GET /api/v1/graph/topology?enterprise=xxx → 拓扑查询
  GET /api/v1/graph/stats                   → 节点/边统计
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from passive_agent.common.result import ok
from passive_agent.graph.asset_graph import AssetGraph

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/topology")
def topology(enterprise: str = Query(..., description="企业全称")):
    """按企业查询关联拓扑（节点列表 + 关联关系）。"""
    ag = AssetGraph()
    topo = ag.query_topology(enterprise)
    return ok({
        "enterprise": topo.enterprise,
        "nodes": [n.model_dump() for n in topo.nodes],
        "edges": [e.model_dump() for e in topo.edges],
        "node_count": len(topo.nodes),
        "edge_count": len(topo.edges),
    })


@router.get("/stats")
def stats(enterprise: str | None = Query(None, description="可选企业名过滤")):
    """节点/边统计。"""
    ag = AssetGraph()
    return ok({
        "node_count": ag.node_count(enterprise),
        "edge_count": ag.edge_count(enterprise),
    })
