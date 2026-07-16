"""R6 频控硬闸 ≤95% / 分片 / 排队 / 日志。"""
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType
from passive_agent.gateway.ip_pool import IpPool
from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.gateway.ratelimiter import RateLimiter


def _req(i):
    return SubmitProxyRequest(biz_req_no=f"r{i}", batch_id="b",
                              shard_index=0, shard_total=1, payload={})


def test_r1_blocks_active():
    d = check(ActionType.ACTIVE_SCAN, source_name="t")
    assert d.allowed is False and d.reason_code == "010001"


def test_passive_allowed():
    d = check(ActionType.PASSIVE_QUERY, source_name="gateway-proxy")
    assert d.allowed is True


def test_ratelimit_hard_cap():
    lim = RateLimiter(capacity=100, window=1000.0)  # 大窗口避免过期
    ip = "127.0.0.1"
    accepted = 0
    for _ in range(200):
        if lim.acquire(ip):
            accepted += 1
    q = lim.usage(ip)
    assert accepted == 95                  # limit = ceil(100*0.95) = 95
    assert q.used == 95
    assert q.limit == 95
    assert q.usage_pct <= 95.0          # 硬上限 95%
    assert q.queued == 105                 # 超限排队不丢弃


def test_proxy_submit_queue():
    proxy = ApiProxy(limiter=RateLimiter(capacity=100, window=1000.0),
                     pool=IpPool(["127.0.0.1"]))
    vo = proxy.submit(_req(0))
    assert vo.accepted is True
    for i in range(1, 200):
        proxy.submit(_req(i))
    q = proxy.quota("127.0.0.1")
    assert q.used <= q.limit
    assert q.usage_pct <= 95.0


def test_ip_pool_rotation():
    pool = IpPool(["10.0.0.1", "10.0.0.2"])
    seen = {pool.next(), pool.next(), pool.next()}
    assert "10.0.0.1" in seen and "10.0.0.2" in seen
    assert pool.size() == 2
