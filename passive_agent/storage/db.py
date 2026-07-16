"""SQLite 连接 + 建表（schema 迁移幂等）。蓝图 §2 / T02。

表清单：t_compliance_rule / t_approval_task / t_task_snapshot / t_oss_inventory /
t_audit_log / t_subject / t_verify_result / t_collect_result / t_rate_quota。
约定：snake_case、主键 INTEGER PK、时间 DATETIME UTC、deleted TINYINT DEFAULT 0。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any, List, Optional, Tuple

from passive_agent.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS t_compliance_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_approval_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    biz_type TEXT,
    subject_id TEXT,
    risk_level TEXT,
    status TEXT,
    payload_ref TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_task_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    offset INTEGER DEFAULT 0,
    state_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_oss_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT,
    license TEXT,
    purpose TEXT,
    call_boundary TEXT,
    boundary_tag TEXT,
    module_ref TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    trace_id TEXT,
    subject_id TEXT,
    action TEXT,
    source TEXT,
    decision TEXT,
    reason_code TEXT,
    msg TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_subject (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enterprise TEXT,
    name TEXT,
    relation TEXT,
    credit_code TEXT,
    depth INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_verify_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id TEXT,
    status TEXT,
    fail_layer INTEGER,
    basis TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_collect_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id TEXT,
    subject_id TEXT,
    source_cnt INTEGER DEFAULT 0,
    payload_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_rate_quota (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    used INTEGER DEFAULT 0,
    limit_val INTEGER DEFAULT 0,
    queued INTEGER DEFAULT 0,
    window REAL DEFAULT 1.0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted TINYINT DEFAULT 0
);
-- ===== P1 增量表（追加，不改已有表）=====
CREATE TABLE IF NOT EXISTS t_asset_node (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    node_type TEXT,
    name TEXT,
    enterprise TEXT,
    properties_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_asset_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL UNIQUE,
    from_node TEXT,
    to_node TEXT,
    edge_type TEXT,
    properties_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS t_source_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adapter_name TEXT NOT NULL UNIQUE,
    cluster TEXT,
    health TEXT,
    fail_count INTEGER DEFAULT 0,
    last_fail_at TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
-- ===== FAFU 反哺：资产采集记录表 =====
CREATE TABLE IF NOT EXISTS t_collect_asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enterprise TEXT,
    domain TEXT,
    asset_value TEXT NOT NULL,
    asset_type TEXT,
    source_name TEXT,
    ip TEXT,
    port INTEGER,
    tech_stack TEXT,
    title TEXT,
    tags TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_unique ON t_collect_asset(asset_value, asset_type, source_name);
"""

_DB_PATH: Optional[str] = None
_CONN: Optional[sqlite3.Connection] = None
_INITIALIZED = False
_LOCK = threading.RLock()


def configure(db_path: str) -> None:
    global _DB_PATH, _CONN, _INITIALIZED
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
            _CONN = None
        _DB_PATH = db_path
        _INITIALIZED = False


def _resolve_path() -> str:
    path = _DB_PATH or settings.DB_PATH
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        with _LOCK:
            if _CONN is None:
                _CONN = sqlite3.connect(_resolve_path(), check_same_thread=False)
                _CONN.row_factory = sqlite3.Row
                _CONN.execute("PRAGMA journal_mode=WAL")
    return _CONN


def init() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    _seed_rules(conn)
    global _INITIALIZED
    _INITIALIZED = True


def ensure_init() -> None:
    global _INITIALIZED
    if not _INITIALIZED:
        init()


def _seed_rules(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) AS c FROM t_compliance_rule WHERE deleted=0")
    if cur.fetchone()["c"] == 0:
        rules = [
            ("block-active-scan", "ACTIVE_SCAN", "BLOCK", "010001"),
            ("block-active-http", "ACTIVE_HTTP", "BLOCK", "010001"),
            ("block-tcp-send", "TCP_SEND", "BLOCK", "010001"),
            ("allow-passive-query", "PASSIVE_QUERY", "ALLOW", "000000"),
        ]
        conn.executemany(
            "INSERT INTO t_compliance_rule (rule_name, action_type, decision, reason_code) VALUES (?,?,?,?)",
            rules,
        )
        conn.commit()


def write(sql: str, params: Tuple[Any, ...] = ()) -> None:
    with _LOCK:
        conn = get_conn()
        conn.execute(sql, params)
        conn.commit()


def query(sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    with _LOCK:
        conn = get_conn()
        return conn.execute(sql, params).fetchall()


# ===== F-6 PII 保护：加密写入 + 删除/匿名化接口 =====
def insert_subject(enterprise, name, relation, credit_code, depth: int = 0) -> None:
    """写入主体（企业/法人/信用代码），敏感字段经 pii 加密/脱敏。"""
    from passive_agent.common import pii

    write(
        "INSERT INTO t_subject (enterprise, name, relation, credit_code, depth) VALUES (?,?,?,?,?)",
        (
            pii.encrypt_pii(enterprise),
            pii.encrypt_pii(name),
            relation,
            pii.encrypt_pii(credit_code),
            depth,
        ),
    )


def get_subject(subject_id) -> Optional[dict]:
    """读取主体并解密敏感字段。"""
    from passive_agent.common import pii

    rows = query("SELECT * FROM t_subject WHERE id=? AND deleted=0", (subject_id,))
    if not rows:
        return None
    r = dict(rows[0])
    r["enterprise"] = pii.decrypt_pii(r.get("enterprise"))
    r["name"] = pii.decrypt_pii(r.get("name"))
    r["credit_code"] = pii.decrypt_pii(r.get("credit_code"))
    return r


def delete_subject(subject_id) -> None:
    """物理删除主体记录（合规删除请求）。"""
    write("UPDATE t_subject SET deleted=1 WHERE id=?", (subject_id,))


def anonymize_subject(subject_id) -> None:
    """匿名化主体敏感字段（保留结构用于图谱分析）。"""
    write(
        "UPDATE t_subject SET enterprise=?, name=?, credit_code=? WHERE id=?",
        ("REDACTED", "REDACTED", "REDACTED", subject_id),
    )


def insert_collect_asset(enterprise, domain, asset_value, asset_type, source_name,
                         ip, port, tech_stack, title, tags) -> None:
    """写入资产采集记录，敏感字段（enterprise/ip/port）经 pii 加密/脱敏。"""
    from passive_agent.common import pii

    write(
        "INSERT INTO t_collect_asset "
        "(enterprise, domain, asset_value, asset_type, source_name, ip, port, tech_stack, title, tags) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            pii.encrypt_pii(enterprise), domain, asset_value, asset_type, source_name,
            pii.encrypt_pii(ip),
            pii.encrypt_pii(str(port)) if port is not None else None,
            tech_stack, title, tags,
        ),
    )


def delete_collect_asset(asset_id) -> None:
    write("UPDATE t_collect_asset SET deleted=1 WHERE id=?", (asset_id,))


def purge_expired_pii() -> None:
    """按 RETENTION_DAYS 清理超期 PII 记录（0=不自动清理）。"""
    if settings.RETENTION_DAYS and settings.RETENTION_DAYS > 0:
        write(
            "UPDATE t_subject SET deleted=1 WHERE julianday('now') - julianday(created_at) > ?",
            (settings.RETENTION_DAYS,),
        )
        write(
            "UPDATE t_collect_asset SET deleted=1 WHERE julianday('now') - julianday(collected_at) > ?",
            (settings.RETENTION_DAYS,),
        )
