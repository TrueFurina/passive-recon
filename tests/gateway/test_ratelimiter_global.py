"""T-P1 频控全局化：跨 worker 全局限流验证。

覆盖两类路径：
1) 回退路径：无 Redis（未配 URL / redis 库缺失）→ get_rate_limiter() 返回进程内
   RateLimiter 单例；已配 Redis 但 FAIL_FAST 时启动即失败。
2) Redis 集中式路径：多 RedisRateLimiter 实例（模拟多 worker）共享同一后端，
   全局聚合容量不被突破（≤95% 硬闸），release 真实释放槽位。

Redis 路径采用 WATCH + MULTI/EXEC 乐观锁事务（非 Lua，兼容 fakeredis / 真实 Redis）。
离线测试用进程内内存实现 `_MemoryRedis`（redis-py 兼容子集），无需网络；
若环境装有 fakeredis 亦可无缝替换为真实事务执行（test_redis_global_capacity_via_real_lua）。
"""
from __future__ import annotations

import bisect

import pytest

import passive_agent.gateway.ratelimiter as rl_mod
from passive_agent.gateway.ratelimiter import (
    RateLimiter,
    RedisRateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
)


# ---------------------------------------------------------------------------
# 进程内内存 Redis（redis-py 兼容子集，覆盖 RedisRateLimiter 用到的命令）。
# 仅实现单线程共享状态所需语义：zset/hash/incr + watch/multi/exec 事务骨架。
# 单线程测试无真实并发，watch 不触发 WatchError，事务所缓冲命令在 execute 一次性生效。
# ---------------------------------------------------------------------------
class _MemoryRedis:
    def __init__(self) -> None:
        self._zsets: dict[str, list] = {}
        self._hashes: dict[str, dict] = {}
        self._incrs: dict[str, int] = {}
        self._watching: set = set()

    # —— 事务骨架（乐观锁，单线程下等价于串行执行）——
    def watch(self, *keys) -> bool:
        self._watching.update(keys)
        return True

    def unwatch(self) -> bool:
        self._watching.clear()
        return True

    # —— ZSET（时间戳滑动窗口）——
    def zremrangebyscore(self, key, min_, max_) -> int:
        zs = self._zsets.setdefault(key, [])
        lo = float("-inf") if min_ == "-inf" else float(min_)
        hi = float(max_)
        before = len(zs)
        self._zsets[key] = [(s, m) for (s, m) in zs if not (lo <= s <= hi)]
        return before - len(self._zsets[key])

    def zcard(self, key) -> int:
        return len(self._zsets.get(key, []))

    def zadd(self, key, mapping) -> int:
        zs = self._zsets.setdefault(key, [])
        for member, score in mapping.items():
            bisect.insort(zs, (float(score), member))
        return len(mapping)

    def zpopmin(self, key, count: int = 1) -> list:
        zs = self._zsets.get(key, [])
        popped = []
        for _ in range(min(count, len(zs))):
            popped.append(zs.pop(0))
        return popped

    # —— 计数 / 序列 / 排队 HASH ——
    def incr(self, key) -> int:
        self._incrs[key] = self._incrs.get(key, 0) + 1
        return self._incrs[key]

    def hincrby(self, key, field, amount) -> int:
        h = self._hashes.setdefault(key, {})
        h[field] = h.get(field, 0) + amount
        return h[field]

    def hget(self, key, field):
        return self._hashes.get(key, {}).get(field, 0)

    def pexpire(self, key, ms) -> bool:
        return True

    # —— 事务管道 ——
    def pipeline(self, transaction: bool = False):
        return _Pipe(self)


class _Pipe:
    def __init__(self, owner: "_MemoryRedis") -> None:
        self._owner = owner
        self._buf: list = []
        self._in_multi = False
        self._watching = False

    # —— 事务控制 ——
    def watch(self, *keys) -> bool:
        self._owner.watch(*keys)
        self._watching = True
        return True

    def unwatch(self) -> bool:
        self._owner.unwatch()
        self._watching = False
        return True

    def reset(self) -> None:
        self._buf = []
        self._in_multi = False
        self._watching = False
        try:
            self._owner.unwatch()
        except Exception:
            pass

    # —— immediate-mode 读（watch 后、multi 前立即执行，返回真实结果）——
    def zcard(self, key) -> int:
        return self._owner.zcard(key)

    def hget(self, key, field):
        return self._owner.hget(key, field)

    def incr(self, key) -> int:
        return self._owner.incr(key)

    # —— 事务内写（multi 后缓冲，execute 一次性生效）——
    def multi(self):
        self._in_multi = True
        return self

    def zremrangebyscore(self, key, min_, max_) -> int:
        # 与真实 RedisRateLimiter 一致：清理过期在 MULTI 内执行，故此处缓冲
        self._buf.append(("zremrangebyscore", key, min_, max_))
        return 0

    def zadd(self, key, mapping):
        self._buf.append(("zadd", key, mapping))
        return self

    def pexpire(self, key, ms):
        self._buf.append(("pexpire", key, ms))
        return self

    def hincrby(self, key, field, amount):
        self._buf.append(("hincrby", key, field, amount))
        return self

    def zpopmin(self, key, count: int = 1):
        self._buf.append(("zpopmin", key, count))
        return self

    def execute(self):
        results = []
        for cmd in self._buf:
            if cmd[0] == "zadd":
                results.append(self._owner.zadd(cmd[1], cmd[2]))
            elif cmd[0] == "pexpire":
                results.append(self._owner.pexpire(cmd[1], cmd[2]))
            elif cmd[0] == "zremrangebyscore":
                results.append(self._owner.zremrangebyscore(cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == "hincrby":
                results.append(self._owner.hincrby(cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == "zpopmin":
                results.append(self._owner.zpopmin(cmd[1], cmd[2]))
        self._buf = []
        self._in_multi = False
        return results


# ---------------------------------------------------------------------------
# 回退路径
# ---------------------------------------------------------------------------
@pytest.fixture
def reset_singleton():
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def _fakeredis_available() -> bool:
    """fakeredis 是否可用且支持 WATCH + MULTI/EXEC（RedisRateLimiter 依赖的事务原语）。

    部分精简版 fakeredis 未实现事务命令，此时真实事务路径无法离线执行；
    跨 worker 全局逻辑改由 _MemoryRedis 内存 mock 覆盖，本测试自动跳过。
    """
    try:
        import fakeredis
    except Exception:
        return False
    try:
        c = fakeredis.FakeStrictRedis()
        c.set("__probe__", 1)
        c.watch("__probe__")
        p = c.pipeline(transaction=False)
        p.multi()
        p.incr("__probe__")
        p.execute()
        c.unwatch()
        return True
    except Exception:
        return False


def test_fallback_no_redis_url_returns_inprocess(reset_singleton, monkeypatch):
    """未配置 RATE_REDIS_URL → 进程内 RateLimiter 单例。"""
    monkeypatch.setattr(rl_mod.settings, "RATE_REDIS_URL", "")
    monkeypatch.setattr(rl_mod.settings, "SINGLE_WORKER_MODE", True)
    lim = get_rate_limiter()
    assert isinstance(lim, RateLimiter)
    # 基本频控语义仍生效
    assert lim.acquire("9.9.9.9") is True


def test_fallback_when_redis_unavailable(reset_singleton, monkeypatch):
    """已配 URL 但 Redis 不可达（_try_connect_redis 返回 None）→ 回退进程内单例。"""
    monkeypatch.setattr(rl_mod.settings, "RATE_REDIS_URL", "redis://unreachable:6379")
    monkeypatch.setattr(rl_mod.settings, "RATE_REDIS_FAIL_FAST", False)
    monkeypatch.setattr(rl_mod, "_try_connect_redis", lambda url: None)
    lim = get_rate_limiter()
    assert isinstance(lim, RateLimiter)


def test_fail_fast_when_redis_unavailable(reset_singleton, monkeypatch):
    """已配 URL + RATE_REDIS_FAIL_FAST=True 且不可达 → 启动即失败。"""
    monkeypatch.setattr(rl_mod.settings, "RATE_REDIS_URL", "redis://unreachable:6379")
    monkeypatch.setattr(rl_mod.settings, "RATE_REDIS_FAIL_FAST", True)
    monkeypatch.setattr(rl_mod, "_try_connect_redis", lambda url: None)
    with pytest.raises(RuntimeError):
        get_rate_limiter()


# ---------------------------------------------------------------------------
# Redis 集中式路径（多 worker 共享）
# ---------------------------------------------------------------------------
def _shared_backend() -> _MemoryRedis:
    return _MemoryRedis()


def test_redis_global_capacity_not_exceeded_across_instances():
    """两个 limiter 实例（模拟两个 worker）共享同一 Redis → 全局容量守住 ≤95%。

    capacity=100 → limit=floor(100*0.95)=95。向两实例各灌 150 次（共 300），
    全局接受数必须恰为 95，其余排队，绝不突破。
    """
    backend = _shared_backend()
    lim1 = RedisRateLimiter(backend, capacity=100, window=1e9)  # 大窗口避免过期
    lim2 = RedisRateLimiter(backend, capacity=100, window=1e9)
    ip = "10.0.0.5"
    accepted = 0
    for _ in range(150):
        if lim1.acquire(ip):
            accepted += 1
        if lim2.acquire(ip):
            accepted += 1
    # 全局接受数
    assert accepted == 95, f"跨实例全局接受数应=95，实际={accepted}"
    # 任意单实例看到的 used 即全局 used
    assert lim1.usage(ip).used == 95
    assert lim2.usage(ip).used == 95
    # 超限全部排队不丢弃
    assert lim1.usage(ip).queued == 205


def test_redis_release_frees_global_slot():
    """release 真实释放槽位，使全局可用额度回升，可再次接受。"""
    backend = _shared_backend()
    lim = RedisRateLimiter(backend, capacity=10, window=1e9)  # limit=floor(10*.95)=9
    ip = "10.0.0.6"
    for _ in range(9):
        assert lim.acquire(ip) is True
    assert lim.acquire(ip) is False  # 第 10 个排队
    assert lim.usage(ip).used == 9
    assert lim.usage(ip).queued == 1
    lim.release(ip)
    assert lim.usage(ip).used == 8
    assert lim.usage(ip).queued == 0
    assert lim.acquire(ip) is True   # 槽位回升后可再接受
    assert lim.usage(ip).used == 9


def test_redis_usage_quota_fields():
    """usage 返回正确的 used/limit/usage_pct/queued。"""
    backend = _shared_backend()
    lim = RedisRateLimiter(backend, capacity=100, window=1e9)
    ip = "10.0.0.7"
    for _ in range(50):
        assert lim.acquire(ip) is True
    q = lim.usage(ip)
    assert q.used == 50
    assert q.limit == 95
    assert q.usage_pct == 50.0
    assert q.queued == 0


def test_redis_persist_does_not_raise_on_missing_db():
    """acquire 触发 _persist（SQLite），DB 未初始化时应静默容错，不抛异常。"""
    backend = _shared_backend()
    lim = RedisRateLimiter(backend, capacity=100, window=1e9)
    # 不初始化 db；acquire 内部 _persist 走 try/except，应安全返回
    assert lim.acquire("10.0.0.8") is True


@pytest.mark.skipif(
    not _fakeredis_available(),
    reason="fakeredis 不可用或不支持事务原语，Redis 事务路径改由内存 mock 覆盖",
)
def test_redis_global_capacity_via_real_lua():
    """用真实 fakeredis 执行 WATCH+MULTI 事务，验证跨实例全局硬闸（生产 Redis 等价）。"""
    import fakeredis

    client = fakeredis.FakeStrictRedis()
    lim1 = RedisRateLimiter(client, capacity=100, window=1e9)
    lim2 = RedisRateLimiter(client, capacity=100, window=1e9)  # 共享同一后端（多 worker）
    ip = "10.0.0.9"
    accepted = 0
    for _ in range(150):
        if lim1.acquire(ip):
            accepted += 1
        if lim2.acquire(ip):
            accepted += 1
    assert accepted == 95, f"fakeredis 路径全局接受数应=95，实际={accepted}"
    assert lim1.usage(ip).used == 95
    assert lim1.usage(ip).queued == 205
    # release 真实释放（事务 ZPOPMIN + HINCRBY）
    lim1.release(ip)
    assert lim1.usage(ip).used == 94
    assert lim1.usage(ip).queued == 204
