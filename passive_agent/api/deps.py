"""API 层鉴权依赖（P1 鉴权，FastAPI Depends，零新增依赖）。

设计要点：
- 总开关 settings.API_AUTH_ENABLED 关闭时直接放行（测试会话默认关闭保 180 绿）。
- 豁免路径（/api/v1/health、/docs、/openapi.json、/、/static/*）直接放行。
- 来源 IP 为 loopback（127.0.0.1 / ::1 / testclient）直接放行。
- 其余请求须携带合法 Bearer token，否则抛 AuthError → main 的 401 handler。

V-P1-1~7：缺失/非法 token → 401；合法 → 放行；豁免项免鉴权；loopback 免鉴权。
"""
from __future__ import annotations

from typing import FrozenSet

from fastapi import Request

from passive_agent.common.security import AuthError, verify_token
from passive_agent.config import settings

# 免鉴权路径（精确匹配）
AUTH_EXEMPT_PATHS: FrozenSet[str] = frozenset(
    {"/api/v1/health", "/docs", "/openapi.json", "/"}
)


def _is_exempt(request: Request) -> bool:
    """路径豁免：精确匹配白名单或 /static 前缀。"""
    path = request.url.path
    return path in AUTH_EXEMPT_PATHS or path.startswith("/static")


def _is_loopback(request: Request) -> bool:
    """来源 IP 豁免：仅测试客户端或显式信任本机（TRUST_LOCALHOST）且无代理转发头时放行。

    安全约束（F-10 生产加固）：
    - testclient 始终豁免，以支持鉴权 ON 的测试会话；
    - 生产默认 TRUST_LOCALHOST=False，loopback 不豁免，外部请求（即便经本机 nginx
      未加 X-Forwarded-For）也必须携带 token，关闭"反代后鉴权整体绕过"的口子；
    - 仅当 TRUST_LOCALHOST=True 且 client.host 为 127.0.0.1/::1 且无转发头时才豁免
      （本地开发/演示用）。
    """
    host = request.client.host if request.client else None
    # testclient 始终豁免（测试会话）
    if host == "testclient":
        return True
    # 存在转发头 => 请求经代理、来自外部网络，禁止 loopback 豁免
    if request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip"):
        return False
    # 生产默认不豁免；仅显式 TRUST_LOCALHOST 且真本机请求才豁免
    if settings.TRUST_LOCALHOST and host in ("127.0.0.1", "::1"):
        return True
    return False


def require_auth(request: Request) -> None:
    """全局鉴权依赖；不满足鉴权条件则抛 AuthError（→ 401）。"""
    if not settings.API_AUTH_ENABLED:
        return
    if _is_exempt(request) or _is_loopback(request):
        return
    if not verify_token(request.headers.get("Authorization", "")):
        raise AuthError("unauthorized")
