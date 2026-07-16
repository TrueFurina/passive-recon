# P0 止血实施进展 · Passive Agent（passive_agent/）

**日期**：2026-07-14
**工作流**：技术债评估（P0 修复落地，由 2026-07-13 全维度体检报告驱动）
**参与成员**：主理人甄宇航（直接落地代码，依据 Cody / Archi / Rex / Tessa / Docu 五人体检结论）

---

## 📌 TL;DR

- 本次新增落地 **P0-6 长任务异步化** 与 **P0-7 频控单例化**，均通过 `py_compile` 语法校验。
- 此前已落地 P0-2（回环绕过）/ P0-3（密钥防回写）/ P0-4（XSS）/ P0-5（采集落库）；P0-1（鉴权接线）实测已过时、无需改。
- **唯一残留人工步骤**：`config.json` 明文密钥的真实轮换（改外部平台 + 移入 `.env`/`PASSIVE_API_KEYS`），AI 不代执行。
- 8 项 🔴 严重阻塞中，代码层可修项已全部止血；剩「审批未真拦截出站」归为非阻塞高优跟进。

---

## ✅ 本次落地（P0-6 / P0-7）

| 项 | 文件 | 改动要点 | 验证 |
|----|------|---------|------|
| P0-6 长任务异步化 | `api/routes_console.py` | `run` 改为 `async`，用 `asyncio.to_thread(run_company, ...)` 派发后台线程，立即返回 `task_id`；新增 `GET /console/run-status/{task_id}` 查询端点；进程内 `_run_tasks` 状态表记录 PENDING/DONE/ERROR | py_compile OK |
| P0-7 频控单例化 | `gateway/ratelimiter.py` | 新增模块级单例 `get_rate_limiter()`（双检锁，线程安全），避免每请求新建实例 | py_compile OK |
| P0-7 频控单例化 | `gateway/proxy.py` | `ApiProxy.__init__` 默认 `limiter = limiter or get_rate_limiter()`，所有 `ApiProxy()` 调用点自动共享同一频控状态 | py_compile OK |

### 改动说明
- **P0-6**：`run_company` 本身是同步重活（多源网络采集 + DB 写入，单企业闭环可达分钟级）。原同步实现会占死一个 worker 线程，并发即耗尽 FastAPI 默认线程池导致网关/客户端超时。改为 `async` 端点 + `asyncio.to_thread` 后，请求线程立即返回，重活在默认线程池执行，不再阻塞事件循环。
- **P0-7**：`ApiProxy()` 在 `routes_console.overview/metrics_overview`、`orchestrator.loop.run_company` 中被反复 `new`，每次都带一个全新的 `RateLimiter`，导致跨请求/跨调用方的频控计数无法累积——全局频控硬闸（≤95% 使用率）实际失效，看板 `quota.usage_pct` 恒为 0。改为进程内单例后，单 worker 内所有请求共享同一频控状态，硬闸真正生效。
- **多 worker 警告**：单例仅覆盖单 worker / 单进程。若以 `--workers N` 多 worker 启动，各 worker 内存态仍独立，频控会再次失效。多 worker 场景须将 `get_rate_limiter()` 替换为 Redis 版（已在部署文档草案标注），或保持单 worker 前置条件。

---

## ✅ 前次已落地（2026-07-13，见会话记录）

| 项 | 文件 | 改动要点 |
|----|------|---------|
| P0-1 鉴权接线 | — | 实测 `main.py` 全部 router 已挂 `Depends(require_auth)`，报告原 🔴#1 已过时，**无需改** |
| P0-2 回环绕过 | `api/deps.py` | `_is_loopback` 增加 `X-Forwarded-For`/`X-Real-IP` 受信头检测，反代后不再整体免鉴权 |
| P0-3 密钥防回写 | `.gitignore` + `config.example.json` | 排除 `config.json`/`data/` 等；提供红acted 配置模板（**真实密钥轮换为人工步骤**） |
| P0-4 前端 XSS | `static/app.js` | `loadQueue`/`runCompany` 由 `innerHTML` 拼接改为 `textContent`+DOM 节点+`addEventListener` |
| P0-5 采集落库 | `orchestrator/loop.py` | 落库改序列化真实采集项（不再写空 `{}`），裸 `except:pass` 改为记录并计入 `summary["errors"]` |

---

## ⚠️ 仍需人工确认

1. **密钥轮换（P0-3 关键）**：`config.json` 中 5 个 Hunter API Key + 企查查 `app_key`/`secret_key` 仍明文存在于版本库历史。须：① 在对应平台轮换并作废旧密钥；② 删除 `config.json`（或加入 `.gitignore` 后 `git rm --cached`）；③ 真实密钥经 `.env` / `PASSIVE_API_KEYS` 环境变量注入；④ 在 CI 增加 gitleaks 类密钥扫描防回写。
2. **多 worker 频控（P0-7 后续）**：如生产用多 worker，须实现 Redis 版频控单例，否则须文档明确保持单 worker。

---

## 📋 非阻塞高优跟进（建议下一轮）

| # | 项 | 来源 | 说明 |
|---|----|------|------|
| 1 | 审批未真拦截出站 | Cody 🟠#6 | `proxy.submit()` 在 `approval.create()` 之前独立执行，HIGH 人工复核不阻断数据出站（网关当前 mock，但架构上审批形同虚设） |
| 2 | 死代码 `collector/adapters.py` | Archi D1 | 被同名包遮蔽成死代码且分叉，改了不生效 |
| 3 | 双重采集引擎收敛 | Archi D6 / Cody #13 | `CollectorManager` 与 `CollectionScheduler` 职责重叠 |
| 4 | 依赖锁定 + pip-audit | Cody 依赖债 | `requirements.txt` 无 `==` 锁定、无 lockfile、无 CVE 扫描 |
| 5 | 循环依赖治理 | Archi D2/D3 | `common↔compliance`、`collector↔enumerator` 靠 20+ 惰性 import 打补丁 |

---

## 📚 数据来源 & 成员产出索引

- 本报告由主理人甄宇航基于 2026-07-13 全维度体检报告（`health-check-passive-agent-2026-07-13.md`）驱动落地
- Cody（代码审查师）原始产出：代码审查报告（鉴权缺失 / XSS / 落库空 / 依赖债）
- Archi（架构师）原始产出：架构债 D1–D10
- Rex（SRE）原始产出：可运维性风险 #1–#15 + 部署前检查要点
- Tessa（测试专家）原始产出：测试覆盖 62% + 测试债清单
- Docu（文档师）原始产出：文档债 19 条 + 部署/回滚文档草案

---

> 本报告由工程保障团队 AI 协作生成，关键决策（尤其密钥轮换、多 worker 频控方案）请由人类工程负责人复核并执行。
