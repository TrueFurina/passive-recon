# 全员保驾护航 · 综合评估报告 — 企业被动信息搜集 Agent（EASM / CTEM）

**日期**：2026-07-13
**场景**：多成员综合评估（产品评审 + 安全审计 + QA 测试与发布就绪 + 设计/代码健康【部分缺位】）
**参与成员**：产品官 ✅ + 安全卫士 ✅ + 质量门神（子 agent 基础设施故障，由主理人离线 pytest 探针兜底）⚠️ + 设计师 ❌ 缺位 + 排障手 ❌ 缺位

> 汇编说明：本报告由主理人（沽思航）基于已交付的两份成员报告（产品官、安全卫士）与安全维度 STRIDE/OWASP 检查表、以及主理人本人执行的离线测试探针合并去重而成。设计师、排障手因 sub-agent 后端（copilot.tencent.com）不可达未能回传，其职责缺位已在"待完善/已知局限"中如实标注，不冒充其专业结论。

---

## 📌 TL;DR（执行摘要）

- **整体结论**：🔴 **不通过（NO-GO）** —— 修复 P0 项前，禁止在任何网络可达环境部署。
- **阻塞项数量**：4（API 无鉴权、config.json 明文密钥+无 .gitignore、第三方 PII 明文入库且入仓、文档-代码严重落差）。
- **核心亮点**：合规引擎 **R1 确为 fail-closed**（主动动作硬编码 BLOCK、未知默认 BLOCK、DB 不可用回退安全集），全部 SQL 参数化、令牌用 `hmac.compare_digest` —— 这是项目真正的护城河，安全官与产品官共同肯定。
- **致命短板**：对外"被动 + 合规可证明"叙事与代码现实严重脱节（R2 四层校验是空壳、R3 股权穿透是 mock、资产图谱实为 SQLite 而非承诺的 Neo4j、LLM 规划 Agent 完全未实现）。
- **测试现状（主理人探针）**：`pytest` 202 项，**192 passed / 8 failed**；8 项失败全在 API 端点层 + R6 代理队列，与"API 无鉴权""R6 频控语义错误"相互印证。
- **下一步**：先清零 P0（鉴权接线 + 密钥治理 + 叙事闭合），再补测试/依赖/频控；设计师与排障手待基础设施恢复后重跑。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🔴 **No-Go**（P0 清零前禁止网络暴露部署） |
| 严重度分布 | 🔴 2 / 🟠 5 / 🟡 8 / 🟢 2（合计 17） |
| 关键行动项 | 8 条（P0×3 / P1×3 / P2×2） |
| 建议负责人 | 工程 + 安全 + 产品官三方协同；QA/设计/排障待恢复补位 |
| 最强资产 | R1 合规 fail-closed 关隘（设计扎实、经测试、可辩护） |
| 最大风险 | 密钥明文 + API 无鉴权（泄露/越权只差一次 `git push`） |

---

## 1. 各成员核心结论

### 🔍 产品官（产品评审）
- **核心判断**：🟡 有条件通过。产品定位（纯被动 + 合规 fail-closed + 资产图谱）在**意图层自洽且可辩护**；但**对外叙事（PRD / 高层架构 / final_report）严重超前于代码现实**——R3 枚举是 mock、R2 四层校验是空壳、资产图谱实为 SQLite 而非 Neo4j、LLM 规划 Agent 零实现。以"已交付产品"标准评判应为 🔴。
- **关键建议**：① 闭合"叙事 = 现实"契约（真实化 R2/R3，或将文档降级为蓝图逐项标注现状）；② 隔离 FAFU 主动脚本、禁用 `verify=False`、把 config.json 密钥移出仓库；③ API 鉴权 + RBAC。
- **原始产出**：`deliverables/gstack/product-architecture-review-2026-07-13.md`

### 🛡️ 安全卫士（OWASP + STRIDE 审计）
- **核心判断**：🔴 NO-GO。R1 合规引擎确实 fail-closed（给予肯定），但"被动/受控"在工程落地有两处致命断裂：① 面板 API 鉴权代码**写了却从未接线**（死代码），等同完全开放；② `config.json` 明文密钥 + 无 `.gitignore` + 全仓已 staged，泄露只差一次 `git push`。经 git 历史核查，**密钥目前尚未进入提交历史（好消息，补救成本最低）**。SSRF、密钥日志泄露、PII 明文入库为 High。
- **关键建议**：P0 为 API 接线鉴权 + 密钥治理（轮换 + .gitignore + 环境变量 + pre-commit 钩子）+ `git rm --cached data/agent.db`；P1 修 SSRF 黑名单、日志脱敏、存储脱敏；P2 依赖锁版、频控、安全头。
- **原始产出**：`deliverables/security-audit-report-2026-07-13.md`

### ✅ 质量门神（QA 测试与发布就绪）
- **核心判断**：⚠️ **子 agent 因基础设施故障（copilot.tencent.com 不可达）两次折戟，未能回传专业评审**。下方数据为**主理人本人执行的离线 pytest 探针**，仅呈现实测结果、不代替 QA 成员的方法论判断：
  - `pytest` 202 项 → **192 passed / 8 failed / 3 warnings（69.25s）**。
  - 失败 8 项：7 个在 `tests/api/test_endpoints.py`（compliance/approval/gateway/inventory/console/metrics/graph 全部端点，`AssertionError`）；1 个 `tests/test_qa_supplement.py::test_r6_proxy_queued_flag_reasonable`。
  - 信号：失败集中在 API 端点层 + R6 代理队列，与安全官"API 无鉴权/死代码"、产品官"R6 频控语义错误（承诺排队实则直接 BLOCK）"相互印证——测试套件已用红线标出架构/安全落差。
- **关键建议**：修复 API 鉴权接线与 R6 队列语义后重跑测试至全绿；待 QA 成员恢复后补做覆盖率量化与发布检查清单。
- **探针数据**：`deliverables/gstack/pytest_run_2026-07-13.log`（早前一次部分运行）+ 本次主理人 pytest 运行（192/8）。

### 🎨 设计师（设计系统与视觉）
- **状态**：❌ **缺位** —— 因 sub-agent 后端不可达，未能回传设计系统/视觉审查结论。其职责（design-tokens-spec 一致性、`enterprise-passive-agent-architecture.html` 视觉落地、面板 UI 令牌对齐）本次未评估。
- **建议**：基础设施恢复后重派；相关交付物见 `deliverables/design-tokens-spec.md`、`deliverables/enterprise-passive-agent-architecture.html`。

### 🔧 排障手（调试与根因 / 代码健康）
- **状态**：❌ **缺位** —— 同上，未能回传代码质量与健康检查结论。其职责（能否跑起来、裸 `except` 吞异常、`domain` 推断边界、频控/代理逻辑隐患）本次未评估。
- **备注**：工作区已有早期健康check 文档 `deliverables/engineering-assurance/health-check-passive-agent-2026-07-13.md`（前次会话产物），可作为参考，但非本次排障手产出。

---

## 2. 综合审查发现（去重合并后按严重度排序）

### 安全维度：威胁建模（STRIDE）+ OWASP Top 10 检查表

**STRIDE**

| 类别 | 威胁场景 | 发现 | 严重度 |
|---|---|---|---|
| Spoofing | 无鉴权 API 可伪造成合法调用方；`source_name` 自报未校验 | F-01, F-09 | 🔴 |
| Tampering | 未鉴权 `/approval/decide` 可任意操纵审批；config.json 明文可被篡改 | F-01 | 🔴 |
| Repudiation | 审计 `subject_id` 为空无法溯源；日志可注入 | F-08 | 🟡 |
| Info Disclosure | 未鉴权暴露全部第三方 PII；data/agent.db 被 git 跟踪；密钥明文+入日志；/docs 暴露 | F-01/02/03/04 | 🔴/🟠 |
| DoS | 未鉴权+无频控→高频采集耗尽配额 | F-07 | 🟡 |
| EoP | 未鉴权即完全控制（触发采集/读全部数据/操纵审批） | F-01 | 🔴 |

**OWASP Top 10 (2021)**：A01 失效访问控制 ❌（F-01/F-09）｜A02 加密失败 ❌（F-02/03/04/11）｜A03 注入 ✅ 基本通过（全参数化；SSRF 归 A10）｜A04 不安全设计 ❌（F-05/07/09）｜A05 安全配置错误 ❌（F-02/04/10）｜A06 脆弱组件 ⚠️（F-06）｜A07 身份鉴别失败 ❌（F-01）｜A08 数据完整性 ⚠️（F-06/12）｜A09 日志监控失败 ❌（F-03/08）｜A10 SSRF ❌（F-05）。

### 合并发现表

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源成员 |
|---|--------|------|------|---------|------|---------|
| 1 | 🔴 | 安全/访问控制 | `passive_agent/api/*`、`main.py:25-31` | 面板 API 鉴权代码（require_auth/API_TOKENS）已实现却**从未接线**，等同完全开放，任意网络可达者越权 | `main.py` 全局 `Depends(require_auth)` + 注入 `PASSIVE_API_TOKENS`；关闭/鉴权 `/docs` | 安全卫士 |
| 2 | 🔴 | 安全/密钥治理 | `config.json:2-14`，无 `.gitignore` | 明文硬编码 hunter×5 + qichacha 密钥，全仓已 staged，**下次 push 即泄露**（已核查尚未入 git 历史） | 立即轮换密钥；新增 `.gitignore`；密钥改环境变量；pre-commit 钩子 | 安全卫士 |
| 3 | 🟠 | 安全/数据合规 | `storage/db.py:72-156`、`data/agent.db` 被 git 跟踪 | 第三方 PII（信用代码/法人/IP/端口）明文入库且随仓库提交 | `git rm --cached data/agent.db` + `.gitignore data/`；存储加密/脱敏；留存期限 | 安全卫士 |
| 4 | 🟠 | 安全/日志泄露 | `collector/sources.py:392/576/...`、`common/logging.py:43-46` | API Key 经异常日志 f-string 泄露到 stdout/JSON 日志 | 异常日志脱敏、URL 剥离 key 参数；logging 层 secret 红action | 安全卫士 |
| 5 | 🟠 | 安全/SSRF | `compliance/engine.py:60-99`、`collector/sources.py:91/131/...`、`api/routes_console.py:34-37` | 用户可控 domain 直入 `httpx.get`，无内部地址黑名单（云元数据 SSRF） | R1 对 target_url 解析+黑名单；domain 入参校验；httpx 禁重定向到内部 | 安全卫士 |
| 6 | 🟠 | 产品/诚信 | `verifier/pipeline.py:46-116`、`orchestrator/loop.py:195-201` | R2 四层校验为空壳：pipeline 仅回显调用方布尔值，L1/L3 硬编码 `True`，从未真实执行 | 真实化 L1 工商匹配/L3 时间过滤，或文档降级为蓝图并标注现状 | 产品官 |
| 7 | 🟠 | 产品/诚信 | `enumerator/adapter.py:47-74` | R3 股权穿透返回 mock 主体（`{企业}-控股子公司L1`），真实采集失败静默 | 落地真实穿透或标注为蓝图规划；mock 标注 TEST 不落真实表 | 产品官 |
| 8 | 🟡 | 产品/文档落差 | `graph/asset_graph.py:1-5`、零 LLM 模块 | 文档承诺 Neo4j 图谱 + LLM 规划 Agent，代码实为 SQLite + 无 LLM | 对齐叙事与代码，或给出迁移路径并标注现状 | 产品官 |
| 9 | 🟡 | 产品/需求盲点 | `cli.py`、整体 | CTEM 的"Continuous"缺失（无调度/监测/告警）；RBAC/多租户/CMDB 缺位；差异化卖点多占位 | 明确路线图；优先兑现一条差异点 | 产品官 |
| 10 | 🟡 | 安全/依赖 | `requirements.txt:2-16`、`manager.py:130` | 依赖未锁版（>= 区间无哈希）；openpyxl 未声明 | pip-tools 锁版+哈希；补 openpyxl；接入 pip-audit | 安全卫士 |
| 11 | 🟡 | 安全/DoS | `api/routes_*.py` 无 rate limit | 面板 API 无频控，未鉴权下可耗尽配额/DoS | 全局/按 IP 限流 | 安全卫士 |
| 12 | 🟡 | 安全/日志溯源 | `routes_console.py:35`、无 auth | 日志注入 + 无操作者身份溯源 | 输入校验+转义；鉴权后记录指纹 | 安全卫士 |
| 13 | 🟡 | 安全/配置 | `main.py` 无安全头、`/docs` 开放、`FAFU/` 主动产物入仓 | 安全头缺项；FAFU 含主动探测且违反被动约束入仓 | 关 `/docs`；加安全头；FAFU 主动产物移出仓库 | 安全卫士 |
| 14 | 🟡 | QA/测试 | `tests/api/test_endpoints.py`×7、`test_qa_supplement.py`×1 | 8 项测试失败（7 API 端点 + R6 代理队列），与 API 无鉴权/R6 语义错误相互印证 | 修复 API 鉴权接线与 R6 队列语义后重跑；补齐端点测试 | 质量门神(主理人探针) |
| 15 | 🟢 | 安全/数据完整性 | `enumerator/adapter.py:48-54`、`sources.py:491` | mock 主体污染风险；企查查签名用 MD5（厂商约束） | mock 标注 TEST；MD5 仅限厂商 | 安全卫士/产品官 |

---

## 🚧 阻塞项清单（No-Go 决策依据）

| 阻塞项 | 说明 | 来源 |
|---|---|---|
| B1 | 面板 API 无鉴权（F-01）—— 网络暴露即对任意人完全越权 | 安全卫士 |
| B2 | `config.json` 明文密钥 + 无 `.gitignore`（F-02）—— 泄露只差一次 `git push`（当前未入历史，补救成本最低） | 安全卫士 |
| B3 | 第三方 PII 明文入库且 `data/agent.db` 被 git 跟踪（F-04） | 安全卫士 |
| B4 | 文档-代码严重落差（R2 空壳/R3 mock/Neo4j↔SQLite/LLM 缺失）—— 答辩/落地核验时叙事易被证伪 | 产品官 |

## 🔄 回滚预案

本阶段为"代码审计 + 加固"，不涉及生产发布。若已误部署含明文密钥/无鉴权的版本，立即：
1. **密钥失效**：轮换全部 Hunter/Qichacha 密钥，使旧密钥即时作废；
2. **清理版本控制**：从索引与历史移除 `config.json`、`data/`（`git filter-repo` / BFG 清历史并强推）；
3. **下线止损**：关闭对外端口 / 临时下线服务；
4. **取证排查**：审计日志排查是否已发生未授权访问。
当前密钥**尚未入 git 历史**，按 P0 步骤前置处理即可避免需要回滚。

---

## ✅ 行动清单（至少 3 条具体可执行项）

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 面板 API 接线鉴权：`main.py` 全局 `Depends(require_auth)` + 注入 `PASSIVE_API_TOKENS`；关闭/鉴权 `/docs` | 工程 + 安全 | P0 | 本周内 |
| 2 | 密钥治理：立即轮换 Hunter/Qichacha 密钥；新增 `.gitignore`（config.json/data/.env/FAFU资产）；密钥改环境变量；加 pre-commit 钩子；`git rm --cached data/agent.db` | 工程 + 安全 | P0 | 本周内 |
| 3 | 闭合"叙事=现实"契约：真实化 R2 四层校验（L1/L3 不再硬编码 `True`）+ R3 真实穿透，或将对外文档降级为蓝图并逐项标注现状 | 产品官 + 工程 | P0 | 答辩/上线前 |
| 4 | 修 SSRF：R1 对 `target_url` 解析 + 内部地址黑名单（含云元数据 169.254.169.254）；异常日志脱敏 | 安全 + 工程 | P1 | 2 周内 |
| 5 | 修 R6 频控队列语义（实现 `release`/重投或拒回退避）；重跑失败测试（7 API 端点 + R6 代理）至全绿 | 工程 + QA(待恢复) | P1 | 2 周内 |
| 6 | 剥离 FAFU 主动脚本出仓库、禁用 `verify=False`、核查 TscanClient 是否符合被动约束 | 工程 + 安全 | P1 | 2 周内 |
| 7 | 依赖锁版（`requirements.lock`+哈希）+ 补 openpyxl + pip-audit；面板 API 全局频控；生产安全头 | 工程 | P2 | 1 个月内 |
| 8 | CTEM "Continuous" 能力（调度/监测/告警）+ RBAC/多租户路线图 | 产品官 | P2 | 下阶段 |

---

## ⚠️ 待完善 / 已知局限

- **设计师、排障手缺位**：因 sub-agent 后端（copilot.tencent.com）不可达，两位成员未能回传专业结论。其职责（设计系统审查、代码质量/健康深度检查）本次未评估，建议基础设施恢复后重派。
- **质量门神子 agent 同样因该基础设施故障两次折戟**：本报告 QA 数据为主理人直接执行的离线 `pytest` 探针（192 passed / 8 failed），非 QA 成员完整方法论评审（缺覆盖率量化、发布检查清单、回滚预案细节），建议其恢复后补做。
- 全部结论基于**静态审计 + 主理人探针**，未执行动态渗透/模糊测试；密钥"未入 git 历史"结论来自安全官主动 `git` 核查，仍建议立即按 P0 处理以防万一。
- 产品官所述"既有评审" `deliverables/gstack/pre-launch-check-passive-agent-2026-07-13.md` 为前次会话产物，本报告的 P0 阻塞项与之共享（API 无鉴权、FAFU 主动扫描），并已纠正其"无硬编码密钥"的误判。

---

## 📚 成员产出索引

- gstack-product-reviewer（产品官）原始产出：`deliverables/gstack/product-architecture-review-2026-07-13.md`
- gstack-security-officer（安全卫士）原始产出：`deliverables/security-audit-report-2026-07-13.md`
- gstack-qa-lead（质量门神）原始产出：⚠️ 子 agent 未回传（基础设施故障）；主理人探针数据见 `deliverables/gstack/pytest_run_2026-07-13.log` 及本次 pytest 运行（192 passed / 8 failed）
- gstack-designer（设计师）原始产出：❌ 缺位（基础设施故障，未回传）
- gstack-investigator（排障手）原始产出：❌ 缺位（基础设施故障，未回传）

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。
> 说明：设计师、排障手、质量门神（子 agent 形态）因平台 sub-agent 后端不可达未能参与，相关结论缺口已在文中如实标注，建议基础设施恢复后重跑补全。
