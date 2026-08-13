"""结果缓存层 — 相同查询 24h 缓存，减少 API 调用成本。

核心能力：
1. 以「数据源 + 查询参数」为键缓存采集结果
2. TTL 默认 24h，过期自动失效
3. 缓存命中直接返回，未命中则执行采集并回填
4. 落 SQLite 表 t_query_cache（重启不丢）

用法（在采集器 collect() 中包装）：
    with query_cache("crt.sh", domain) as cached:
        if cached is not None:
            return cached
        records = _do_collect(domain)
        return records  # 自动回填缓存
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from passive_agent.common import logging as clog
from passive_agent.storage import db

_logger = clog.get_logger("query-cache")

# 默认 TTL：24 小时
DEFAULT_TTL = 24 * 3600

# 哪些数据源不缓存（实时性要求高/成本低）
NO_CACHE_SOURCES = {"crt.sh", "hackertarget", "otx"}

# 全局开关（测试时可禁用）
ENABLED = True


def _ensure_table() -> None:
    try:
        db.write(
            "CREATE TABLE IF NOT EXISTS t_query_cache ("
            "  cache_key TEXT PRIMARY KEY,"
            "  payload_json TEXT NOT NULL,"
            "  created_at TEXT NOT NULL,"
            "  expires_at REAL NOT NULL"
            ")"
        )
    except Exception:
        pass


def _now_ts() -> float:
    return time.time()


def _cache_key(source: str, params: str) -> str:
    return f"{source}:{params}"


def get(source: str, params: str, ttl: float = DEFAULT_TTL) -> Optional[List[Dict]]:
    """获取缓存结果；未命中或过期返回 None。"""
    if not ENABLED or source in NO_CACHE_SOURCES:
        return None
    try:
        _ensure_table()
        key = _cache_key(source, params)
        rows = db.query(
            "SELECT payload_json, expires_at FROM t_query_cache WHERE cache_key=?",
            (key,),
        )
        if not rows:
            return None
        payload, expires_at = rows[0]["payload_json"], rows[0]["expires_at"]
        if _now_ts() > expires_at:
            # 过期清理
            db.write("DELETE FROM t_query_cache WHERE cache_key=?", (key,))
            return None
        data = json.loads(payload)
        _logger.info(f"缓存命中: {key}")
        return data
    except Exception:
        return None


def put(source: str, params: str, data: List[Dict], ttl: float = DEFAULT_TTL) -> None:
    """写入缓存。"""
    if not ENABLED or source in NO_CACHE_SOURCES:
        return
    try:
        _ensure_table()
        key = _cache_key(source, params)
        expires = _now_ts() + ttl
        db.write(
            "INSERT OR REPLACE INTO t_query_cache (cache_key, payload_json, created_at, expires_at) "
            "VALUES (?,?,?,?)",
            (key, json.dumps(data, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(), expires),
        )
    except Exception:
        pass


def clear() -> int:
    """清空全部缓存，返回清除条数。"""
    try:
        _ensure_table()
        rows = db.query("SELECT COUNT(*) AS c FROM t_query_cache")
        count = rows[0]["c"] if rows else 0
        db.write("DELETE FROM t_query_cache")
        _logger.info(f"缓存已清空: {count} 条")
        return count
    except Exception:
        return 0


def stats() -> Dict:
    """缓存统计。"""
    try:
        _ensure_table()
        rows = db.query(
            "SELECT COUNT(*) AS c, MIN(expires_at) AS oldest, MAX(expires_at) AS newest "
            "FROM t_query_cache"
        )
        r = rows[0] if rows else {}
        return {
            "entries": r.get("c", 0),
            "oldest_expires_in": round(max(0, (r.get("oldest") or 0) - _now_ts())),
            "newest_expires_in": round(max(0, (r.get("newest") or 0) - _now_ts())),
        }
    except Exception:
        return {"entries": 0}


class QueryCache:
    """上下文管理器：命中返回缓存，未命中执行并回填。"""

    def __init__(self, source: str, params: str, ttl: float = DEFAULT_TTL):
        self.source = source
        self.params = params
        self.ttl = ttl
        self._hit = False

    def __enter__(self) -> Optional[List[Dict]]:
        cached = get(self.source, self.params, self.ttl)
        if cached is not None:
            self._hit = True
            return cached
        return None  # 未命中，调用方执行真实采集

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # 不吞异常

    def store(self, data: List[Dict]) -> None:
        """调用方采集完成后回填缓存。"""
        if not self._hit:
            put(self.source, self.params, data, self.ttl)