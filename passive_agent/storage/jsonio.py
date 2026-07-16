"""JSON 文件读写（R3 主体清单 / R5 台账导出 / 留档）。"""
from __future__ import annotations

import json
import os
from typing import Any


def write_json(path: str, obj: Any) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_subjects(subj: Any, path: str) -> None:
    """导出主体清单 JSON（供采集集群分发 / 本战役 mock 采集用）。"""
    payload = subj.model_dump() if hasattr(subj, "model_dump") else subj
    write_json(path, payload)
