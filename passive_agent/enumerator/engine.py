"""R3 全主体枚举 / 股权穿透引擎（蓝图 T06）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from passive_agent.common import logging as elog
from passive_agent.enumerator.adapter import PassiveSourceAdapter
from passive_agent.enumerator.model import SubjectList, TargetSubject
from passive_agent.storage import db

_logger = elog.get_logger("enumerator")


class SubjectEnumerator:
    def __init__(self, adapter: PassiveSourceAdapter | None = None,
                 max_depth: int | None = None) -> None:
        self.adapter = adapter or PassiveSourceAdapter()
        self.max_depth = max_depth  # 默认 None → 使用 config.MAX_ENUM_DEPTH

    def enumerate(self, enterprise: str, max_depth: int | None = None) -> SubjectList:
        # 穿透层数：参数 > 实例默认 > 配置（≥3）
        from passive_agent.config import settings

        depth = max_depth if max_depth is not None else self.max_depth
        if depth is None:
            depth = settings.MAX_ENUM_DEPTH
        depth = max(int(depth), settings.MAX_ENUM_DEPTH)

        subjects: List[TargetSubject] = self.adapter.query_relations(enterprise, depth)
        subj_list = SubjectList(
            enterprise=enterprise,
            max_depth=depth,
            subjects=subjects,
            exported_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            for s in subjects:
                # F-6：敏感字段（企业名/法人姓名/credit_code）经 pii 加密后落库
                db.insert_subject(enterprise, s.name, s.relation, s.credit_code, s.depth)
        except Exception as exc:
            _logger.error(f"主体落库失败: {exc}")
        return subj_list

    def export(self, subj: SubjectList, path: str) -> None:
        from passive_agent.storage import jsonio

        jsonio.dump_subjects(subj, path)
