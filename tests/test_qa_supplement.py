"""QA 补充测试套件（严过关 / Yan）。

独立验证施工蓝图 §5 验收 + PRD 红线，覆盖主理人派发的 10 个验证重点：
  - 红线 #1  R1 主动动作 100% 拦截（BLOCK + 010001 + fail-closed）+ 审计落库
  - 红线 #2  R2 L2 仅 dnspython.resolver.resolve()，无 socket 主动连接（静态）
  - 红线 #3  代码库无 nmap/主动扫描类库 import；全部出站经 compliance_client.check()（静态）
  - 红线 #4  R6 频控硬闸 limit=ceil(capacity*0.95)，超限排队不丢弃（queued>0）
  - 功能 #5  R3 全主体枚举（母+子+分）+ 穿透层数可配置
  - 功能 #6  R2 四层独立开关+计数；L4 ≥2 源 PASS、单源 SUSPEND
  - 功能 #7  R4 三级分流 + HIGH 人工不可跳过 + 断点续跑零丢失
  - 功能 #8  R5 export_proof() 自研占比证明（保命内核全标自研）
  - 功能 #9  T15 run_company() 端到端跑通
  - 功能 #10 T17 压测：违规=0、封禁=0、usage_pct 始终 ≤95%（含 DB 级证据）

所有断言均以 PRD/蓝图 验收条款为准，不改动任何业务源码。
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from passive_agent.approval.model import ApprovalEvent, ApprovalTask
from passive_agent.approval.service import ApprovalService
from passive_agent.approval.snapshot import SnapshotStore
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType, Decision, RiskLevel
from passive_agent.compliance.engine import get_engine
from passive_agent.compliance.model import ComplianceCheckRequest
from passive_agent.enumerator.engine import SubjectEnumerator
from passive_agent.gateway.ip_pool import IpPool
from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.gateway.ratelimiter import RateLimiter
from passive_agent.inventory.registry import InventoryRegistry
from passive_agent.orchestrator.loop import run_company
from passive_agent.storage import db
from passive_agent.verifier.model import VerifyRequest, VerifyStatus
from passive_agent.verifier.pipeline import VerificationPipeline

PKG = Path(__file__).resolve().parent.parent / "passive_agent"

ACTIVE_ACTIONS = [ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND]


# --------------------------------------------------------------------------
# 红线 #1：R1 主动动作 100% 拦截 + fail-closed + 审计
# --------------------------------------------------------------------------
def test_r1_active_actions_blocked_with_audit():
    eng = get_engine()
    for at in ACTIVE_ACTIONS:
        d = eng.check(ComplianceCheckRequest(action_type=at, source_name="qa-r1"))
        assert d.allowed is False
        assert d.decision is Decision.BLOCK
        assert d.reason_code == "010001"
        assert d.rule_hit  # 命中具体规则

    # 审计落库必须记录 BLOCK + 010001
    rows = db.query(
        "SELECT decision, reason_code FROM t_audit_log "
        "WHERE deleted=0 AND action IN ('ACTIVE_SCAN','ACTIVE_HTTP','TCP_SEND')"
    )
    assert len(rows) >= len(ACTIVE_ACTIONS)
    assert all(r["decision"] == "BLOCK" and r["reason_code"] == "010001" for r in rows)


def test_r1_unknown_action_fail_closed():
    d = get_engine().check(ComplianceCheckRequest(
        action_type="TOTALLY_UNKNOWN_ACTION", source_name="qa-r1-unknown"))
    assert d.allowed is False
    assert d.decision is Decision.BLOCK
    assert d.reason_code == "010001"


# --------------------------------------------------------------------------
# 红线 #2 / #3：静态审查（纯被动红线，物理不可达主动探测）
# --------------------------------------------------------------------------
_FORBIDDEN_ACTIVE_MODULES = [
    "nmap", "shodan", "scapy", "paramiko", "masscan", "impacket", "python-nmap",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_static_no_active_scan_imports():
    """代码库不得引入任何可发起主动探测的第三方库。"""
    for f in PKG.rglob("*.py"):
        text = _read(f)
        for mod in _FORBIDDEN_ACTIVE_MODULES:
            hit = re.search(rf"^\s*(import|from)\s+{re.escape(mod)}\b", text, re.M)
            assert hit is None, f"{f.relative_to(PKG)} 引入主动扫描类库: {mod}"


def test_static_no_socket_active_connect():
    """不得出现 socket 直连 / 主动连接解析出的 IP。"""
    for f in PKG.rglob("*.py"):
        text = _read(f)
        assert "socket.connect" not in text, f"{f.relative_to(PKG)} 存在 socket.connect"
        assert "create_connection" not in text, f"{f.relative_to(PKG)} 存在 create_connection"
        assert "shodan" not in text, f"{f.relative_to(PKG)} 存在 shodan"
        assert "scapy" not in text, f"{f.relative_to(PKG)} 存在 scapy"


def test_static_l2_dns_resolve_only():
    """R2 L2 仅 dnspython.resolver.resolve()，绝不对解析 IP 发起连接。

    注：layers.py 文档字符串会提到「socket 连接」以说明红线，但不得存在
    真实的 `import socket` / `socket.connect` / `create_connection` 等主动连接。
    """
    text = _read(PKG / "verifier" / "layers.py")
    assert ("import dns" in text) or ("from dns" in text)
    assert "import socket" not in text, "L2 不得导入 socket 模块"
    assert "socket.connect" not in text, "L2 不得 socket 直连解析 IP"
    assert "socket.create_connection" not in text
    assert "create_connection" not in text, "L2 不得主动建立连接"
    assert ".get(" not in text, "L2 不得存在 httpx/requests 等主动出站"
    assert "requests" not in text


def test_static_egress_routed_through_compliance():
    """全部真实出站模块必须先经 compliance_client.check() 关隘。"""
    for rel in [
        "gateway/proxy.py",
        "enumerator/adapter.py",
        "orchestrator/loop.py",
        "api/routes_compliance.py",
    ]:
        text = _read(PKG / rel)
        assert "compliance_client" in text, f"{rel} 未引用合规客户端"
        assert "check(" in text, f"{rel} 未调用 check() 关隘"


# --------------------------------------------------------------------------
# 红线 #4：R6 频控硬闸 limit=ceil(capacity*0.95)，超限排队不丢弃
# --------------------------------------------------------------------------
def test_r6_limit_formula_and_queue_not_discard():
    from passive_agent.config import settings

    cap = 1000
    ip = "10.0.0.9"
    lim = RateLimiter(capacity=cap, window=100000.0)  # 大窗口避免过期
    for _ in range(cap + 500):
        lim.acquire(ip)

    q = lim.usage(ip)
    expected_limit = math.ceil(cap * settings.FREQ_BUFFER)  # 950
    assert q.limit == expected_limit
    assert q.used == q.limit                     # 使用率硬上限处封顶
    assert q.queued > 0                          # 超限请求排队（不丢弃）
    assert q.usage_pct <= 95.0                   # 硬上限 95%


def test_r6_proxy_queued_flag_reasonable():
    proxy = ApiProxy(limiter=RateLimiter(capacity=100, window=100000.0),
                     pool=IpPool(["127.0.0.1"]))
    # 先打满（limit=95）
    for i in range(200):
        proxy.submit(SubmitProxyRequest(biz_req_no=f"q{i}", batch_id="b",
                                        shard_index=0, shard_total=1, payload={}))
    q = proxy.quota("127.0.0.1")
    assert q.used <= q.limit
    assert q.queued > 0
    # 超限时 accepted=False 且 queued>0（明确告知调用方"已排队、未丢弃"）
    assert q.usage_pct <= 95.0


# --------------------------------------------------------------------------
# 功能 #5：R3 全主体枚举（母+子+分）+ 穿透层数可配置
# --------------------------------------------------------------------------
def test_r3_all_relations_present():
    subj = SubjectEnumerator().enumerate("全主体测试企业", max_depth=3)
    rels = {s.relation for s in subj.subjects}
    assert "目标企业" in rels
    assert "控股子公司" in rels
    assert "分公司" in rels
    assert all(s.depth <= 3 for s in subj.subjects)


def test_r3_depth_configurable():
    e = SubjectEnumerator()
    default = e.enumerate("深度企业")            # 无参 -> 配置默认 3
    deeper = e.enumerate("深度企业", max_depth=5)
    assert default.max_depth == 3
    assert deeper.max_depth == 5
    assert len(deeper.subjects) > len(default.subjects)
    assert all(s.depth <= 5 for s in deeper.subjects)


# --------------------------------------------------------------------------
# 功能 #6：R2 四层独立开关+计数；L4 ≥2 源 PASS、单源 SUSPEND
# --------------------------------------------------------------------------
def test_r2_layer_switch_and_counter():
    p = VerificationPipeline()
    p.set_layer_enabled(4, False)
    vr = p.run(VerifyRequest(result_id="r-l4off", layer1_biz_match=True,
                             layer2_dns_alive=True, layer3_time_ok=True,
                             layer4_src_cnt=1))  # L4 关后单源也应通过
    assert vr.status == VerifyStatus.PASS
    c = p.counters()
    assert c[4] == 0            # 关闭层不计数
    assert c[1] >= 1 and c[2] >= 1 and c[3] >= 1


def test_r2_l4_two_sources_pass():
    p = VerificationPipeline()
    vr = p.run(VerifyRequest(result_id="r-2src", layer1_biz_match=True,
                             layer2_dns_alive=True, layer3_time_ok=True,
                             layer4_src_cnt=2))
    assert vr.status == VerifyStatus.PASS
    assert vr.fail_layer is None


def test_r2_l4_single_source_suspend():
    p = VerificationPipeline()
    vr = p.run(VerifyRequest(result_id="r-1src", layer1_biz_match=True,
                             layer2_dns_alive=True, layer3_time_ok=True,
                             layer4_src_cnt=1))
    assert vr.status == VerifyStatus.SUSPEND
    assert vr.fail_layer == 4


# --------------------------------------------------------------------------
# 功能 #7：R4 三级分流 + HIGH 人工不可跳过 + 断点续跑零丢失
# --------------------------------------------------------------------------
def test_r4_three_tier_routing():
    svc = ApprovalService()
    low = svc.create(ApprovalTask(task_id="AP-low", risk_level=RiskLevel.LOW,
                                  subject_id="x"))
    mid = svc.create(ApprovalTask(task_id="AP-mid", risk_level=RiskLevel.MID,
                                  subject_id="y"))
    high = svc.create(ApprovalTask(task_id="AP-high", risk_level=RiskLevel.HIGH,
                                   subject_id="z"))
    assert low.status == "APPROVED"        # 低危自动入库
    assert mid.status == "REMINDING"       # 中危入库+提醒
    assert high.status == "REVIEWING"      # 高价值人工复核（置顶）


def test_r4_high_not_skippable_by_auto_pass():
    """高价值工控/政务强制人工复核，AUTO_PASS 不得跳过。"""
    svc = ApprovalService()
    svc.create(ApprovalTask(task_id="AP-skip", risk_level=RiskLevel.HIGH,
                            subject_id="某工控集团"))
    updated = svc.decide(ApprovalEvent(task_id="AP-skip", action="AUTO_PASS",
                                       risk_level=RiskLevel.HIGH, operator="bot"))
    assert updated.status == "REVIEWING"


def test_r4_keyword_elevation_to_high():
    svc = ApprovalService()
    t = svc.create(ApprovalTask(task_id="AP-kw", risk_level=RiskLevel.LOW,
                                subject_id="某电网公司"))
    assert t.risk_level == RiskLevel.HIGH
    assert t.status == "REVIEWING"


def test_r4_snapshot_resume_zero_loss():
    snap = SnapshotStore()
    state = {"phase": "collect", "done": 7, "total": 10}
    snap.save("RESUME-1", 7, state)
    res = snap.load("RESUME-1")
    assert res is not None
    offset, loaded = res
    assert offset == 7
    assert loaded == state


# --------------------------------------------------------------------------
# 功能 #8：R5 export_proof() 自研占比证明（保命内核全标自研）
# --------------------------------------------------------------------------
def test_r5_self_dev_proof_kernels():
    reg = InventoryRegistry()
    reg.seed_defaults()
    proof = reg.export_proof()
    self_dev = {t.name for t in proof.tools if t.boundary_tag == "自研"}
    for kernel in [
        "compliance-engine", "verifier-pipeline", "subject-enumerator",
        "api-proxy", "approval-service", "inventory-registry",
    ]:
        assert kernel in self_dev, f"自研内核缺失: {kernel}"
    assert "self_dev_pct" in proof.ratio and "open_source_pct" in proof.ratio
    assert proof.ratio["self_dev_pct"] > 0
    assert proof.ratio["open_source_pct"] > 0


# --------------------------------------------------------------------------
# 功能 #9：T15 run_company() 端到端跑通（mock 被动源）
# --------------------------------------------------------------------------
def test_t15_closed_loop_end_to_end():
    summary = run_company("端到端企业")
    assert summary["blocked"] is False
    assert summary["subjects"] > 0
    assert summary["verified"] > 0
    assert summary["submitted"] > 0
    assert len(summary["approvals"]) == summary["subjects"]


# --------------------------------------------------------------------------
# 功能 #10：T17 压测 —— 违规=0、封禁=0、usage_pct 始终 ≤95%（含 DB 级证据）
# --------------------------------------------------------------------------
def _req(i: int) -> SubmitProxyRequest:
    return SubmitProxyRequest(biz_req_no=f"stress-{i}", batch_id="b",
                              shard_index=0, shard_total=1, payload={})


def test_t17_stress_no_violation_no_ban():
    proxy = ApiProxy(limiter=RateLimiter(capacity=1000, window=100000.0),
                     pool=IpPool(["127.0.0.5"]))
    violations = 0
    bans = 0
    actions = [ActionType.PASSIVE_QUERY, ActionType.PASSIVE_QUERY,
               ActionType.ACTIVE_SCAN, ActionType.ACTIVE_HTTP, ActionType.TCP_SEND]

    for i in range(3000):
        at = actions[i % len(actions)]
        d = check(at, source_name="stress-qa")
        if at in ACTIVE_ACTIONS:
            if d.allowed:                      # 主动动作必须被拦截
                violations += 1
        else:
            if not d.allowed:                  # 被动必须放行
                violations += 1
            else:
                vo = proxy.submit(_req(i))
                # 封禁=0：被动提交要么 accepted 要么 queued（不丢弃），绝不被"封禁丢弃"
                if (not vo.accepted) and vo.quota.queued == 0 and vo.quota.used < vo.quota.limit:
                    bans += 1

    assert violations == 0
    assert bans == 0
    q = proxy.quota("127.0.0.5")
    assert q.usage_pct <= 95.0

    # DB 级红线证据：审计日志中任何主动动作绝不允许被 ALLOW
    rows = db.query(
        "SELECT COUNT(*) AS c FROM t_audit_log "
        "WHERE deleted=0 AND action IN ('ACTIVE_SCAN','ACTIVE_HTTP','TCP_SEND') "
        "AND decision='ALLOW'"
    )
    assert rows[0]["c"] == 0
