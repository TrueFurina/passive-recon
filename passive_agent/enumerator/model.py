"""R3 主体数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TargetSubject(BaseModel):
    name: str
    relation: str = "全资子公司"     # 母公司 / 全资子公司 / 控股子公司 / 分公司 / 目标企业
    credit_code: Optional[str] = None
    depth: int = 0                    # 穿透层数
    # FAFU 反哺扩展：资产字段
    domain: str = ""
    ip: Optional[str] = None
    port: Optional[int] = None
    tech_stack: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"           # LOW / MID / HIGH
    risk_notes: str = ""


class SubjectList(BaseModel):
    enterprise: str
    max_depth: int = 3
    subjects: List[TargetSubject] = Field(default_factory=list)
    exported_at: str = ""            # ISO8601 UTC
