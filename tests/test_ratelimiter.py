"""频控全局化回归测试（生产级加固项 #5）。

- 进程内单例：单 worker 内所有使用者共享同一频控状态（全局硬闸基础）。
- 容量硬闸：聚合吞吐受 floor(capacity*buffer) 约束，超限排队不丢弃。
- Redis 集中式：多 RedisRateLimiter 共享同一 backend，跨 worker 聚合仍受 ≤95% 硬闸。
"""
import pytest

from passive_agent.gateway import ratelimiter as rl


def test_inprocess_singleton_is_shared():
    """同一进程内 get_rate_limiter() 必须返回同一对象——这是单 worker 全局硬闸的前提。"""
    rl.reset_rate_limiter()
    a = rl.get_rate_limiter()
    b = rl.get_rate_limiter()
    assert a is b
    assert isinstance(a, rl.RateLimiter)


def test_inprocess_capacity_hard_cap_and_queue():
    """连续 acquire 超过 limit 必须排队（False），release 后恢复。"""
    rl.reset_rate_limiter()
    lim = rl.get_rate_limiter()
    ip = "10.0.0.1"
    limit = lim._limit()

    accepted = sum(1 for _ in range(limit) if lim.acquire(ip))
    assert accepted == limit, "前 limit 次应全部放行"

    # 第 limit+1 次应进入排队（False），而非突破硬闸
    assert lim.acquire(ip) is False

    # 释放一个配额后应可再次 acquire
    lim.release(ip)
    assert lim.acquire(ip) is True

    # 清理，避免污染后续测试
    for _ in range(limit + 1):
        lim.release(ip)


@pytest.mark.parametrize("window", [30.0, 1.0], ids=["enlarged_window", "prod_window_1s"])
def test_redis_shared_backend_enforces_global_cap(window):
    """两个 RedisRateLimiter 实例共享同一 backend 时，硬闸在**任意时刻**都不得突破 limit（≤95%）。

    时序无关不变量（真正安防属性，采纳安全官建议）：无论窗口大小、fakeredis 快慢，
    逐步断言 `used <= limit`——证明「窗口内并发用量永不超过 limit」，而非仅在末尾断言
    total_accept==limit（后者隐含「整段突发落入同一窗口」的时序假设，环境慢时失真，
    正是「绿≠正确」陷阱）。

    双窗口联跑（采纳安全官建议，亦对应 QA 跨模块清单要求）：
    - enlarged_window(30s)：整段突发落入同一窗口，等价于原 total_accept==limit 口径；
    - prod_window_1s（生产默认）：滑动窗口下旧条目自然过期使 total 可超 limit（正确行为），
      但「窗口内并发 used 不超 limit」必须成立——由逐步 used<=limit 保证。
    """
    fakeredis = pytest.importorskip("fakeredis")
    rl.reset_rate_limiter()
    client = fakeredis.FakeStrictRedis()
    lim1 = rl.RedisRateLimiter(client, window=window)
    lim2 = rl.RedisRateLimiter(client, window=window)
    ip = "10.0.0.2"
    limit = lim1._limit()

    total_accept = 0
    max_used = 0
    for _ in range(limit * 2):  # 故意请求两倍容量
        if lim1.acquire(ip) or lim2.acquire(ip):
            total_accept += 1
        # 时序无关硬闸不变量：任意时刻窗口内用量不得超过 limit（真正安防属性）
        used = lim1.usage(ip).used
        assert used <= limit, (
            f"硬闸在 window={window} 下被突破：used={used} > limit={limit}"
        )
        max_used = max(max_used, used)
    # 大窗口口径：整段突发落同一窗口，最终累计接受应恰为 limit
    if window >= 30.0:
        assert total_accept == limit, "大窗口下跨实例聚合吞吐应被 ≤95% 硬闸约束"
    # 真实安防属性：峰值用量不得超过 limit
    assert max_used <= limit, f"峰值用量突破 limit：max_used={max_used} > limit={limit}"
