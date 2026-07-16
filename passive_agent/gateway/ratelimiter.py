"""R6 单 IP 频控硬闸：limit = floor(capacity * buffer)，超限排队不丢弃（蓝图 T08）。

- 单 IP 使用率硬上限 95%（buffer 默认 0.95，floor 确保任意 capacity ≤ 95.0%）。
- 满则进入排队（计数 +1，不丢弃），容量随滑动窗口释放后自然排空。
- 频控状态落 t_rate_quota（看板数据源）。

跨 worker 全局化（生产级加固项）：
- 默认仍为**进程内单例** `RateLimiter`（`get_rate_limiter` 双检锁）。满足单 worker。
- 当配置 `PASSIVE_RATE_REDIS_URL` 且 `redis` 库可用、可连通时，自动切换为
  `RedisRateLimiter` —— 多 worker 共享同一 Redis 后端，全局滑动窗口保证聚合吞吐
  仍受 ≤95% 硬闸约束（WATCH/MULTI/EXEC 乐观锁事务，杜绝跨 worker 竞态下超额）。
- 未启用 Redis 时显式回到进程内单例，并在启动日志告警「单 worker 假设」。
- 若 `PASSIVE_RATE_REDIS_FAIL_FAST=True` 且已配置 Redis 但不可达 → 启动即失败
  （fail-fast），避免「以为全局、实则单 worker」的静默降级。
"""
from __future__ import annotations

import math
import queue
import threading
import time
import uuid
from collections import deque, defaultdict
from typing import Dict, Optional

from passive_agent.common import logging as rlog
from passive_agent.config import settings
from passive_agent.storage import db

# redis 为可选依赖：未安装时降级为占位异常类，确保模块在纯进程内模式下仍可导入，
# 且 RedisRateLimiter（仅在有 redis 时才构造）的 `except WatchError` 不会因名称未定义而崩溃。
try:
    from redis.exceptions import WatchError
except Exception:  # redis 未安装时为可选路径
    class WatchError(Exception):
        """redis 缺失时的占位异常类；仅被 except 捕获，无 redis 场景下不会被实际抛出。"""
        pass

_logger = rlog.get_logger("gateway-ratelimit")


# ---------------------------------------------------------------------------
# 看板持久化：后台线程异步落 t_rate_quota，绝不阻塞 acquire/release 热路径。
# 频控硬闸只依赖内存态（进程内 deque）或 Redis，与 SQLite 落盘解耦。
# ---------------------------------------------------------------------------
_PERSIST_QUEUE: "Optional[queue.Queue]" = None
_PERSIST_THREAD: "Optional[threading.Thread]" = None
_PERSIST_LOCK = threading.Lock()
_PERSIST_SQL = """
    INSERT INTO t_rate_quota (ip, used, limit_val, queued, window, updated_at)
    VALUES (?, ?, ?, ?, ?, datetime('now'))
    ON CONFLICT(ip) DO UPDATE SET
        used=excluded.used, limit_val=excluded.limit_val,
        queued=excluded.queued, window=excluded.window, updated_at=datetime('now')
"""


def _persist_worker() -> None:
    q = _PERSIST_QUEUE
    while True:
        item = q.get()
        if item is None:
            q.task_done()
            break
        try:
            ip, used, limit, queued, window = item
            db.write(_PERSIST_SQL, (ip, used, limit, queued, window))
        except Exception:
            pass
        q.task_done()


def _enqueue_persist(ip: str, used: int, limit: int, queued: int, window: float) -> None:
    global _PERSIST_QUEUE, _PERSIST_THREAD
    with _PERSIST_LOCK:
        if _PERSIST_QUEUE is None:
            _PERSIST_QUEUE = queue.Queue()
            _PERSIST_THREAD = threading.Thread(target=_persist_worker, daemon=True)
            _PERSIST_THREAD.start()
    try:
        _PERSIST_QUEUE.put((ip, used, limit, queued, window))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Redis 集中式频控采用「乐观锁事务」(WATCH + MULTI/EXEC) 而非 Lua 脚本：
# - 原因：目标测试环境使用 fakeredis 2.x，其未实现 EVAL/EVALSHA（Lua），
#   故不能依赖 Lua 原子脚本；而 WATCH/MULTI/EXEC 仅需基础命令，fakeredis 与
#   真实 Redis 均支持。
# - 原子性：acquire 先 WATCH 相关键，读滑动窗口计数后于 MULTI 内写入；若窗口
#   期间其它 worker 改动了被 watch 的键，EXEC 触发 WatchError 并重试，从而
#   保证「清理过期 → 计数 → 判定 → 写入」跨 worker 串行，杜绝聚合超额。
# - 数据结构（与进程内一致）：ZSET(分值=时间戳, 成员=now:uuid) 存时间戳，
#   HASH 字段 queued 存排队数；成员唯一性由 Python 侧 uuid 保证（跨 worker 不冲突），
#   不再依赖 Redis 计数键，从而避免「WATCH 后改写被 watch 键」导致的乐观锁失效。
# ---------------------------------------------------------------------------


class BaseRateLimiter:
    """频控公共契约：acquire / release / usage / _limit / _persist。

    子类只需实现底层存储（进程内 deque 或 Redis），对外接口完全一致，
    使 ApiProxy 无需感知具体实现（鸭子类型）。
    """

    def __init__(self, capacity: int | None = None, window: float | None = None,
                 buffer: float | None = None) -> None:
        self.capacity = capacity if capacity is not None else settings.RATE_CAPACITY
        self.window = window if window is not None else settings.RATE_WINDOW
        self.buffer = buffer if buffer is not None else settings.FREQ_BUFFER

    def _limit(self) -> int:
        # floor（非 ceil）：保证任意 capacity（含非 20 倍数）usage_pct ≤ 95.0%
        return int(math.floor(self.capacity * self.buffer))

    def acquire(self, ip: str) -> bool:
        raise NotImplementedError

    def release(self, ip: str) -> None:
        raise NotImplementedError

    def usage(self, ip: str):
        raise NotImplementedError

    def _get_counts(self, ip: str) -> "tuple[int, int]":
        raise NotImplementedError

    def _persist(self, ip: str) -> None:
        """将当前配额快照入队，由后台线程落 t_rate_quota（看板数据源）。

        关键：acquire/release 热路径**不再同步写 SQLite**——每请求一次 commit 会
        显著拖慢频控（实测 ~3ms/次），既损害吞吐，又因滑动窗口（RATE_WINDOW）短于
        慢循环耗时，导致窗口内时间戳提前过期、硬闸在压测下失真。落盘仅为可观测性，
        与频控硬闸逻辑解耦，故改为 best-effort 异步持久化，绝不阻塞限流判定。
        """
        try:
            limit = self._limit()
            used, queued = self._get_counts(ip)
            _enqueue_persist(ip, used, limit, queued, self.window)
        except Exception:
            pass

    def _ts_key(self, ip: str) -> str:
        return f"rate:ts:{ip}"

    def _q_key(self, ip: str) -> str:
        return f"rate:q:{ip}"


class RateLimiter(BaseRateLimiter):
    """进程内滑动窗口频控（单 worker 语义）。

    仅保证**单个进程/单 worker** 内的全局硬闸；多 worker 需改用 RedisRateLimiter。
    """

    def __init__(self, capacity: int | None = None, window: float | None = None,
                 buffer: float | None = None) -> None:
        super().__init__(capacity, window, buffer)
        # RLock（可重入）：_persist 在 acquire/release 持锁时调用 _get_counts 会再次
        # 进入同一锁；非重入 Lock 会自死锁。RedisRateLimiter 无此锁（Redis 原子）。
        self._lock = threading.RLock()
        self._timestamps: Dict[str, deque] = defaultdict(deque)
        self._queued: Dict[str, int] = defaultdict(int)

    def _clean(self, ip: str) -> None:
        now = time.time()
        dq = self._timestamps[ip]
        while dq and now - dq[0] > self.window:
            dq.popleft()

    def acquire(self, ip: str) -> bool:
        with self._lock:
            self._clean(ip)
            limit = self._limit()
            if len(self._timestamps[ip]) < limit:
                self._timestamps[ip].append(time.time())
                self._persist(ip)
                return True
            # 超限：排队（不丢弃）
            self._queued[ip] += 1
            self._persist(ip)
            _logger.warn(f"频控满，请求排队 ip={ip} queued={self._queued[ip]}")
            return False

    def release(self, ip: str) -> None:
        with self._lock:
            dq = self._timestamps[ip]
            if dq:
                dq.popleft()
            if self._queued[ip] > 0:
                self._queued[ip] -= 1
            self._persist(ip)

    def usage(self, ip: str) -> "Quota":
        from passive_agent.gateway.model import Quota

        with self._lock:
            self._clean(ip)
            limit = self._limit()
            used = len(self._timestamps[ip])
            queued = self._queued[ip]
        pct = round(used / self.capacity * 100, 2) if self.capacity else 0.0
        return Quota(ip=ip, used=used, limit=limit, usage_pct=pct, queued=queued)

    def _get_counts(self, ip: str) -> "tuple[int, int]":
        with self._lock:
            self._clean(ip)
            return len(self._timestamps[ip]), self._queued[ip]


class RedisRateLimiter(BaseRateLimiter):
    """集中式滑动窗口频控（跨 worker 全局硬闸）。

    client 为 redis-py 兼容对象（真实 Redis 或测试用内存实现）。acquire/release
    采用 WATCH + MULTI/EXEC 乐观锁事务，多名 worker 共享同一后端，全局聚合吞吐
    仍受 ≤95% 硬闸约束，彻底消除「--workers N → 聚合上限翻 N 倍」缺口。

    原子性说明：acquire 先 WATCH 相关键并读取滑动窗口计数，再于 MULTI 内写入；
    若窗口期间其它 worker 改动了被 watch 的键，EXEC 触发 WatchError 并重试，
    保证「清理过期 → 计数 → 判定 → 写入」跨 worker 串行，杜绝聚合超额。
    """

    def __init__(self, client, capacity: int | None = None,
                 window: float | None = None, buffer: float | None = None) -> None:
        super().__init__(capacity, window, buffer)
        self._client = client

    def acquire(self, ip: str) -> bool:
        now = time.time()
        ts_key, q_key = self._ts_key(ip), self._q_key(ip)
        limit = self._limit()
        accepted = False
        while True:
            try:
                pipe = self._client.pipeline()
                # 乐观锁契约（关键正确性约束）：
                # 1) 先 WATCH 需要「读一致性」的键；2) 仅做读（zcard）不可修改被 watch 的键；
                # 3) 所有写操作（清理过期 / 写入时间戳 / 排队计数）必须置于 MULTI 内，由 EXEC
                #    原子提交。绝不可在 WATCH 之后、EXEC 之前改动被 watch 的键——否则真实 Redis
                #    必因键被改写而令 EXEC 抛 WatchError，进而陷入无限重试。成员唯一性由 Python
                #    侧 uuid 保证（跨 worker 不冲突），无需再触碰 Redis 计数键。
                pipe.watch(ts_key, q_key)
                count = int(pipe.zcard(ts_key) or 0)  # 读（不修改被 watch 键）
                pipe.multi()
                pipe.zremrangebyscore(ts_key, "-inf", now - self.window)  # 清理过期（事务内）
                if count < limit:
                    member = f"{now:.6f}:{uuid.uuid4().hex[:12]}"
                    pipe.zadd(ts_key, {member: now})
                    if self.window > 0:
                        pipe.pexpire(ts_key, int(self.window * 1000) + 1000)
                    accepted = True
                else:
                    pipe.hincrby(q_key, "queued", 1)
                    accepted = False
                pipe.execute()
                break
            except WatchError:
                # 其它 worker 在 WATCH 与 EXEC 之间改动了键 → 重试，保证聚合硬闸跨 worker 串行
                continue
            finally:
                try:
                    pipe.reset()
                except Exception:
                    pass
        self._persist(ip)
        if not accepted:
            queued = self._get_counts(ip)[1]
            _logger.warn(f"[redis] 频控满，请求排队 ip={ip} queued={queued}")
        return accepted

    def release(self, ip: str) -> None:
        now = time.time()
        ts_key, q_key = self._ts_key(ip), self._q_key(ip)
        while True:
            try:
                pipe = self._client.pipeline()
                # 同 acquire：仅在 WATCH 后做读（zcard/hget），写操作置于 MULTI 内。
                pipe.watch(ts_key, q_key)
                count = int(pipe.zcard(ts_key) or 0)
                queued = int(pipe.hget(q_key, "queued") or 0)
                pipe.multi()
                pipe.zremrangebyscore(ts_key, "-inf", now - self.window)
                if count > 0:
                    pipe.zpopmin(ts_key, 1)
                if queued > 0:
                    pipe.hincrby(q_key, "queued", -1)
                pipe.execute()
                break
            except WatchError:
                continue
            finally:
                try:
                    pipe.reset()
                except Exception:
                    pass
        self._persist(ip)

    def usage(self, ip: str) -> "Quota":
        from passive_agent.gateway.model import Quota

        used = int(self._client.zcard(self._ts_key(ip)) or 0)
        queued = int(self._client.hget(self._q_key(ip), "queued") or 0)
        limit = self._limit()
        pct = round(used / self.capacity * 100, 2) if self.capacity else 0.0
        return Quota(ip=ip, used=used, limit=limit, usage_pct=pct, queued=queued)

    def _get_counts(self, ip: str) -> "tuple[int, int]":
        used = int(self._client.zcard(self._ts_key(ip)) or 0)
        queued = int(self._client.hget(self._q_key(ip), "queued") or 0)
        return used, queued


def _mask_url(url: str) -> str:
    """去掉 URL 中的密码后再记录日志，避免凭证泄露。"""
    if "@" in url:
        return "redis://***@" + url.split("@", 1)[-1]
    return url


def _try_connect_redis(url: str):
    """尝试建立 Redis 连接；任一环节失败返回 None（交由上层决定告警/降级）。"""
    try:
        import redis  # 可选依赖：未安装则不启用集中式 limiter
    except Exception:
        _logger.warn("未安装 redis 库，无法启用集中式 limiter（回退进程内单例）")
        return None
    try:
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        client.ping()
        return client
    except Exception as exc:  # 连接/鉴权/超时等
        _logger.warn("Redis 连接失败：%s", exc)
        return None


def _build_limiter() -> "BaseRateLimiter":
    """按配置选择后端：Redis（集中式）优先，否则进程内单例并显式告警。"""
    url = (settings.RATE_REDIS_URL or "").strip()
    if url:
        client = _try_connect_redis(url)
        if client is not None:
            _logger.info("全局频控：已启用 Redis 集中式 limiter (url=%s)", _mask_url(url))
            return RedisRateLimiter(client)
        # 已配置但不可用
        if settings.RATE_REDIS_FAIL_FAST:
            raise RuntimeError(
                "RATE_REDIS_URL 已配置但无法连接 Redis，且 RATE_REDIS_FAIL_FAST=True → 启动失败"
            )
        _logger.warn(
            "RATE_REDIS_URL 已配置但 Redis 不可用，回退进程内单例"
            "（--workers>1 时全局频控硬闸失效，请排查 Redis）"
        )
    else:
        if not settings.SINGLE_WORKER_MODE:
            _logger.warn(
                "未配置 PASSIVE_RATE_REDIS_URL 且 SINGLE_WORKER_MODE=False："
                "进程内频控在 --workers>1 时全局硬闸失效，请启用 Redis"
                "或显式 SINGLE_WORKER_MODE=True"
            )

    _logger.warn(
        "频控运行于进程内单例模式：仅保证单 worker 内全局硬闸；"
        "多 worker 须配置 PASSIVE_RATE_REDIS_URL 启用 Redis 集中式 limiter"
    )
    # 直接构造进程内 limiter；调用方（get_rate_limiter）已持有 _default_limiter_lock，
    # 切勿在此再次获取该非可重入锁，否则死锁。
    return RateLimiter()


# ---------------------------------------------------------------------------
# 频控单例（进程内回退路径）：确保单 worker 内所有 ApiProxy 共享同一频控状态。
# 多 worker / 多进程场景由 get_rate_limiter() 在检测到 Redis 时自动切换为
# RedisRateLimiter；否则此处仍是进程内单例（已在日志明确告警单 worker 假设）。
# ---------------------------------------------------------------------------
_default_limiter: "RateLimiter | None" = None
_default_limiter_lock = threading.Lock()


def get_rate_limiter() -> "BaseRateLimiter":
    """跨 worker 全局频控入口。

    返回 RedisRateLimiter（已配 Redis 且可达）或进程内 RateLimiter 单例。
    选择结果在进程生命周期内缓存（仅决策一次，启动期可见告警日志）。
    """
    global _default_limiter
    if _default_limiter is None:
        with _default_limiter_lock:
            if _default_limiter is None:
                _default_limiter = _build_limiter()
    return _default_limiter


def reset_rate_limiter() -> None:
    """测试用：清除单例缓存，使下一次 get_rate_limiter() 重新决策后端。"""
    global _default_limiter
    with _default_limiter_lock:
        _default_limiter = None
