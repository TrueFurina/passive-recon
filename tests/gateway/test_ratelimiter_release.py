"""V-P1-14/15：频控硬上限 ≤95.0% + release 真实消费（used/queued 递减）。

不依赖外部资源；直接驱动 RateLimiter + ApiProxy。
"""
from __future__ import annotations

import pytest

from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.gateway.ratelimiter import RateLimiter


@pytest.mark.parametrize("capacity", [1000, 1003, 1007, 1234])
def test_usage_pct_within_95(capacity: int):
    """任意 capacity（含非 20 倍数）打满后 usage_pct ≤ 95.0%。"""
    rl = RateLimiter(capacity=capacity, window=3600)
    limit = rl._limit()
    for _ in range(limit):
        assert rl.acquire("1.1.1.1") is True
    # 超出 limit 的请求应排队（不丢弃）
    assert rl.acquire("1.1.1.1") is False
    usage = rl.usage("1.1.1.1")
    assert usage.usage_pct <= 95.0, f"capacity={capacity} usage_pct={usage.usage_pct}"
    # release 后 used 递减、queued 归零
    rl.release("1.1.1.1")
    assert rl.usage("1.1.1.1").used == limit - 1
    assert rl.usage("1.1.1.1").queued == 0


def test_submit_acquires_no_immediate_release():
    """submit 接受时占用频控槽位（acquire）但不立即 release——背压由编排层驱动。

    若 submit 内部立即 release，则 used 永远 0↔1 震荡、无法形成排队，
    破坏 R6「限流≤95% + 排队不丢弃」语义。正确契约：编排层在分片真正
    出站完成后调用 proxy.release(vo.src_ip) 才递减。
    """
    rl = RateLimiter(capacity=1000)
    proxy = ApiProxy(limiter=rl)
    calls: list[str] = []
    orig = rl.release

    def _spy(ip: str) -> None:
        calls.append(ip)
        return orig(ip)

    rl.release = _spy  # type: ignore[assignment]
    req = SubmitProxyRequest(
        biz_req_no="x", batch_id="x", shard_index=0, shard_total=1, payload={}
    )
    vo = proxy.submit(req)
    assert vo.accepted is True
    # submit 内部不得调用 release（否则无背压）
    assert len(calls) == 0, "submit 不应立即 release，背压须由编排层在出站完成后驱动"
    # 编排层出站完成后调用 proxy.release(vo.src_ip) → used 递减
    before = rl.usage(vo.src_ip).used
    assert before == 1, "submit 接受后 used 应为 1（已占用槽位）"
    proxy.release(vo.src_ip)
    assert rl.usage(vo.src_ip).used == before - 1


def test_queue_decrement_on_release():
    """排队计数在 release 后真实递减（V-P1-15 消费侧）。"""
    rl = RateLimiter(capacity=10, window=3600)
    for _ in range(rl._limit()):
        assert rl.acquire("2.2.2.2") is True
    # 超出 → 排队
    assert rl.acquire("2.2.2.2") is False
    assert rl.usage("2.2.2.2").queued == 1
    rl.release("2.2.2.2")
    assert rl.usage("2.2.2.2").queued == 0
