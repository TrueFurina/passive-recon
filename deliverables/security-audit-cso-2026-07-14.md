# 企业被动信息收集智能体 — 安全审计（CSO 视角）

- **审计对象**：`E:\Program\DBAPPSecurity Ltd\Passive information collection Agent for enterprises`
- **审计模式**：上线前最终审查（STRIDE + OWASP Top 10 逐条核对）
- **审计日期**：2026-07-14
- **范围**：`config.json` / `config.example.json`、`passive_agent/`（源码 ~77 .py）、`data/`（SQLite 持久化）、CLI 入口、CI/CD、前端面板
- **方法**：实际读取源码与配置、检查 DB 实际内容、主动核对（非凭推断）；未调用任何外部 LLM/API，未对生产数据做破坏性操作。

> 说明：本报告**不出现任何真实密钥/Token 明文值**，相关位置一律以占位符（如 `<HUNTER_KEY_1>`、`<QCC_APP_KEY>`）表示。

---

## 一、核心判断

本系统的「纯被动」架构设计扎实：所有出站动作都经过 R1 合规关隘（fail-closed），主动动作（ACTIVE_SCAN/ACTIVE_HTTP/TCP_SEND）被物理拦截；数据库访问全程参数化、无 SQL 注入；API 令牌采用常量时间比较；CI 已集成 gitleaks + 纯被动静态闸门 + pytest 回归门禁；出站目标均为硬编码 HTTPS 公开情报源，**未发现外部回调/Webhook/即时通讯等隐蔽外传通道**，SSRF 风险低。但存在一组必须在生产前修复的「配置与数据合规」类问题：① `config.json` 含**真实第三方 API 密钥明文**且被 `.gitignore` 排除（CI 扫描不到）；② `archive/competition-artifacts/FAFU/数据资料/` 含**真实采集数据与 API 导出文件**，已被 staged 进 git 且未被忽略；③ 密钥轮换脚本输出的 `.env` 未被 `.gitignore` 覆盖（轮换反而重新引入明文密钥）；④ 出站审批闸门**fail-open**（无匹配任务即放行）+ `OUTBOUND_REQUIRE_APPROVAL` 默认关闭；⑤ 出站目标白名单（EGRESS_IPS）**实际未生效**；⑥ 企业/个人敏感信息**明文落库且无留存策略**；⑦ 前端 `innerHTML` 渲染服务端数据存在存储型 XSS。综合判定：**条件 Go（Conditional Go）**——架构可上线，但上述 must-fix 项须在上线前全部闭环；受控/演示环境可在完成密钥轮换与数据清理后先行使用。

---

## 二、STRIDE 威胁建模 + OWASP Top 10 检查表

### STRIDE

| 维度 | 判定 | 说明 |
|------|------|------|
| **Spoofing（伪装）** | ⚠️ | API 令牌比较安全（hmac.compare_digest），但鉴权对 loopback（127.0.0.1/::1）整体豁免；若置于未设置 `X-Forwarded-For` 的反代之后，外部请求会被误判为 127.0.0.1 而绕过鉴权。 |
| **Tampering（篡改）** | ✅ | httpx 默认 `verify=True`（无 `verify=False`）；DB 全程参数化；默认 PKI 校验未被关闭。缺陷：合规引擎不校验 `target_url`（纵深防御不足）。 |
| **Repudiation（抵赖）** | ⚠️ | 有结构化审计日志 `t_audit_log`（含 trace_id），但 loopback 请求的操作者身份记为 `anonymous`，本地场景难以追责。 |
| **Information Disclosure（信息泄露）** | ❌ | `config.json` 含真实 API 密钥明文；`archive/FAFU/数据资料/` 含真实组织资产与 API 导出并被 staged；`.env` 未被忽略；PII/企业信息明文落库。 |
| **Denial of Service（拒绝服务）** | ⚠️ | 频控硬闸（≤95%、排队不丢弃）设计良好；但任务态为进程内内存表（单实例），且 `run-company` 接口若暴露可被滥用耗尽采集线程。 |
| **Elevation of Privilege（权限提升）** | ⚠️ | 网关 submit 审批 fail-open（无匹配任务即放行）；`/docs`、`/openapi.json`、`/`、`/static` 免鉴权并暴露完整 API schema。 |

### OWASP Top 10（2021）

| 项 | 判定 | 说明 |
|----|------|------|
| **A01 失效的访问控制** | ⚠️ | 网关 submit 审批 fail-open；loopback 鉴权豁免；`/docs`/`/static`/`/` 免鉴权。 |
| **A02 加密机制失效** | ❌ | 敏感数据（credit_code、法人姓名、IP）明文存 SQLite；密钥明文落 `config.json`；企查查 MD5 签名属外部 API 约束（非可改项）。 |
| **A03 注入（SQL）** | ✅ | 全部 DB 访问参数化（`db.write/query` 用元组参数），未发现 SQL 注入。 |
| **A03 注入（XSS）** | ⚠️ | `app.js` 用 `innerHTML` 渲染服务端 `e.msg`/`e.source`/`e.enterprise`，操作员输入的目标名进入 `msg`→存储型 XSS（影响限于本机面板）。 |
| **A04 不安全设计** | ⚠️ | `OUTBOUND_REQUIRE_APPROVAL` 默认 False；EGRESS_IPS 白名单未接入校验；ICP 采集器 R1 关隘逻辑反转（死代码）。 |
| **A05 安全配置错误** | ❌ | 真实密钥在仓库工作树；`.env` 未被忽略；`/docs` 暴露；缺 CSP/HSTS 等安全头；`.coverage`/`cov_result.json` 留仓。 |
| **A06 脆弱/过时组件** | ⚠️ | 依赖仅 `>=` 下界（fastapi<1.0、httpx>=0.27），无 lockfile，未做周期性 CVE 扫描；未见已知严重漏洞。 |
| **A07 认证/标识失败** | ⚠️ | loopback 免鉴权；`API_TOKENS` 默认空 → fail-closed（良好）但需运维显式配置；操作者身份未记录。 |
| **A08 软件/数据完整性失败** | ✅ | 无未签名自动更新；CI 含 gitleaks + 纯被动闸门；但对 config/密钥无完整性校验，staged 数据未校验。 |
| **A09 安全日志/监控失败** | ⚠️ | 日志结构化良好，但无告警；审计日志明文存 PII 且无留存/轮转；loopback 操作者匿名。 |
| **A10 SSRF** | ✅ | 出站仅指向硬编码 HTTPS 公开情报源，用户输入仅作查询参数；无任意 URL 抓取。纵深短板：合规不校验 `target_url`（白名单未生效）。 |
| *XXE* | ✅（N/A） | 未对不可信输入做 XML 解析，API 均为 JSON。 |
| *不安全反序列化* | ✅ | 未发现对不可信数据做 pickle 等危险反序列化。 |

---

## 三、关键发现

### 🔴 严重（Critical）

**F-1｜config.json 含真实第三方 API 密钥明文，且被 .gitignore 排除（CI 扫描不到）**
- 位置：`config.json`（工作树）；`API_KEYS.hunter`（5 个值：`<HUNTER_KEY_1>`…`<HUNTER_KEY_5>`）、`API_KEYS.qichacha.app_key=<QCC_APP_KEY>`、`API_KEYS.qichacha.secret_key=<QCC_SECRET_KEY>`。
- 问题：密钥为真实可复用值；`config.json` 在 `.gitignore` 中，CI 的 gitleaks（仅扫已跟踪/已提交文件）**不会扫描它**；任何能拷贝该目录者（CI 机、共享盘、备份）可直接盗用并消耗配额。
- 建议：① 立即在 Hunter/企查查 平台**轮换并作废**当前密钥；② 删除工作树明文，改用环境变量 `PASSIVE_API_KEYS` 注入（项目已提供 `scripts/rotate_secrets.py`）；③ 将 `config.json` 纳入密钥管理；④ CI 增加对工作树的全量 gitleaks 扫描（含未跟踪文件）。

**F-2｜真实采集数据与 API 导出文件已被 staged 进 git，且未被 .gitignore 覆盖**
- 位置：`archive/competition-artifacts/FAFU/数据资料/*`（git 状态 `AD`＝已加入索引、工作树删除，仍留在暂存区），如 `企查查Hunter_API_300条.txt`、`目标系统-20260713-145555(1).xlsx`、`数据资料_20260713_145106.xlsx`、`assets_2026713.csv`、`猎奇Hunter_API_账号额度.xlsx` 等。
- 问题：含真实组织资产（域名/IP/端口/技术栈）、企查查/Hunter API 导出与额度信息；`.gitignore` 未覆盖 `archive/`、`deliverables/`，首次 `git commit` 将把这些**真实第三方数据与目标情报**永久写入仓库历史；gitleaks 会扫描这些已暂存文件，可能进一步暴露密钥/额度。
- 建议：① 首次 commit 前从 git 索引与工作树彻底移除（`git rm --cached` + 删除）；② 加入 `.gitignore`（`archive/`、`deliverables/FAFU/数据资料/` 等）；③ 若已/将提交，用 `git filter-repo`/`BFG` 清理历史；④ 评估 PIPL/数据安全法合规与第三方数据授权。

### 🟠 中（Medium）

**F-3｜`.env` 未被 `.gitignore` 覆盖，密钥轮换脚本反而把明文密钥重新引入可提交文件**
- 位置：`.gitignore`（缺 `.env`）；`scripts/rotate_secrets.py`（写入 `.env` 的 `PASSIVE_API_KEYS`）。
- 问题：运行 `rotate_secrets.py --apply` 会生成 `.env` 并写入密钥，而 `.env` 不在忽略列表 → 轮换动作把明文密钥重新变成可提交文件，抵消了「移出 config.json」的努力。
- 建议：`.gitignore` 增加 `.env`、`config.json.bak.*`；脚本改写到已忽略路径或密钥管理器。

**F-4｜出站审批闸门 fail-open + 默认不强制审批**
- 位置：`passive_agent/api/routes_gateway.py:34-40`（`if task is not None and task.status not in ("APPROVED","REMINDING")` 才拦截）；`passive_agent/config.py:88`（`OUTBOUND_REQUIRE_APPROVAL=False`）。
- 问题：当 `biz_req_no` 不匹配任何 `AP-` 任务（`task is None`）时，条件为 False → **直接放行出站**；结合默认关闭的强制审批，R4 审批流在生产默认不生效。
- 建议：改为「无匹配审批任务一律拦截（fail-closed）」；生产默认 `OUTBOUND_REQUIRE_APPROVAL=True`。

**F-5｜出站目标白名单（EGRESS_IPS）实际未生效**
- 位置：`passive_agent/compliance/engine.py:60-99`（仅按 `action_type` 判定，从不读 `target_url`）；`passive_agent/config.py:62`（`EGRESS_IPS=["127.0.0.1"]` 仅用于频控打标，见 `gateway/ip_pool.py`）。
- 问题：合规关隘不校验出站目标，纯被动约束仅靠「采集器 BASE_URL 写死」。新增指向内网/云元数据（`169.254.169.254`）的采集器可绕过约束外传，纵深防御缺失。
- 建议：在合规关隘中解析 `target_url` 主机/IP，拒绝非 HTTPS、内网段与链路本地地址；把 `EGRESS_IPS` 真正接入校验。

**F-6｜企业/个人敏感信息明文落库且无留存策略**
- 位置：`passive_agent/storage/db.py:72-156`（`t_subject` 存企业名/关系/`credit_code`；`t_collect_asset` 存 IP/端口/技术栈/标题）；`passive_agent/collector/sources.py:544-570`（企查查采集 `法人` 姓名＝自然人 PII、`信用代码`）。
- 问题：实测 `data/agent.db` 含 654 条 `t_collect_asset`、14 条 `t_subject`（如「阿里巴巴」及其控股子公司/分公司结构、福建农林大学真实 IP `210.34.80.209` 等）；全部明文、无加密、无脱敏、无留存/删除策略。
- 建议：明确数据分类与留存期限；对 `credit_code`/法人姓名等字段加密或加盐哈希；提供删除/匿名化接口；在授权与隐私声明中明确「被动采集范围与用途」。

### 🟡 轻（Low）

**F-7｜前端存储型 XSS 隐患**
- 位置：`passive_agent/static/app.js:173-204`（`loadFaultLog`/`loadConsoleOverview` 用 `innerHTML` 拼接 `e.msg`/`e.source`/`e.enterprise`）。
- 问题：操作员输入的目标名（`enterprise`）经 `orchestrator/loop.py:236,88,296` 进入审计日志 `msg`，再由面板 `innerHTML` 渲染 → 目标名含 HTML 可触发存储型 XSS。**当前面板仅本机豁免，影响限于本地**，但模式不安全。
- 建议：对所有非枚举字段改用 `textContent`；确需 HTML 时做白名单转义。

**F-8｜生产暴露与缺安全响应头**
- 位置：`passive_agent/main.py:21-46`（`/docs`、`/openapi.json`、`/`、`/static` 免鉴权并暴露完整 API）；无 CSP/HSTS；`.coverage`、`cov_result.json` 留仓。
- 建议：生产关闭 `/docs`；增加安全响应头；调试产物加入 `.gitignore`。

**F-9｜ICP 采集器 R1 关隘逻辑反转（死代码 + 误改风险）**
- 位置：`passive_agent/collector/sources.py:722-724`（`if not _r1_pass(source="miit-icp"): return`；`_r1_pass` 放行时返回 `None` → 恒为 `True` → 永远提前返回空）。
- 问题：ICP 采集实际从不执行（属「安全失败」），但易被误改（如改为 `if _r1_pass(...)`）而引入绕过；应修正并补测。
- 建议：改为直接 `self._r1_pass(source="mipt-icp")` 不包裹 `if not`；补充该路径测试。

**F-10｜部署加固：loopback 鉴权豁免依赖 `request.client.host`**
- 位置：`passive_agent/api/deps.py:32-44`。
- 问题：若置于未设置 `X-Forwarded-For` 的反代后，外部请求被误判为 127.0.0.1 → 绕过鉴权（代码已对「有 XFF」情形禁用豁免，但「无 XFF 的反代」未覆盖）。
- 建议：部署 Runbook 明确要求反代设置 XFF；非本机部署默认关闭 loopback 豁免。

**F-11｜组件供应链无 lockfile / 周期性漏洞扫描**
- 位置：`requirements.txt`（仅 `>=` 下界，fastapi<1.0、httpx>=0.27 等）。
- 建议：引入 `pip-tools`/`uv` lockfile；接入 Dependabot 或周期性 CVE 扫描。

### 🟢 提示（Info / 正向）

- ✅ 出站全部经 R1 关隘（fail-closed），主动动作物理拦截。
- ✅ 数据库访问全程参数化，未发现 SQL 注入。
- ✅ API 令牌 `hmac.compare_digest` 常量时间比较，fail-closed。
- ✅ 无 `verify=False`、无 `eval/exec`、无针对目标的 subprocess、无明文 socket 发送（`guard_passive.py` 静态闸门覆盖）。
- ✅ 无外部回调/Webhook/即时通讯外传通道；出站仅指向硬编码 HTTPS 公开情报源（SSRF 风险低）。
- ✅ CI 已集成 gitleaks + 纯被动闸门 + pytest 回归门禁。

---

## 四、关键建议（Top 5）

1. **上线前必做（密钥与数据清理）**：在 Hunter/企查查 平台轮换并作废 `config.json` 中的真实密钥；彻底删除工作树明文并改环境变量注入；从 git 索引/工作树移除 `archive/FAFU/数据资料/` 真实数据并加入 `.gitignore`；`.gitignore` 增补 `.env`、`config.json.bak.*`。
2. **强化审批与出站控制**：网关 `submit` 改为 fail-closed（无匹配审批任务即拦截）；生产默认 `OUTBOUND_REQUIRE_APPROVAL=True`；把 `EGRESS_IPS` 真正接入合规关隘做目标白名单（拒绝非 HTTPS/内网/链路本地）。
3. **数据合规**：对 `credit_code`/法人姓名等敏感字段加密或加盐哈希；制定留存期限与删除/匿名化接口；在授权与隐私层面明确「被动采集范围与用途」，评估 PIPL/数据安全法边界。
4. **修复前端 XSS 与生产暴露**：`innerHTML`→`textContent`；生产关闭 `/docs`、增加安全响应头；部署 Runbook 明确反代 XFF 要求。
5. **供应链与代码健壮性**：引入依赖 lockfile + 周期性 CVE 扫描；修复 ICP 采集器 R1 逻辑反转并补测。

---

## 五、上线判定

**判定：条件 Go（Conditional Go）**

- 架构与「纯被动」红线设计扎实，主动采集被物理拦截、出站受控、无隐蔽外传，具备上线基础。
- 但存在 **F-1（真实密钥明文）、F-2（真实数据入库/入仓）、F-3（.env 未忽略）、F-4（审批 fail-open）、F-5（白名单未生效）、F-6（PII 明文留存）** 等必须在生产前闭环的项。
- **受控/演示环境**：完成 F-1（密钥轮换+清理）、F-2（数据清理+gitignore）、F-3（gitignore .env）后可先行使用。
- **生产环境**：上述 must-fix 全部闭环 + F-4/F-5/F-6/F-7 修复后，方可正式上线。

---

## 六、补充（交叉评审协同，2026-07-14）

gstack-product-reviewer 同步两条与本审计直接相关的发现，已交叉确认：

- 与 **F-10** 一致：反代（如本机 nginx `proxy_pass`→127.0.0.1 且未加 `X-Forwarded-For`）下 `request.client.host=="127.0.0.1"` 导致整条 API 免鉴权。结论与建议一致：loopback 豁免应收进显式生产开关（默认 False），或仅豁免 `testclient`；部署 Runbook 必须要求反代设置 XFF。
- 与 **F-1** 一致且强化：`config.json` 真实密钥明文落盘（Hunter×5 + 企查查 secret_key）。补充确认 `.gitleaks.toml` 的 allowlist 未列入 `config.json`，且 `config.json` 被 `.gitignore` 排除 → CI 的 gitleaks 对该密钥**实际不可见**，仅靠纪律兜底。建议升级为：密钥改 env 注入、`config.json` 不进镜像/备份、CI 增加工作树全量（含未跟踪文件）gitleaks 扫描。

另一项加固提示（**gstack-product-reviewer #11 ↔ 本审计 F-5，同一结构性短板的两面**）：`scripts/guard_passive.py` 为**启发式**静态闸门，仅覆盖 `httpx`/`requests`/`socket.send*`/`verify=False`，不覆盖 `urllib`/`socket.connect`/`aiohttp`；且即便静态闸门全绿，合规引擎在运行时**不校验 `target_url`**（EGRESS_IPS 未生效，见 F-5），无法从运行时保证纯被动。建议：文档上不称其为红线「证明」，仅作开发期辅助；真正保证纯被动须把出站目标白名单接入合规关隘（F-5）。

正面结论协同确认：R1 合规引擎确为 fail-closed（主动→BLOCK、未知→BLOCK）、SQL 全参数化无注入、token 用 `hmac.compare_digest`——安全核心实现扎实。上述补充不改变上线判定：仍为 **条件 Go**。
