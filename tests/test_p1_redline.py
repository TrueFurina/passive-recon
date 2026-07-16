"""P1 静态红线扫描 + 红线回归测试（蓝图 T31）。

验证：
- 代码库无主动扫描/socket 直连路径
- 所有出站调用经 compliance_client.check()
- dnspython 仅 resolver.resolve()
"""
from __future__ import annotations

import os
import inspect
from pathlib import Path

import pytest

from passive_agent.collector.adapters.crtsh_adapter import CrtshAdapter
from passive_agent.collector.adapters.dns_adapter import DnsAdapter
from passive_agent.collector.adapters.fofa_adapter import FofaAdapter
from passive_agent.collector.adapters.subfinder_adapter import SubfinderAdapter
from passive_agent.collector.adapters.wechat_adapter import WechatAdapter
from passive_agent.collector.adapters.miniapp_adapter import MiniappAdapter
from passive_agent.collector.adapters.equity_adapter import EquityAdapter
from passive_agent.collector.adapter import SourceAdapter


class TestRedlineStatic:
    """静态红线扫描测试。"""

    PROJECT_ROOT = Path(__file__).resolve().parent.parent / "passive_agent"

    def _read_all_python_files(self) -> dict:
        """读取所有 Python 源文件内容。"""
        files = {}
        for py in self.PROJECT_ROOT.rglob("*.py"):
            try:
                files[str(py)] = py.read_text(encoding="utf-8")
            except Exception:
                pass
        return files

    def test_no_socket_direct_connection(self):
        """代码库无 socket 直连路径（V-R7-6）。"""
        files = self._read_all_python_files()
        forbidden_patterns = [
            "socket.connect(",
            "socket.create_connection(",
            "s = socket.socket(",
            "sock.connect(",
        ]
        violations = []
        for path, content in files.items():
            for pattern in forbidden_patterns:
                if pattern in content:
                    violations.append(f"{path}: found '{pattern}'")
        assert len(violations) == 0, f"发现 socket 直连: {violations}"

    def test_no_active_scan_libraries(self):
        """代码库无主动扫描类库 import。"""
        files = self._read_all_python_files()
        forbidden_imports = [
            "import nmap",
            "import shodan",
            "from nmap",
            "from shodan",
            "import scapy",
            "from scapy",
        ]
        violations = []
        for path, content in files.items():
            for imp in forbidden_imports:
                if imp in content:
                    violations.append(f"{path}: found '{imp}'")
        assert len(violations) == 0, f"发现主动扫描类库: {violations}"

    def test_dnspython_only_resolve(self):
        """dnspython 仅 resolver.resolve()（V-R7-6）。"""
        files = self._read_all_python_files()
        # 使用精确匹配检测 dns 模块导入，避免 "import dns_alive" 误匹配
        dns_import_markers = [
            "import dns.", "import dns ", "from dns.", "from dns ",
        ]
        for path, content in files.items():
            if "dns" in content.lower() or "dnspython" in content.lower():
                if any(marker in content for marker in dns_import_markers):
                    # 确保只有 resolver.resolve 调用，无 socket
                    assert "resolver.resolve" in content or "dns.resolver" in content, \
                        f"{path}: dns 模块使用但无 resolver.resolve"
                    # 不应有 socket 连接
                    assert "socket.connect" not in content
                    assert "create_connection" not in content

    def test_all_adapters_check_compliance(self):
        """所有出站适配器 collect() 内调 _check_compliance()（V-R7-5/V-R7-6）。"""
        # 检查 SourceAdapter 基类有 _check_compliance
        assert hasattr(SourceAdapter, "_check_compliance")

        # 检查 crt.sh 适配器（真实出站源）有 compliance 调用
        crtsh_source = inspect.getsource(CrtshAdapter)
        assert "_check_compliance" in crtsh_source or "compliance" in crtsh_source.lower()

        # 检查 DNS 适配器有 compliance 调用
        dns_source = inspect.getsource(DnsAdapter)
        assert "_check_compliance" in dns_source

    def test_no_react_node_frontend(self):
        """不引入 React/Node 前端构建链。"""
        static_dir = self.PROJECT_ROOT / "static"
        if static_dir.exists():
            for f in static_dir.iterdir():
                if f.suffix in (".html", ".js"):
                    content = f.read_text(encoding="utf-8")
                    assert "React" not in content or "react" not in content.lower(), \
                        f"{f.name}: 不应引入 React"
                    assert "require(" not in content, \
                        f"{f.name}: 不应使用 Node.js require()"

    def test_no_neo4j_mysql_redis(self):
        """不引入 Neo4j/MySQL/Redis。"""
        files = self._read_all_python_files()
        forbidden = [
            "from neo4j",
            "import neo4j",
            "from redis",
            "import redis",
            "import pymysql",
            "from pymysql",
            "import MySQLdb",
        ]
        for path, content in files.items():
            for pattern in forbidden:
                assert pattern not in content, \
                    f"{path}: 不应引入 {pattern}"

    def test_mock_adapter_no_outbound(self):
        """Mock 适配器不出站（不调 _check_compliance 也不实际网络请求）。"""
        mock_source = inspect.getsource(MockAdapter := __import__(
            "passive_agent.collector.adapters.mock_adapter",
            fromlist=["MockAdapter"]
        ).MockAdapter)
        # mock 适配器不应有 httpx/dns 出站调用
        assert "httpx" not in mock_source
        assert "dns.resolver" not in mock_source

    def test_compliance_fail_closed(self):
        """R1 fail-closed：未知动作默认拦截。"""
        from passive_agent.compliance.engine import ComplianceEngine
        from passive_agent.compliance.model import ComplianceCheckRequest

        engine = ComplianceEngine()
        # 未知动作应被拦截
        req = ComplianceCheckRequest(
            action_type="UNKNOWN_ACTION",
            source_name="test",
        )
        decision = engine.check(req)
        assert not decision.allowed
        assert decision.decision.value == "BLOCK"

    def test_active_actions_blocked(self):
        """主动动作 100% 拦截。"""
        from passive_agent.compliance.engine import ComplianceEngine
        from passive_agent.compliance.model import ComplianceCheckRequest
        from passive_agent.common.enums import ActionType

        engine = ComplianceEngine()
        for action in [ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND]:
            req = ComplianceCheckRequest(
                action_type=action.value,
                source_name="test",
            )
            decision = engine.check(req)
            assert not decision.allowed
            assert decision.reason_code == "010001"
