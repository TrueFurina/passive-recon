"""R4 三级审批 / 续跑 / 快照。"""
from passive_agent.approval.model import ApprovalEvent, ApprovalTask
from passive_agent.approval.service import ApprovalService
from passive_agent.approval.snapshot import SnapshotStore
from passive_agent.common.enums import RiskLevel


def test_low_auto_pass():
    svc = ApprovalService()
    t = svc.create(ApprovalTask(task_id="AP-low", risk_level=RiskLevel.LOW, subject_id="x"))
    assert t.status == "APPROVED"


def test_mid_reminding():
    svc = ApprovalService()
    t = svc.create(ApprovalTask(task_id="AP-mid", risk_level=RiskLevel.MID, subject_id="y"))
    assert t.status == "REMINDING"


def test_high_reviewing():
    svc = ApprovalService()
    t = svc.create(ApprovalTask(task_id="AP-high", risk_level=RiskLevel.HIGH, subject_id="z"))
    assert t.status == "REVIEWING"
    q = svc.queue()
    assert q[0].risk_level == RiskLevel.HIGH  # 高价值置顶


def test_high_keyword_elevation():
    svc = ApprovalService()
    t = svc.create(ApprovalTask(task_id="AP-kw", risk_level=RiskLevel.LOW,
                               subject_id="某工控公司"))
    assert t.risk_level == RiskLevel.HIGH
    assert t.status == "REVIEWING"


def test_decide_approve():
    svc = ApprovalService()
    svc.create(ApprovalTask(task_id="AP-dec", risk_level=RiskLevel.HIGH, subject_id="w"))
    updated = svc.decide(ApprovalEvent(task_id="AP-dec", action="APPROVE",
                                     risk_level=RiskLevel.HIGH, operator="human"))
    assert updated.status == "APPROVED"


def test_snapshot_resume():
    snap = SnapshotStore()
    snap.save("T1", 42, {"phase": "enumerate", "count": 10})
    res = snap.load("T1")
    assert res is not None
    offset, state = res
    assert offset == 42
    assert state["count"] == 10
