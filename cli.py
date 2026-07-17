"""命令行面板入口（根目录）— 一通百通：任意目标 → 自动推断 → 全源采集。

子命令：
  collect <目标>      全能被动资产采集（自动推断域名 + 6大数据源）
  audit-queue         查看合规审计队列
  resume <task_id>    断点续跑
  enumerate <目标>    R3 全主体枚举（--depth）
  import-path <目录>  从已有资产目录/文件导入种子数据
  submit-status       R6 频控/提交状态
  compliance-status   R1 合规态势
  inventory-export    R5 台账导出
  list-sources        列出可用被动数据源
  domain-info <目标>  查询域推断结果

🎯 collect 是一通百通核心命令：
   python cli.py collect 北京大学          # 自动推断 pku.edu.cn → 全源采集
   python cli.py collect 阿里巴巴          # 自动推断 alibaba.com → 全源采集
   python cli.py collect --domain whu.edu.cn 武汉大学  # 手动指定域名
   python cli.py collect --sources crt.sh,hackertarget 北京大学  # 指定数据源
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保根目录在 sys.path，便于直接 import passive_agent
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from passive_agent.common.result import ok  # noqa: F401 (CLI 内部可用)
from passive_agent.storage import db


def _ensure() -> None:
    db.ensure_init()


def cmd_audit_queue(args) -> None:
    _ensure()
    rows = db.query(
        "SELECT ts, action, source, decision, reason_code, msg FROM t_audit_log "
        "WHERE deleted=0 ORDER BY id DESC LIMIT ?",
        (args.limit,),
    )
    for r in rows:
        print(f"[{r['ts']}] {r['decision']} {r['action']} "
              f"src={r['source']} code={r['reason_code']} :: {r['msg']}")
    print(f"--- 共 {len(rows)} 条 ---")


def cmd_resume(args) -> None:
    _ensure()
    from passive_agent.approval.snapshot import SnapshotStore

    snap = SnapshotStore()
    res = snap.load(args.task_id)
    if not res:
        print(f"无快照：{args.task_id}")
        return
    offset, state = res
    print(json.dumps({"task_id": args.task_id, "offset": offset, "state": state},
                    ensure_ascii=False, indent=2))


def cmd_enumerate(args) -> None:
    _ensure()
    from passive_agent.enumerator.engine import SubjectEnumerator

    subj = SubjectEnumerator().enumerate(args.enterprise, max_depth=args.depth)
    print(f"企业={subj.enterprise} 主体数={len(subj.subjects)} max_depth={subj.max_depth}")
    for s in subj.subjects:
        print(f"  - [L{s.depth}] {s.relation}: {s.name}")


def cmd_submit_status(args) -> None:
    _ensure()
    from passive_agent.gateway.proxy import ApiProxy

    q = ApiProxy().quota(args.ip)
    print(json.dumps(q.model_dump(), ensure_ascii=False, indent=2))


def cmd_compliance_status(args) -> None:
    _ensure()
    from passive_agent.common.compliance_client import check
    from passive_agent.common.enums import ActionType
    from passive_agent.compliance.engine import get_engine

    eng = get_engine()
    print(json.dumps({"fail_closed": True, "rules_count": len(eng._rules)},
                    ensure_ascii=False, indent=2))
    # 演示主动动作拦截（fail-closed）
    d = check(ActionType.ACTIVE_SCAN, source_name="cli-demo")
    print(f"主动动作 ACTIVE_SCAN -> allowed={d.allowed} "
          f"decision={d.decision.value} code={d.reason_code}")


def cmd_inventory_export(args) -> None:
    _ensure()
    from passive_agent.inventory.registry import InventoryRegistry

    reg = InventoryRegistry()
    proof = reg.export_proof()
    if args.path:
        reg.export_json(args.path)
        print(f"台账已导出：{args.path}")
    print(json.dumps(proof.model_dump(), ensure_ascii=False, indent=2))


def cmd_collect(args) -> None:
    """一通百通：任意目标 → 自动推断域名 → 全源采集。"""
    _ensure()
    from passive_agent.collector.domain_db import infer_domain, list_known_universities, list_known_enterprises
    from passive_agent.collector.manager import CollectorManager

    target = args.name
    domain = args.domain or ""
    sources = args.sources.split(",") if args.sources else None

    # 显示域推断结果
    if not domain:
        domain = infer_domain(target)
        print(f"🎯 目标: {target}")
        print(f"🌐 自动推断域名: {domain}")
        print()

    # 压制 JSON 日志输出，保证终端输出干净的人类可读报告
    from passive_agent.common.logging import SUPPRESS_CLI_OUTPUT
    import passive_agent.common.logging as _clog
    _clog.SUPPRESS_CLI_OUTPUT = True

    print(f"⏳ 正在采集，请稍候...")
    mgr = CollectorManager()
    report = mgr.collect(name=target, domain=domain, enabled_sources=sources)

    # 恢复日志输出
    _clog.SUPPRESS_CLI_OUTPUT = False

    # 输出报告
    print(report.to_table())
    print(f"\n📊 执行时间: {report.completed_at}")

    # 修复：将"采集错误"重命名为"风险发现"
    risk_items = [e for e in report.errors if "🔴" in e or "P0" in e or "P1" in e or "P2" in e]
    if risk_items:
        print(f"\n🚨 发现 {len(risk_items)} 个安全风险:")
        for e in risk_items[:5]:
            print(f"   - {e}")

    # 落库
    stored = 0
    for r in report.records:
        try:
            db.write(
                "INSERT OR IGNORE INTO t_collect_asset "
                "(enterprise, domain, asset_value, asset_type, source_name, ip, port, tech_stack, title, tags) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    report.enterprise, report.domain,
                    r.value, r.asset_type.value, r.source.value,
                    r.ip, r.port,
                    json.dumps(r.tech_stack, ensure_ascii=False),
                    r.title, json.dumps(r.tags, ensure_ascii=False),
                ),
            )
            stored += 1
        except Exception as exc:
            print(f"  落库异常: {exc}")
    print(f"💾 已落库 {stored}/{len(report.records)} 条资产到 t_collect_asset")

    # 自动保存 Markdown 报告
    from pathlib import Path
    report_dir = Path("data")
    report_dir.mkdir(exist_ok=True)
    safe_name = target.replace(" ", "_").replace("/", "_")
    report_path = report_dir / f"report_{safe_name}_{domain}.md"
    report_path.write_text(report.to_table(), encoding="utf-8")
    print(f"📝 报告已保存: {report_path}")

    # Excel 导出
    if args.export:
        from passive_agent.collector.model import CollectReport
        mgr.export_to_excel(report, args.export)
        print(f"📁 Excel 已导出: {args.export}")

    # 下一步提示
    print(f"\n💡 试试：python cli.py inventory-export 导出资产清单")


def cmd_import_path(args) -> None:
    """从已有资产目录/文件导入种子数据（通用版，不限 FAFU）。"""
    _ensure()
    from passive_agent.collector.manager import CollectorManager

    mgr = CollectorManager()
    report = mgr.import_from_dir(
        path=args.path,
        enterprise=args.enterprise or "",
        domain=args.domain or "",
    )
    print(report.to_table())

    # 落库
    count = 0
    for r in report.records:
        try:
            db.write(
                "INSERT OR IGNORE INTO t_collect_asset "
                "(enterprise, domain, asset_value, asset_type, source_name, ip, tags) "
                "VALUES (?,?,?,?,?,?,?)",
                (report.enterprise, report.domain,
                 r.value, r.asset_type.value, r.source.value,
                 r.ip or "", json.dumps(r.tags, ensure_ascii=False)),
            )
            count += 1
        except Exception:
            pass
    print(f"✅ 已导入 {count} 条种子资产到 t_collect_asset")


def cmd_batch(args) -> None:
    """批量采集：文件每行一个目标，自动并行执行。"""
    _ensure()
    from passive_agent.collector.domain_db import infer_domain
    from passive_agent.collector.manager import CollectorManager

    with open(args.file, "r", encoding="utf-8") as fh:
        targets = [line.strip() for line in fh if line.strip()]

    print(f"📋 批量模式: {len(targets)} 个目标")
    print(f"   数据源: {args.sources or '全部'}")
    print()

    mgr = CollectorManager()
    results = []
    for i, target in enumerate(targets, 1):
        domain = args.domain or ""
        if not domain:
            domain = infer_domain(target)
        print(f"[{i}/{len(targets)}] {target} → {domain}")
        report = mgr.collect(name=target, domain=domain,
                             enabled_sources=args.sources.split(",") if args.sources else None)
        results.append(report)
        print(f"  → {report.total_records} 条资产\n")

    # 汇总
    total = sum(r.total_records for r in results)
    print(f"📊 批量完成: {len(results)} 个目标, 共 {total} 条资产")

    # 可选导出汇总Excel
    if args.export:
        mgr2 = CollectorManager()
        merged = CollectReport(enterprise="批量报告", domain="")
        for r in results:
            merged.merge(r)
        mgr2.export_to_excel(merged, args.export)
        print(f"📁 已导出: {args.export}")


def cmd_list_sources(args) -> None:
    """列出所有可用被动数据源。"""
    from passive_agent.collector.manager import SUPPORTED_SOURCES
    from passive_agent.config import settings

    print("📡 可用被动数据源:")
    print(f"{'名称':<20} {'说明':<35} {'状态':<10}")
    print("-" * 65)
    for name, desc in SUPPORTED_SOURCES.items():
        api_keys = getattr(settings, "API_KEYS", {})
        needs_key = name in ("hunter", "securitytrails", "fofa")
        if name == "fofa":
            has_key = bool(api_keys.get("fofa", ""))
            status = "✅ 已配置" if has_key else "⏳ 需配置email+Key"
        elif needs_key:
            has_key = bool(api_keys.get(name, ""))
            status = "✅ 已配置" if has_key else "⏳ 需配置Key"
        else:
            status = "✅ 免凭证"
        print(f"{name:<20} {desc:<35} {status:<10}")


def cmd_diff(args) -> None:
    """资产变化追踪：对比两次采集结果。"""
    _ensure()
    from passive_agent.collector.sources import diff_reports
    from passive_agent.collector.model import CollectReport
    from passive_agent.collector.manager import CollectorManager

    old_report = CollectorManager().import_from_dir(args.old_dir, args.name, args.domain)
    new_report = CollectorManager().import_from_dir(args.new_dir, args.name, args.domain)
    result = diff_reports(old_report, new_report)

    print(f"\n📊 资产变化追踪: {args.name}")
    print(f"  {"旧数据":12s}: {result['old_total']} 条 ({args.old_dir})")
    print(f"  {"新数据":12s}: {result['new_total']} 条 ({args.new_dir})")
    print(f"  {"新增":12s}: {result['added_count']} 条")
    print(f"  {"消失":12s}: {result['removed_count']} 条")
    if result['added']:
        print(f"\n  🆕 新增资产 ({result['added_count']}):")
        for r in result['added'][:10]:
            print(f"    + {r.value} ({r.asset_type.value}) [{r.source.value}]")
        if result['added_count'] > 10:
            print(f"    ... 还有 {result['added_count'] - 10} 条")
    if result['removed']:
        print(f"\n  ❌ 消失资产 ({result['removed_count']}):")
        for r in result['removed'][:10]:
            print(f"    - {r.value}")
        if result['removed_count'] > 10:
            print(f"    ... 还有 {result['removed_count'] - 10} 条")


def cmd_icp(args) -> None:
    """ICP备案查询。"""
    from passive_agent.collector.sources import IcpCollector
    collector = IcpCollector()
    records = collector.collect(args.domain)
    if records:
        print(f"\n📜 ICP备案信息: {args.domain}")
        for r in records:
            print(f"  {r.value}")
            if r.source_extra:
                print(f"  {r.source_extra}")
    else:
        print(f"\n❌ 未查到 {args.domain} 的ICP备案信息")
        print("   (工信部备案系统可能屏蔽了自动化查询)")
        print(f"   手动查询: https://beian.miit.gov.cn/")


def cmd_serve(args) -> None:
    """🚀 一键启动 Web 面板。"""
    print("🚀 启动 Web 面板...")
    print(f"   地址: http://{args.host}:{args.port}")
    print(f"   文档: http://{args.host}:{args.port}/docs")
    print()
    import uvicorn
    uvicorn.run("passive_agent.main:app", host=args.host, port=args.port, reload=args.reload)


def cmd_schedule(args) -> None:
    """⏰ 定时自动采集。"""
    _ensure()
    from passive_agent.scheduler import load_targets, run_once, show_status, DailyScheduler

    if args.status:
        show_status()
        return

    if not args.targets:
        print("❌ 请指定目标列表文件：--targets targets.txt")
        print("   格式：每行一个目标，支持 名称,域名 或 名称（自动推断域名）")
        return

    targets = load_targets(args.targets)
    if not targets:
        print(f"❌ 目标文件为空或格式错误: {args.targets}")
        return

    if args.once:
        run_once(targets, verbose=True)
    else:
        scheduler = DailyScheduler(targets, hour=args.hour, minute=args.minute)
        scheduler.start(block=True)


def cmd_domain_info(args) -> None:
    """查询任意目标的域推断结果。"""
    from passive_agent.collector.domain_db import (
        infer_domain,
        list_known_universities,
        list_known_enterprises,
        verify_domain_alive,
    )

    target = args.name
    domain = infer_domain(target)
    alive = verify_domain_alive(domain)

    print(f"🎯 目标: {target}")
    print(f"   ├─ 推断域名: {domain}")
    print(f"   ├─ DNS 可达: {'✅ 是' if alive else '❌ 否'}")
    print(f"   └─ 来源: ", end="")

    # 判断是精确匹配还是算法推算
    if target in list_known_universities():
        print(f"高校知识库精确匹配")
    elif target in list_known_enterprises():
        print(f"企业知识库精确匹配")
    elif "大学" in target or "学院" in target:
        print(f"高校算法推算（拼音首字母 + .edu.cn）")
    else:
        print(f"企业算法推算（拼音首字母 + .com）")


# ═══════════════════════════════════════════
#  企查查 新命令
# ═══════════════════════════════════════════


def cmd_qichacha_detail(args) -> None:
    """企查查 企业工商详情查询。"""
    _ensure()
    from passive_agent.collector.sources import QichachaCollector
    from passive_agent.config import settings

    api_keys = settings.API_KEYS.get("qichacha", {})
    qc = QichachaCollector(api_key=api_keys)
    if not qc.is_available():
        print("❌ 企查查 API Key 未配置")
        return

    result = qc.get_business_detail(args.keyword)
    if "error" in result:
        print(f"❌ 查询失败: {result['error']}")
        return

    print(f"\n🏢 企业工商详情: {result.get('Name', '')}")
    print(f"  {'信用代码':12s}: {result.get('CreditCode','')}")
    print(f"  {'法人代表':12s}: {result.get('OperName','')}")
    print(f"  {'注册资本':12s}: {result.get('RegistCapi','')} {result.get('RegisteredCapitalUnit','')}")
    print(f"  {'成立日期':12s}: {result.get('StartDate','')}")
    print(f"  {'登记状态':12s}: {result.get('Status','')}")
    print(f"  {'登记机关':12s}: {result.get('BelongOrg','')}")
    print(f"  {'企业类型':12s}: {result.get('EconKind','')}")
    print(f"  {'地址':12s}: {result.get('Address','')}")
    print(f"  {'经营范围':12s}: {(result.get('Scope','') or '')[:100]}")
    print(f"  {'联系电话':12s}: {result.get('ContactInfo',{}).get('PhoneNumber','')}")
    print(f"  {'邮箱':12s}: {result.get('ContactInfo',{}).get('Email','')}")
    print(f"  {'人员规模':12s}: {result.get('PersonScope','')}")
    print(f"  {'参保人数':12s}: {result.get('InsuredCount','')}")

    partners = result.get('Partners', [])
    if partners:
        print(f"  \n  股东信息 ({len(partners)}):")
        for p in partners[:5]:
            print(f"    - {p.get('StockName','')} {p.get('StockPercent','')}")

    branches = result.get('Branches', [])
    if branches:
        print(f"  \n  分支机构 ({len(branches)}):")
        for b in branches[:5]:
            print(f"    - {b.get('Name','')}")

    websites = result.get('ContactInfo', {}).get('WebSite', [])
    if websites:
        print(f"  \n  官网:")
        for w in websites[:3]:
            print(f"    - {w.get('Url','')}")


def cmd_qichacha_verify2(args) -> None:
    """企查查 企业二要素核验。"""
    _ensure()
    from passive_agent.collector.sources import QichachaCollector
    from passive_agent.config import settings

    api_keys = settings.API_KEYS.get("qichacha", {})
    qc = QichachaCollector(api_key=api_keys)
    if not qc.is_available():
        print("❌ 企查查 API Key 未配置")
        return

    result = qc.verify_two_element(args.credit_code, args.verify_name, args.verify_type)
    if "error" in result:
        print(f"❌ 核验失败: {result['error']}")
        return

    v = result.get("VerifyResult", -1)
    msg_map = {0: "❌ 公司编号有误", 1: "✅ 一致", 2: "❌ 不一致"}
    print(f"\n二要素核验结果: {msg_map.get(v, f'未知({v})')}")


def cmd_qichacha_verify3(args) -> None:
    """企查查 企业三要素核验。"""
    _ensure()
    from passive_agent.collector.sources import QichachaCollector
    from passive_agent.config import settings

    api_keys = settings.API_KEYS.get("qichacha", {})
    qc = QichachaCollector(api_key=api_keys)
    if not qc.is_available():
        print("❌ 企查查 API Key 未配置")
        return

    result = qc.verify_three_element(args.credit_code, args.company_name, args.oper_name)
    if "error" in result:
        print(f"❌ 核验失败: {result['error']}")
        return

    v = result.get("VerifyResult", -1)
    msg_map = {0: "❌ 公司编号有误", 1: "✅ 三者一致",
               2: "❌ 企业名称不一致", 3: "❌ 法定代表人名称不一致"}
    print(f"\n三要素核验结果: {msg_map.get(v, f'未知({v})')}")


def cmd_export(args) -> None:
    """导出资产数据（JSON / CSV），便于其他工具消费。"""
    _ensure()
    from passive_agent.storage import db
    import json, csv, sys
    from pathlib import Path

    # 查询资产表
    rows = db.query(
        "SELECT enterprise, domain, asset_value, asset_type, source_name, "
        "ip, port, title, tags FROM t_collect_asset "
        "ORDER BY id DESC"
    )

    if not rows:
        print("📭 暂无资产数据。先运行 `python cli.py collect <target>` 采集。")
        return

    output = args.output or sys.stdout
    close = False
    if isinstance(output, str):
        output = open(output, "w", encoding="utf-8")
        close = True

    try:
        if args.format == "json":
            assets = []
            for r in rows:
                assets.append({
                    "enterprise": r["enterprise"],
                    "domain": r["domain"],
                    "asset": r["asset_value"],
                    "type": r["asset_type"],
                    "source": r["source_name"],
                    "ip": r["ip"],
                    "port": r["port"],
                    "title": r["title"],
                    "tags": r["tags"],
                })
            json.dump(assets, output, ensure_ascii=False, indent=2)
            print(f"✅ 已导出 {len(assets)} 条资产 (JSON)")

        elif args.format == "csv":
            writer = csv.writer(output)
            writer.writerow(["enterprise", "domain", "asset", "type", "source", "ip", "port", "title", "tags"])
            for r in rows:
                writer.writerow([
                    r["enterprise"], r["domain"], r["asset_value"],
                    r["asset_type"], r["source_name"], r["ip"],
                    r["port"], r["title"], r["tags"],
                ])
            print(f"✅ 已导出 {len(rows)} 条资产 (CSV)")

        elif args.format == "markdown":
            print(f"# 资产导出 ({len(rows)} 条)")
            print()
            print(f"| 企业 | 域名 | 资产 | 类型 | 数据源 | IP | 端口 |")
            print(f"|------|------|------|------|--------|----|------|")
            for r in rows:
                print(f"| {r['enterprise']} | {r['domain']} | {r['asset_value']} | {r['asset_type']} | {r['source_name']} | {r['ip'] or ''} | {r['port'] or ''} |")

    finally:
        if close:
            output.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli.py", description="Passive Recon — Enterprise OSINT/EASM/CTEM CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("audit-queue", help="View compliance audit queue")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_audit_queue)

    sp = sub.add_parser("resume", help="Resume task from snapshot")
    sp.add_argument("task_id")
    sp.set_defaults(func=cmd_resume)

    sp = sub.add_parser("enumerate", help="Full subject enumeration")
    sp.add_argument("enterprise")
    sp.add_argument("--depth", type=int, default=3)
    sp.set_defaults(func=cmd_enumerate)

    sp = sub.add_parser("submit-status", help="Rate limit / submission status")
    sp.add_argument("--ip", default="127.0.0.1")
    sp.set_defaults(func=cmd_submit_status)

    sp = sub.add_parser("compliance-status", help="Compliance dashboard")
    sp.set_defaults(func=cmd_compliance_status)

    sp = sub.add_parser("inventory-export", help="Export asset inventory")
    sp.add_argument("--path", default="")
    sp.set_defaults(func=cmd_inventory_export)

    # ⭐ One command to rule them all
    sp = sub.add_parser("collect", help="🎯 One-shot passive asset collection (auto domain inference + 15 sources)")
    sp.add_argument("name", help="Target name: 'Tsinghua University', 'Alibaba', 'pku.edu.cn'...")
    sp.add_argument("--domain", default="", help="Main domain (optional, auto-inferred if omitted)")
    sp.add_argument("--sources", default="", help="Comma-separated sources, default all (crt.sh,hackertarget,otx,urlscan,hunter,...)")
    sp.add_argument("--export", default="", help="Export Excel report path (e.g. report.xlsx)")
    sp.set_defaults(func=cmd_collect)

    # Batch mode
    sp = sub.add_parser("batch", help="📋 Batch collection: one target per line")
    sp.add_argument("file", help="Target list file (one name/domain per line)")
    sp.add_argument("--domain", default="", help="Common domain suffix (optional)")
    sp.add_argument("--sources", default="", help="Comma-separated sources")
    sp.add_argument("--export", default="", help="Export summary Excel")
    sp.set_defaults(func=cmd_batch)

    # Generic import
    sp = sub.add_parser("import-path", help="Import seed data from asset directory/file")
    sp.add_argument("path", help="Directory or file path")
    sp.add_argument("--enterprise", default="", help="Target name (optional, auto-inferred from dir)")
    sp.add_argument("--domain", default="", help="Main domain (optional, auto-inferred)")
    sp.set_defaults(func=cmd_import_path)

    # List sources
    sp = sub.add_parser("list-sources", help="List available passive data sources and status")
    sp.set_defaults(func=cmd_list_sources)

    # Domain info
    sp = sub.add_parser("domain-info", help="Query domain inference result for a target")
    sp.add_argument("name", help="Target name")
    sp.set_defaults(func=cmd_domain_info)

    # ═══ Qichacha commands ═══
    sp = sub.add_parser("qichacha-detail", help="Qichacha enterprise detail query")
    sp.add_argument("keyword", help="Unified social credit code / enterprise name")
    sp.set_defaults(func=cmd_qichacha_detail)

    sp = sub.add_parser("qichacha-verify2", help="Qichacha 2-factor verification")
    sp.add_argument("credit_code", help="Unified social credit code")
    sp.add_argument("verify_name", help="Verification name (enterprise or legal person)")
    sp.add_argument("--verify-type", default="1", choices=["1","2"],
                    help="1=verify enterprise name 2=verify legal person name")
    sp.set_defaults(func=cmd_qichacha_verify2)

    sp = sub.add_parser("qichacha-verify3", help="Qichacha 3-factor verification")
    sp.add_argument("credit_code", help="Unified social credit code")
    sp.add_argument("company_name", help="Enterprise name")
    sp.add_argument("oper_name", help="Legal representative name")
    sp.set_defaults(func=cmd_qichacha_verify3)

    # Asset diff
    sp = sub.add_parser("diff", help="📊 Asset change tracking: compare two collection results")
    sp.add_argument("name", help="Target name")
    sp.add_argument("old_dir", help="Old data directory")
    sp.add_argument("new_dir", help="New data directory")
    sp.add_argument("--domain", default="", help="Main domain")
    sp.set_defaults(func=cmd_diff)

    # ICP lookup
    sp = sub.add_parser("icp", help="📜 Chinese ICP filing lookup")
    sp.add_argument("domain", help="Domain name")
    sp.set_defaults(func=cmd_icp)

    # Web dashboard
    sp = sub.add_parser("serve", help="🚀 Start web dashboard")
    sp.add_argument("--host", default="127.0.0.1", help="Listen address (default: 127.0.0.1)")
    sp.add_argument("--port", type=int, default=8000, help="Listen port (default: 8000)")
    sp.add_argument("--reload", action="store_true", help="Hot reload (dev mode)")
    sp.set_defaults(func=cmd_serve)

    # Schedule
    sp = sub.add_parser("schedule", help="⏰ Scheduled daily auto-collection")
    sp.add_argument("--targets", default="", help="Target list file (one per line)")
    sp.add_argument("--once", action="store_true", help="Run once immediately, no loop")
    sp.add_argument("--status", action="store_true", help="View schedule status")
    sp.add_argument("--hour", type=int, default=2, help="Execution hour (default: 2=2AM)")
    sp.add_argument("--minute", type=int, default=0, help="Execution minute (default: 0)")
    sp.set_defaults(func=cmd_schedule)

    # Export
    sp = sub.add_parser("export", help="📤 Export asset data (JSON/CSV/Markdown) for other tools")
    sp.add_argument("--format", default="json", choices=["json", "csv", "markdown"], help="Output format (default: json)")
    sp.add_argument("--output", default="", help="Output file path (default: stdout)")
    sp.set_defaults(func=cmd_export)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
