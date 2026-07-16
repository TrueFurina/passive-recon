# PRD · Phase 1「上线加固」

> 文档类型：简单 PRD（默认模式）
> 产出角色：产品经理（许清楚）
> 日期：2026-07-13
> 关联阶段：Phase 1 上线加固（仅加固 + 补测，不引入 P2 新功能）
> 落盘路径：`deliverables/product-strategy/prd-phase1-hardening-2026-07-13.md`

---

## 1. 项目信息

| 项 | 内容 |
|---|---|
| Language | 简体中文 |
| Programming Language | Python 3.13 + FastAPI + uvicorn + pydantic + pydantic-settings + dnspython（仅解析）+ httpx + pytest + SQLite/JSON。**不引入** MySQL/Redis/Neo4j/RabbitMQ/React/Node/celery/apscheduler/LLM 推理/任何新依赖 |
| Project Name | `prd_phase1_hardening` |
| 仓库根 | `E:\Program\DBAPPSecurity Ltd\Passive information collection Agent for enterprises` |
| 核心包 | `passive_agent/`（76 个 .py） |
| 原始需求复述 | 将晚间上线前全检的 **No-Go** 翻成 **Go**：补齐 P0 全 API 无鉴权、消除 FAFU 主动探测违例、修复 R6 频控两处设计层边界、补上 HTTP/API 层与频控消费侧测试缺口；全程维持纯被动红线（违规=0/封禁=0）与 180/180 测试全绿，不扩大范围。 |

---

## 2. 产品定义

### 2.1 Product Goals（3 个，清晰且正交）

1. **翻 Go**：关闭上线前全检全部 No-Go 项（P0-1 鉴权、P0-2 FAFU 违例），使发布判定的阻塞项归零。
2. **保红线**：FAFU 整改后纯被动红线 100% 成立——任何出站必经 `passive_agent/common/compliance_client.py::check()`（fail-closed），频控使用率 ≤95% 不变，DNS 仅 `resolver.resolve` 无 socket 出站。
3. **守基线**：不引入新依赖/新功能；180/180 既有测试保持全绿，新增 API 层与频控消费侧测试全绿。

### 2.2 User Stories

- **US-1（内部编排脚本）**：As an internal orchestration script, I want to call `/api/v1/gateway/submit`、`/api/v1/console/run-company`、`/api/v1/approval/decide` etc. only with a valid Bearer Token, so that anonymous callers are rejected and only authorized actors can trigger collection.
- **US-2（安全审计员）**：As a security auditor, I want every egress action to still pass through `compliance_client.check()` and be audited, so that "violations=0" holds after FAFU remediation.
- **US-3（运维）**：As an operator, I want rate-limit usage to never exceed 95.0% under any capacity config, and queued requests to be genuinely consumed/retried, so that we never trip upstream throttling or drop tasks.
- **US-4（QA）**：As QA, I want HTTP/API-layer automated tests (TestClient) covering auth reject/allow and key endpoints, so that the "no-auth" P0 gap becomes visible and regressable.
- **US-5（主理人）**：As the team lead, I want Phase 1 to do hardening + test-fill only, with no new features/dependencies, so that the launch scope stays controlled and lowest-risk.

---

## 3. 技术规范 · 需求池（V-P1-1 ~ V-P1-17）

> 优先级：P0 = Must（翻 Go 必需）/ P1 = Should / P2 = Nice（仅列后续，不展开）。
> 「关联红线」列标注该验收点与哪条纯被动铁律强相关；无则填「—」。

### 3.1 P0-1 全 API 鉴权

| 编号 | 验收标准 | 测试方法 | 关联红线 |
|---|---|---|---|
| V-P1-1 | 所有受保护端点（见 §4.2 清单，除 `/api/v1/health` 外）在缺失/非法 `Authorization: Bearer <token>` 时返回 **401**；合法 token 返回 2xx。 | 新增 `tests/api/test_auth.py`，用 `fastapi.testclient.TestClient` 以无 token 调 `/api/v1/approval/queue`→401，带合法 Bearer→200。 | — |
| V-P1-2 | 豁免清单精确：无 token 调 `/api/v1/health`=200、`/docs`=200、`/openapi.json`=200、`/`=200、`/static/*`=200；其余 `/api/v1/*` 仍需 token。 | 同上测试文件，对豁免路径断言 200/重定向且不要求 token。 | — |
| V-P1-3 | 令牌经配置注入（`PASSIVE_API_KEY` / `config.json` / env），**不硬编码**进源码；仓库不含明文生产令牌。 | 启动测试：用临时 token 启动 app 并验证鉴权生效；grep 校验源码无明文 token 常量。 | — |
| V-P1-12 | 引入 HTTP/API 层测试（`TestClient`），覆盖 7 个 router 的关键端点（每 router ≥1 个 GET + 关键 POST），全绿。 | 新增 `tests/api/` 目录，端点见 §4.2，断言各端点 401/200 与基本响应结构。 | — |
| V-P1-14 | 回归门禁：本阶段后 `pytest` 全量（180+ 既有 + 新增）全绿；纯被动红线测试（fail-closed 100%、DNS 仅 resolve、频控 ≤95%）保持通过。 | CI 步骤 `pytest -q` 必须 0 失败。 | 纯被动（回归） |

### 3.2 P0-2 FAFU 主动探测违例整改

> 现状核实：`FAFU/fafu_auto_verify.py`（L104、L135 `requests.get(..., verify=False)` + `socket.getaddrinfo` 主动 DNS）、`FAFU/verify_fafu.py`（L34 `requests.get(..., verify=False)`、L54 `requests.post(..., verify=False)` 登录凭据测试）均为**主动出站**且**绕过 `compliance_client`**；二者为比赛工具，**未被 `passive_agent` 包 import**（不在运行时），但存在于仓库即构成纯被动定位风险。

| 编号 | 验收标准 | 测试方法 | 关联红线 |
|---|---|---|---|
| V-P1-5 | FAFU 主动探测代码**移出生产树**：`passive_agent/` 不 import FAFU；发布/构建产物不含 `fafu_auto_verify.py`、`verify_fafu.py`、`fafu_deep_scan.py`。`FAFU/` 整体移至 `archive/competition-artifacts/`（或删除）。 | grep 校验 `passive_agent/` 无 `FAFU` import；构建产物清单校验无上述脚本。 | 纯被动（违规=0） |
| V-P1-6 | 仓库静态闸门：CI / pre-commit 在 production 路径（`passive_agent/`）检测到 `verify=False`、裸 `requests`/`httpx` 出站调用、原始 socket 发送即 **失败**（FAFU 已隔离，不在扫描范围或显式 allowlist）。 | 新增 CI 步骤；反向测试：在 `passive_agent/` 临时放含 `verify=False` 的提交→CI 红（验证后撤回）。 | 纯被动 |
| V-P1-7 | 运行时纯被动断言：静态扫描 `passive_agent/` 全部出站入口仅经 `compliance_client.check()`（及 `dnspython resolver.resolve` 用于 DNS），无任何绕过。 | 新增 `tests/test_passive_egress.py`，遍历源码断言出站入口唯一且经合规关隘。 | 纯被动（fail-closed 100%） |

### 3.3 R6 频控边界（设计层，不阻断 P0 但需消）

> 现状核实：`ratelimiter.py` 中 `usage_pct = used / self.capacity`（用原始 `capacity`，非 `ceil(capacity*0.95)` 的 limit）。capacity=1000 时 limit=950、usage_pct 上限=95.0% 成立；capacity 非 20 倍数（如 1003）时 limit=ceil(952.85)=953、usage_pct=953/1003≈**95.01%** 略越界。`release()` 已定义但**全仓零调用**，队列为纯计数器、永不递减、无重消费；`proxy.py` 仅 `acquire()`，`orchestrator`（collector/sources.py）仅处理上游 429/403，不处理本地「排队」重试。

| 编号 | 验收标准 | 测试方法 | 关联红线 |
|---|---|---|---|
| V-P1-8 | 频控使用率硬上限确保 **≤95.0%**（任意 `RATE_CAPACITY`，含非 20 倍数）。 | 单元测试参数化 capacity∈{1000,1003,1007,1234}；打满后 `usage().usage_pct ≤ 95.0`。实现建议二选一/并用：① `_limit()` 改 `math.floor(capacity*buffer)`；② 配置校验 `RATE_CAPACITY` 为 20 倍数。 | 频控 ≤95% |
| V-P1-9 | 「排队不丢弃」真实可消费：`release()` 被调用使 `used-1`、`queued-1`；新增消费侧测试。 | 新增 `tests/gateway/test_ratelimiter_release.py`：acquire 满 → release → 断言 used/queued 递减；并确认 `proxy`/`orchestrator` 在请求完成后调用 `release()`。 | 排队不丢弃（消费侧） |
| V-P1-10 | 编排层对 429/「排队」返回做最小重试+退避：gateway 返回 `accepted=False`（排队）时，orchestrator 以指数退避重试 N 次（默认 3），不丢任务。 | mock `ApiProxy.submit` 连续返回未接受，断言重试次数与退避间隔；任务最终不丢失。 | 排队不丢弃 |
| V-P1-13 | 网关超压集成测试：用 `TestClient` 模拟超压，断言 401（鉴权）/排队（accepted=False）/重试行为一致。 | 见 V-P1-9、V-P1-10 组合集成用例。 | 频控 ≤95% |

### 3.4 P2 / 后续阶段（仅列，不展开）

| 编号 | 内容 | 阶段 |
|---|---|---|
| V-P1-15 | 每客户端 API Key（key→client_id 映射）以支持审计归因 | Phase 2 |
| V-P1-16 | mTLS / 网络层隔离增强 | Phase 2 |
| V-P1-17 | 面板 Token UI 注入（static 注入 token，替代 loopback 豁免） | Phase 2 |

---

## 4. UI / 接口设计要点

### 4.1 鉴权机制设计（推荐方案）

- **新增 `passive_agent/api/deps.py`**：`require_auth` FastAPI 依赖（或全局中间件 + 路径白名单）。校验 `Authorization: Bearer <token>`，使用 `hmac.compare_digest` 做常量时间比较，避免时序侧信道。
- **新增 `passive_agent/common/security.py`**：token 校验与 client 标识解析。
- **配置项（写入 `config.py`）**：
  - `API_AUTH_ENABLED: bool = True`
  - `API_TOKENS: List[str]`（来自 env `PASSIVE_API_TOKENS`，逗号分隔；或单 `PASSIVE_API_KEY`）
- **401 响应体**（与现有 `result.ok` 风格一致）：`{"ok": false, "error": "unauthorized", "code": "040001"}`。
- **静态面板（static/index.html + app.js）**：Phase 1 推荐 **loopback 豁免**（见 §5 待确认 Q2）——编排层与面板均运行于受控本机，127.0.0.1 请求免 token；非 loopback（跨主机内网访问）强制 Bearer。后续（V-P1-17）可改为向 `static/api-token.js`（gitignored）注入 token。
- **挂载方式**：依赖挂在各 router（`include_router(..., dependencies=[Depends(require_auth)])`），`/health`、`/docs`、`/openapi.json`、`/`、`/static` 不走该依赖。

### 4.2 受保护端点清单（当前 7 router / 20 endpoint，全部需鉴权）

| Router | 端点（均 `/api/v1` 前缀） | 方法 |
|---|---|---|
| compliance | `/compliance/status`、`/compliance/check` | GET / POST |
| approval | `/approval/queue`、`/approval/create`、`/approval/decide`、`/approval/resume` | GET / POST / POST / POST |
| gateway | `/gateway/quota`、`/gateway/submit` | GET / POST |
| inventory | `/inventory/proof`、`/inventory/export` | GET / GET |
| console | `/console/overview`、`/console/run-company`、`/console/metrics-overview` | GET / POST / GET |
| metrics | `/snapshot`、`/war-report`、`/fault-events` | GET / GET / GET |
| graph | `/topology`、`/stats` | GET / GET |

> 注：No-Go 报告称「5 个 router 裸挂」，实际当前 `main.py` 挂载 **7 个 router / 20 个 endpoint** 均无鉴权。本 PRD 鉴权设计覆盖全部 20 个端点，避免遗漏。

### 4.3 纯被动红线保障设计（FAFU 整改后）

- **隔离**：`FAFU/` 整体移出生产树（V-P1-5），消除主动探测/TLS 关闭代码的执行可能。
- **静态闸门（V-P1-6）**：CI 运行 `scripts/guard_passive.py`（AST/字符串扫描），在 `passive_agent/` 出现 `verify=False`、裸 `requests`/`httpx` 出站、原始 socket 发送即失败。
- **运行时断言（V-P1-7）**：测试断言 `passive_agent/` 全部出站入口仅经 `compliance_client.check()` + `dnspython resolver.resolve`，保证「违规=0」可证。
- **频控（V-P1-8/9/10）**：修正 `usage_pct` 计算 + 真实消费 `release()` + 编排层重试退避，维持「频控 ≤95%、排队不丢弃」。

---

## 5. 待确认问题（Open Questions）— 含鉴权选型裁决

### 5.1 鉴权方案选型（关键待确认）

| 候选 | 方案 | 取舍 |
|---|---|---|
| **A（推荐）** | 共享 Bearer API Key（配置注入）+ 中间件/依赖统一校验；豁免 `/health`、`/docs`、`/openapi.json`、`/`、`/static`；**loopback（127.0.0.1）豁免**。 | 最轻量，契合「内部脚本/编排层调用」场景；零新依赖；开发量最小。 |
| B | 每客户端 API Key（key→client_id 映射），用于审计归因 | 归因更强，但需密钥管理；建议 Phase 2（V-P1-15）。 |
| C | 仅靠 mTLS / 网络隔离，无应用层鉴权 | 若主机被网络可达即失效；不推荐单独使用。 |
| D | OAuth2 / JWT | 需 IdP，超出技术栈且不必要；**Phase 1 否决**。 |

**👉 请主理人/用户裁决：选 A（推荐）还是 B？是否接受 loopback 豁免（见 Q2）？**

### 5.2 其他待确认

- **Q2**：loopback（127.0.0.1）是否豁免鉴权？**推荐豁免**（面板/编排本机运行）。若组织要求即便 loopback 也需 token，则改 B 或启用 V-P1-17 面板 token 注入。
- **Q3**：FAFU 最终处置——删除还是归档到 `archive/competition-artifacts/`（保留比赛材料）？**推荐隔离归档 + 加闸门**；最终删除与否为政策项，不阻断 Phase 1 隔离动作。
- **Q4**：生产 `RATE_CAPACITY` 取值——保持 1000（20 倍数）或他值？floor 修复（V-P1-8）已保证 ≤95%，仍建议保持 20 倍数便于运维读数。
- **Q5**：生产 `PASSIVE_API_KEY` 由谁提供/托管（env / secrets）？仓库不提交明文。
- **Q6**：是否需在 Phase 1 即引入每客户端密钥（候选 B）以支持审计归因，还是 Phase 2 再做？

---

## 6. 需用户确认的外部资源（标注「需用户确认」，不阻断本阶段可自主部分）

| 资源 | 对本阶段影响 | 自主推进方式 |
|---|---|---|
| 真实生产 `PASSIVE_API_KEY` 密钥 | 仅影响生产部署，不影响开发与测试 | dev 用占位/测试 token 即可自主完成 V-P1-1/2/3 |
| 生产 `RATE_CAPACITY` / `EGRESS_IPS` 真实值 | 仅影响压测读数，不影响逻辑 | dev 用默认 1000 / 127.0.0.1 推进，V-P1-8 floor 修复已保证达标 |
| FAFU 最终处置政策（删/归档） | 不影响隔离动作 | 先隔离 + 加闸门（V-P1-5/6），最终处置待确认 |
| 部署网络暴露面 | 决定 loopback 豁免是否足够 | 开发先按推荐 A 实现，暴露面确认后微调 |

---

## 7. 验收总览（翻 Go 判定）

- **全部 P0 项（V-P1-1/2/3/5/6/7/8/12/14）关闭** → 上线前全检 No-Go 翻 Go。
- **纯被动红线测试保持通过** → 违规=0 / 封禁=0 成立。
- **180+ 测试全绿 + 新增 API/频控测试全绿** → 质量基线守住。
- **未引入任何新依赖 / 新功能** → 范围可控。
