"""FastAPI 入口：挂载面板 API + 静态页 + 健康检查（蓝图 T12）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from passive_agent.api.deps import require_auth
from passive_agent.api.routes_approval import router as approval_router
from passive_agent.api.routes_compliance import router as compliance_router
from passive_agent.api.routes_console import router as console_router
from passive_agent.api.routes_gateway import router as gateway_router
from passive_agent.api.routes_inventory import router as inventory_router
from passive_agent.api.routes_metrics import router as metrics_router
from passive_agent.api.routes_graph import router as graph_router
from passive_agent.common.result import ok
from passive_agent.common.security import AuthError
from passive_agent.storage import db

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="企业被动信息搜集 Agent · 最小面板", version="0.1.0")


@app.exception_handler(AuthError)
def _auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    """鉴权失败统一返回 401 体（{ok:false, error, code:040001}）。"""
    return JSONResponse(
        status_code=401,
        content={"ok": False, "error": "unauthorized", "code": "040001"},
    )


app.include_router(compliance_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(approval_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(gateway_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(inventory_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(console_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(metrics_router, prefix="/api/v1", dependencies=[Depends(require_auth)])
app.include_router(graph_router, prefix="/api/v1", dependencies=[Depends(require_auth)])

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup() -> None:
    db.ensure_init()


@app.get("/api/v1/health")
def health():
    return ok({"status": "up"})


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
