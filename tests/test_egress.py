"""R1 关隘出站目标校验（F-5 生产加固）回归测试。

验证：即便动作被白名单放行，出站目标仍须满足
① 仅 HTTPS；② 非内网/链路本地（SSRF 防护）；③ EGRESS_ENFORCE 时命中白名单。
用 unittest.mock 替换 socket.getaddrinfo，避免真实 DNS 与网络依赖。
"""
from unittest.mock import patch

from passive_agent import config as cfg
from passive_agent.compliance.engine import get_engine
from passive_agent.compliance.model import ComplianceCheckRequest
from passive_agent.common.enums import ActionType

_PUBLIC = [(None, None, None, None, ("93.184.216.34", 0))]
_PRIVATE = [(None, None, None, None, ("127.0.0.1", 0))]
_WHITELISTED = [(None, None, None, None, ("1.2.3.4", 0))]
_NOTLISTED = [(None, None, None, None, ("5.6.7.8", 0))]


def _req(target_url):
    return ComplianceCheckRequest(
        action_type=ActionType.PASSIVE_QUERY.value,
        target_url=target_url,
        source_name="t",
    )


def test_non_https_blocked():
    eng = get_engine()
    d = eng.check(_req("http://example.com"))
    assert d.allowed is False
    assert d.reason_code == "010002"


def test_private_ip_blocked():
    eng = get_engine()
    with patch("socket.getaddrinfo", return_value=_PRIVATE):
        d = eng.check(_req("https://127.0.0.1/api"))
    assert d.allowed is False
    assert d.reason_code == "010002"


def test_public_https_allowed():
    eng = get_engine()
    with patch("socket.getaddrinfo", return_value=_PUBLIC):
        d = eng.check(_req("https://example.com/api"))
    assert d.allowed is True


def test_egress_whitelist_enforce_blocks_unlisted(monkeypatch):
    eng = get_engine()
    monkeypatch.setattr(cfg.settings, "EGRESS_ENFORCE", True)
    monkeypatch.setattr(cfg.settings, "EGRESS_IPS", ["1.2.3.4"])
    with patch("socket.getaddrinfo", return_value=_NOTLISTED):
        d = eng.check(_req("https://other.example.com/api"))
    assert d.allowed is False
    assert d.reason_code == "010002"


def test_egress_whitelist_enforce_allows_listed(monkeypatch):
    eng = get_engine()
    monkeypatch.setattr(cfg.settings, "EGRESS_ENFORCE", True)
    monkeypatch.setattr(cfg.settings, "EGRESS_IPS", ["1.2.3.4"])
    with patch("socket.getaddrinfo", return_value=_WHITELISTED):
        d = eng.check(_req("https://1.2.3.4/api"))
    assert d.allowed is True
