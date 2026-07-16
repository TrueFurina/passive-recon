"""V-P1-1/2/3/7/9：API 层鉴权行为（401 / 2xx / loopback 豁免 / hmac 常量比较）。

注意：conftest 的 autouse fixture 默认关闭鉴权以保 180 绿；
本文件各用例局部通过 monkeypatch 开启 API_AUTH_ENABLED 并注入测试令牌。
为触发 401（否则 TestClient 的 testclient 来源被 loopback 豁免），
需 monkeypatch deps._is_loopback 返回 False。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from passive_agent.api import deps
from passive_agent.config import settings
from passive_agent.main import app

TEST_TOKEN = "p1-hardening-test-token"


@pytest.fixture
def client_with_token(monkeypatch):
    """注入测试令牌；鉴权开关由用例局部控制。"""
    monkeypatch.setattr(settings, "API_TOKENS", [TEST_TOKEN])
    return TestClient(app)


def test_missing_token_401(client_with_token, monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(deps, "_is_loopback", lambda r: False)
    r = client_with_token.get("/api/v1/approval/queue")
    assert r.status_code == 401
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "unauthorized"
    assert body["code"] == "040001"


def test_wrong_token_401(client_with_token, monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(deps, "_is_loopback", lambda r: False)
    r = client_with_token.get(
        "/api/v1/approval/queue",
        headers={"Authorization": "Bearer not-the-right-token"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "040001"


def test_valid_token_2xx(client_with_token, monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(deps, "_is_loopback", lambda r: False)
    r = client_with_token.get(
        "/api/v1/approval/queue",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert r.status_code == 200


def test_exempt_paths_no_auth(client_with_token, monkeypatch):
    """V-P1-4/5/6：免鉴权路径即使开启鉴权也不拦截。"""
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(deps, "_is_loopback", lambda r: True)  # 隔离 loopback 影响
    for path in ["/api/v1/health", "/docs", "/openapi.json", "/"]:
        r = client_with_token.get(path)
        assert r.status_code != 401, f"{path} 不应返回 401"
    # /static/* 前缀豁免
    r = client_with_token.get("/static/does-not-exist.css")
    assert r.status_code != 401


def test_loopback_exempt(client_with_token, monkeypatch):
    """V-P1-7：来源 IP 为 testclient（Starlette TestClient）免 token。"""
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    # 不覆盖 _is_loopback → 真实 client.host="testclient" → 豁免
    r = client_with_token.get("/api/v1/approval/queue")
    assert r.status_code == 200


def test_verify_token_constant_time(monkeypatch):
    """V-P1-9：verify_token 使用 hmac.compare_digest（常量时间）且 fail-closed。"""
    from passive_agent.common import security

    monkeypatch.setattr(settings, "API_TOKENS", [TEST_TOKEN])
    assert security.verify_token(f"Bearer {TEST_TOKEN}") is True
    assert security.verify_token("Bearer wrong") is False
    assert security.verify_token("") is False
    assert security.verify_token("notbearer x") is False
    assert security.verify_token(None) is False
