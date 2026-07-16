"""R6 分片提交 + 限流队列 + 结构化日志（蓝图 T09）。

ApiProxy.submit 流程：
  1) R1 关隘：出站前必须 PASSIVE_QUERY 放行（fail-closed）；
  2) 多出口 IP 轮询；
  3) 频控硬闸：≤95% 使用率，超限请求排队不丢弃；
  4) 每条请求产出全链路结构化日志（request_id / src_ip / timestamp / 频控计数）。
赛事 API 字段遵循官方规范（本战役 mock 端点）。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from passive_agent.common import logging as glog
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType
from passive_agent.common.result import gen_trace_id, now_iso
from passive_agent.gateway.ip_pool import IpPool
from passive_agent.gateway.model import SubmitProxyRequest, SubmitProxyVO
from passive_agent.gateway.ratelimiter import RateLimiter, get_rate_limiter

_logger = glog.get_logger("gateway-proxy")


class ApiProxy:
    def __init__(self, limiter: RateLimiter | None = None,
                 pool: IpPool | None = None) -> None:
        self.limiter = limiter or get_rate_limiter()
        self.pool = pool or IpPool()
        self._lock = threading.Lock()

    def submit(self, req: SubmitProxyRequest) -> SubmitProxyVO:
        trace_id = gen_trace_id()

        # 1) R1 关隘：出站前必须 PASSIVE_QUERY 放行
        decision = check(ActionType.PASSIVE_QUERY, source_name="gateway-proxy")
        if not decision.allowed:
            _logger.error(f"R1 拦截提交 biz_req_no={req.biz_req_no} {decision.reason_code}")
            self._audit(trace_id, "", "SUBMIT", "BLOCK", decision.reason_code,
                        f"R1 拦截出站提交 biz_req_no={req.biz_req_no}")
            return SubmitProxyVO(request_id=req.biz_req_no, src_ip="", timestamp=now_iso(),
                                 accepted=False, quota=self.quota("127.0.0.1"))

        # 2) 多出口 IP 轮询
        src_ip = self.pool.next()

        # 3) 频控硬闸：超限排队不丢弃
        acquired = self.limiter.acquire(src_ip)
        if not acquired:
            quota = self.quota(src_ip)
            self._audit(trace_id, src_ip, "SUBMIT", "BLOCK", "010002",
                        f"频控满排队 biz_req_no={req.biz_req_no} "
                        f"shard={req.shard_index + 1}/{req.shard_total}")
            return SubmitProxyVO(request_id=req.biz_req_no, src_ip=src_ip, timestamp=now_iso(),
                                 accepted=False, quota=quota)

        # 4) 接受：写结构化日志
        quota = self.quota(src_ip)
        self._audit(trace_id, src_ip, "SUBMIT", "ALLOW", "000000",
                    f"分片提交 shard={req.shard_index + 1}/{req.shard_total} batch={req.batch_id}")
        # 注意：此处「接受」仅代表网关频控槽位已占用（acquire），
        # 不立即 release——槽位须由编排层在分片真正出站完成后调用
        # proxy.release(vo.src_ip) 释放，方能形成真实背压（排队不丢弃）。
        return SubmitProxyVO(request_id=req.biz_req_no, src_ip=src_ip, timestamp=now_iso(),
                             accepted=True, quota=quota)

    def release(self, src_ip: str) -> None:
        """释放指定源 IP 的频控槽位（委托 RateLimiter.release）。"""
        self.limiter.release(src_ip)

    def quota(self, ip: str) -> "Quota":
        return self.limiter.usage(ip)

    def _audit(self, trace_id: str, src_ip: str, action: str, decision: str,
                reason_code: str, msg: str) -> None:
        try:
            from passive_agent import audit

            audit.log(trace_id=trace_id, subject_id=src_ip, action=action,
                      source="gateway-proxy", decision=decision, reason_code=reason_code, msg=msg)
        except Exception:
            pass
