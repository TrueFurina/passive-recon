# 企业被动信息收集智能体 · 生产加固交付报告（F-4 / F-5 / F-6 / F-10 + 限流全球化）

**日期**：2026-07-15
**场景**：全流程交付（安全加固实现：安全驱动审计 → 代码实现 → QA验证与发布就绪）
**参与成员**：安全卫士（gstack-security-officer，提供驱动审计）+ 主理人（沽思航，代执行实现与 QA；排障手 / 质量门神子 Agent 因框架故障未独立产出）

---

## 📌 TL;DR（执行摘要，3-5 行）

- **整体结论**：🟡 条件 Go（Conditional Go）。四块生产加固（出站 fail-closed、SSRF 白名单、PII 加密/删除、反代鉴权显式开关）+ 限流全球化**已全部落地且单测全绿**，受控/演示环境可达标。
- **阻塞项数量**：0 项代码级 P0（本次加固范围内）；残留 3 项生产前置动作 + 2 项已知局限（见行动清单 / 已知局限）。
- **测试结果**：针对性回归 **54 passed / 0 failed**（覆盖全部改动路径，含 12 个新增单测全绿）；全量 broad run 因沙箱真实 I/O 挂起（已知局限，非本次引入回归）。
- **下一步**：生产前置——开启 `EGRESS_ENFORCE=True` 并填 `EGRESS_IPS`、补齐剩余 PII 写入点加密、按需上 Redis 全局限流；测试套件 hermetic 化后在 CI 真跑绿。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟡 条件 Go（受控/演示：Go；生产前置动作闭环后：Go） |
| 严重度分布（本次新增问题） | 🔴 0 / 🟠 0 / 🟡 2（残留局限）/ 🟢 4（加固完成） |
| 关键行动项 | 5 条（见行动清单，含 2 条 P0 生产前置） |
| 建议负责人 | 张敏杰（主开发） |

---

## 1. 各成员核心结论

### 🛡️ 安全卫士（OWASP + STRIDE 审计，驱动方）
- **核心判断**：本次加固直接落实其 CSO 审计报告中的生产级 must-fix——F-4/F-5 对应"出站审批 fail-open + 白名单运行时未生效"（原 STRIDE 缺失项），F-6 对应"PII 明文留存无策略"，F-10 对应"反代下 loopback 鉴权可绕过"，限流全球化对应"频控进程内单例多 worker 失效"。四项均按 fail-closed / 默认安全方向实现。
- **关键建议**：生产环境必须将 `EGRESS_ENFORCE` 置 True 并填充 `EGRESS_IPS`；PII 加密需扩展到 collector/sources.py 等其他写入点；限流需 Redis 才能真全局。
- **原始产出**：`deliverables/security-audit-cso-2026-07-14.md`（F-1~F-11、STRIDE + OWASP Top 10 检查表）。

### 🔧 排障手（gstack-investigator）
- **状态**：子 Agent 在派发时触发框架故障（`Tool TaskStop not found`，与质量门神同因），未能独立产出。其在本轮前已写出 `passive_agent/gateway/ratelimiter.py`（Redis 集中式限流）及对应 config / requirements 改动；主理人已接手验证其产物编译通过且单测 4/4 通过。
- **关键建议（转述其代码意图）**：Redis 不可达时优雅降级为进程内单例并告警；支持 `RATE_REDIS_FAIL_FAST` 在强一致场景失败即拒。

### ✅ 质量门神（gstack-qa-lead）
- **状态**：子 Agent 同样因框架故障（`Tool TaskStop not found`）未能独立产出；QA 验证由主理人基于隔离 venv（依赖已装）直接执行，结论为实测非推断。
- **核心判断**：针对性回归 **54 passed / 0 failed**，新增单测 12 个全绿（限流 4 + 出网 5 + PII 3）。验证过程中抓到一次偶发 `sqlite3.OperationalError`，根因为一个挂起的全量测试进程持有真实库 WAL 锁（资源争用），非代码缺陷；清理后连跑 8 次 + 全套件均全绿，主库 `PRAGMA integrity_check = ok`。
- **关键建议**：全量 `pytest` 在沙箱会卡真实 I/O 并争用默认单例 `data/agent.db`，需 hermetic 化后方可宣称 CI 真绿。

### 👤 主理人（沽思航，汇编 + 代执行实现）
- **核心判断**：四块加固 + 限流全球化实现正确、测试覆盖到位、无代码级 P0 阻塞；剩余均为生产前置配置与测试 hermetic 化，非阻塞性缺陷。
- **关键建议**：见行动清单。

> 未上场成员：产品官（gstack-product-reviewer）本轮未单独派发，其 422 端点修复已在 2026-07-14 终审报告中闭环。

---

## 2. 综合审查发现（本次加固闭环项 + 残留局限，按严重度排序）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源成员 |
|---|--------|------|------|---------|------|---------|
| 1 | 🟢 | 安全/出站 | passive_agent/api/routes_gateway.py | F-4 网关 submit 端点改为 fail-closed：`task is None` 或状态不在 APPROVED/REMINDING 一律拒绝（修复前 None 可绕过） | 已闭环；生产保持默认拒绝 | 安全 + 主理人 |
| 2 | 🟢 | 安全/SSRF | passive_agent/compliance/engine.py | F-5 关隘内校验 `target_url`：禁非 HTTPS、禁私网/链路本地 IP、EGRESS_ENFORCE=True 时禁非白名单 host（reason 010002） | 已闭环；生产置 `EGRESS_ENFORCE=True` | 安全 + 主理人 |
| 3 | 🟢 | 数据安全 | passive_agent/common/pii.py + storage/db.py + enumerator/engine.py | F-6 PII：新增 `hash_pii`（HMAC-SHA256 加盐，不可逆）/ `encrypt_pii`/`decrypt_pii`（AES-256-GCM，密钥缺失降级哈希）；db 增 insert/get/delete/anonymize subject、insert/delete collect_asset、purge_expired_pii；enumerator 改加密写入 | 已闭环（主路径）；扩展至 collector/sources.py 见 #5 | 安全 + 主理人 |
| 4 | 🟢 | 认证/部署 | passive_agent/api/deps.py | F-10 loopback 鉴权豁免收进显式开关：`testclient` 恒豁免、带 XFF 拒绝、仅 `TRUST_LOCALHOST=True` 且 127.0.0.1/::1 才豁免（默认 False） | 已闭环；生产确认 TRUST_LOCALHOST=False | 安全 + 主理人 |
| 5 | 🟡 | 数据安全（残留） | passive_agent/collector/sources.py + audit/logger.py | F-6 仅覆盖主路径 t_subject（经 enumerator）；collector/sources.py 等"God 模块"的其他 PII 写入点及审计日志 PII 尚未加密 | 生产前置：扩展 pii 加密到其余写入点 | 安全 + 主理人 |
| 6 | 🟡 | 测试充分性（残留局限） | tests/（全量） | 套件非 hermetic：默认走单例 `data/agent.db`，全量跑卡真实 I/O 并争用真实库（本次偶发 db 锁即源于此）；本次新增 test_pii 已用 tmp_path 隔离，但其余套件未隔离 | hermetic 化（mock 出站/compliance_client）后 CI 真绿 | QA(主理人) + 产品 |

---

## 交付清单（代码变更 + 测试覆盖 + 发布检查清单 + 回滚预案）

### 代码变更（8 文件，全部编译通过）
- `passive_agent/config.py`：新增 `TRUST_LOCALHOST`(默认 False)、`EGRESS_ENFORCE`(默认 False)、`PII_SALT`、`PII_KEY`、`RETENTION_DAYS`；限流配置 `RATE_REDIS_URL`、`SINGLE_WORKER_MODE`、`RATE_REDIS_FAIL_FAST`。
- `passive_agent/api/deps.py`：F-10 `_is_loopback` 重写（testclient 豁免 → XFF 拒绝 → 显式开关）。
- `passive_agent/api/routes_gateway.py`：F-4 submit 端点 fail-closed。
- `passive_agent/compliance/engine.py`：F-5 `_is_private_ip()` / `_validate_egress()`，check() 接入出站校验。
- `passive_agent/gateway/ratelimiter.py`：限流全球化（Redis Lua 集中式 + 进程内单例降级）。
- `passive_agent/common/pii.py`：**新增**，hash/encrypt/decrypt 工具。
- `passive_agent/storage/db.py`：F-6 insert_subject/get_subject/delete_subject/anonymize_subject/insert_collect_asset/delete_collect_asset/purge_expired_pii。
- `passive_agent/enumerator/engine.py`：F-6 改走加密写入。

### 测试覆盖（新增 12，全绿）
- `tests/test_ratelimiter.py`（4）：单例共享、容量硬顶+排队、Redis 共享后端强制全局上限。
- `tests/test_egress.py`（5）：非 HTTPS 拦截、私网 IP 拦截、公网 HTTPS 放行、白名单拦截/放行。
- `tests/test_pii.py`（3）：哈希不可逆、无密钥非明文+删除、有密钥往返+匿名化。
- 针对性回归（含上述 + test_gateway/test_compliance/test_approval/test_enumerator/test_collector）：**54 passed / 0 failed**。

### 发布检查清单（上线前逐项确认）
- [ ] `EGRESS_ENFORCE=True` 且 `EGRESS_IPS` 已填生产目标域名/IP。
- [ ] `TRUST_LOCALHOST=False`（生产）；反向代理强制设 `X-Forwarded-For`。
- [ ] `PII_KEY` 经环境变量注入（非入库）；`PII_SALT` 随机生成。
- [ ] 限流：已部署 Redis 并设 `PASSIVE_RATE_REDIS_URL`，或文档明示单 worker 假设。
- [ ] `config.json` 真实密钥不进镜像/备份（gitignore 隔离，不可变密钥运维纪律）。
- [ ] 保留发布前 `git tag` + 上一镜像 tag，支持一键回退。

### 回滚预案
- **代码回滚**：修复均经 git 提交；异常时 `git revert` 对应提交；保留 `pre-hardening` tag。
- **配置回滚**：密钥/开关经环境变量注入，不入库；回滚从密钥管理恢复。
- **数据回滚**：加密改造前已对 `data/*.db` 有备份；如加密异常，降级为"只读明文 + 限期清理"并用备份恢复。
- **运行时熔断**：出站异常立即 `EGRESS_ENFORCE=True` 并启用 target_url 白名单；紧急撤销 API token、关闭 `/docs`；保留进程级 kill-switch。
- **金丝雀**：先放受控流量，观测审计日志无异常再全量。

---

## ✅ 行动清单（具体可执行项）

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 生产环境置 `EGRESS_ENFORCE=True` 并填充 `EGRESS_IPS`（出站白名单真正生效） | 张敏杰 | P0（生产前置） | 生产前置 |
| 2 | 扩展 PII 加密到 collector/sources.py 等其余写入点 + 审计日志 PII（闭合 F-6 残留） | 张敏杰 | P0（生产前置） | 生产前置 |
| 3 | 限流上 Redis 全局化：部署 Redis 并设 `PASSIVE_RATE_REDIS_URL`；或文档明示单 worker 假设 | 张敏杰 | P1 | 生产前置 |
| 4 | 测试套件 hermetic 化（mock 出站 / compliance_client / httpx），使全量 `pytest` 在 CI 真跑绿且不复用真实 `data/agent.db` | 张敏杰 | P1 | 1 周内 |
| 5 | 确认部署拓扑：反代设 X-Forwarded-For + `TRUST_LOCALHOST=False`；`PII_KEY` 环境变量注入 | 张敏杰 | P1 | 生产前置 |

---

## ⚠️ 待完善 / 已知局限

- **子 Agent 框架故障**：gstack-investigator 与 gstack-qa-lead 派发时均触发 `Tool TaskStop not found`（框架级偶发，非任务本身问题）。本轮实现与 QA 验证由主理人直接执行，结论为实测。建议框架恢复后由质量门神补一轮独立 QA 报告。
- **全量测试挂起**：受沙箱真实 I/O 限制，全量 `pytest` 会卡真实采集/网络测试并争用默认单例 `data/agent.db`（本次偶发 db 锁即源于挂起的全量进程持有 WAL 锁）。已清理 WAL、主库 `integrity_check=ok`，后续以 hermetic 化解决。
- **F-6 仅覆盖主路径**：collector/sources.py 等"God 模块"其余 PII 写入点及审计日志 PII 尚未加密（见行动 #2）。
- **不可变密钥残留风险**：Hunter/企查查密钥唯一不可变，无法轮换，仍明文驻 `config.json`（gitignore 隔离，从未入库）；缓解靠运维纪律，非代码可根除。
- **EGRESS_IPS 默认关闭**：`EGRESS_ENFORCE=False` 为不破坏既有行为的默认，生产必须显式开启。
- **合规边界**：PIPL/数据安全法合规评估需法务/合规侧确认，本报告仅技术面提示。

---

## 📚 成员产出索引

- gstack-security-officer（安全卫士）原始产出：`deliverables/security-audit-cso-2026-07-14.md`（驱动本轮回固的审计结论 F-1~F-11）。
- gstack-investigator（排障手）原始产出：**未独立产出（子 Agent 框架故障）**；其代码产物 `passive_agent/gateway/ratelimiter.py` + config/requirements 改动已由主理人验证（编译通过、单测 4/4）。
- gstack-qa-lead（质量门神）原始产出：**未独立产出（子 Agent 框架故障）**；QA 实测由主理人代执行（54 passed / 0 failed，详见第 1 节"质量门神"段与第 2 节）。
- gstack-product-reviewer（产品官）：本轮未单独派发；其 422 端点修复已在前序终审报告闭环。
- 主理人（沽思航）汇编与代执行记录：本报告全文 + 附录修复执行轨迹。

---

## 附录：本轮修复执行轨迹（2026-07-15）

| 项 | 文件 | 操作 | 验证 |
|----|------|------|------|
| F-4 网关 fail-closed | api/routes_gateway.py | submit 端点 `task is None` 或状态非 APPROVED/REMINDING 即拒绝 | test_gateway 绿 |
| F-5 出站 SSRF 白名单 | compliance/engine.py | 新增 `_is_private_ip`/`_validate_egress`，check() 接入，reason 010002 | test_egress 5/5 绿 |
| F-6 PII 加密/删除 | common/pii.py（新）+ storage/db.py + enumerator/engine.py | hash/encrypt/decrypt + 增删/匿名化/留存清理接口 | test_pii 3/3 绿 |
| F-10 反代鉴权开关 | api/deps.py | `_is_loopback` 重写为 testclient 豁免→XFF 拒绝→显式开关 | 单测 + 既有 auth 路径绿 |
| 限流全球化 | gateway/ratelimiter.py | Redis Lua 集中式 + 进程内单例降级 + fail-fast 开关 | test_ratelimiter 4/4 绿 |

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人（张敏杰）复核。安全/合规项涉及 PIPL 与数据安全法，建议同步法务确认。
