"""V-P1-13：纯被动红线静态闸门（guard_passive.scan_path）对 passive_agent/ 零违例。

与 CI 同源（scripts/guard_passive.py），保证「违规=0」可证、可回归。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.guard_passive import scan_path  # noqa: E402


def test_passive_agent_zero_egress_violations():
    """生产树 passive_agent/ 不得出现 verify=False / 裸 httpx/requests 出站 / 原始 socket 发送。"""
    violations = scan_path(str(ROOT / "passive_agent"))
    assert violations == [], "纯被动红线违例:\n" + "\n".join(str(v) for v in violations)
