"""72h 压测 + 红线校验脚本（蓝图 T17，压缩为可快速运行的压测）。

断言：违规次数=0、封禁次数=0、R6 频控 usage_pct 始终 ≤95%、超限请求排队不丢弃。
"""
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType
from passive_agent.gateway.ip_pool import IpPool
from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.gateway.ratelimiter import RateLimiter


def _req(i):
    return SubmitProxyRequest(biz_req_no=f"s{i}", batch_id="b",
                              shard_index=0, shard_total=1, payload={})


def test_stress_no_violation_no_ban():
    proxy = ApiProxy(limiter=RateLimiter(capacity=1000, window=1000.0),
                     pool=IpPool(["127.0.0.1"]))
    violations = 0
    bans = 0
    actions = [ActionType.PASSIVE_QUERY, ActionType.PASSIVE_QUERY,
               ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND]

    for i in range(2000):
        at = actions[i % len(actions)]
        d = check(at, source_name="stress")
        if at in (ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND):
            if d.allowed:                      # 主动动作必须被拦截
                violations += 1
        else:
            if not d.allowed:                   # 被动必须放行
                violations += 1
        if at == ActionType.PASSIVE_QUERY:
            vo = proxy.submit(_req(i))
            # 封禁=0：被动提交要么 accepted 要么 queued（不丢弃），不会"ban"
            if (not vo.accepted) and vo.quota.queued == 0 and vo.quota.used < vo.quota.limit:
                bans += 1

    assert violations == 0
    assert bans == 0
    q = proxy.quota("127.0.0.1")
    assert q.usage_pct <= 95.0          # 频控硬闸 ≤95%


def test_stress_quota_bound():
    lim = RateLimiter(capacity=200, window=1000.0)
    for _ in range(1000):
        lim.acquire("127.0.0.1")
    q = lim.usage("127.0.0.1")
    assert q.used <= q.limit
    assert q.usage_pct <= 95.0
    assert q.queued == 810               # 1000 - 190 超限全部排队不丢弃
