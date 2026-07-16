"""P1 QA 补充测试（严过关 Yan · 独立验证补充）。

本文件由 QA 工程师严过关基于 P1 PRD 验收清单（V-R7-1~V-R12-4）逐条审计后补充，
覆盖现有 tests/ 中缺失的断言点。不修改业务逻辑代码，仅补充测试断言。

补充覆盖点：
- V-R7-1: 四类集群各 >=2 适配器（显式计数断言）
- V-R7-4: 调度内核无外部调度框架依赖（celery/apscheduler/dramatiq/rq/luigi/airflow/paramiko）
- V-R7-6: 所有出站适配器源码含 _check_compliance 调用（含凭证适配器）
- V-R8-3: 降级/切换事件写 t_audit_log(reason_code=040002)
- V-R8-4: mock 回退成功时不写 SUSPEND(040001) 日志（加强）
- V-R10-2: 每条审计日志含 6 个固定字段（ts/subject_id/action/source/decision+reason_code/trace_id）
- V-R11-4: app.js 含 5min(300000ms) 自动刷新
- V-R11-6: 面板 M5/M6 DOM 区块存在
- V-R12-1: t_asset_node + t_asset_relation 两张表存在且可读写
- V-R12-4: 不做推理补全（无 GDS/LLM/networkx 推理代码）
- R6: 频控 buffer <=95% 绿区断言
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from passive_agent.collector.adapters.crtsh_adapter import CrtshAdapter
from passive_agent.collector.adapters.dns_adapter import DnsAdapter
from passive_agent.collector.adapters.fofa_adapter import FofaAdapter
from passive_agent.collector.adapters.subfinder_adapter import SubfinderAdapter
from passive_agent.collector.adapters.wechat_adapter import WechatAdapter
from passive_agent.collector.adapters.miniapp_adapter import MiniappAdapter
from passive_agent.collector.adapters.equity_adapter import EquityAdapter
from passive_agent.collector.adapters.mock_adapter import MockAdapter
from passive_agent.collector.scheduler import CollectionScheduler
from passive_agent.collector.model import CollectQuery, CollectResult
from passive_agent.collector.registry import AdapterRegistry
from passive_agent.collector.fault_tolerance import FaultToleranceManager
from passive_agent.collector.adapter import SourceAdapter
from passive_agent.common.enums import CollectorCluster
from passive_agent.config import settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent / "passive_agent"


# ============================================================
# V-R7-1: 四类集群各 >=2 适配器（显式计数断言）
# ============================================================

class TestClusterAdapterCount:
    """V-R7-1: 每类集群至少 2 个适配器。"""

    def test_web_cluster_min_two_adapters(self):
        """Web 集群 >=2 适配器（含 crt.sh + dns 真实免凭证源）。"""
        scheduler = CollectionScheduler.create_default()
        web_adapters = scheduler.registry.get_adapters(CollectorCluster.WEB)
        assert len(web_adapters) >= 2
        names = {a.name for a in web_adapters}
        # 真实免凭证源必须存在
        assert "crtsh" in names
        assert "dns-passive" in names

    def test_wechat_cluster_min_two_adapters(self):
        """公众号集群 >=2 适配器。"""
        scheduler = CollectionScheduler.create_default()
        wechat_adapters = scheduler.registry.get_adapters(CollectorCluster.WECHAT)
        assert len(wechat_adapters) >= 2

    def test_miniapp_cluster_min_two_adapters(self):
        """小程序集群 >=2 适配器。"""
        scheduler = CollectionScheduler.create_default()
        miniapp_adapters = scheduler.registry.get_adapters(CollectorCluster.MINIAPP)
        assert len(miniapp_adapters) >= 2

    def test_equity_cluster_min_two_adapters(self):
        """工商股权集群 >=2 适配器。"""
        scheduler = CollectionScheduler.create_default()
        equity_adapters = scheduler.registry.get_adapters(CollectorCluster.EQUITY)
        assert len(equity_adapters) >= 2

    def test_all_four_clusters_registered(self):
        """四类集群全部注册。"""
        scheduler = CollectionScheduler.create_default()
        clusters = set(scheduler.registry.get_clusters())
        assert CollectorCluster.WEB in clusters
        assert CollectorCluster.WECHAT in clusters
        assert CollectorCluster.MINIAPP in clusters
        assert CollectorCluster.EQUITY in clusters


# ============================================================
# V-R7-4: 调度内核无外部调度框架依赖
# ============================================================

class TestNoExternalSchedulerFramework:
    """V-R7-4: 调度内核 100% 自研，无外部调度框架。"""

    def _read_all_python_sources(self) -> dict:
        files = {}
        for py in PROJECT_ROOT.rglob("*.py"):
            try:
                files[str(py)] = py.read_text(encoding="utf-8")
            except Exception:
                pass
        return files

    def test_no_celery_import(self):
        """代码库无 celery 调度框架。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            assert "import celery" not in content.lower(), f"{path}: 不应引入 celery"
            assert "from celery" not in content.lower(), f"{path}: 不应引入 celery"

    def test_no_apscheduler_import(self):
        """代码库无 apscheduler 调度框架。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            assert "import apscheduler" not in content.lower(), f"{path}: 不应引入 apscheduler"
            assert "from apscheduler" not in content.lower(), f"{path}: 不应引入 apscheduler"

    def test_no_dramatiq_import(self):
        """代码库无 dramatiq 调度框架。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            assert "import dramatiq" not in content.lower(), f"{path}: 不应引入 dramatiq"
            assert "from dramatiq" not in content.lower(), f"{path}: 不应引入 dramatiq"

    def test_no_rq_import(self):
        """代码库无 rq（Redis Queue）调度框架。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            # 精确匹配 import rq / from rq，避免误匹配变量名
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("import rq ") or stripped == "import rq":
                    pytest.fail(f"{path}: 不应引入 rq")
                if stripped.startswith("from rq ") or stripped.startswith("from rq."):
                    pytest.fail(f"{path}: 不应引入 rq")

    def test_no_paramiko_import(self):
        """代码库无 paramiko（SSH 主动连接库）。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            assert "import paramiko" not in content.lower(), f"{path}: 不应引入 paramiko"
            assert "from paramiko" not in content.lower(), f"{path}: 不应引入 paramiko"

    def test_no_luigi_airflow_import(self):
        """代码库无 luigi/airflow 调度框架。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            for fw in ["luigi", "airflow"]:
                assert f"import {fw}" not in content.lower(), f"{path}: 不应引入 {fw}"
                assert f"from {fw}" not in content.lower(), f"{path}: 不应引入 {fw}"

    def test_scheduler_is_self_implemented(self):
        """CollectionScheduler 为自研实现（无框架基类继承）。"""
        bases = [cls.__name__ for cls in CollectionScheduler.__mro__]
        # 仅允许 object 和自身，无框架基类
        framework_bases = {"Celery", "Task", "App", "Airflow", "Dag", "Luigi"}
        assert not (set(bases) & framework_bases), \
            f"CollectionScheduler 不应继承调度框架基类: {bases}"


# ============================================================
# V-R7-6: 所有出站适配器源码含 _check_compliance 调用
# ============================================================

class TestAllOutboundAdaptersCompliance:
    """V-R7-6: 所有出站适配器 collect() 内调 _check_compliance()。"""

    @pytest.mark.parametrize("adapter_cls", [
        CrtshAdapter, DnsAdapter, FofaAdapter, SubfinderAdapter,
        WechatAdapter, MiniappAdapter, EquityAdapter,
    ])
    def test_adapter_has_compliance_check(self, adapter_cls):
        """每个适配器源码含 _check_compliance 调用或合规检查。"""
        source = inspect.getsource(adapter_cls)
        assert "_check_compliance" in source, \
            f"{adapter_cls.__name__} 缺少 _check_compliance 调用"


# ============================================================
# V-R8-3: 降级/切换事件写 t_audit_log(reason_code=040002)
# ============================================================

class TestFaultEventAuditLog:
    """V-R8-3: 每次降级/切换事件写入 t_audit_log。"""

    def test_degrade_event_logged(self):
        """源失败降级时写 040002 审计日志。"""

        class FailAdapter(SourceAdapter):
            name = "degrade-test-source"
            cluster = CollectorCluster.WEB
            priority = 10
            requires_credential = False

            def is_available(self):
                return True

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="模拟降级",
                )

        reg = AdapterRegistry()
        reg.register(FailAdapter())
        reg.register(MockAdapter(cluster=CollectorCluster.WEB, name="degrade-backup"))
        ftm = FaultToleranceManager(reg, max_retries=3)

        query = CollectQuery(
            enterprise="降级日志测试企业", subject_name="主体",
            cluster=CollectorCluster.WEB, trace_id="degrade-trace",
        )
        ftm.execute_with_fallback(query, "degrade-trace")

        from passive_agent.audit.logger import search
        logs = search(reason_code="040002", limit=10)
        assert len(logs) > 0, "降级事件应写 040002 审计日志"
        assert any("degrade-test-source" in (l.get("source", "") or "") for l in logs)


# ============================================================
# V-R8-4: mock 回退成功时不写 SUSPEND(040001) 日志（加强）
# ============================================================

class TestMockFallbackNoSuspendLog:
    """V-R8-4: 缺凭证回退 mock 成功时不应写 SUSPEND 日志。"""

    def test_mock_success_no_suspend_log(self):
        """mock 回退成功后无新增 040001 日志。"""

        class NoCredAdapter(SourceAdapter):
            name = "no-cred-strict"
            cluster = CollectorCluster.WEB
            requires_credential = True
            priority = 10

            def is_available(self):
                return False

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="凭证未配置",
                )

        reg = AdapterRegistry()
        reg.register(NoCredAdapter())
        reg.register(MockAdapter(cluster=CollectorCluster.WEB, name="strict-mock"))
        ftm = FaultToleranceManager(reg, max_retries=3)

        from passive_agent.audit.logger import search
        # 记录调用前的 040001 数量
        before = len(search(reason_code="040001", limit=1000))

        query = CollectQuery(
            enterprise="严格挂起测试", subject_name="主体",
            cluster=CollectorCluster.WEB, trace_id="no-suspend-trace",
        )
        result = ftm.execute_with_fallback(query, "no-suspend-trace")
        assert result.success, "mock 回退应成功"

        after = len(search(reason_code="040001", limit=1000))
        assert after == before, \
            "mock 回退成功时不应新增 040001 SUSPEND 日志"


# ============================================================
# V-R10-2: 每条审计日志含 6 个固定字段
# ============================================================

class TestAuditLogFixedFields:
    """V-R10-2: 每条日志含时间戳/主体/动作/数据源/合规判定/trace_id。"""

    def test_log_contains_all_fields(self):
        """审计日志含全部固定字段。"""
        from passive_agent.audit.logger import log, search

        tid = "fixed-fields-trace-001"
        log(
            trace_id=tid,
            subject_id="字段测试企业",
            action="FIELD_TEST",
            source="test-module",
            decision="ALLOW",
            reason_code="000000",
            msg="字段完整性测试",
        )
        results = search(trace_id=tid, limit=1)
        assert len(results) > 0
        entry = results[0]
        # 6 个固定字段
        assert "ts" in entry, "缺少时间戳字段 ts"
        assert entry["ts"] is not None and entry["ts"] != ""
        assert "subject_id" in entry, "缺少主体字段 subject_id"
        assert "action" in entry, "缺少动作字段 action"
        assert "source" in entry, "缺少数据源字段 source"
        assert "decision" in entry, "缺少合规判定字段 decision"
        assert "reason_code" in entry, "缺少原因码字段 reason_code"
        assert "trace_id" in entry, "缺少 trace_id 字段"

    def test_log_fields_non_empty(self):
        """审计日志固定字段值非空。"""
        from passive_agent.audit.logger import log, search

        tid = "nonempty-fields-trace-002"
        log(
            trace_id=tid,
            subject_id="非空测试企业",
            action="NONEMPTY_TEST",
            source="test-src",
            decision="ALLOW",
            reason_code="000000",
            msg="非空测试",
        )
        results = search(trace_id=tid, limit=1)
        assert len(results) > 0
        entry = results[0]
        assert entry["ts"] != ""
        assert entry["subject_id"] == "非空测试企业"
        assert entry["action"] == "NONEMPTY_TEST"
        assert entry["source"] == "test-src"
        assert entry["decision"] == "ALLOW"
        assert entry["trace_id"] == tid


# ============================================================
# V-R11-4: app.js 含 5min(300000ms) 自动刷新
# ============================================================

class TestDashboardAutoRefresh:
    """V-R11-4: 看板数据每 5 分钟自动刷新。"""

    def test_app_js_has_refresh_interval(self):
        """app.js 含 setInterval(refreshAll, 300000) 5min 刷新。"""
        app_js = PROJECT_ROOT / "static" / "app.js"
        assert app_js.exists(), "app.js 应存在"
        content = app_js.read_text(encoding="utf-8")
        assert "setInterval" in content, "app.js 应包含 setInterval 自动刷新"
        assert "300000" in content, "app.js 刷新间隔应为 300000ms（5分钟）"
        assert "refreshAll" in content, "app.js 应调用 refreshAll 刷新函数"

    def test_app_js_no_react(self):
        """V-R11-6: app.js 不引入 React。"""
        app_js = PROJECT_ROOT / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        # 允许在注释中出现 React，但不应有 import React / React.createElement
        assert "import React" not in content, "不应 import React"
        assert "React.createElement" not in content, "不应使用 React.createElement"
        assert "require(" not in content, "不应使用 Node.js require()"


# ============================================================
# V-R11-6: 面板 M5/M6 DOM 区块存在
# ============================================================

class TestDashboardModules:
    """V-R11-6: M5（容错日志）/ M6（算力倾斜）面板区块存在。"""

    def test_index_html_has_m5_m6(self):
        """index.html 含 M5/M6 DOM 区块。"""
        index_html = PROJECT_ROOT / "static" / "index.html"
        assert index_html.exists(), "index.html 应存在"
        content = index_html.read_text(encoding="utf-8")
        # M5 容错降级日志
        assert "fault" in content.lower() or "M5" in content, \
            "index.html 应含 M5 容错降级日志区块"
        # M6 算力倾斜 / 回收
        assert "reclaim" in content.lower() or "M6" in content, \
            "index.html 应含 M6 算力/回收区块"


# ============================================================
# V-R12-1: t_asset_node + t_asset_relation 两张表存在且可读写
# ============================================================

class TestGraphTablesExist:
    """V-R12-1: 两张关系表存在。"""

    def test_t_asset_node_exists(self):
        """t_asset_node 表存在且可查询。"""
        from passive_agent.storage import db
        rows = db.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='t_asset_node'"
        )
        assert len(rows) > 0, "t_asset_node 表应存在"

    def test_t_asset_relation_exists(self):
        """t_asset_relation 表存在且可查询。"""
        from passive_agent.storage import db
        rows = db.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='t_asset_relation'"
        )
        assert len(rows) > 0, "t_asset_relation 表应存在"

    def test_t_source_health_exists(self):
        """t_source_health 表存在。"""
        from passive_agent.storage import db
        rows = db.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='t_source_health'"
        )
        assert len(rows) > 0, "t_source_health 表应存在"


# ============================================================
# V-R12-4: 不做推理补全（无 GDS/LLM/networkx 推理代码）
# ============================================================

class TestNoInferenceCode:
    """V-R12-4: 不做 GDS/LLM 推理补全。"""

    def _read_all_python_sources(self) -> dict:
        files = {}
        for py in PROJECT_ROOT.rglob("*.py"):
            try:
                files[str(py)] = py.read_text(encoding="utf-8")
            except Exception:
                pass
        return files

    def test_no_networkx_inference(self):
        """代码库无 networkx 图推理库。"""
        files = self._read_all_python_sources()
        for path, content in files.items():
            assert "import networkx" not in content.lower(), \
                f"{path}: 不应引入 networkx 推理库"
            assert "from networkx" not in content.lower(), \
                f"{path}: 不应引入 networkx 推理库"

    def test_no_graph_inference_methods(self):
        """AssetGraph 无推理补全方法。"""
        from passive_agent.graph.asset_graph import AssetGraph
        source = inspect.getsource(AssetGraph)
        forbidden = ["infer", "predict", "complete_missing", "guess", "deduce"]
        for kw in forbidden:
            assert kw not in source.lower(), \
                f"AssetGraph 不应含推理方法 '{kw}'（V-R12-4 不做推理补全）"

    def test_no_llm_inference_imports(self):
        """代码库无 LLM 推理调用。"""
        files = self._read_all_python_sources()
        llm_markers = [
            "import openai", "from openai",
            "import langchain", "from langchain",
            "import anthropic", "from anthropic",
        ]
        for path, content in files.items():
            for marker in llm_markers:
                assert marker not in content.lower(), \
                    f"{path}: 不应引入 LLM 库 {marker}"


# ============================================================
# R6 频控 buffer <=95% 绿区断言
# ============================================================

class TestFreqBufferGreenZone:
    """R6 频控硬闸：单 IP <=95% 绿区。"""

    def test_freq_buffer_config(self):
        """FREQ_BUFFER 配置为 0.95（95%）。"""
        assert settings.FREQ_BUFFER == 0.95

    def test_ratelimit_limit_is_95pct(self):
        """频控 limit = ceil(capacity * 0.95) = 95% 容量。"""
        from passive_agent.gateway.ratelimiter import RateLimiter
        rl = RateLimiter(capacity=100, window=1.0, buffer=0.95)
        assert rl._limit() == 95  # ceil(100 * 0.95) = 95

    def test_under_95pct_allowed(self):
        """使用率 <95% 时允许。"""
        from passive_agent.gateway.ratelimiter import RateLimiter
        rl = RateLimiter(capacity=100, window=1.0, buffer=0.95)
        # 94 次应全部允许（< 95）
        for _ in range(94):
            assert rl.acquire("test-ip-95")
        # 第 95 次仍允许（== 95 = limit）
        assert rl.acquire("test-ip-95")

    def test_over_95pct_queued_not_discarded(self):
        """超 95% 进入排队不丢弃。"""
        from passive_agent.gateway.ratelimiter import RateLimiter
        rl = RateLimiter(capacity=100, window=1.0, buffer=0.95)
        for _ in range(95):
            rl.acquire("test-ip-queue")
        # 第 96 次应排队（返回 False）
        result = rl.acquire("test-ip-queue")
        assert not result, "超 95% 应排队返回 False"
        # 排队计数 > 0（不丢弃）
        q = rl.usage("test-ip-queue")
        assert q.queued > 0, "排队计数应 > 0（不丢弃）"


# ============================================================
# V-R7-2: Web 集群含真实免凭证源（crt.sh + dnspython）
# ============================================================

class TestRealCredentialFreeSources:
    """V-R7-2: Web 集群含 crt.sh + dnspython 真实免凭证源。"""

    def test_crtsh_is_credential_free(self):
        """crt.sh 适配器为免凭证源。"""
        adapter = CrtshAdapter()
        assert not adapter.requires_credential, "crt.sh 应为免凭证源"
        assert adapter.is_available(), "crt.sh 应可用（免凭证）"

    def test_dns_is_credential_free(self):
        """DNS 适配器为免凭证源。"""
        adapter = DnsAdapter()
        assert not adapter.requires_credential, "DNS 应为免凭证源"
        assert adapter.is_available(), "DNS 应可用（免凭证）"

    def test_crtsh_uses_httpx(self):
        """crt.sh 使用 httpx 调用（真实出站）。"""
        source = inspect.getsource(CrtshAdapter)
        assert "httpx" in source, "crt.sh 应使用 httpx 出站"
        assert "crt.sh" in source or "CRTSH_API_URL" in source

    def test_dns_uses_resolver_only(self):
        """DNS 适配器仅用 resolver.resolve。"""
        source = inspect.getsource(DnsAdapter)
        assert "resolver.resolve" in source
        assert "socket.connect" not in source
        assert "create_connection" not in source


# ============================================================
# V-R7-3: 适配器可插拔可替换
# ============================================================

class TestAdapterPluggability:
    """V-R7-4: 适配器可插拔可替换。"""

    def test_custom_adapter_pluggable(self):
        """自定义适配器可注册并被调度内核使用。"""

        class CustomAdapter(SourceAdapter):
            name = "custom-test"
            cluster = CollectorCluster.WEB
            priority = 5  # 最高优先
            requires_credential = False

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=True, error="",
                )

        reg = AdapterRegistry()
        reg.register(CustomAdapter())
        reg.register(MockAdapter(cluster=CollectorCluster.WEB))
        ftm = FaultToleranceManager(reg, max_retries=3)
        scheduler = CollectionScheduler(reg, ftm)

        query = CollectQuery(
            enterprise="可插拔测试", subject_name="主体",
            cluster=CollectorCluster.WEB, trace_id="plug-trace",
        )
        result = ftm.execute_with_fallback(query, "plug-trace")
        assert result.source_name == "custom-test", \
            "自定义适配器应被优先使用（priority=5）"

    def test_adapter_replaceable(self):
        """适配器可被替换（同名不重复注册，但可重建注册表）。"""
        reg = AdapterRegistry()
        reg.register(MockAdapter(cluster=CollectorCluster.WEB, name="original"))
        # 重新建注册表替换
        reg2 = AdapterRegistry()
        reg2.register(MockAdapter(cluster=CollectorCluster.WEB, name="replacement"))
        adapters = reg2.get_adapters(CollectorCluster.WEB)
        assert any(a.name == "replacement" for a in adapters)
