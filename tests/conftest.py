"""测试会话级 fixture：将项目根加入 sys.path，并初始化临时 SQLite 库。

P1 扩展：新增 collector/scheduler/graph 临时实例 fixture。
全局 mock 外部网络调用（httpx + dns），避免测试中真实出站。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from passive_agent.config import settings  # noqa: E402
from passive_agent.storage import db  # noqa: E402


@pytest.fixture(autouse=True)
def mock_external_network():
    """全局 mock httpx.Client + dns.resolver.resolve，避免测试真实出站。

    默认行为：
    - httpx.Client.get() → 返回空 JSON 列表（CrtshAdapter 得 0 条 → success=False → mock 回退）
    - dns.resolver.resolve() → 抛异常（DnsAdapter 得 0 条 → success=False → mock 回退）

    需验证真实适配器行为的测试用 @patch 覆盖即可（装饰器 patch 优先级高于 autouse fixture）。
    """
    # Mock httpx.Client (used by P1 CrtshAdapter)
    httpx_patcher = patch("httpx.Client")
    mock_httpx_cls = httpx_patcher.start()
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = []  # 空结果
    mock_resp.raise_for_status = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp
    mock_httpx_cls.return_value = mock_client

    # Mock httpx.get (used by FAFU sources.py collectors)
    httpx_get_patcher = patch("httpx.get")
    mock_httpx_get = httpx_get_patcher.start()
    mock_get_resp = MagicMock()
    mock_get_resp.json.return_value = []
    mock_get_resp.text = ""
    mock_get_resp.status_code = 200
    mock_get_resp.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_get_resp

    # Mock dns.resolver.resolve
    dns_patcher = patch("dns.resolver.resolve", side_effect=Exception("mocked: no DNS in tests"))
    dns_patcher.start()

    yield

    httpx_patcher.stop()
    httpx_get_patcher.stop()
    dns_patcher.stop()


@pytest.fixture(scope="session", autouse=True)
def setup_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "agent.db"
    db.configure(str(path))
    db.init()
    yield
    # 还原（避免污染其它会话）
    db.configure(str(path))


# ===== P1 增量 fixture =====

@pytest.fixture
def adapter_registry():
    """创建带默认适配器的注册表。"""
    from passive_agent.collector.registry import AdapterRegistry
    from passive_agent.collector.adapters import (
        CrtshAdapter, DnsAdapter, FofaAdapter, SubfinderAdapter,
        WechatAdapter, MiniappAdapter, EquityAdapter, MockAdapter,
    )
    from passive_agent.common.enums import CollectorCluster

    reg = AdapterRegistry()
    reg.register(CrtshAdapter())
    reg.register(DnsAdapter())
    reg.register(FofaAdapter())
    reg.register(SubfinderAdapter())
    reg.register(MockAdapter(cluster=CollectorCluster.WEB))
    reg.register(WechatAdapter())
    reg.register(MockAdapter(cluster=CollectorCluster.WECHAT))
    reg.register(MiniappAdapter())
    reg.register(MockAdapter(cluster=CollectorCluster.MINIAPP))
    reg.register(EquityAdapter())
    reg.register(MockAdapter(cluster=CollectorCluster.EQUITY))
    return reg


@pytest.fixture
def collection_scheduler(adapter_registry):
    """创建采集调度器。"""
    from passive_agent.collector.scheduler import CollectionScheduler
    from passive_agent.collector.fault_tolerance import FaultToleranceManager

    ftm = FaultToleranceManager(adapter_registry, max_retries=3)
    return CollectionScheduler(adapter_registry, ftm)


@pytest.fixture
def compute_scheduler():
    """创建算力调度器。"""
    from unittest.mock import MagicMock
    from passive_agent.scheduler.compute_scheduler import ComputeScheduler
    return ComputeScheduler(snapshot_store=MagicMock())


@pytest.fixture
def asset_graph():
    """创建资产图谱实例。"""
    from passive_agent.graph.asset_graph import AssetGraph
    return AssetGraph()


@pytest.fixture
def metrics_aggregator(compute_scheduler):
    """创建度量聚合器。"""
    from passive_agent.metrics.aggregator import MetricsAggregator
    return MetricsAggregator(compute_scheduler=compute_scheduler)


# ===== P1 鉴权测试支撑 fixture =====

@pytest.fixture(autouse=True)
def _disable_api_auth(monkeypatch):
    """P1 鉴权默认关闭，保 180 既有测试绿（新鉴权测试局部开启 API_AUTH_ENABLED）。"""
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", False)


@pytest.fixture
def api_client(monkeypatch):
    """带测试令牌的 TestClient；鉴权可由测试局部开启。

    仅注入测试令牌到 settings.API_TOKENS；鉴权开关默认由 _disable_api_auth
    置 False，新鉴权测试内再 monkeypatch 置 True 即可。
    """
    from fastapi.testclient import TestClient

    from passive_agent.main import app

    monkeypatch.setattr(settings, "API_TOKENS", ["test-token-p1-hardening"])
    return TestClient(app)
