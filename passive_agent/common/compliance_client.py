"""内部合规校验统一封装：所有出站模块复用本函数（fail-closed 关隘）。

任何出站动作必须先本函数放行（返回 allowed=True）才可发出；未 ALLOW 不得发出。
为避免导入期循环依赖，引擎在调用时惰性加载。
"""
from __future__ import annotations

from typing import Optional

from passive_agent.common.enums import ActionType
from passive_agent.compliance.model import ComplianceCheckRequest, ComplianceDecision


def check(
    action_type: str,
    target_url: Optional[str] = None,
    source_name: str = "unknown",
    biz_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ComplianceDecision:
    """出站前必经关隘。未 ALLOW 不得发出。

    action_type 接受 ActionType 枚举或其字符串值；未知动作将在引擎层被默认拦截。
    """
    from passive_agent.compliance.engine import get_engine

    req = ComplianceCheckRequest(
        action_type=action_type if isinstance(action_type, str) else str(action_type),
        target_url=target_url,
        source_name=source_name,
        biz_id=biz_id,
    )
    return get_engine().check(req, trace_id=trace_id)
