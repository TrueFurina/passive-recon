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
    clauses = []
    params = []

    filters = [
        (enterprise, "enterprise = ?", [enterprise]),
        (asset_type, "asset_type = ?", [asset_type]),
        (source, "source_name = ?", [source]),
    ]
    for val, clause, vals in filters:
        if val:
            clauses.append(clause)
            params.extend(vals)

    if search:
        like = f"%{search}%"
        clauses.append("(asset_value LIKE ? OR title LIKE ? OR ip LIKE ?)")
        params.extend([like, like, like])

    where = " AND ".join(clauses) if clauses else "1=1"
    full_params = params + [limit, offset]

    rows = db.query(
        f"SELECT * FROM t_collect_asset WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        tuple(full_params),
    )
    total = db.query(
        f"SELECT COUNT(*) as cnt FROM t_collect_asset WHERE {where}",
        tuple(params),
    )[0]["cnt"]

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
