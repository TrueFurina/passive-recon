"""R6 网关数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class SubmitProxyRequest(BaseModel):
    biz_req_no: str                 # 幂等键（唯一）
    batch_id: str
    shard_index: int
    shard_total: int
    payload: Dict[str, Any] = Field(default_factory=dict)  # 单分片情报 ≤ 限额


class Quota(BaseModel):             # R6 网关契约（请求ID/源IP/timestamp/频控计数）
    ip: str
    used: int
    limit: int                     # = ceil(capacity * 0.95)
    usage_pct: float               # ≤ 95
    queued: int


class SubmitProxyVO(BaseModel):
    request_id: str
    src_ip: str
    timestamp: str
    accepted: bool
    quota: Quota
