# 上线前全检报告：被动信息收集 Agent for enterprises

**日期**：2026-07-13
**场景**：上线前检查（代码审查 + 安全审计 + QA 测试）
**参与成员**：产品官（gstack-product-reviewer） + 安全卫士（gstack-security-officer） + 质量门神（gstack-qa-lead，因 429 额度中断，QA 评估由主理人代行）

---

## 📌 TL;DR（执行摘要）

- 整体结论：🔴 **不通过（No-Go）**——当前状态不可上线。
- 阻塞项数量：**2 项 P0**（全 API 无鉴权；FAFU 子模块含主动扫描 + 关闭 TLS 校验，违背"被动-only"产品定位）。
- 正面项：核心 `passive_agent` 无 SQL/命令注入、无硬编码密钥、合规 fail-closed 关隘设计到位、**51/51 测试全过**、L2 确为 DNS-only 被动实现。
- 下一步：先清两项 P0（接入鉴权 + 剔除 FAFU 主动扫描），再补 API 层测试与发布就绪项，复检后方可上线。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🔴 No-Go |
| 严重度分布 | 🔴 2 / 🟠 5 / 🟡 5 / 🟢 4（正面项） |
| 关键行动项 | 9 条 |
| 建议负责人 | 后端工程（鉴权/频控/幂等） + 安全工程（FAFU 剔除/DB 加固） + QA（API 层测试） |

---

## 1. 各成员核心结论

### 🔍 产品官（gstack-product-reviewer · 代码审查 + 工程评审）
- 核心判断：🟡 **需打磨**。架构分层清晰、合规 fail-closed 关隘到位、核心模块有单测；但作为"被动信息收集"安全产品，真实采集能力是 mock、全 API 无鉴权、频控队列语义破损——距真实上线仍有硬伤。
- 关键建议：接入统一 API 鉴权（P0）；修复频控队列语义（`release()` 全代码零调用，超限只计数不重投）；落地真实被动源或明确改为"合规/频控/审批框架"再上线；`run_company` 改后台任务 + 幂等去重。
- 原文判断："任何出站模块复用本函数（fail-closed 关隘）只守了出站、没守入口。"

### 🛡️ 安全卫士（gstack-security-officer · OWASP + STRIDE 审计）
- 核心判断：🔴 **不可上线**。控制面完全无鉴权（P0）；FAFU/ 子模块包含违背"被动-only"红线、并关闭 TLS 校验的主动扫描脚本（P0）。
- 关键建议：所有 `/api/v1` 加鉴权中间件 + RBAC；移除/隔离 FAFU 主动扫描脚本、禁用 `verify=False`；`agent.db` 加密或至少 0600 权限；关闭 `/docs` 匿名访问 + 安全响应头；锁定依赖版本 + 哈希。
- 正面判断："`passive_agent` 核心无 SQL 注入、无命令注入、无硬编码密钥、verifier L2 确为 DNS-only 被动实现，基础代码卫生良好。"

### ✅ 质量门神（gstack-qa-lead 因 429 额度中断；QA 评估由主理人代行）
- 核心判断：🟡 **需补测试**。功能正确性测试扎实（51/51 全过，46.53s），但发布就绪度不足——最大缺口是**零 HTTP/API 层测试**，使 P0 级无鉴权问题对测试套件完全不可见。
- 关键建议：补 FastAPI `TestClient` 集成测试覆盖鉴权与路由；补频控 `release`/重投用例（当前只测队列累积、不测消费）；补 `run_company` 幂等/续跑端到端用例；锁定依赖 + 补回滚预案 + 部署文档。
- 测试执行结果：venv 隔离环境（Python 3.13 + pytest 9.1.1），`pytest tests/ -v` → **51 passed in 46.53s**，零失败零跳过。

> 本次实际上场成员：产品官、安全卫士、质量门神（中断，主理人代行 QA）。设计师、排障手未上场。

---

## 2. 综合审查发现（去重合并后按严重度排序）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 1 | 🔴 | 安全/工程 | `main.py:23-27` | 全 API 无鉴权：5 个 router 裸挂 `/api/v1`，无任何 `Depends`/auth 中间件；`/approval/decide`、`/gateway/submit`、`/console/run-company` 可匿名调用，等价"无鉴权即全权限" | 所有 `/api/v1` 加统一鉴权依赖（API Key/Bearer）+ RBAC，运行/审批接口强制授权 | 安全+产品 |
| 2 | 🔴 | 安全/合规 | `FAFU/fafu_auto_verify.py:104,135`、`verify_fafu.py:34,54` | FAFU 子模块含主动 HTTP 探测 + 4 处 `verify=False` 关闭 TLS + `urllib3.disable_warnings()`，违背"被动-only"定位且有 MITM 风险 | 上线前从交付物剔除/隔离 FAFU 主动扫描脚本，全局禁用 `verify=False` | 安全 |
| 3 | 🟠 | 功能正确 | `passive_agent/gateway/ratelimiter.py:55` | 频控队列语义破损：`release()` 全仓零调用，`acquire()` 超限仅 `_queued+=1` 返回 BLOCK，队列只增不减、永不重投；注释"排队不丢弃"与实际矛盾 | 引入窗口释放后后台重投，或改"拒回+退避"并移除误导性 queued 计数 | 产品（QA 已实测验证） |
| 4 | 🟠 | 安全 | `data/agent.db` | 数据库明文落盘 + 默认 world-readable 权限；`t_compliance_rule` 从明文可写 SQLite 加载无签名校验 | 加密落盘或至少 `chmod 600`，合规规则加载加完整性校验 | 安全 |
| 5 | 🟠 | 安全 | `main.py:21` | FastAPI 默认暴露 `/docs`、`/openapi.json`（匿名）；无 CORS 限制、无 HSTS/CSP/X-Frame-Options；缺 `.gitignore` | 生产关闭 `/docs`，加安全响应头 + CORS 白名单，补 `.gitignore` | 安全 |
| 6 | 🟠 | 可靠性 | `passive_agent/api/routes_console.py`（run-company） | `run_company` 在 HTTP handler 内同步阻塞、无超时、无幂等；双击 100ms 内触发两次全量采集 | 改 `BackgroundTasks`/任务队列 + `task_id` 去重 | 产品 |
| 7 | 🟠 | 范围/产品 | `passive_agent/enumerator/adapter.py`、`orchestrator/loop.py` | 被动采集为 mock：`_mock_relations` 返回假股权结构，`run_company` 硬编码 `dns_ok=True`/`src_cnt=2`，真实 L2 探测从未触发——"被动信息收集"能力本身未落地 | 落地真实被动源（R7），或明确改为"合规/频控/审批框架"后再上线 | 产品 |
| 8 | 🟡 | 可靠性 | `passive_agent/orchestrator/loop.py` | 断点续跑未闭环：每轮 `snapshot.save`，但 `run_company` 启动不读快照恢复 offset，`/approval/resume` 仅加载打印；注释"崩溃可恢复零丢失"未兑现 | `run_company` 入口接入快照续跑 | 产品 |
| 9 | 🟡 | QA | `tests/`（整体） | 零 HTTP/API 层测试：51 个测试全直调 service 层，无一用 `TestClient` 走 FastAPI 路由——P0 无鉴权对测试不可见，加鉴权后也无回归保障 | 补 `TestClient` 集成测试覆盖鉴权、路由、审批越权负向 | QA（主理人代行） |
| 10 | 🟡 | 安全/供应链 | `requirements.txt` | 依赖用 `>=` 未锁版本、无哈希（fastapi>=0.110、httpx>=0.27），供应链漂移风险 | 引锁定文件（uv/pip-tools lock）+ 哈希校验 | 安全+QA |
| 11 | 🟡 | 工程 | `passive_agent/compliance/rules.py:27` | `PASSIVE_WHITELIST` 定义后从未被引用（死代码）；R1 对任一 PASSIVE_QUERY 一律放行不校验来源，与文档"白名单 ACL"不符 | 清理死代码或兑现白名单校验语义 | 产品 |
| 12 | 🟡 | 安全 | 审计日志 | 日志仅 stdout，无告警、审计无操作者身份绑定、可换行注入 | 绑定操作者身份、追加写日志、转义 | 安全 |

**正面项（🟢）**：① 核心 `passive_agent` 无 SQL/命令注入（全参数化查询）；② 无硬编码密钥；③ 合规 fail-closed 关隘设计到位（未知动作默认 BLOCK）；④ 51/51 测试全过，功能正确性基础扎实。

---

## 🚫 阻塞项清单（P0，必须修复方可上线）

| # | 阻塞项 | 位置 | 修复方向 | 验收标准 |
|---|--------|------|---------|---------|
| P0-1 | 全 API 无鉴权 | `main.py:23-27` + 5 个 router | 统一鉴权依赖 + RBAC，运行/审批/提交接口强制授权 | 匿名调用 `/console/run-company`、`/approval/decide`、`/gateway/submit` 返回 401；补 `TestClient` 鉴权回归测试 |
| P0-2 | FAFU 主动扫描 + `verify=False` | `FAFU/*.py`（4 处） | 从交付物剔除/隔离 FAFU 主动扫描脚本，全局禁用 `verify=False` | 交付物中无 `verify=False`、无主动 HTTP 探测脚本；静态扫描通过 |

---

## 🔄 回滚预案

1. **版本标记**：上线前对当前 `data/agent.db` 与代码打 tag（如 `v0.1.0-pre`），保留可回滚快照。
2. **数据库回滚**：`agent.db` 为本地 SQLite，上线前 `cp agent.db agent.db.bak.<ts>`；异常时停服 + 覆盖回滚 + 重启。
3. **代码回滚**：保留上一稳定 commit，出现严重故障 `git revert`/`checkout` 到 tag 后重启 `uvicorn`。
4. **熔断**：`/console/run-company` 上线后先以限流 + 手动触发方式灰度，发现异常采集/违规立即停服。
5. **健康检查**：保留 `/api/v1/health` 端点，部署层配存活探针；异常自动回滚到上一版本镜像/进程。

---

## ✅ 行动清单

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 所有 `/api/v1` 接口加统一鉴权 + RBAC，审批/运行/提交强制授权 | 后端工程 | P0 | 上线前 |
| 2 | 剔除/隔离 FAFU 主动扫描脚本，全局禁用 `verify=False` | 安全工程 | P0 | 上线前 |
| 3 | 补 FastAPI `TestClient` 集成测试，覆盖鉴权、路由、审批越权负向 | QA | P0 | 上线前 |
| 4 | 修复频控队列语义：实现 `release`/重投或改"拒回+退避"，补对应单测 | 后端工程 | P1 | 上线前 |
| 5 | `agent.db` 加密或 0600 权限；关闭 `/docs` 匿名访问 + 安全响应头 + CORS 白名单 | 安全工程 | P1 | 上线前 |
| 6 | `run_company` 改后台任务 + `task_id` 幂等去重 + 超时 | 后端工程 | P1 | 上线前 |
| 7 | 锁定依赖版本（uv/pip-tools lock）+ 哈希校验；补 `.gitignore` | 后端工程 | P1 | 上线前 |
| 8 | 断点续跑闭环：`run_company` 入口接入快照恢复 offset | 后端工程 | P2 | 上线后首轮 |
| 9 | 明确产品边界：落地真实被动源，或定位改为"合规/频控/审批框架" | 产品 | P2 | 上线决策前 |

---

## ⚠️ 待完善 / 已知局限

- **质量门神结论为代行**：gstack-qa-lead 因 429 额度限制（重置于 2026-07-14 01:04）未能完成独立 QA 评估，QA 部分由主理人亲自执行（实测 51 测试 + 静态覆盖分析），已明确标注。额度恢复后建议由质量门神复检一次以闭环。
- **未做性能/压测基线**：本次仅跑了功能测试套件，未做并发压测与资源占用基线。
- **FAFU 深度未审**：FAFU 子模块因属"应剔除"范围，未做逐文件深度审查。
- **静态扫描局限**：`verify=False` 等为文本扫描，未做实际网络行为抓包验证。

---

## 📚 成员产出索引

- gstack-product-reviewer（产品官）原始产出：已回传完整工程成熟度结论（🟡 需打磨，1 条 P0，5 条 P1/P2），见正文第 1 节。
- gstack-security-officer（安全卫士）原始产出：已回传完整 OWASP Top 10 + STRIDE 审计结论（🔴 不可上线，2 条 P0），见正文第 1 节。
- gstack-qa-lead（质量门神）原始产出：**因 429 额度中断未产出**，QA 评估由主理人代行（实测 51/51 通过 + 覆盖缺口分析）。

---

> 本报告由软件工坊 AI 协作生成（产品官 + 安全卫士 + 主理人代行 QA），关键决策请由工程负责人复核。
