"""R1 合规校验数据模型（蓝图 §3.1）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from passive_agent.common.enums import ActionType, Decision


class ComplianceCheckRequest(BaseModel):
    action_type: str                       # ActionType 值或其字符串；未知动作在引擎层被默认拦截
    target_url: Optional[str] = None       # 主动类必填（此处仅记录）
    source_name: str                       # 发起模块，如 "collector-c1"
    biz_id: Optional[str] = None


class ComplianceDecision(BaseModel):
    """R1 统一输出 {放行/拦截, 理由码}。fail-closed 默认 allowed=False。"""
    allowed: bool = False
    decision: Decision = Decision.BLOCK
    reason_code: str = "010001"
    rule_hit: str = ""
    reason: str = ""
