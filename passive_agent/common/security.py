"""API 层令牌校验（P1 鉴权，零新增依赖，hmac 常量时间比较）。

令牌仅经环境变量（PASSIVE_API_TOKENS / PASSIVE_API_KEY）注入 settings.API_TOKENS。
fail-closed：缺令牌 / 格式错 / 不匹配 / API_TOKENS 为空 → 一律拒绝（401）。

V-P1-8/9：令牌比较用 hmac.compare_digest，防时序侧信道。
"""
from __future__ import annotations

import hmac
from typing import List, Optional

from passive_agent.config import settings


class AuthError(Exception):
    """鉴权失败异常；由 main 注册为 401 handler 返回 040001。"""

    code = "040001"


def get_valid_tokens() -> List[str]:
    """返回去空白后的有效令牌列表（源自 settings.API_TOKENS）。"""
    return [t.strip() for t in settings.API_TOKENS if t and t.strip()]


def verify_token(raw: Optional[str]) -> bool:
    """常量时间比较 Bearer token；不满足即 False（fail-closed）。

    解析规则：``Authorization: Bearer <token>``。
    - 无 header / 格式错（非 ``Bearer`` 前缀）/ 令牌不匹配 → False
    - 配置中无任何令牌（API_TOKENS 为空）→ False（fail-closed）
    - 匹配采用 hmac.compare_digest 常量时间比较，避免时序侧信道
    """
    if not raw:
        return False
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    supplied = parts[1].strip()
    valid = get_valid_tokens()
    if not valid:
        return False
    return any(hmac.compare_digest(supplied, t) for t in valid)


def client_from_token(raw: Optional[str]) -> str:
    """审计用：返回令牌指纹（前 8 位），无则 'anonymous'（V-P1-15 后续可用）。"""
    if not raw:
        return "anonymous"
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "anonymous"
    token = parts[1].strip()
    return token[:8] if token else "anonymous"
