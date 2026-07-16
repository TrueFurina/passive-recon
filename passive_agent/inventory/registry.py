"""R5 台账登记 / 查询 / 导出 / 自研占比证明（一键出具）。蓝图 T05。

预置本战役开源依赖与自研保命模块内核；export_proof() 按 R 模块统计自研占比。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import List

from passive_agent.common import logging as ilog
from passive_agent.inventory.model import InventoryExport, OssTool

_logger = ilog.get_logger("inventory")


class InventoryRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tools: List[OssTool] = []
        self._seeded = False

    def register(self, tool: OssTool) -> None:
        with self._lock:
            self._tools.append(tool)

    def seed_defaults(self) -> None:
        """预置本战役台账（开源依赖 + 自研保命内核）。幂等。"""
        with self._lock:
            if self._seeded:
                return
            defaults = [
                # —— 开源第三方依赖 ——
                OssTool(name="fastapi", version="0.111.0", license="MIT",
                        purpose="R4 面板 API / R6 代理网关 API", call_boundary="仅被动 Web 框架",
                        boundary_tag="开源", module_ref="R4/R6"),
                OssTool(name="uvicorn", version="0.30.0", license="BSD",
                        purpose="ASGI 服务器", call_boundary="仅本地服务",
                        boundary_tag="开源", module_ref="R4/R6"),
                OssTool(name="pydantic", version="2.7.0", license="MIT",
                        purpose="数据模型校验", call_boundary="内存校验，无出站",
                        boundary_tag="开源", module_ref="通用"),
                OssTool(name="pydantic-settings", version="2.3.0", license="MIT",
                        purpose="配置加载", call_boundary="内存加载，无出站",
                        boundary_tag="开源", module_ref="通用"),
                OssTool(name="dnspython", version="2.6.0", license="ISC",
                        purpose="R2 L2 DNS 仅解析", call_boundary="仅 resolver.resolve，绝不连接解析IP",
                        boundary_tag="开源", module_ref="R2"),
                OssTool(name="httpx", version="0.27.0", license="BSD",
                        purpose="被动 API 出站", call_boundary="仅白名单被动源，出站前经 R1",
                        boundary_tag="开源", module_ref="R3/R6"),
                OssTool(name="pytest", version="8.2.0", license="MIT",
                        purpose="测试", call_boundary="本地执行，无出站",
                        boundary_tag="开源", module_ref="通用"),
                # —— 自研保命模块内核（边界自研，标 100% 自研）——
                OssTool(name="compliance-engine", version="1.0.0", license="自研",
                        purpose="R1 全局合规拦截", call_boundary="fail-closed 拦截主动动作",
                        boundary_tag="自研", module_ref="R1"),
                OssTool(name="verifier-pipeline", version="1.0.0", license="自研",
                        purpose="R2 四层情报校验", call_boundary="纯函数校验，无出站",
                        boundary_tag="自研", module_ref="R2"),
                OssTool(name="subject-enumerator", version="1.0.0", license="自研",
                        purpose="R3 全主体枚举", call_boundary="经 ACL 被动查询",
                        boundary_tag="自研", module_ref="R3"),
                OssTool(name="api-proxy", version="1.0.0", license="自研",
                        purpose="R6 赛事网关代理", call_boundary="分片+频控+轮询",
                        boundary_tag="自研", module_ref="R6"),
                OssTool(name="approval-service", version="1.0.0", license="自研",
                        purpose="R4 三级审批+续跑", call_boundary="内部状态机",
                        boundary_tag="自研", module_ref="R4"),
                OssTool(name="inventory-registry", version="1.0.0", license="自研",
                        purpose="R5 开源台账", call_boundary="本地台账",
                        boundary_tag="自研", module_ref="R5"),
            ]
            self._tools.extend(defaults)
            self._seeded = True
            _logger.info(f"预置台账完成：{len(defaults)} 项")

    def all(self) -> List[OssTool]:
        with self._lock:
            if not self._seeded:
                self.seed_defaults()
            return list(self._tools)

    def export_json(self, path: str) -> None:
        from passive_agent.storage import jsonio

        tools = self.all()
        jsonio.write_json(path, [t.model_dump() for t in tools])

    def export_proof(self) -> InventoryExport:
        """一键出具自研占比证明（按 R 模块统计口径）。"""
        tools = self.all()
        total = len(tools)
        self_dev = [t for t in tools if t.boundary_tag == "自研"]
        oss = [t for t in tools if t.boundary_tag != "自研"]
        self_dev_pct = round(len(self_dev) / total * 100, 2) if total else 0.0
        oss_pct = round(len(oss) / total * 100, 2) if total else 0.0
        proof = InventoryExport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tools=tools,
            ratio={
                "open_source_pct": oss_pct,
                "self_dev_pct": self_dev_pct,
                "self_dev_modules": [t.name for t in self_dev],
            },
        )
        return proof
