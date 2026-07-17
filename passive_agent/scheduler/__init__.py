"""定时任务调度器 — 每日自动采集，零依赖。

用法:
    # 设置定时采集（每天 02:00）
    python cli.py schedule --targets targets.txt

    # 立即执行一次
    python cli.py schedule --targets targets.txt --once

    # 查看调度状态
    python cli.py schedule --status
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread, Event
from typing import List, Optional

from passive_agent.collector.manager import CollectorManager
from passive_agent.collector.domain_db import infer_domain
from passive_agent.storage import db
from passive_agent.common import logging as slog

_logger = slog.get_logger("scheduler")

# 调度状态数据库表
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS t_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    domain TEXT NOT NULL,
    last_run TEXT,
    next_run TEXT,
    total_assets INTEGER DEFAULT 0,
    new_assets INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    UNIQUE(target, domain)
);
"""

# 采集历史记录表
HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS t_schedule_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    domain TEXT NOT NULL,
    run_at TEXT NOT NULL,
    total_assets INTEGER DEFAULT 0,
    new_assets INTEGER DEFAULT 0,
    risk_count INTEGER DEFAULT 0,
    summary TEXT
);
"""


def _ensure_tables() -> None:
    """确保调度相关表存在。"""
    for sql in (SCHEMA_SQL, HISTORY_SQL):
        db.write(sql)


def load_targets(path: str) -> List[dict]:
    """从文件加载目标列表。
    
    文件格式：每行一个目标，支持注释（#开头）和空行。
    """
    targets = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 支持 "名称,域名" 格式
            if "," in line:
                parts = [p.strip() for p in line.split(",", 1)]
                targets.append({"name": parts[0], "domain": parts[1]})
            else:
                targets.append({"name": line, "domain": ""})
    return targets


def run_once(targets: List[dict], verbose: bool = True) -> List[dict]:
    """对目标列表执行一次采集，返回结果摘要。"""
    _ensure_tables()
    mgr = CollectorManager()
    results = []

    if verbose:
        print(f"\n{'='*50}")
        print(f"📡 定时采集开始: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   目标数: {len(targets)}")
        print(f"{'='*50}\n")

    for i, t in enumerate(targets, 1):
        name = t["name"]
        domain = t["domain"] or ""

        if verbose:
            print(f"[{i}/{len(targets)}] 🎯 {name}...", end=" ", flush=True)

        # 自动推断域名
        if not domain:
            domain = infer_domain(name)

        # 压制 JSON 日志
        from passive_agent.common.logging import SUPPRESS_CLI_OUTPUT
        import passive_agent.common.logging as _clog
        _clog.SUPPRESS_CLI_OUTPUT = True

        try:
            report = mgr.collect(name=name, domain=domain)

            # 统计本次新增资产
            prev_rows = db.query(
                "SELECT total_assets FROM t_schedule WHERE target=? AND domain=?",
                (name, domain),
            )
            prev_total = prev_rows[0]["total_assets"] if prev_rows else 0
            new_count = max(0, report.total_records - prev_total)
            risk_count = len([e for e in report.errors if "🔴" in e])

            # 更新调度状态
            now = datetime.now(timezone.utc).isoformat()
            db.write(
                "INSERT OR REPLACE INTO t_schedule "
                "(target, domain, last_run, total_assets, new_assets, status) "
                "VALUES (?,?,?,?,?,?)",
                (name, domain, now, report.total_records, new_count, "success"),
            )

            # 写入历史
            db.write(
                "INSERT INTO t_schedule_history "
                "(target, domain, run_at, total_assets, new_assets, risk_count, summary) "
                "VALUES (?,?,?,?,?,?,?)",
                (name, domain, now, report.total_records, new_count, risk_count,
                 json.dumps(report.errors[:5], ensure_ascii=False)),
            )

            # 自动保存报告
            report_dir = Path("data")
            report_dir.mkdir(exist_ok=True)
            safe_name = name.replace(" ", "_").replace("/", "_")
            report_path = report_dir / f"schedule_{safe_name}_{domain}.md"
            report_path.write_text(report.to_table(), encoding="utf-8")

            if verbose:
                print(f"✅ {report.total_records} 条 (+{new_count} 新增, ⚠️ {risk_count} 风险)")

            results.append({
                "name": name,
                "domain": domain,
                "total": report.total_records,
                "new": new_count,
                "risks": risk_count,
                "status": "success",
            })

        except Exception as exc:
            if verbose:
                print(f"❌ 失败: {exc}")
            results.append({
                "name": name,
                "domain": domain,
                "total": 0,
                "new": 0,
                "risks": 0,
                "status": f"error: {exc}",
            })
        finally:
            _clog.SUPPRESS_CLI_OUTPUT = False

    if verbose:
        print(f"\n{'='*50}")
        print(f"✅ 采集完成")
        total_new = sum(r["new"] for r in results)
        total_risks = sum(r["risks"] for r in results)
        print(f"   总新增资产: {total_new}")
        print(f"   总风险发现: {total_risks}")
        print(f"{'='*50}\n")

    return results


def show_status() -> None:
    """显示调度状态。"""
    _ensure_tables()
    rows = db.query(
        "SELECT target, domain, last_run, total_assets, new_assets, status "
        "FROM t_schedule ORDER BY last_run DESC"
    )

    if not rows:
        print("📭 暂无调度记录。运行 `python cli.py schedule --targets targets.txt --once` 开始。")
        return

    print(f"\n{'='*60}")
    print(f"📊 调度状态")
    print(f"{'='*60}")
    print(f"{'目标':<20} {'域名':<20} {'上次采集':<22} {'资产':<6} {'新增':<6} {'状态'}")
    print(f"{'-'*80}")
    for r in rows:
        last = r["last_run"][:19] if r["last_run"] else "-"
        print(f"{r['target']:<20} {r['domain']:<20} {last:<22} {r['total_assets']:<6} {r['new_assets']:<6} {r['status']}")

    # 显示最近历史
    history = db.query(
        "SELECT target, run_at, total_assets, new_assets, risk_count "
        "FROM t_schedule_history ORDER BY id DESC LIMIT 5"
    )
    if history:
        print(f"\n📋 最近5次采集")
        print(f"{'目标':<20} {'时间':<22} {'资产':<6} {'新增':<6} {'风险'}")
        print(f"{'-'*60}")
        for r in history:
            print(f"{r['target']:<20} {str(r['run_at'])[:19]:<22} {r['total_assets']:<6} {r['new_assets']:<6} {r['risk_count']}")


class DailyScheduler:
    """每日定时调度器（零依赖，纯 Python 实现）。"""

    def __init__(self, targets: List[dict], hour: int = 2, minute: int = 0):
        self.targets = targets
        self.hour = hour
        self.minute = minute
        self._stop = Event()

    def _seconds_until_next(self) -> float:
        """计算到下次执行时间的秒数。"""
        now = datetime.now()
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if target <= now:
            # 今天的已过，明天
            from datetime import timedelta
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def _loop(self) -> None:
        """调度主循环。"""
        while not self._stop.is_set():
            wait = self._seconds_until_next()
            next_time = datetime.now().timestamp() + wait
            next_str = datetime.fromtimestamp(next_time).strftime("%Y-%m-%d %H:%M:%S")
            _logger.info(f"下次调度: {next_str} (等待 {wait/3600:.1f} 小时)")
            print(f"⏰ 下次调度: {next_str} (等待 {wait/3600:.1f} 小时)")

            # 等待到指定时间（可被 _stop 中断）
            self._stop.wait(wait)
            if self._stop.is_set():
                break

            run_once(self.targets, verbose=True)

    def start(self, block: bool = True) -> None:
        """启动调度器。"""
        print(f"🚀 调度器已启动")
        print(f"   时间: 每天 {self.hour:02d}:{self.minute:02d}")
        print(f"   目标: {len(self.targets)} 个")
        print(f"   按 Ctrl+C 停止\n")

        if block:
            try:
                self._loop()
            except KeyboardInterrupt:
                print("\n🛑 调度器已停止")
                self.stop()
        else:
            Thread(target=self._loop, daemon=True).start()

    def stop(self) -> None:
        """停止调度器。"""
        self._stop.set()