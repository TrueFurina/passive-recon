"""R5 开源台账 / 自研占比 API。"""
from __future__ import annotations

from fastapi import APIRouter

from passive_agent.common.result import ok
from passive_agent.inventory.registry import InventoryRegistry

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
