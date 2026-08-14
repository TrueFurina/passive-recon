"""合规报表导出 — 周期合规审计报告（企业版特性）。

从 t_audit_log 生成周期合规审计报告：
- 违规统计（BLOCK 事件 + 原因码分布）
- 封禁统计
- 放行统计（ALLOW 事件）
- 合规率（ALLOW / 总决策）
- 按源统计违规 TOP 榜
- 导出格式：Markdown / CSV / JSON

用法：
    python cli.py compliance-report --days 7
    python cli.py compliance-report --days 30 --format csv --output report.csv
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from passive_agent.audit.query import AuditQuery
from passive_agent.common import logging as clog

_logger = clog.get_logger("compliance-report")

# 违规原因码 → 描述
REASON_DESC = {
    "010001": "主动动作拦截",
    "010002": "出站目标不合规（内网/非HTTPS）",
    "020002": "审批闸门拦截",
    "040001": "鉴权失败",
    "040003": "权限不足",
}

# 主动违规决策集合
VIOLATION_DECISIONS = {"BLOCK", "FAIL"}


def build_report(days: int = 7, enterprise: Optional[str] = None) -> Dict:
    """构建周期合规审计报告。

    Args:
        days: 统计天数（默认 7 天）
        enterprise: 限定企业（可选）

    Returns:
        报告数据字典
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_ts = start.isoformat()

    aq = AuditQuery()
    rows = aq.search(enterprise=enterprise, start_ts=start_ts, limit=100000)

    total = len(rows)
    allow = sum(1 for r in rows if r.get("decision") == "ALLOW")
    block = sum(1 for r in rows if r.get("decision") in VIOLATION_DECISIONS)
    suspend = sum(1 for r in rows if r.get("decision") == "SUSPEND")
    other = total - allow - block - suspend

    # 原因码分布（违规）
    reason_dist: Dict[str, int] = {}
    for r in rows:
        if r.get("decision") in VIOLATION_DECISIONS:
            code = r.get("reason_code") or "unknown"
            reason_dist[code] = reason_dist.get(code, 0) + 1

    # 按源统计违规 TOP
    source_violations: Dict[str, int] = {}
    for r in rows:
        if r.get("decision") in VIOLATION_DECISIONS:
            src = r.get("source") or "unknown"
            source_violations[src] = source_violations.get(src, 0) + 1
    top_sources = sorted(source_violations.items(), key=lambda x: -x[1])[:10]

    # 合规率
    compliance_rate = round(allow / total * 100, 2) if total else 100.0

    return {
        "period_days": days,
        "start_ts": start_ts[:19],
        "end_ts": end.isoformat()[:19],
        "enterprise": enterprise or "全部企业",
        "total_events": total,
        "allow_count": allow,
        "block_count": block,
        "suspend_count": suspend,
        "other_count": other,
        "compliance_rate": compliance_rate,
        "reason_distribution": {
            k: {"count": v, "desc": REASON_DESC.get(k, "未知原因")}
            for k, v in sorted(reason_dist.items(), key=lambda x: -x[1])
        },
        "top_violation_sources": [
            {"source": s, "count": c} for s, c in top_sources
        ],
    }


def to_markdown(report: Dict) -> str:
    """报告 → Markdown。"""
    lines = [
        "# 📊 周期合规审计报告",
        "",
        f"> 统计周期: {report['start_ts']} ~ {report['end_ts']} ({report['period_days']} 天)",
        f"> 统计范围: {report['enterprise']}",
        "",
        "## 总览",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 事件总数 | {report['total_events']} |",
        f"| 放行 (ALLOW) | {report['allow_count']} |",
        f"| 违规拦截 (BLOCK/FAIL) | {report['block_count']} |",
        f"| 挂起 (SUSPEND) | {report['suspend_count']} |",
        f"| 其他 | {report['other_count']} |",
        f"| **合规率** | **{report['compliance_rate']}%** |",
        "",
    ]

    if report["reason_distribution"]:
        lines += [
            "## 违规原因分布",
            "",
            "| 原因码 | 描述 | 次数 |",
            "|--------|------|------|",
        ]
        for code, info in report["reason_distribution"].items():
            lines.append(f"| {code} | {info['desc']} | {info['count']} |")
        lines.append("")

    if report["top_violation_sources"]:
        lines += [
            "## 违规来源 TOP",
            "",
            "| 数据源/模块 | 违规次数 |",
            "|------------|---------|",
        ]
        for item in report["top_violation_sources"]:
            lines.append(f"| {item['source']} | {item['count']} |")
        lines.append("")

    if report["total_events"] == 0:
        lines.append("> 📭 统计周期内无审计事件（或尚未运行采集）。")

    return "\n".join(lines)


def to_csv(report: Dict) -> str:
    """报告 → CSV 字符串。"""
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["指标", "数值"])
    w.writerow(["统计周期", f"{report['start_ts']} ~ {report['end_ts']}"])
    w.writerow(["统计范围", report["enterprise"]])
    w.writerow(["事件总数", report["total_events"]])
    w.writerow(["放行(ALLOW)", report["allow_count"]])
    w.writerow(["违规拦截", report["block_count"]])
    w.writerow(["挂起(SUSPEND)", report["suspend_count"]])
    w.writerow(["合规率(%)", report["compliance_rate"]])
    w.writerow([])
    w.writerow(["原因码", "描述", "次数"])
    for code, info in report["reason_distribution"].items():
        w.writerow([code, info["desc"], info["count"]])
    w.writerow([])
    w.writerow(["来源", "违规次数"])
    for item in report["top_violation_sources"]:
        w.writerow([item["source"], item["count"]])
    return buf.getvalue()