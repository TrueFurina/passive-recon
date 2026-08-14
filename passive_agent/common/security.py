"""API 层令牌校验（P1 鉴权，零新增依赖，hmac 常量时间比较）。

令牌仅经环境变量（PASSIVE_API_TOKENS / PASSIVE_API_KEY）注入 settings.API_TOKENS。
fail-closed：缺令牌 / 格式错 / 不匹配 / API_TOKENS 为空 → 一律拒绝（401）。

角色分级（企业版 RBAC）：
- 普通令牌：PASSIVE_API_TOKENS（读/采集/导出）
- 管理员令牌：PASSIVE_ADMIN_TOKENS（+ 审批/合规报表/敏感操作）
- 令牌支持 "token:admin" 后缀显式声明管理员角色（可选，与独立列表并存）

V-P1-8/9：令牌比较用 hmac.compare_digest，防时序侧信道。
"""
from __future__ import annotations

import hmac
import os
from typing import List, Optional, Tuple

from passive_agent.config import settings


class AuthError(Exception):
    """鉴权失败异常；由 main 注册为 401 handler 返回 040001。"""

    code = "040001"


class PermissionDenied(Exception):
    """权限不足异常；由 main 注册为 403 handler。"""

    code = "040003"


def get_valid_tokens() -> List[str]:
    """返回去空白后的有效令牌列表（源自 settings.API_TOKENS）。"""
    return [t.strip() for t in settings.API_TOKENS if t and t.strip()]


def get_admin_tokens() -> List[str]:
    """返回管理员令牌列表（PASSIVE_ADMIN_TOKENS 环境变量 + 显式 :admin 后缀）。"""
    admin: List[str] = []
    # 1) 独立管理员令牌环境变量
    raw = os.environ.get("PASSIVE_ADMIN_TOKENS", "")
    if raw:
        admin.extend(t.strip() for t in raw.split(",") if t.strip())
    # 2) 显式 ":admin" 后缀的普通令牌（保留原始形式，供精确匹配）
    for t in get_valid_tokens():
        if t.endswith(":admin"):
            admin.append(t)
    return admin


def _base_tokens() -> List[str]:
    """基础令牌集合（去掉 :admin 后缀后的普通令牌）。"""
    return [
        t.rsplit(":", 1)[0] if t.endswith(":admin") else t
        for t in get_valid_tokens()
    ]


def _match(raw_token: str, candidates: List[str]) -> bool:
    """常量时间比较令牌是否命中候选列表。"""
    return any(hmac.compare_digest(raw_token, t) for t in candidates)


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
    # 兼容 "token:admin" 显式角色后缀
    supplied_base = supplied.rsplit(":", 1)[0] if supplied.endswith(":admin") else supplied
    return _match(supplied, valid) or _match(supplied_base, valid)


def is_admin_token(raw: Optional[str]) -> bool:
    """判断令牌是否具备管理员角色（RBAC 权限判定）。"""
    if not raw:
        return False
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    supplied = parts[1].strip()
    admins = get_admin_tokens()
    if not admins:
        return False
    # 显式 ":admin" 后缀：base 命中普通令牌即视为管理员
    if supplied.endswith(":admin"):
        base = supplied.rsplit(":", 1)[0]
        return _match(base, _base_tokens())
    return _match(supplied, admins)


def client_from_token(raw: Optional[str]) -> str:
    """审计用：返回令牌指纹（前 8 位），无则 'anonymous'（V-P1-15 后续可用）。"""
    if not raw:
        return "anonymous"
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "anonymous"
    token = parts[1].strip()
    return token[:8] if token else "anonymous"
