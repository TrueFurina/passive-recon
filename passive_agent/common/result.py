"""统一返回 Result 与 6 位错误码体系（MMCCSS）。

MM=模块域(01合规/02审批/03调度/04规划/05采集/06核验/07图谱/08经验/09日志/10看板/00全局)。
业务失败返回 HTTP 200 + 错误码；系统错误 5xx。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# 6 位错误码注册表
ERROR_CODES: dict[str, str] = {
    "000000": "成功",
    "000001": "系统错误",
    "010001": "主动动作被拦截(fail-closed)",
    "010002": "频控已满，请求排队",
    "020001": "高价值目标需人工复核",
    "020002": "出站被审批闸门拦截(待人工复核/已驳回)",
    "030001": "算力回收",
    "040001": "源不可用(全源挂起)",   # P1 新增：R8 全源不可用
    "040002": "源超时",              # P1 新增：R7 适配器调用超时
    "050001": "全源挂起",
    "060001": "单源挂起",
    "400001": "参数错误",
}


def gen_trace_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Result(BaseModel):
    code: str = "000000"
    msg: str = "OK"
    data: Any = None
    trace_id: str = Field(default_factory=gen_trace_id)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return self.model_dump()


def ok(data: Any = None, trace_id: Optional[str] = None, msg: str = "OK") -> Result:
    # trace_id 为 None 时不显式传入，交由 default_factory 生成（避免 Result 校验 None 为 str 失败）
    if trace_id is None:
        return Result(code="000000", msg=msg, data=data)
    return Result(code="000000", msg=msg, data=data, trace_id=trace_id)


def fail(
    code: str = "000001",
    msg: Optional[str] = None,
    data: Any = None,
    trace_id: Optional[str] = None,
) -> Result:
    if trace_id is None:
        return Result(
            code=code,
            msg=msg or ERROR_CODES.get(code, "未知错误"),
            data=data,
        )
    return Result(
        code=code,
        msg=msg or ERROR_CODES.get(code, "未知错误"),
        data=data,
        trace_id=trace_id,
    )
