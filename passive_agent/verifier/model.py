"""R2 校验数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from passive_agent.common.enums import VerifyStatus


class LayerResult(BaseModel):
    layer: int                 # 1..4
    name: str                  # 工商主体匹配 / DNS被动存活 / 时间过滤 / 多源交叉
    enabled: bool              # 每层独立开关
    passed: bool
    count: int                # 该层命中/拦截计数
    basis: str                # 依据描述


class VerifyRequest(BaseModel):
    result_id: str
    layer1_biz_match: bool = False   # 层1 工商主体匹配
    layer2_dns_alive: bool = False   # 层2 DNS 仅解析存活（dnspython）
    layer3_time_ok: bool = False     # 层3 时间过滤 ≤1 年
    layer4_src_cnt: int = 0         # 层4 多源佐证方数


class VerifyResult(BaseModel):
    result_id: str
    status: VerifyStatus                # PASS / SUSPEND
    layers: List[LayerResult] = Field(default_factory=list)
    fail_layer: Optional[int] = None
    basis: str = ""
