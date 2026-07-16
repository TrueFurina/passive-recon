"""R10 审计日志检索/导出测试（蓝图 T30）。

覆盖：
- 企业/时间/违规三维组合检索
- trace_id 轨迹导出
- count_by_type 统计
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from passive_agent.audit.query import AuditQuery
from passive_agent.audit.export import AuditExport
from passive_agent.audit.logger import log, search, log_chain


class TestAuditQuery:
    """审计日志检索测试。"""

    def test_search_by_enterprise(self):
        """按企业维度检索（V-R10-3）。"""
        log(trace_id="trace-1", subject_id="测试企业A",
            action="COLLECT", source="test", decision="ALLOW", msg="测试")
        results = AuditQuery().search(enterprise="测试企业A")
        assert len(results) > 0
        assert all(r["subject_id"] == "测试企业A" for r in results)

    def test_search_by_decision(self):
        """按违规类型（decision）检索。"""
        log(trace_id="trace-2", subject_id="测试企业B",
            action="BLOCK_TEST", source="test", decision="BLOCK", msg="拦截测试")
        results = AuditQuery().search(decision="BLOCK")
        assert len(results) > 0
        assert all(r["decision"] == "BLOCK" for r in results)

    def test_search_by_reason_code(self):
        """按 reason_code 检索。"""
        log(trace_id="trace-3", subject_id="测试企业C",
            action="SUSPEND_TEST", source="test", decision="SUSPEND",
            reason_code="040001", msg="挂起测试")
        results = AuditQuery().search(reason_code="040001")
        assert len(results) > 0
        assert all(r["reason_code"] == "040001" for r in results)

    def test_search_by_trace_id(self):
        """按 trace_id 检索。"""
        tid = "trace-specific-12345"
        log(trace_id=tid, subject_id="测试企业D",
            action="COLLECT", source="test", decision="ALLOW", msg="trace 测试")
        results = AuditQuery().search(trace_id=tid)
        assert len(results) > 0
        assert all(r["trace_id"] == tid for r in results)

    def test_search_combined(self):
        """三维组合检索（企业+decision+reason_code）。"""
        log(trace_id="trace-combined", subject_id="组合测试企业",
            action="COMBINED", source="test", decision="BLOCK",
            reason_code="040002", msg="组合检索测试")
        results = AuditQuery().search(
            enterprise="组合测试企业",
            decision="BLOCK",
            reason_code="040002",
        )
        assert len(results) > 0

    def test_count_by_type(self):
        """按 action 维度统计计数（V-R10-1）。"""
        log(trace_id="c1", subject_id="统计测试",
            action="COLLECT", source="test", decision="ALLOW", msg="采集")
        log(trace_id="c2", subject_id="统计测试",
            action="VERIFY", source="test", decision="ALLOW", msg="校验")
        counts = AuditQuery().count_by_type()
        assert isinstance(counts, dict)
        # 应至少有 COLLECT 或 VERIFY 的计数
        assert "COLLECT" in counts or "VERIFY" in counts


class TestAuditExport:
    """审计日志导出测试。"""

    def test_export_json(self):
        """导出检索结果为 JSON 文件（V-R10-4）。"""
        log(trace_id="export-trace", subject_id="导出测试企业",
            action="COLLECT", source="test", decision="ALLOW", msg="导出测试")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=tempfile.gettempdir()
        ) as f:
            path = f.name

        try:
            AuditExport().export_json(path, enterprise="导出测试企业")
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            assert "records" in data
            assert data["count"] > 0
            assert all(r["subject_id"] == "导出测试企业" for r in data["records"])
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_trace(self):
        """按 trace_id 导出完整链路轨迹（V-R10-5）。"""
        tid = "trace-export-67890"
        log(trace_id=tid, subject_id="链路测试企业",
            action="COLLECT", source="adapter-1", decision="ALLOW", msg="采集开始")
        log(trace_id=tid, subject_id="链路测试企业",
            action="VERIFY", source="pipeline", decision="ALLOW", msg="核验通过")
        log(trace_id=tid, subject_id="链路测试企业",
            action="SUBMIT", source="gateway", decision="ALLOW", msg="提交成功")

        result = AuditExport().export_trace(tid)
        assert result["trace_id"] == tid
        assert result["record_count"] >= 3
        assert len(result["timeline"]) >= 3
        # 时间线按时间排序
        actions = [t["action"] for t in result["timeline"]]
        assert "COLLECT" in actions
        assert "VERIFY" in actions
        assert "SUBMIT" in actions

    def test_export_trace_to_file(self):
        """trace 轨迹导出到文件。"""
        tid = "trace-file-export"
        log(trace_id=tid, subject_id="文件导出测试",
            action="COLLECT", source="test", decision="ALLOW", msg="文件导出")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=tempfile.gettempdir()
        ) as f:
            path = f.name

        try:
            result = AuditExport().export_trace(tid, path=path)
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["trace_id"] == tid
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestLoggerBackwardCompatibility:
    """audit/logger.py search() 兼容性测试。"""

    def test_old_search_signature(self):
        """旧调用方式（仅 subject_id/decision/reason_code/limit）兼容。"""
        log(trace_id="compat-trace", subject_id="兼容测试企业",
            action="COMPAT", source="test", decision="ALLOW", msg="兼容性测试")
        # 旧方式调用
        results = search(subject_id="兼容测试企业", limit=10)
        assert len(results) > 0

    def test_new_search_with_time_range(self):
        """新参数（start_ts/end_ts）可用。"""
        log(trace_id="time-trace", subject_id="时间范围测试",
            action="TIME", source="test", decision="ALLOW", msg="时间测试")
        # 用很早的起始时间确保能查到
        results = search(enterprise="时间范围测试", start_ts="2000-01-01")
        assert len(results) > 0

    def test_log_chain(self):
        """log_chain() 全链路日志辅助函数。"""
        log_chain(
            trace_id="chain-trace",
            action="CHAIN_TEST",
            source="test-module",
            msg="链路日志测试",
            subject_id="链路企业",
        )
        results = search(trace_id="chain-trace")
        assert len(results) > 0
        assert results[0]["action"] == "CHAIN_TEST"
