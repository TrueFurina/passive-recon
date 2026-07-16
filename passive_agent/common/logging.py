"""结构化 JSON lines 日志封装（固定字段，统一出口，蓝图 §7）。

字段：ts(UTC) / level / module / trace_id / subject_id / action / source /
decision / reason_code / msg。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Optional

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    level: str,
    module: str,
    msg: str,
    trace_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    action: Optional[str] = None,
    source: Optional[str] = None,
    decision: Optional[str] = None,
    reason_code: Optional[str] = None,
) -> dict:
    record = {
        "ts": _now(),
        "level": level,
        "module": module,
        "trace_id": trace_id,
        "subject_id": subject_id,
        "action": action,
        "source": source,
        "decision": decision,
        "reason_code": reason_code,
        "msg": msg,
    }
    line = json.dumps(record, ensure_ascii=False)
    # 全链路透传的结构化日志，输出到 stdout（可被采集/重定向到 LOG_PATH）
    with _LOCK:
        print(line, flush=True)
    return record


class JsonLogger:
    def __init__(self, module: str) -> None:
        self.module = module

    def _emit(self, level: str, msg: str, **kw: Any) -> dict:
        return log_event(level, self.module, msg, **kw)

    def debug(self, msg: str, **kw: Any) -> dict:
        return self._emit("DEBUG", msg, **kw)

    def info(self, msg: str, **kw: Any) -> dict:
        return self._emit("INFO", msg, **kw)

    def warn(self, msg: str, **kw: Any) -> dict:
        return self._emit("WARN", msg, **kw)

    def error(self, msg: str, **kw: Any) -> dict:
        return self._emit("ERROR", msg, **kw)


def get_logger(module: str) -> JsonLogger:
    return JsonLogger(module)
