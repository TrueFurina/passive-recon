# 企业被动信息搜集 Agent — 独立安全审计报告

- **审计角色**：GStack 工程团队 安全官（CSO 级，OWASP Top 10 2021 + STRIDE）
- **审计对象**：企业被动信息搜集 Agent（被动式 EASM/CTEM 工具，约束：仅被动采集、绝不主动连接、R1 合规引擎 fail-closed）
- **工作区**：`E:\Program\DBAPPSecurity Ltd\Passive information collection Agent for enterprises`
- **审计日期**：2026-07-13
- **审计方式**：静态代码审计 + git 历史核查 + 主动验证（Grep/Bash 核验，未执行任何对外请求、未触碰生产数据）
- **结论（Go / No-Go）**：🔴 **NO-GO**。在修复 P0 项（API 鉴权接线 + 密钥治理 + 出站目标校验 + 敏感数据移出 git）之前，**不得在任何网络可达环境部署**。

---

## 一、执行摘要

本审计对 14 个核心模块、配置文件与 git 历史做了逐行核查。结论如下：

1. **合规引擎 R1 确实 fail-closed（设计扎实，给予肯定）**：主动动作硬编码 BLOCK、未知动作默认 BLOCK、DB 不可用时回退安全默认集；所有采集器出站前均先过 R1；网关代理 `submit()` 出站前确有 R1 前置校验；全部 SQL 参数化（无注入）；令牌比较用 `hmac.compare_digest`（防时序）。**这是本项目最强的部分。**

2. **但"被动"与"受控"在工程落地上存在两处致命断裂**：
   - **面板 API 完全无鉴权（A01/EoP，Critical）**：`require_auth`/`API_AUTH_ENABLED`/`API_TOKENS` 整套鉴权代码已实现却**从未接线**（死代码），任何能访问服务的客户端可触发采集、读取全部第三方资产/PII、操纵审批流。
   - **密钥治理形同虚设（P0，Critical）**：`config.json` 明文硬编码 hunter×5、qichacha app_key/secret_key，且**根目录无 `.gitignore`**、整个仓库已 staged 待提交 → 下一次 `git add -A && commit && push` 即把密钥推送出去。**经 git 历史核查，密钥目前尚未进入提交历史（好消息），但泄露一触即发。**

3. **次要但高危**：API Key 经异常日志泄露（F-03）、采集所得第三方 PII 明文入库且随仓库提交（F-04）、出站目标无白名单校验导致 SSRF（F-05）。

**整体安全态势评分：D（不及格）**。核心合规设计优秀，但外部暴露面与密钥管理将整体风险拉至不可接受。

---

## 二、严重度分布

| 严重度 | 数量 | 编号 |
|---|---|---|
| 🔴 Critical (P0) | 2 | F-01, F-02 |
| 🟠 High | 3 | F-03, F-04, F-05 |
| 🟡 Medium | 5 | F-06, F-07, F-08, F-09, F-10 |
| 🟢 Low/Info | 2 | F-11, F-12 |
| **合计** | **12** | |

---

## 三、STRIDE 威胁建模表

| 类别 | 威胁场景 | 对应发现 | 严重度 |
|---|---|---|---|
| **Spoofing 伪造** | 无鉴权 API → 任意客户端可伪造成合法调用方；合规 `source_name` 由调用方自报（未被校验） | F-01, F-09 | Critical |
| **Tampering 篡改** | 未鉴权 `/approval/decide` 可任意批准/驳回任务；config.json 明文可被本地篡改；采集数据无完整性校验 | F-01 | Critical |
| **Repudiation 抵赖** | 未鉴权 API 的审计记录 `subject_id` 为空，无法溯源到操作者；日志可被注入伪造 | F-08 | Medium |
| **Info Disclosure 信息泄露** | 未鉴权 API 暴露全部已采集第三方资产/PII；`data/agent.db`（含 PII）被 git 跟踪；密钥明文 + 日志泄露密钥；`/docs`、`/openapi.json` 暴露 | F-01, F-02, F-03, F-04 | Critical/High |
| **DoS 拒绝服务** | 未鉴权 + 无频控 → 高频触发对外采集，耗尽第三方配额并造成资源 DoS | F-07 | Medium |
| **EoP 权限提升** | 未鉴权即等同于完全控制（触发采集/读全部数据/操纵审批）= 对任意网络可达者的完全越权 | F-01 | Critical |

---

## 四、OWASP Top 10 (2021) 检查表

| # | 类别 | 结论 | 发现 |
|---|---|---|---|
| A01 | 失效的访问控制 | ❌ 失败 | **F-01**（API 全无鉴权）、F-09（loopback 豁免） |
| A02 | 加密失败 | ❌ 失败 | **F-02**（密钥明文）、**F-03**（密钥入日志）、F-04（PII 明文入库入库仓）、F-11（MD5 签名） |
| A03 | 注入 | ✅ 基本通过 | SQL 全部参数化（无 SQLi）；无命令注入；**但存在 SSRF（归入 A10）** |
| A04 | 不安全设计 | ❌ 失败 | F-05（R1 不校验目标）、F-07（无频控）、F-09（loopback 信任） |
| A05 | 安全配置错误 | ❌ 失败 | F-02（无 .gitignore）、F-04（敏感库入仓）、F-10（`/docs` 开放、无安全头、FAFU 主动产物入仓） |
| A06 | 脆弱/过时组件 | ⚠️ 风险 | **F-06**（依赖未锁版、openpyxl 未声明） |
| A07 | 身份鉴别失败 | ❌ 失败 | F-01（鉴权代码未启用，等同无认证）；令牌比较本身安全（`hmac.compare_digest`） |
| A08 | 软件与数据完整性 | ⚠️ 风险 | F-06（供应链未锁版）、F-12（mock 数据污染）、subfinder 适配器设计为 shell-out（当前 stub） |
| A09 | 日志与监控失败 | ❌ 失败 | **F-03**（密钥入日志）、F-08（无身份溯源、日志注入）、无异常告警 |
| A10 | SSRF | ❌ 失败 | **F-05**（用户可控 domain 直入 httpx.get，无内部地址阻断） |

---

## 五、逐条发现（含位置 / 证据 / 建议 / 严重度 / 置信度）

### F-01 🔴 Critical — 面板 API 完全无鉴权（A01 / EoP）
- **位置**：`passive_agent/api/deps.py:38`（定义 `require_auth`）、`passive_agent/main.py:25-31`（挂载 router，未设全局依赖）、`passive_agent/api/routes_*.py`（7 个路由文件均无 `Depends(require_auth)`）
- **证据**：Grep 确认 `require_auth` **仅在其定义处出现一次**；全部路由文件均未引用；`main.py` 未设置 `app.dependencies`。即 `API_AUTH_ENABLED`/`API_TOKENS`/`require_auth`/`verify_token` 整套鉴权实现是**死代码，从未接线**。
- **影响**：任意网络可达客户端可：
  - `POST /api/v1/console/run-company` 触发对外采集（耗尽第三方配额 + 触发 SSRF）；
  - `GET /api/v1/graph/topology`、`/inventory/export`、`/approval/queue` 读取全部已采集的第三方资产与 PII；
  - `POST /api/v1/approval/{create,decide,resume}` 操纵三级审批工作流（篡改治理）。
  - 等价于对任意人的完全越权（EoP）。
- **置信度**：10/10
- **建议**：
  1. 在 `main.py` 为每个 router（或全局 `app.dependencies`）添加 `Depends(require_auth)`；
  2. 通过环境变量 `PASSIVE_API_TOKENS` 注入合法令牌，确保 `API_TOKENS` 非空；
  3. 生产环境关闭 `/docs`、`/openapi.json` 或对其实行鉴权；
  4. 参见 F-09，移除 loopback 豁免或改为受信代理下的 `X-Forwarded-For` 解析。

### F-02 🔴 Critical/P0 — config.json 明文硬编码凭证 + 无 .gitignore → 随时泄露
- **位置**：`config.json:2-14`（明文 hunter×5、qichacha `app_key`/`secret_key`）；根目录**无 `.gitignore`**；`git status` 显示大量文件已 staged（`A`）待提交。
- **git 历史核查结论（关键，已主动验证）**：
  - `git ls-files --error-unmatch config.json` → **报错**，证明 config.json 既未被提交也未被暂存；
  - `git log --all -- config.json` → 空；`git grep` 全历史检索 `hunter`/`qichacha` → 无结果；
  - 唯一提交 `1931796 baseline-empty` 为空提交（其 `git show --stat` 无文件列表）；
  - 结论：**密钥目前尚未进入 git 历史（好消息）**。
- **但风险一触即发**：无 `.gitignore`，且其余文件已全部 `git add -A` 暂存。下一次 `git add .` / `git commit` / `git push` 将把 `config.json` 一并纳入并推送到远端。
- **影响**：5 组 Hunter Key + 企查查 app_key/secret_key 一旦外泄，攻击者可冒用企业被动采集配额、查询第三方工商 PII；凭据轮换成本高。
- **置信度**：10/10
- **建议（完整处置链，尽管尚未入 git，按"疑似泄露"处置）**：
  1. **立即轮换**全部 Hunter Key 与企查查 app_key/secret_key（工作目录可能曾被共享/备份，按已泄露预案执行）；
  2. **新增 `.gitignore`**：忽略 `config.json`、`data/`、`*.db`、`*.db-wal`、`*.db-shm`、`.env`、`FAFU/*资产*`、`__pycache__/`；
  3. **密钥迁移**：经环境变量（如 `PASSIVE_API_KEYS_HUNTER`、`PASSIVE_API_KEYS_QICHACHA`）注入——`config.py` 已支持 env 优先于 config.json，不再落盘；
  4. **预提交钩子**：用 pre-commit（或自定义 `pre-commit` hook）扫描密钥模式，阻止含密钥文件提交；
  5. **（预备）** 若后续不慎提交，用 `git filter-repo` / BFG 清除历史并强制推送——当前无需执行。

### F-03 🟠 High — API Key 经异常日志泄露至 stdout/JSON 日志（A09 / A02）
- **位置**：`passive_agent/collector/sources.py:392`（Hunter `_logger.warn(f"Hunter page={page} 异常: {e}")`）、`:576`（企查查）、`:157/:198/:199/:238`（其他源）；`passive_agent/common/logging.py:43-46`（`print` JSON 到 stdout，无脱敏）。
- **证据**：`httpx` 异常对象的字符串表示包含**完整请求 URL**（含 `?api-key=...` 与 `&key=app_key`）。采集器出错时该 URL 被 f-string 化写入日志 → Hunter/Qichacha 密钥泄露到 stdout，若 stdout 重定向到 `LOG_PATH` 则落入 `data/audit.jsonl`。
- **置信度**：9/10（代码路径明确；httpx 异常含 URL 为公开行为）
- **建议**：异常日志不要直接 f-string 化 `e`；记录结构化字段（动作/源/状态码）；对 URL 做脱敏（剥离 query 中的 `api-key`/`key`/`token` 值）；在 `common/logging.py` 增加 secret 红action（正则替换密钥值）。

### F-04 🟠 High — 采集所得第三方 PII / 资产情报明文入库并随仓库提交（A02 / A09 / 数据合规）
- **位置**：`passive_agent/storage/db.py:72-81`（`t_subject`：enterprise/name/credit_code/relation 明文）、`:142-156`（`t_collect_asset`：domain/ip/port/tech_stack/title 明文）、`:91-99`（`t_collect_result.payload_json` 明文）；`data/agent.db` 被 git 跟踪（`git ls-files` 中含 `data/agent.db`）。
- **影响**：统一社会信用代码、法人、联系方式、资产 IP/端口等第三方 PII 与情报以明文存于 SQLite，且该库文件被纳入版本控制 → 一旦仓库推送即泄露；无脱敏、无留存期限、无加密。
- **置信度**：10/10
- **建议**：将 `data/` 加入 `.gitignore` 并立即从索引移除（`git rm --cached data/agent.db`）；落地存储加密或至少字段级脱敏（信用代码/法人做掩码）；制定留存期限与定期销毁策略；审计日志不记录敏感目标原文（配合 F-03）。

### F-05 🟠 High — 出站目标无白名单校验，存在 SSRF（A10）
- **位置**：`passive_agent/compliance/engine.py:60-99`（R1 仅校验 `action_type`，`target_url` 参数被接受但**从未评估**）；`passive_agent/collector/sources.py`（各 `collect` 将 `domain` 直接拼入 `httpx.get` URL，如 :91 / :131 / :181 / :215 / :256 / :340 / :513）；`passive_agent/collector/manager.py:63-124`（`domain` 来自用户输入，无校验）；`passive_agent/api/routes_console.py:34-37`（`run-company` 接受 enterprise→推断 domain→采集）。
- **影响**：用户可控的 `domain` 直接进入 `httpx.get`，无私有地址/链路本地/元数据服务（`169.254.169.254`）阻断；云环境下面向元数据服务的 SSRF；经未鉴权 API 可远程触发。
- **置信度**：8/10（代码明确无目标校验；经 API 触发需 enterprise→domain 推断，难度中等但存在）
- **建议**：在 R1 引擎中对 `target_url` 做解析 + 黑名单（拒绝私有/链路本地/元数据地址段）；采集器 `domain` 入参做格式与归属校验（仅允许公开域名后缀）；`httpx` 层强制绑定出口并禁用重定向到内部地址。

### F-06 🟡 Medium — 依赖未锁版本 / 未声明依赖（A06 / A08）
- **位置**：`requirements.txt:2-16`（全部使用 `>=` 范围，无精确版本 / 无哈希）；`passive_agent/collector/manager.py:130`（`import openpyxl` 但 requirements 未声明）。
- **影响**：`>=` 范围允许安装更高（可能含漏洞或被投毒）版本；无 hashes 无法防篡改；`openpyxl` 缺失导致 `collect --export` 运行时 `ImportError`。
- **置信度**：10/10
- **建议**：用 pip-tools 生成 `requirements.lock` 精确锁版 + 哈希；补 `openpyxl`（或移除 Excel 导出）；接入 `pip-audit` / Dependabot 定期扫描 CVE。

### F-07 🟡 Medium — API 层无频控/限流，可被用于 DoS 与配额耗尽（A04）
- **位置**：`passive_agent/api/routes_*.py`（各端点无 rate limit）；频控仅存在于 `passive_agent/gateway/proxy.py`（赛事提交），不覆盖面板 API。
- **影响**：未鉴权 + 无频控 → 攻击者可高频调用 `/console/run-company` 触发大量对外请求，耗尽第三方 API 配额并造成资源 DoS。
- **置信度**：9/10
- **建议**：面板 API 增加全局 / 按 IP 限流（slowapi 或自定义限速中间件），与鉴权一并启用。

### F-08 🟡 Medium — 日志注入 / 无操作者身份溯源（A09）
- **位置**：`passive_agent/api/routes_console.py:35`（`enterprise` 用户可控并传入 `run_company` → `manager.collect` 经 `_logger.info(f"开始采集: {name}...")` 入库 `t_collect_asset.enterprise` 与审计）；无 auth → 审计记录 `subject_id` 为空，无法归因。
- **影响**：用户可控 `enterprise` 若含换行可伪造日志行（日志注入）；未鉴权导致所有 API 行为无法追溯到人（抵赖）。
- **置信度**：7/10
- **建议**：日志前对 `enterprise` 做白名单/长度/字符校验并转义换行；鉴权后记录操作者指纹到审计日志。

### F-09 🟡 Medium — loopback 鉴权豁免（若将来接线将成绕过）（A01）
- **位置**：`passive_agent/api/deps.py:32-42`（`_is_loopback` 对 `127.0.0.1`/`::1`/`testclient` 直接放行）。
- **影响**：当前未接线故无直接影响；但若启用 `require_auth` 且部署在反向代理后（未正确传递真实客户端 IP），所有请求表现为 loopback → 鉴权整体绕过。
- **置信度**：8/10
- **建议**：不要基于 TCP peer 做信任判定；通过受信反向代理的 `X-Forwarded-For`（经 proxy trust）获取真实 IP，或干脆不对 loopback 豁免。

### F-10 🟡 Medium — 安全配置缺项（A05）
- **位置**：`passive_agent/main.py`（无 CORSMiddleware——此为安全默认，但亦无安全响应头 HSTS/CSP/X-Frame-Options）；`/docs`、`/openapi.json` 开放且鉴权豁免；`FAFU/` 目录含 `TscanClient` 主动探测结果与"目标资产"表，被 git 跟踪。
- **影响**：API schema 暴露；FAFU 主动扫描产物与第三方目标情报入库/入仓，既违反"严格被动"原则，也构成数据治理风险。
- **置信度**：8/10
- **建议**：生产关闭 `/docs`；增加基础安全头；将 FAFU 主动扫描产物移出本仓库并禁止提交第三方目标情报；核查 `TscanClient` 使用是否符合被动约束（若确为主动探测，需从被动 Agent 仓库剥离，见 F-12 备注）。

### F-11 🟢 Low/Info — 企查查签名使用 MD5（A02）
- **位置**：`passive_agent/collector/sources.py:491`（`hashlib.md5(origin).hexdigest()`）。
- **影响**：MD5 用于接口签名强度弱；但为企查查 API 强制规范，非我方可控。
- **置信度**：10/10
- **建议**：记录为厂商约束；自身侧不在别处复用 MD5 做安全用途。

### F-12 🟢 Low/Info — 枚举器返回伪造（mock）主体数据（A08 数据完整性）
- **位置**：`passive_agent/enumerator/adapter.py:48-54`（返回 `{enterprise}-控股子公司L{d}` 等伪造主体）。
- **影响**：为通过测试而构造的 mock 关系数据若混入真实台账/拓扑，可能污染情报准确性（非安全漏洞，但影响 CTEM 可信度）。
- **置信度**：8/10
- **建议**：mock 数据明确标注来源=TEST，不写入 `t_subject`/`t_asset` 真实表。

---

## 六、正向验证（给予肯定，非问题）

- **R1 合规引擎确为 fail-closed**：主动动作硬编码 BLOCK（`engine.py:62`、`rules.py:37-39`），未知动作默认 BLOCK（`engine.py:90-99`），DB 不可用时回退安全默认集（`engine.py:54-56`）。
- **采集器每个对外方法均先 `_r1_pass` / `_assert_passive`**（`sources.py:87/126/...`、`adapter.py:43/92/105`）。
- **网关代理 `submit()` 出站前确有 R1 前置校验**（`proxy.py:37-43`）。
- **全部 SQL 使用参数化查询**（`db.py` write/query、`audit/logger.py`、`audit/query.py`、`cli.py`）→ 无 SQL 注入。
- **令牌校验使用 `hmac.compare_digest` 常量时间比较**（`security.py:44`）→ 防时序侧信道。
- **未引入 nmap / 主动扫描类库**；subfinder 适配器当前为 stub（未实际 shell out），`verify_domain_alive` 与 dnspython 仅做 DNS 解析、不主动连接 → 符合被动约束（实现层面）。

---

## 七、关键行动项（P0 优先）

| 优先级 | 行动 | 对应发现 |
|---|---|---|
| **P0** | 为面板 API 接线鉴权（`main.py` 全局 `Depends(require_auth)` + 注入 `PASSIVE_API_TOKENS`）；关闭/鉴权 `/docs` | F-01, F-09 |
| **P0** | 立即轮换全部 Hunter/Qichacha 密钥；新增 `.gitignore`（config.json/data//.env/FAFU 资产）；密钥改环境变量注入；加 pre-commit 密钥扫描钩子 | F-02 |
| **P0** | `git rm --cached data/agent.db` 并从 `.gitignore` 排除 `data/`；密钥已读，确认未入历史，但需防止下次提交泄露 | F-02, F-04 |
| **P1** | 修复日志密钥泄露：异常日志脱敏、URL 剥离 key 参数 | F-03 |
| **P1** | R1 增加对 `target_url` 的解析 + 内部地址黑名单，阻断 SSRF（含云元数据 169.254.169.254） | F-05 |
| **P1** | 采集数据加密/脱敏存储 + 留存期限 + 定期销毁 | F-04 |
| **P2** | 依赖锁版（`requirements.lock` + 哈希）+ 补 `openpyxl` + 接入 `pip-audit` | F-06 |
| **P2** | 面板 API 增加全局频控/限流 | F-07 |
| **P2** | 日志输入校验（防注入）+ 鉴权后记录操作者指纹 | F-08 |
| **P2** | 生产安全响应头；FAFU 主动扫描产物移出仓库；核查 TscanClient 是否符合被动约束 | F-10 |
| **P3** | mock 数据标注 TEST 不落真实表；MD5 仅限厂商接口 | F-11, F-12 |

---

## 八、给 team-lead 的处置摘要

- **最致命两项（P0）**：① 面板 API 鉴权代码写了却没接线——等于完全开放；② `config.json` 明文密钥 + 无 `.gitignore` + 全仓已 staged，泄露只差一次 `git push`。好消息：**密钥经核查尚未进入 git 历史**，现在补救成本最低。
- **合规引擎本身可信**：R1 fail-closed 经代码验证成立，这是项目护城河，勿因表面问题否定。
- **SSRF 与密钥日志泄露**为 High，需随 P0 一并修复。
- **Go/No-Go = NO-GO**：修复 F-01、F-02 及 F-03~F-05 前，禁止网络暴露部署。
