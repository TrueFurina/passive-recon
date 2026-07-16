"""R1 规则集：主动动作黑名单 + 被动源白名单。蓝图 §3.2 / T03。"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from passive_agent.common.enums import ActionType, Decision


class Rule(BaseModel):
    name: str
    action_type: ActionType
    decision: Decision
    reason_code: str = "000000"
    enabled: bool = True


# 主动动作集合（命中即物理拦截，fail-closed 强硬执行）
ACTIVE_ACTIONS = {
    ActionType.ACTIVE_SCAN,
    ActionType.ACTIVE_HTTP,
    ActionType.TCP_SEND,
}

# 被动源白名单（仅这些被动查询可放行；出站前必须经本引擎校验）
PASSIVE_WHITELIST = {
    "gateway-proxy",
    "enumerator-adapter",
    "collector-c1",
    "verifier-l2",
}


def default_rules() -> List[Rule]:
    return [
        Rule(name="block-active-scan", action_type=ActionType.ACTIVE_SCAN, decision=Decision.BLOCK, reason_code="010001"),
        Rule(name="block-active-http", action_type=ActionType.ACTIVE_HTTP, decision=Decision.BLOCK, reason_code="010001"),
        Rule(name="block-tcp-send", action_type=ActionType.TCP_SEND, decision=Decision.BLOCK, reason_code="010001"),
        Rule(name="allow-passive-query", action_type=ActionType.PASSIVE_QUERY, decision=Decision.ALLOW, reason_code="000000"),
    ]
