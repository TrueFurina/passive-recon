"""结构化审计日志：落 t_audit_log + JSON lines（蓝图 T04）。

每次拦截/放行/提交写：{ts(UTC), trace_id, subject_id, action, source, decision, reason_code, msg}。
支持按 subject/时间/违规类型 检索导出（底层走 SQLite）。
"""
from __future__ import annotations

from typing import Optional

from passive_agent.common import logging as clog
from passive_agent.storage import db

_logger = clog.get_logger("audit")


def log(
    trace_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    action: Optional[str] = None,
    source: Optional[str] = None,
    decision: Optional[str] = None,
    reason_code: Optional[str] = None,
    msg: str = "",
    level: str = "INFO",
) -> None:
    # 1) 结构化审计落库（证据链）
    try:
        db.write(
            """
            INSERT INTO t_audit_log
            (ts, trace_id, subject_id, action, source, decision, reason_code, msg)
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)
            """,
            (trace_id, subject_id, action, source, decision, reason_code, msg),
        )
    except Exception as exc:
        _logger.error(f"审计落库失败: {exc}")
    # 2) 同时输出 JSON lines（统一出口，便于采集 / 溯源）
    clog.log_event(
        level, "audit", msg,
        trace_id=trace_id, subject_id=subject_id,
        action=action, source=source, decision=decision, reason_code=reason_code,
    )


def search(subject_id: Optional[str] = None, decision: Optional[str] = None,
           reason_code: Optional[str] = None, limit: int = 100,
           start_ts: Optional[str] = None, end_ts: Optional[str] = None,
           enterprise: Optional[str] = None, trace_id: Optional[str] = None) -> list:
    """按条件检索审计记录（供决赛答辩溯源）。

    P1 扩展：新增 start_ts/end_ts/enterprise/trace_id 可选参数。
    旧调用方式（仅传 subject_id/decision/reason_code/limit）完全兼容。

    Args:
        subject_id: 主体 ID（兼容旧参数）
        decision: 合规判定
        reason_code: 错误码
        limit: 返回上限
        start_ts: 起始时间（P1 新增）
        end_ts: 结束时间（P1 新增）
        enterprise: 企业名（P1 新增，等价于 subject_id）
        trace_id: 追踪 ID（P1 新增）
    """
    sql = "SELECT ts, trace_id, subject_id, action, source, decision, reason_code, msg FROM t_audit_log WHERE deleted=0"
    params = []
    # 企业维度：enterprise 和 subject_id 取其一
    effective_subject = enterprise or subject_id
    if effective_subject:
        sql += " AND subject_id=?"
        params.append(effective_subject)
    if decision:
        sql += " AND decision=?"
        params.append(decision)
    if reason_code:
        sql += " AND reason_code=?"
        params.append(reason_code)
    if trace_id:
        sql += " AND trace_id=?"
        params.append(trace_id)
    if start_ts:
        sql += " AND ts>=?"
        params.append(start_ts)
    if end_ts:
        sql += " AND ts<=?"
        params.append(end_ts)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    try:
        return [dict(r) for r in db.query(sql, tuple(params))]
    except Exception:
        return []


def log_chain(trace_id: str, action: str, source: str, msg: str,
              subject_id: Optional[str] = None,
              decision: str = "ALLOW", reason_code: str = "000000",
              level: str = "INFO") -> None:
    """全链路日志辅助函数（P1 新增）。

    简化采集/校验/提交/调度各调用点的审计日志写入。
    确保 trace_id 从 run_company() 透传到各适配器/调度器。
    """
    log(
        trace_id=trace_id,
        subject_id=subject_id,
        action=action,
        source=source,
        decision=decision,
        reason_code=reason_code,
        msg=msg,
        level=level,
    )
