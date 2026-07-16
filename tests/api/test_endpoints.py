"""V-P1-10/12：各 router 关键端点带 Bearer 令牌的可达性与基本响应结构。

鉴权默认由 conftest autouse 关闭；本文件用例局部开启 API_AUTH_ENABLED
并禁用 loopback 豁免，验证「合法令牌 → 2xx / 业务 code=000000」。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from passive_agent.api import deps
from passive_agent.config import settings
from passive_agent.main import app

# 与 conftest.api_client 注入的测试令牌保持一致
TEST_TOKEN = "test-token-p1-hardening"


@pytest.fixture
def auth_client(monkeypatch):
    """开启鉴权 + 禁用 loopback 豁免，并把测试令牌作为默认请求头注入。

    这样所有 GET/POST 自动携带 Bearer token，无需逐请求显式传 headers。
    """
    monkeypatch.setattr(settings, "API_TOKENS", [TEST_TOKEN])
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(deps, "_is_loopback", lambda r: False)
    return TestClient(app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})


def _h() -> dict:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


def test_compliance_endpoints(auth_client):
    assert auth_client.get("/api/v1/compliance/status").status_code == 200
    r = auth_client.post(
        "/api/v1/compliance/check",
        json={"action_type": "PASSIVE_QUERY", "source_name": "api"},
    )
    assert r.status_code == 200 and r.json()["code"] == "000000"


def test_approval_endpoints(auth_client):
    assert auth_client.get("/api/v1/approval/queue").status_code == 200
    c = auth_client.post(
        "/api/v1/approval/create",
        json={"task_id": "T-EP-1", "subject_id": "s1"},
    )
    assert c.status_code == 200 and c.json()["code"] == "000000"


def test_gateway_endpoints(auth_client):
    assert auth_client.get("/api/v1/gateway/quota").status_code == 200
    s = auth_client.post(
        "/api/v1/gateway/submit",
        json={"biz_req_no": "B1", "batch_id": "B1"},
    )
    assert s.status_code == 200 and s.json()["code"] == "000000"


def test_inventory_endpoints(auth_client):
    assert auth_client.get("/api/v1/inventory/proof").status_code == 200
    assert auth_client.get("/api/v1/inventory/export").status_code == 200


def test_console_endpoints(auth_client):
    assert auth_client.get("/api/v1/console/overview").status_code == 200
    rc = auth_client.post(
        "/api/v1/console/run-company",
        json={"enterprise": "端点测试企业"},
    )
    assert rc.status_code == 200 and rc.json()["code"] == "000000"
    assert auth_client.get("/api/v1/console/metrics-overview").status_code == 200


def test_metrics_endpoints(auth_client):
    assert auth_client.get("/api/v1/metrics/snapshot").status_code == 200
    assert auth_client.get("/api/v1/metrics/war-report").status_code == 200
    assert auth_client.get("/api/v1/metrics/fault-events").status_code == 200


def test_graph_endpoints(auth_client):
    assert (
        auth_client.get(
            "/api/v1/graph/topology", params={"enterprise": "端点测试企业"}
        ).status_code
        == 200
    )
    assert auth_client.get("/api/v1/graph/stats").status_code == 200
