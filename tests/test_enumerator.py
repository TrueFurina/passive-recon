"""R3 枚举 / 穿透层 / 导出。"""
import json
import os

from passive_agent.enumerator.engine import SubjectEnumerator


def test_enumerate_returns_subjects():
    subj = SubjectEnumerator().enumerate("示例科技", max_depth=3)
    assert subj.enterprise == "示例科技"
    assert len(subj.subjects) > 0
    assert any(s.relation == "目标企业" for s in subj.subjects)
    # 穿透层数不超过 max_depth
    assert all(s.depth <= 3 for s in subj.subjects)


def test_enumerate_passive_guarded():
    # adapter 内部调用 R1 校验（被动放行）
    subj = SubjectEnumerator().enumerate("甲公司")
    assert subj.max_depth >= 3


def test_export(tmp_path):
    subj = SubjectEnumerator().enumerate("乙公司")
    p = str(tmp_path / "subjects.json")
    SubjectEnumerator().export(subj, p)
    assert os.path.exists(p)
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["enterprise"] == "乙公司"
    assert len(data["subjects"]) == len(subj.subjects)
