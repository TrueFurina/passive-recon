"""R5 开源台账 / 自研占比 API + 资产浏览 API。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from passive_agent.common.result import ok
from passive_agent.inventory.registry import InventoryRegistry
from passive_agent.storage import db

router = APIRouter(tags=["inventory"])
_reg = InventoryRegistry()


@router.get("/inventory/proof")
def proof():
    p = _reg.export_proof()
    return ok(p.model_dump())


@router.get("/inventory/export")
def export():
    p = _reg.export_proof()
    return ok(p.model_dump())


@router.get("/assets/list")
def list_assets(
    enterprise: Optional[str] = Query(None, description="Filter by enterprise name"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type (subdomain, ip, port, ...)"),
    source: Optional[str] = Query(None, description="Filter by data source"),
    search: Optional[str] = Query(None, description="Search in asset value"),
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """列出资产，支持筛选和分页。"""
    conditions = []
    params = []

    if enterprise:
        conditions.append("enterprise = ?")
        params.append(enterprise)
    if asset_type:
        conditions.append("asset_type = ?")
        params.append(asset_type)
    if source:
        conditions.append("source_name = ?")
        params.append(source)
    if search:
        conditions.append("(asset_value LIKE ? OR title LIKE ? OR ip LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM t_collect_asset WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = db.query(sql, tuple(params))

    # 获取总数
    count_sql = f"SELECT COUNT(*) as cnt FROM t_collect_asset WHERE {where}"
    total = db.query(count_sql, tuple(params[:-2]))[0]["cnt"]

    return ok({
        "total": total,
        "limit": limit,
        "offset": offset,
        "assets": [dict(r) for r in rows],
    })


@router.get("/assets/enterprises")
def list_enterprises():
    """列出所有已采集的企业及其资产统计。"""
    rows = db.query(
        "SELECT enterprise, domain, COUNT(*) as count, "
        "COUNT(DISTINCT asset_type) as type_count, "
        "MAX(id) as last_collected "
        "FROM t_collect_asset GROUP BY enterprise ORDER BY count DESC"
    )
    return ok({
        "enterprises": [dict(r) for r in rows],
    })


@router.get("/assets/risk-summary")
def risk_summary():
    """风险汇总。"""
    rows = db.query(
        "SELECT enterprise, asset_value, ip, source_name, title "
        "FROM t_collect_asset WHERE tags LIKE '%risk%' OR tags LIKE '%P1%' "
        "ORDER BY id DESC LIMIT 50"
    )
    return ok({
        "risks": [dict(r) for r in rows],
    })
