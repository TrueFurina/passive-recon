"""R1 合规拦截 / 放行 / 白名单 + 压测断言。"""
from passive_agent.compliance.engine import get_engine
from passive_agent.compliance.model import ComplianceCheckRequest
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType


def test_active_scan_blocked():
    d = get_engine().check(ComplianceCheckRequest(
        action_type=ActionType.ACTIVE_SCAN, source_name="t"))
    assert d.allowed is False
    assert d.decision.value == "BLOCK"
    assert d.reason_code == "010001"


def test_active_http_blocked():
    d = get_engine().check(ComplianceCheckRequest(
        action_type=ActionType.ACTIVE_HTTP, source_name="t"))
    assert not d.allowed and d.reason_code == "010001"


def test_tcp_send_blocked():
    d = get_engine().check(ComplianceCheckRequest(
        action_type=ActionType.TCP_SEND, source_name="t"))
    assert not d.allowed and d.reason_code == "010001"


def test_passive_allowed():
    d = get_engine().check(ComplianceCheckRequest(
        action_type=ActionType.PASSIVE_QUERY, source_name="gateway-proxy"))
    assert d.allowed and d.decision.value == "ALLOW"


def test_unknown_fail_closed():
    # 未知动作默认拦截（fail-closed）
    d = get_engine().check(ComplianceCheckRequest(
        action_type="WEIRD_ACTION_X", source_name="x"))
    assert d.allowed is False and d.reason_code == "010001"


def test_client_blocks_active():
    d = check(ActionType.ACTIVE_SCAN, source_name="client-demo")
    assert d.allowed is False and d.reason_code == "010001"
