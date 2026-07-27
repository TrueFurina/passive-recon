"""修复闭环跟踪 — 风险状态追踪与趋势分析。

每次采集对比上次结果：
- 新增风险 → 🔴 标记
- 已修复风险 → ✅ 标记
- 持续存在风险 → 🟡 标记

依赖 t_risk_tracking 表存储历史状态。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from passive_agent.storage import db
from passive_agent.collector.model import CollectReport

# 确保跟踪表存在
TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS t_risk_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enterprise TEXT NOT NULL,
    risk_key TEXT NOT NULL,
    risk_desc TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    UNIQUE(enterprise, risk_key)
);
CREATE INDEX IF NOT EXISTS idx_risk_tracking_ent ON t_risk_tracking(enterprise);
"""


def _ensure_tables() -> None:
    try:
        db.write(TRACKING_TABLE_SQL)
    except Exception:
        pass


def track_risks(report: CollectReport) -> None:
    """跟踪报告中的风险状态。

    Args:
        report: 采集报告（原地修改，添加跟踪状态标签）
    """
    _ensure_tables()

    enterprise = report.enterprise
    now = datetime.now(timezone.utc).isoformat()[:19]

    # 提取当前风险
    current_risks: Dict[str, str] = {}
    for e in report.errors:
        if "🔴" in e or "P0" in e or "P1" in e or "P2" in e:
            # 用风险描述的前80字符作为唯一键
            key = e[:80]
            current_risks[key] = e

    if not current_risks:
        return

    # 查询历史风险
    previous_rows = db.query(
        "SELECT risk_key, status, first_seen FROM t_risk_tracking WHERE enterprise=?",
        (enterprise,),
    )
    previous: Dict[str, Tuple[str, str]] = {}
    for r in previous_rows:
        previous[r["risk_key"]] = (r["status"], r["first_seen"])

    new_count = 0
    active_count = 0
    fixed_count = 0

    # 处理当前风险
    for key, desc in current_risks.items():
        if key in previous:
            # 持续存在的风险
            status, first_seen = previous[key]
            if status == "active":
                active_count += 1
            db.write(
                "UPDATE t_risk_tracking SET last_seen=?, status='active' WHERE enterprise=? AND risk_key=?",
                (now, enterprise, key),
            )
        else:
            # 新增风险
            db.write(
                "INSERT OR REPLACE INTO t_risk_tracking (enterprise, risk_key, risk_desc, first_seen, last_seen, status) "
                "VALUES (?,?,?,?,?,?)",
                (enterprise, key, desc, now, now, "active"),
            )
            new_count += 1

    # 标记已修复的风险（之前有但现在没有的）
    for key, (status, first_seen) in previous.items():
        if status == "active" and key not in current_risks:
            db.write(
                "UPDATE t_risk_tracking SET status='fixed', last_seen=? WHERE enterprise=? AND risk_key=?",
                (now, enterprise, key),
            )
            fixed_count += 1
            report.errors.append(f"✅ [FIXED] 风险已修复: {key[:60]}")

    if new_count > 0 or fixed_count > 0:
        report.errors.append(
            f"📊 风险趋势: +{new_count} 新增 / -{fixed_count} 修复 / {active_count} 持续"
        )


def show_trend(enterprise: str, days: int = 30) -> str:
    """显示风险趋势报告。"""
    _ensure_tables()

    rows = db.query(
        "SELECT risk_desc, status, first_seen, last_seen FROM t_risk_tracking "
        "WHERE enterprise=? ORDER BY status, first_seen DESC",
        (enterprise,),
    )

    if not rows:
        return f"📭 {enterprise}: 暂无风险跟踪记录"

    active = [r for r in rows if r["status"] == "active"]
    fixed = [r for r in rows if r["status"] == "fixed"]

    lines = [
        f"📊 风险趋势报告: {enterprise}",
        f"   活跃风险: {len(active)} | 已修复: {len(fixed)}",
        "",
    ]

    if active:
        lines.append(f"🟡 活跃风险 ({len(active)}):")
        for r in active[:10]:
            lines.append(f"  - {r['risk_desc'][:60]} (发现: {r['first_seen'][:10]})")

    if fixed:
        lines.append(f"✅ 已修复 ({len(fixed)}):")
        for r in fixed[:5]:
            lines.append(f"  - {r['risk_desc'][:50]} (修复: {r['last_seen'][:10]})")

    return "\n".join(lines)