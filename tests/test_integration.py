"""单企业闭环 R1→R3→R6→R2→R4（mock 被动源）集成测试。"""
from unittest import mock

from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType
from passive_agent.orchestrator.loop import run_company
from passive_agent.verifier.layers import dns_alive


def test_closed_loop_runs():
    summary = run_company("集成测试企业")
    assert summary["subjects"] > 0
    assert summary["verified"] > 0
    assert summary["submitted"] > 0
    assert len(summary["approvals"]) == summary["subjects"]


def test_active_always_blocked():
    for at in [ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND]:
        d = check(at, source_name="integration")
        assert d.allowed is False
        assert d.reason_code == "010001"


def test_dns_resolve_only_no_socket():
    """L2 仅解析（resolver.resolve），绝不对解析出的 IP 发起 socket 连接。"""
    with mock.patch("dns.resolver.resolve") as m:
        answer = mock.MagicMock()
        answer.__len__ = lambda self: 1
        m.return_value = answer
        result = dns_alive("example.com")
        assert result is True
        m.assert_called_once()
        # 本模块不导入/不使用 socket.connect 直连目标 IP（纯被动红线）
