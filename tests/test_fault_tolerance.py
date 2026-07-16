"""R8 容错降级测试（蓝图 T29）。

覆盖：
- 主源失败→备用源成功切换
- 全源失败→SUSPEND + 040001 日志
- mock 回退不计挂起
- 健康状态转换（HEALTHY→DEGRADED→UNAVAILABLE→恢复）
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from passive_agent.collector.adapter import SourceAdapter
from passive_agent.collector.fault_tolerance import FaultToleranceManager
from passive_agent.collector.model import CollectQuery, CollectResult
from passive_agent.collector.registry import AdapterRegistry
from passive_agent.collector.adapters.mock_adapter import MockAdapter
from passive_agent.common.enums import CollectorCluster, SourceHealth


class TestFaultTolerance:
    """容错降级管理器测试。"""

    def _make_query(self, cluster=CollectorCluster.WEB) -> CollectQuery:
        return CollectQuery(
            enterprise="测试企业",
            subject_name="测试主体",
            cluster=cluster,
            trace_id="test-trace",
        )

    def test_primary_source_success(self):
        """主源成功直接返回。"""
        reg = AdapterRegistry()
        reg.register(MockAdapter(cluster=CollectorCluster.WEB))
        ftm = FaultToleranceManager(reg, max_retries=3)

        result = ftm.execute_with_fallback(self._make_query(), "test-trace")
        assert result.success
        assert len(result.items) > 0

    def test_failover_to_backup(self):
        """主源失败→备用源成功切换（V-R8-1）。"""

        class FailAdapter(SourceAdapter):
            name = "fail-source"
            cluster = CollectorCluster.WEB
            priority = 10

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="连接超时",
                )

        reg = AdapterRegistry()
        reg.register(FailAdapter())
        reg.register(MockAdapter(cluster=CollectorCluster.WEB, name="backup-mock"))
        ftm = FaultToleranceManager(reg, max_retries=3)

        result = ftm.execute_with_fallback(self._make_query(), "test-trace")
        assert result.success
        assert result.source_name == "backup-mock"

    def test_all_sources_fail_suspend(self):
        """全源不可用→SUSPEND + 040001 日志（V-R8-2）。"""

        class FailAdapter1(SourceAdapter):
            name = "fail-1"
            cluster = CollectorCluster.WEB
            priority = 10
            requires_credential = False

            def is_available(self):
                return True

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="不可用",
                )

        class FailAdapter2(SourceAdapter):
            name = "fail-2"
            cluster = CollectorCluster.WEB
            priority = 20
            requires_credential = False

            def is_available(self):
                return True

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="不可用",
                )

        reg = AdapterRegistry()
        reg.register(FailAdapter1())
        reg.register(FailAdapter2())
        ftm = FaultToleranceManager(reg, max_retries=1)

        result = ftm.execute_with_fallback(self._make_query(), "test-trace")
        assert not result.success
        assert "SUSPEND" in result.error

        # 验证 040001 日志写入
        from passive_agent.audit.logger import search
        logs = search(reason_code="040001", limit=5)
        assert len(logs) > 0

    def test_mock_fallback_no_suspend(self):
        """缺凭证回退 mock 不计挂起（V-R8-4）。"""
        # 凭证适配器缺凭证 + mock 适配器可用 → 应回退 mock 成功
        reg = AdapterRegistry()
        # 注册一个缺凭证的适配器（is_available=False）

        class NoCredAdapter(SourceAdapter):
            name = "no-cred"
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

        reg.register(NoCredAdapter())
        reg.register(MockAdapter(cluster=CollectorCluster.WEB))
        ftm = FaultToleranceManager(reg, max_retries=3)

        result = ftm.execute_with_fallback(self._make_query(), "test-trace")
        # mock 回退成功
        assert result.success

    def test_health_state_transition(self):
        """健康状态转换：HEALTHY→DEGRADED→UNAVAILABLE→恢复。"""
        fail_count = [0]

        class FlakyAdapter(SourceAdapter):
            name = "flaky"
            cluster = CollectorCluster.WEB
            priority = 10
            requires_credential = False

            def is_available(self):
                return True

            def collect(self, query, trace_id):
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=False, error="临时故障",
                )

        reg = AdapterRegistry()
        reg.register(FlakyAdapter())
        ftm = FaultToleranceManager(reg, max_retries=3)

        query = self._make_query()
        # 第一次失败 → DEGRADED
        ftm.execute_with_fallback(query, "trace-1")
        assert ftm._get_health("flaky") == SourceHealth.DEGRADED

        # 第二次失败 → 仍 DEGRADED (count=2 < max_retries=3)
        ftm.execute_with_fallback(query, "trace-2")
        assert ftm._get_health("flaky") == SourceHealth.DEGRADED

        # 第三次失败 → UNAVAILABLE (count=3 >= max_retries=3)
        ftm.execute_with_fallback(query, "trace-3")
        assert ftm._get_health("flaky") == SourceHealth.UNAVAILABLE

    def test_health_recovery(self):
        """成功后健康状态恢复 HEALTHY。"""

        class RecoverableAdapter(SourceAdapter):
            name = "recoverable"
            cluster = CollectorCluster.WEB
            priority = 10
            call_count = [0]

            def is_available(self):
                return True

            def collect(self, query, trace_id):
                self.call_count[0] += 1
                if self.call_count[0] == 1:
                    return CollectResult(
                        query=query, items=[], source_name=self.name,
                        success=False, error="临时故障",
                    )
                return CollectResult(
                    query=query, items=[], source_name=self.name,
                    success=True,
                )

        reg = AdapterRegistry()
        adapter = RecoverableAdapter()
        reg.register(adapter)
        reg.register(MockAdapter(cluster=CollectorCluster.WEB))
        ftm = FaultToleranceManager(reg, max_retries=3)

        query = self._make_query()
        # 第一次失败 → DEGRADED
        ftm.execute_with_fallback(query, "trace-1")
        assert ftm._get_health("recoverable") == SourceHealth.DEGRADED

        # 重置 call_count 使第二次成功
        adapter.call_count[0] = 1
        ftm.execute_with_fallback(query, "trace-2")
        assert ftm._get_health("recoverable") == SourceHealth.HEALTHY

    def test_get_health_status(self):
        """get_health_status 返回所有源状态（供 M5 面板）。"""
        reg = AdapterRegistry()
        reg.register(MockAdapter(cluster=CollectorCluster.WEB))
        ftm = FaultToleranceManager(reg, max_retries=3)

        # 执行一次采集
        ftm.execute_with_fallback(self._make_query(), "test")
        status = ftm.get_health_status()
        assert isinstance(status, dict)
