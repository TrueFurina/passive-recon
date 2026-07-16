# 产品 / 架构评审结论 — 企业被动信息搜集 Agent（EASM / CTEM）

**评审人**：gstack-product-reviewer（产品官）
**日期**：2026-07-13
**视角**：产品定位与架构一致性 · CLI / DX · 市场契合度 · 文档承诺 vs 代码现实
**方法**：基于工作区真实文件证据（引用路径），不臆测。代码量 ≈ 6862 行 Python。

---

## 整体判断：🟡 有条件通过（Conditional Pass）

**一句话**：产品定位（纯被动 + 合规 fail-closed + 资产图谱）在**意图层面自洽且可辩护**，R1 关隘真实落地并经测试；但**对外叙事（PRD / 高层架构 / final_report）严重超前于代码现实**——R3 枚举是 mock、R2 四层校验是空壳、资产图谱实为 SQLite 而非 Neo4j、LLM 规划 Agent 完全未实现。若以"已交付产品"标准评判为 🔴；以"架构原型 + 清晰意图"标准评判为 🟡，但须在答辩/上线前闭合下述契约落差。

> 本评审与既有 `deliverables/gstack/pre-launch-check-passive-agent-2026-07-13.md`（🔴 No-Go）共享两项阻塞（API 无鉴权 P0-1、FAFU 主动扫描 P0-2），并在产品/架构层面补充其未覆盖的落差。

---

## 一、核心优势（真实、可辩护，应保留）

1. **R1 合规 fail-closed 关隘真实且经测试**
   - `passive_agent/compliance/engine.py`：主动动作 `BLOCK(010001)` + 未知动作默认拦截（fail-closed）+ 审计落 `t_audit_log`；`common/compliance_client.py` 提供统一关隘。
   - 每个采集器出站前 `compliance_client.check(PASSIVE_QUERY)`（`collector/sources.py:39-44` 的 `_r1_pass`），`test_p1_redline.py` / `test_qa_supplement.py` 静态断言全部出站经此关隘。**这是整个产品最扎实、最自洽的部分。**

2. **模块分层清晰，职责边界明确**
   - collector / gateway / compliance / inventory / enumerator / verifier / orchestrator / graph 分工合理，CLI 子命令与 R1–R6 需求形成可对齐的表面映射（collect→采集, enumerate→R3, compliance-status→R1, submit-status→R6, inventory-export→R5, audit-queue→审计）。

3. **SQL 卫生良好**（继承自 prior）：全参数化查询，无 SQL 注入；`requirements.txt` 明示不引入 nmap / 主动扫描类库。

4. **R5 台账机制设计到位**：`inventory/registry.py` 预置开源/自研边界 + `export_proof()` 按 R 模块统计自研占比，直面决赛"源码核验"诉求，思路正确。

---

## 二、关键风险与缺口

### A. 文档承诺 vs 代码现实（最大落差，按严重度）

| # | 承诺（文档） | 现实（代码） | 证据路径 |
|---|---|---|---|
| A1 | R12 资产关联图谱 = **Neo4j** 底座（PRD D4、高层架构 §2.4/§5.2 L4 N4） | **SQLite 关系表，非图数据库**，注释"便于后续 Neo4j 迁移" | `passive_agent/graph/asset_graph.py:1-5` |
| A2 | L2 **全局规划 Agent（LLM）+ LangGraph 多智能体 + Docker microVM 编排**（final_report 第3章、PRD L2、高层架构 §5.1） | **零 LLM / planner / langgraph 模块**（grep 确认）；`orchestrator/loop.py` 是顺序 Python 函数 | `grep -rni "langgraph\|openai\|planner" passive_agent/` 无命中；`passive_agent/orchestrator/loop.py` |
| A3 | R3 **全主体枚举 / 股权穿透**（P0，PRD §6 "母+子+分全量主体"） | `query_relations()` 的 P0 行为返回 **mock 主体**（`{企业}-控股子公司L1`）；真实采集为可选"FAFU 增强"且失败静默吞掉 | `passive_agent/enumerator/adapter.py:47-74` |
| A4 | R2 **四层自动校验流水线**（P0 自研，工商匹配 / DNS存活 / 时间过滤 / 多源≥2） | `pipeline.run()` **仅回显调用方传入的布尔值**；`orchestrator/loop.py` 硬编码 `layer1_biz_match=True`、`layer3_time_ok=True` → **L1 工商匹配、L3 时间过滤从未真正执行** | `passive_agent/verifier/pipeline.py:46-116`；`passive_agent/orchestrator/loop.py:195-201` |
| A5 | R6 **频控队列"排队不丢弃"**（PRD R6、高层架构 §5.2） | `proxy.submit` 超限直接 `BLOCK(accepted=False)` 返回；`ratelimiter.release()` 全仓零调用，队列只增不减（prior #3） | `passive_agent/gateway/proxy.py:49-56`；`passive_agent/gateway/ratelimiter.py` |

> **结论**：A1–A5 共同指向一个核心问题——**对外交付物描绘的是"Neo4j + LLM + 真实穿透 + 四层校验"的完整产品，代码是 SQLite 原型 + mock 枚举 + 空壳校验**。当评委/落地用户按文档核验时，"可审计、可证明零主动、差异化的资产图谱"叙事极易被证伪，与产品自我宣称的"合规可证明"原则自相矛盾。

### B. 需求覆盖盲点

- **"Continuous"（CTEM 之 C）缺失**：无定时调度、无增量监测、无告警。仅 CLI 单次触发（`cli.py collect`），与 CTEM"持续威胁暴露管理"定位不符。
- **政企落地用户（US-2）所需能力缺位**：RBAC、多租户、告警、CMDB/工单集成均无；API 无鉴权（prior P0-1）。
- **差异化卖点多为空位**：资产图谱推理补全、加权算力调度 60:30:10（A/B/C 实际未加权，仅 `ComputeScheduler.check_reclaim` 占位）、三级人机审批面板 M1–M7（FastAPI 仅最小面板）。
- **R8 多源容错降级 / R11 度量看板 / R9 算力调度**：蓝图中有接口，但"加权冲分"闭环（每 5min 看榜倾斜）未在代码中体现。

### C. 产品叙事清晰度

- **两套并存叙事**：`final_report.md`（研究版，5 章，2/3 篇幅讲多智能体/LangGraph/Neo4j）+ `PRD` + `高层架构设计`（Neo4j/LLM）描绘完整产品；而 `passive-agent-*-task-blueprint`（实现蓝图）坦承 SQLite + mock-first。对外应统一为"原型现状 + 路线图"，否则叙事失真。
- **合规定位被仓库现实削弱**：
  - `config.json` 明文存 hunter API Key×5 + 企查查 app_key/secret_key，**无 `.gitignore`**（`git add .` 即提交）→ 凭据泄露 + 与"合规"叙事冲突（prior 称"无硬编码密钥"，实为明文密钥文件，结论需纠正）。
  - `FAFU/fafu_auto_verify.py`、`verify_fafu.py`、`fafu_deep_scan.py` 含 `requests.get(..., verify=False)` + `socket.getaddrinfo` 主动探测，绕过 R1（prior P0-2 仍未清除）。

### D. CLI / DX 具体问题（可快速修）

- `cli.py` 顶部 docstring 列 10 命令，**漏列已实现的** `qichacha-detail/verify2/verify3`（cli.py:248-412）。
- `collect` 帮助写"**6 大数据源**"，`SUPPORTED_SOURCES` 实为 **8**（crt.sh/hackertarget/otx/urlscan/securitytrails/hunter/reverse_dns/qichacha），帮助仅列 5（`cli.py:377` vs `collector/manager.py:30-39`）。
- `cmd_list_sources` 死代码：`name.replace("hunter","hunter").replace("securitytrails","securitytrails")` 空操作（`cli.py:206-207`）。
- `cmd_import_path` 静默吞异常（`except Exception: pass`，`cli.py:190-191`）；`cmd_compliance_status` 访问私有 `eng._rules`（`cli.py:93`）。
- **语义混淆**：`_detect_risks` 把风险发现追加进 `report.errors`（`collector/manager.py:401-402`），CLI 以"采集错误"打印，混同真实错误。
- 输出为 `print` + emoji + 裸 JSON，**无 `--json` 全局开关**，CI/编排不友好；无结构化退出码。

---

## 三、可落地建议（按优先级）

### P0 — 上线 / 答辩前必须闭合
1. **闭合"叙事 = 现实"契约**：二选一——(a) 真正落地 R3 股权穿透 + R2 四层校验（尤其 L1 工商匹配、L3 时间过滤做真实校验，不再硬编码 `True`），或 (b) 把对外文档降级为"架构蓝图 / 原型"，逐项标注**已实现 vs 规划**。最危险的是用蓝图文档冒充现状。（产品 + 工程）
2. **隔离 FAFU 主动脚本 + 全局禁用 `verify=False`；`config.json` 密钥移出仓库改密钥管理 + 补 `.gitignore`**（与 gstack-security-officer 协同；纠正 prior "无硬编码密钥"误判）。
3. **API 鉴权 + RBAC**（prior P0-1）：`/console/run-company`、`/approval/decide`、`/gateway/submit` 强制授权。

### P1 — 本阶段
4. **修复 R6 频控队列语义**：实现 `release()`/后台重投，或改"拒回 + 退避"，使"排队不丢弃"成真。
5. **CLI DX 收敛**：docstring 与命令同步；统一数据源口径（6 vs 8）；删除死代码；增加 `--json`；错误不再静默吞。

### P2 — 差异化兑现
6. **选一条差异点真实兑现**：建议优先"四层校验真实化"（→ 资产准确率可度量，最贴合"可信"叙事），其余明确列入路线图而非现状。
7. **图谱定位对齐**：若坚持 Neo4j 叙事，给出 `SQLite → Neo4j` 迁移路径与兼容层；否则把图谱定位改为"SQLite 拓扑 + 后续图库"，文档与代码一致。

---

## 四、与既有评审的关系

- 继承 `deliverables/gstack/pre-launch-check-passive-agent-2026-07-13.md`（🔴 No-Go）的安全/QA 结论（无鉴权 P0-1、FAFU 主动扫描 P0-2、频控语义 #3、run_company 阻塞 #6、断点续跑未闭环 #8、依赖未锁 #10、PASSIVE_WHITELIST 死代码 #11）。
- **本次新增 / 纠正**：
  - ① `config.json` 明文密钥 + 无 `.gitignore`（prior 误判"无硬编码密钥"）；
  - ② **R2 四层校验空壳**（L1/L3 硬编码 `True`，prior 未单独立项）；
  - ③ **R3 枚举 mock**（prior #7 提及，本次给出确证代码位置 `enumerator/adapter.py:47-74`）；
  - ④ **Neo4j↔SQLite、LLM 规划缺失**等文档-代码落差的系统梳理。

---

**证据索引（关键路径）**
- `cli.py`（CLI 设计 / DX）
- `passive_agent/compliance/engine.py`、`common/compliance_client.py`（R1）
- `passive_agent/graph/asset_graph.py`（SQLite 非 Neo4j）
- `passive_agent/enumerator/adapter.py:47-74`（R3 mock）
- `passive_agent/verifier/pipeline.py`、`orchestrator/loop.py:195-201`（R2 空壳）
- `passive_agent/gateway/proxy.py:49-56`、`ratelimiter.py`（R6 队列）
- `config.json`、`FAFU/fafu_auto_verify.py`（密钥 / 主动扫描）
- `deliverables/product-strategy/prd-passive-info-agent-2026-07-13.md`、`deliverables/architecture/高层架构设计.md`、`deliverables/final_report.md`（承诺文档）
