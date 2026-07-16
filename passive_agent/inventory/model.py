"""R5 台账数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class OssTool(BaseModel):
    name: str
    version: str = ""
    license: str = ""
    purpose: str = ""
    call_boundary: str = ""     # 调用边界（仅被动源 / 禁主动模块）
    boundary_tag: str = "开源"   # "自研" / "开源"
    module_ref: str = ""         # 归属 R 模块（统计口径）


class InventoryExport(BaseModel):
    generated_at: str = ""
    tools: List[OssTool] = Field(default_factory=list)
    ratio: dict = Field(default_factory=dict)  # {open_source_pct, self_dev_pct, self_dev_modules}
