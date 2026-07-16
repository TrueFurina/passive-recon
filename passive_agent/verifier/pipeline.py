"""R2 四层情报自动校验流水线（蓝图 T07）。

四层各自可独立开关 + 计数：
  L1 工商主体匹配（剔除非目标）
  L2 DNS 仅解析存活（dnspython，严禁 socket 连接解析 IP）
  L3 时间过滤（>1 年过期情报拦截）
  L4 多源交叉（≥2 源入库，单源 SUSPEND，060001）
输出 VerifyResult（层序 + 通过/拦截 + 依据），落 t_verify_result。
"""
from __future__ import annotations

import threading
from typing import List

from passive_agent.common import logging as plog
from passive_agent.common.enums import VerifyStatus
from passive_agent.storage import db
from passive_agent.verifier.layers import dns_alive
from passive_agent.verifier.model import LayerResult, VerifyRequest, VerifyResult

_logger = plog.get_logger("verifier")


class VerificationPipeline:
    LAYER_NAMES = {
        1: "工商主体匹配",
        2: "DNS被动存活",
        3: "时间过滤(≤1年)",
        4: "多源交叉佐证",
    }

    def __init__(self) -> None:
        self._enabled = {1: True, 2: True, 3: True, 4: True}
        self._counters = {1: 0, 2: 0, 3: 0, 4: 0}
        self._lock = threading.Lock()

    def set_layer_enabled(self, layer: int, enabled: bool) -> None:
        with self._lock:
            if layer in self._enabled:
                self._enabled[layer] = enabled

    def counters(self) -> dict:
        with self._lock:
            return dict(self._counters)

    def run(self, req: VerifyRequest) -> VerifyResult:
        layers: List[LayerResult] = []
        fail_layer: Optional[int] = None
        fail_reason = ""

        with self._lock:
            enabled = dict(self._enabled)

        # L1 工商主体匹配
        if enabled.get(1, True):
            self._counters[1] += 1
            passed = bool(req.layer1_biz_match)
            if not passed and fail_layer is None:
                fail_layer = 1
                fail_reason = "层1 未匹配目标工商主体"
            layers.append(LayerResult(layer=1, name=self.LAYER_NAMES[1], enabled=True,
                                   passed=passed, count=self._counters[1],
                                   basis="目标企业工商主体一致性校验"))

        # L2 DNS 仅解析存活（不访问）
        if enabled.get(2, True):
            self._counters[2] += 1
            passed = bool(req.layer2_dns_alive)
            if not passed and fail_layer is None:
                fail_layer = 2
                fail_reason = "层2 DNS 存活校验未通过"
            layers.append(LayerResult(layer=2, name=self.LAYER_NAMES[2], enabled=True,
                                   passed=passed, count=self._counters[2],
                                   basis="dnspython 仅解析(无主动连接)"))

        # L3 时间过滤 ≤1 年
        if enabled.get(3, True):
            self._counters[3] += 1
            passed = bool(req.layer3_time_ok)
            if not passed and fail_layer is None:
                fail_layer = 3
                fail_reason = "层3 情报超过 1 年有效期"
            layers.append(LayerResult(layer=3, name=self.LAYER_NAMES[3], enabled=True,
                                   passed=passed, count=self._counters[3],
                                   basis="情报时效性过滤"))

        # L4 多源交叉（≥2 源入库，单源挂起）
        if enabled.get(4, True):
            self._counters[4] += 1
            passed = req.layer4_src_cnt >= 2
            if not passed and fail_layer is None:
                fail_layer = 4
                fail_reason = "层4 单一来源，需补充佐证"
            layers.append(LayerResult(layer=4, name=self.LAYER_NAMES[4], enabled=True,
                                   passed=passed, count=self._counters[4],
                                   basis=f"多源佐证方数={req.layer4_src_cnt}"))

        status = VerifyStatus.PASS if fail_layer is None else VerifyStatus.SUSPEND
        basis = "四层校验全部通过" if fail_layer is None else fail_reason
        reason_code = "000000" if fail_layer is None else ("060001" if fail_layer == 4 else "050001")

        result = VerifyResult(
            result_id=req.result_id,
            status=status,
            layers=layers,
            fail_layer=fail_layer,
            basis=basis,
        )
        try:
            db.write(
                "INSERT INTO t_verify_result (result_id, status, fail_layer, basis) VALUES (?,?,?,?)",
                (result.result_id, result.status.value, result.fail_layer, result.basis),
            )
        except Exception as exc:
            _logger.error(f"核验结果落库失败: {exc}")
        return result
