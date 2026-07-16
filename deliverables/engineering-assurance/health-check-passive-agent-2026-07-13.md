# 全维度项目体检报告 · Passive Agent（passive_agent/）

**日期**：2026-07-13
**工作流**：工作流 1（全面代码审查）+ 工作流 5（技术债评估）组合，叠加测试/可运维性/文档维度（全维度体检）
**参与成员**：Cody（代码审查师）· Archi（架构师）· Rex（SRE 工程师）· Tessa（测试专家）· Docu（技术文档师）

---

## 📌 TL;DR（执行摘要）

- **整体结论**：架构分层骨架清晰、合规红线（R1 fail-closed）与代码内联文档基础扎实，但**工程落地与"企业级"定位存在明显落差**——多处"能跑通演示但生产不可信"的硬伤：API 鉴权写好却未接线、明文密钥已入版本库、频控实际失效、采集结果未真落库。当前**适合赛事/演示，离生产级还有一轮以"鉴权落地 + 凭证治理 + 数据可信 + 测试止血"为主线的硬仗**。
- **严重度分布**：🔴严重 8 项 / 🟠高 18 项 / 🟡中 23 项 / 🟢低 9 项
- **阻塞 / 非阻塞**：8 项 🔴 均为生产上线阻塞项（安全/合规/数据可信直接威胁），必须修复后方可投产；🟠 项建议在首版生产化前清零。
- **关键事实更正**：经主理人实测复核，多库文档债报告中"无 CI / 无 guard_passive"判定为**漏判**（Glob 默认跳过隐藏目录 `.github/`），实际 `.github/workflows/ci.yml` 与 `scripts/guard_passive.py` 均已存在；相应文档债条目已降级修正，详见 §6。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🔴 不通过（生产级）；🟡 有条件通过（赛事/演示级） |
| 阻塞项数量 | 8（全部为 🔴 严重） |
| 关键行动项 | 12 条（见 §行动清单，P0 共 7 条） |
| 建议下一步 | 先集中 1–2 周做 P0 止血（鉴权接线 + 凭证轮换出仓 + 前端 XSS + 采集落库 + 长任务异步化 + 旧采集补测 + CI 鉴权 ON 作业），再做 P1 架构止血与文档体系搭建 |

---

## 🔍 一、审查发现（按严重度排序，跨安全/性能/正确性/可维护性去重合并）

> 来源：Cody 代码审查 16 项 + Rex 可运维性 15 项 + 主理人事实复核。去重后按严重度排列关键项。

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| 1 | 🔴严重 | 安全·鉴权缺失 | `api/deps.py:38` / `main.py:25-31` | `require_auth` 已定义但从未作为 `Depends` 接入任何 router，全量 API 实际零鉴权 | 在 `main.py` 用 `include_router(..., dependencies=[Depends(require_auth)])` 全局接线；`API_TOKENS` 为空时 fail-closed 已正确 | Cody |
| 2 | 🔴严重 | 安全·鉴权绕过 | `api/deps.py:32-35` | `_is_loopback` 对 127.0.0.1 免鉴权，部署在反向代理后所有外部请求 client.host 均为代理地址 → 鉴权整体绕过 | 改用受信 `X-Forwarded-For` 或部署层网络隔离，禁止对代理来源免鉴权 | Cody |
| 3 | 🔴严重 | 密钥管理 | `config.json:2-14` | 明文提交 5 个 Hunter Key + qichacha `app_key/secret_key`，且无 `.gitignore` → 凭证已入版本库 | 立即轮换并移出版本库 + `.gitignore` + `config.example.json`；改 `PASSIVE_API_KEYS` 环境变量注入；CI 接 gitleaks | Rex |
| 4 | 🔴严重 | 可靠性·频控 | `gateway/proxy.py:27-31` / `routes_console.py:26,48` | `ApiProxy`/`RateLimiter` 每请求新建，跨请求/跨 worker 频控状态不共享 → 全局频控硬闸实际失效、看板 quota 恒为 0 | 改为进程单例（多 worker 用 Redis）；压测验证频控确实生效 | Rex |
| 5 | 🔴严重 | 并发·可用性 | `api/routes_console.py:34-37` / `loop.py:39,122-239` | `run_company` 同步在请求线程跑完整企业闭环（含阻塞网络 IO，可达分钟级），无任务队列 → 并发耗尽线程池 | 改 `BackgroundTasks`/任务队列（arq/RQ/Celery）+ 状态查询接口；HTTP 层设超时 | Cody/Rex |
| 6 | 🟠高 | 正确性·数据丢失 | `orchestrator/loop.py:209-215` | 采集结果 INSERT 写空 `payload_json="{}"`，`except: pass` 吞写库失败 → 数据不可溯源 | 序列化 `collect_results/total_items` 持久化；移除裸 except，计入 errors | Cody |
| 7 | 🟠高 | 安全·XSS | `static/app.js:53-58,86-89` | 企业名/task_id 未转义插值进 `innerHTML` 与 `onclick` → 存储/反射型 XSS（多运营者共用看板） | 用 `textContent`/DOM 构造替代拼接；`task_id` 经 `encodeURIComponent`/`JSON.stringify` 传参 | Cody |
| 8 | 🟠高 | 正确性·合规缺口 | `orchestrator/loop.py:218-231` | `proxy.submit()` 在 `approval.create()` 之前独立执行，从不检查审批状态 → 审批形同虚设 | 提交前读审批状态，非 APPROVED 拦截；审批 gate 前置为出站硬依赖 | Cody |
| 9 | 🟠高 | 性能·挂死 | `collector/manager.py:312-322` | `_enrich_ips` 用 `ThreadPoolExecutor` + `as_completed(timeout=30)`，但 `socket.getaddrinfo` 无超时挂死；退出 `shutdown(wait=True)` 阻塞 → 编排线程卡死 | DNS 解析套硬超时；超时后 `shutdown(cancel_futures=True)` | Cody |
| 10 | 🟠高 | 正确性·设计不符 | `gateway/proxy.py:49-56` / `ratelimiter.py:50-53` | 注释称"超限排队不丢弃"，实现却 `acquire` 返回 False 直接拒绝；`_queued` 计数从不被消费 | 实现真排队重试或如实改为限流拒绝并更新文档 | Cody |
| 11 | 🟡中 | 并发·竞态 | `collector/sources.py:289,413-419` | `HunterCollector._key_index` 类级共享，多实例并发 `collect()` 自增无锁 → Key 轮询错乱 | 改实例级指针或加 `threading.Lock()` | Cody |
| 12 | 🟡中 | 正确性·校验失真 | `orchestrator/loop.py:197,199` | 调用 `VerificationPipeline.run` 硬编码 `layer1_biz_match=True`、`layer3_time_ok=True` → 所谓"四层校验"仅 L2/L4 生效 | 由真实情报结果驱动 L1/L3，否则移除该层并更正文档 | Cody |
| 13 | 🟡中 | 正确性·假数据 | `enumerator/adapter.py:48-54` | `query_relations` 返回硬编码占位主体当真实股权穿透结果并写入 `t_subject` | 明确标注占位/降级；真实穿透接入后再生效 | Cody |
| 14 | 🟡中 | 正确性·死方法 | `enumerator/adapter.py:106` | `import_fafu_seeds` 调 `self._manager.import_from_fafu(...)`，但 `CollectorManager` 无此方法 → AttributeError | 改为 `import_from_dir` 或补方法 | Cody |
| 15 | 🟡中 | 可维护性·重复 | `collector/manager.py` vs `scheduler.py` | 两套并行采集编排（CollectorManager / CollectionScheduler），`sources.py` 被复用，行为分叉 | 收敛为单一采集内核，统一入口 | Cody/Archi |
| 16 | 🟡中 | 依赖债 | `requirements.txt` | 仅下限/部分上限，无 `==` 锁定、无 lockfile/hash，面临 pydantic 3.0 / httpx 1.0 破坏性升级 | 引入 pip-tools/poetry 锁定精确版本 + 哈希；CI 跑 pip-audit | Cody |
| 17 | 🟢低 | 可维护性·异常掩盖 | `proxy.py:75`/`audit/logger.py:36`/`loop.py:214` 等多处 | 大量 `except Exception: pass` 静默吞异常 | 至少 `logger.error` 并上抛关键路径异常 | Cody |

> 正面项：全仓 SQL 参数化（无注入）、无 `eval/exec/pickle` 误用、`Token` 用 `hmac.compare_digest` 常量时间比较、密钥仅经环境变量注入、无命令注入命中——安全基线达标。

---

## 🏗️ 二、架构债评估（Archi）

> 分层骨架清晰（api→域服务→storage/common），API→服务层边界守得住，R1 关隘统一 fail-closed。核心债集中在循环依赖、死代码、全局状态。

| # | 描述 | Impact | Risk | Effort | 改进方向 |
|---|------|------|------|------|---------|
| D1 | `collector/adapters.py`（472 行）被同名包 `collector/adapters/` 遮蔽 → 死代码+分叉，文件内独有 4 适配器从未注册 | 4 | 4 | 3 | 删除被遮蔽文件（先 grep 确认无外部引用）；以包为唯一源 |
| D2 | `collector ↔ enumerator` 循环依赖（惰性 import 掩盖） | 4 | 4 | 3 | 依赖倒置：下沉 `infer_domain` 等到 `common/domainkit`；enumerator 依赖接口 |
| D3 | `common ↔ compliance` 循环依赖（`common` 非纯净基础层） | 4 | 4 | 2 | 把 `compliance_client.check` 上移到 `compliance.gate`；使 `common` 回归叶子层 |
| D4 | `storage/db.py` 进程级全局单例连接 + 全局锁 → 并发瓶颈+难测试 | 4 | 3 | 3 | Repository/连接提供抽象 + 依赖注入；保留 WAL 但解耦全局状态 |
| D5 | 上帝文件 + 数据内嵌：`sources.py` 689 / `domain_db.py` 602（内嵌知识库）/ `manager.py` 390 | 3 | 3 | 4 | 知识库外置 JSON/YAML；`sources.py` 按源拆文件；`manager` 抽取独立函数 |
| D6 | `orchestrator/loop.py` 巨型过程函数 `run_company()`（251 行）串联全链路 | 3 | 3 | 3 | 拆为可注入 `Phase` 步骤/流水线；`db.write` 经 repository |
| D7 | 同名词调度模块混淆：`collector/scheduler.py` vs `scheduler/compute_scheduler.py` | 2 | 2 | 2 | 统一命名或在文档明确区分 |
| D8 | 20+ 处惰性 import 破解循环依赖（隐藏耦合、碍静态分析） | 2 | 3 | 2 | 消除 D2/D3 根因后回归顶层 import |
| D9 | API 层越界读 `eng._rules`；handler 内 `new` 全局对象无生命周期管理 | 2 | 2 | 2 | 加公开只读接口；经 DI/单例提供共享实例 |
| D10 | 配置散落/硬编码常量（端口、魔法数写在适配器内） | 2 | 2 | 2 | 收敛到 `config.py`；知识库外置 |

**Top 5 改进（按性价比 Impact×Risk/Effort）**：① D3 解 common↔compliance 环（性价比 8.0）② D1 删死代码（5.33）③ D2 解 collector↔enumerator 环（5.33）④ D4 解耦 DB 全局态（4.0）⑤ D6 拆巨型函数（3.0）。

---

## 🧪 三、测试覆盖与测试债（Tessa）

> 实测总覆盖率 **62%**（基于工作区已有 `.coverage`，未重跑 180+ 套件）。框架 pytest 8 + TestClient，外部依赖经 conftest 全局 patch 拦截。

**覆盖良好（≥80%）**：api/deps 95%、routes_gateway 82%、compliance/* 90-100%、verifier/pipeline 91%、approval 79-100%、storage/db 95%、gateway/ratelimiter 97%、adapters/* 83-97%。
**薄弱（部分覆盖）**：routes_console 49%、routes_compliance 55%、routes_metrics 55%、routes_approval 63%、common/security 70%（仅附带）、orchestrator/loop 61%、verifier/layers 50%、domain_db 57%、collector/model 54%、fault_tolerance 80%。
**关键未覆盖（高风险）**：`collector/manager.py` **11%**、`collector/sources.py` **18%**、`collector/adapters.py`（顶层）**0%** —— 旧采集核心逻辑几乎无回归保护。

**测试债清单**

| # | 缺失项 / 债务 | 严重度 | 影响 |
|---|---|---|---|
| 1 | 旧采集 manager 11%/sources 18%/adapters 0% 无测试 | 🔴 | 出网安全 & 数据完整性回归无法拦截 |
| 2 | 认证默认关闭且 CI 以"鉴权 OFF"跑全量 → 安全红线假绿 | 🔴 | 鉴权 ON 路径破坏 CI 仍绿 |
| 3 | API 端点覆盖不均（49%-82%，缺错误/鉴权分支） | 🟠 | 约半数业务端点错误分支未验证 |
| 4 | common/security.py 无专门边界单测（仅附带 70%） | 🟠 | 令牌比较/畸形输入边界无针对性验证 |
| 5 | CI 无覆盖率门禁 | 🟠 | 覆盖率可随意下滑无告警 |
| 6 | 过度依赖 conftest 全局 autouse patch，缺 respx/pytest-mock | 🟠 | 真实适配器响应形状从未被校验 |
| 7 | 外部 API 契约/消费者测试缺失 | 🟠 | 上游响应结构变更无预警 |
| 8 | orchestrator/loop 61%、verifier/layers 50% 半覆盖 | 🟡 | 主循环与验证分层分支遗漏 |
| 9 | 测试数据隔离不足（全局 monkeypatch settings） | 🟡 | 用例隐式耦合，"假绿" |
| 10 | 集成/E2E/压测偏轻 | 🟡 | 端到端编排与容量基线缺保障 |
| 11 | fault_tolerance 重试/熔断边界、级联失败兜底不全 | 🟡 | 故障注入覆盖不足 |
| 12 | .coverage 未发布、无阈值基线 | 🟢 | 无法趋势追踪 |

**测试策略（金字塔 + 分阶段）**：风险优先补"出网安全 + 数据完整性 + 鉴权"三类高影响路径。Phase 0 止血（1-2 周）：旧采集补单测（manager≥70%/sources≥60%）+ `test_security.py` + CI 拆"鉴权 ON"作业 + 覆盖率门禁 `--fail-under=70`；Phase 1 均衡（2-4 周）：API 端点对拍至 ≥80% + 引入 respx + 外部契约测试 + 故障注入；Phase 2 加固：loop/layers 分支 + 被动出网闸门单测 + 压测基线入 CI。工具建议：respx、pytest-mock、pytest-cov、hypothesis/schemathesis。

---

## ⚙️ 四、可运维性 & 可靠性风险（Rex）

> 合规红线与多源容错设计扎实；运行态/部署态存在可用性、合规证据完整性、频控失控三类风险。

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议 |
|---|--------|------|---------|---------|------|
| 1 | 🔴 | 密钥管理 | `config.json:2-14` | 明文密钥入版本库且无 gitignore | 轮换+出仓+`.gitignore`+env 注入+CI gitleaks |
| 2 | 🔴 | 频控 | `gateway/proxy.py:27-31` | RateLimiter 每请求新建 → 频控失效、quota 恒 0 | 进程单例/Redis；压测验证 |
| 3 | 🔴 | 并发 | `routes_console.py:34-37` | 长任务同步阻塞请求线程 | 后台任务/队列+限并发+超时 |
| 4 | 🟠 | 健康检查 | `main.py:42-44` | `/health` 空壳，不探 DB/依赖 | 拆 liveness/readiness，readiness 失败返 5xx |
| 5 | 🟠 | 持久化/SPOF | `storage/db.py:160-194` | 全局单连接无 `busy_timeout`，容器临时 FS 重启丢数据 | 挂持久卷+`PRAGMA busy_timeout=5000`+WAL 检查点；多 worker 换 Postgres |
| 6 | 🟠 | 容错恢复 | `fault_tolerance.py:115-117` | 源失败达阈值永久降级到 mock，无半开探测 | 断路器半开机制，定时探测恢复 |
| 7 | 🟠 | 优雅停机 | `main.py:37-39` | 废弃 `@app.on_event` 无 shutdown 钩子 | 改 `lifespan`；SIGTERM 排空在途任务+落快照 |
| 8 | 🟠 | 网络调用 | `sources.py` 多处 | 阻塞 `httpx.get` 无连接池/keep-alive，与 adapters 不一致 | 共享 `httpx.Client` + 统一 `timeout=settings.SOURCE_TIMEOUT` |
| 9 | 🟡 | 可观测性 | `metrics/aggregator.py:182-225` | 大量 `_estimate_*` 占位估算，无 Prometheus/告警 | 接真实计数器并导出 Prometheus |
| 10 | 🟡 | 配置校验 | `config.py:47-108` | pydantic 仅类型转换，无语义校验 | `field_validator` + 启动 `ensure_init` 自检 fail-fast |
| 11 | 🟡 | 重试/限流语义 | `fault_tolerance.py`/`ratelimiter.py` | 无指数退避重试；`release()` 死代码 | 同适配器有界退避；`_queued` 设上限 |
| 12 | 🟡 | 数据一致性 | `loop.py:209-213` | `t_collect_result` 无 `result_id` 唯一约束，重复插入 | 加 UNIQUE + `ON CONFLICT DO UPDATE` |
| 13 | 🟡 | 部署/回滚 | 仓库根 | 无 Dockerfile/compose/`.env.example`/回滚 runbook | 提供容器化+runbook（与 Docu 协同） |
| 14 | 🟡 | 日志治理 | `common/logging.py:43-46` | 无级别过滤/采样，全量 print | 加级别过滤+采样；structlog+OTel |
| 15 | 🟢 | 并发一致性 | `fault_tolerance.py:51 vs 121-138` | `_get_health` 读未加锁 | 读用同一把锁或原子结构 |

**部署前检查验收口径（7 项）**：密钥出仓+gitignore+gitleaks / 频控单例+压测非 0 / SQLite 持久卷+busy_timeout / liveness-readiness 拆分+lifespan / 长任务移出请求链路+启动自检 / Prometheus 真实指标 / Dockerfile+compose+`.env.example`+回滚 runbook。

---

## 📚 五、文档债（Docu，含事实纠错更正）

> 代码内联注释基础尚可（模块级 docstring 全覆盖，`config.py` 内联注释详尽，`cli.py` 自说明良好，FastAPI `/docs` 自动文档具备），但**工程化文档体系缺失**。

**文档债清单（合并表，共 19 项）**

| # | 缺失项 | 现状与证据 | 影响 | 优先级 |
|---|--------|-----------|------|--------|
| 1 | 根 `README.md` | 仓库根无 `*.md` | 新人/运维无法上手 | 高 |
| 2 | 准确可维护的系统设计文档 | 唯一设计文档 `docs/system_design.md` 是"Phase 1 加固施工蓝图"，**描述的状态与代码事实不符**（见 §6 更正） | 误导性过期文档比缺失更危险 | 高→**中（更正后）** |
| 3 | 配置项统一说明（Config Reference） | 配置散落 `config.py` 注释 + `config.json`，无总表 | 运维改配置易错 | 高 |
| 4 | `config.json` 明文密钥 + 无 `.gitignore` | 已核实属实（hunter/qichacha 明文） | **密钥泄露风险** | 高 |
| 5 | Runbook / 部署文档 | 仅设计稿，无可操作 runbook | 上线/回滚无据 | 高 |
| 6 | ADR（架构决策记录） | 无 `adr/` 目录 | 关键约束无持久化依据 | 高 |
| 7 | API 文档（人工编写） | 仅 FastAPI 自动 `/docs`，路由 handler 无 docstring | 外部调用方无权威契约 | 中 |
| 8 | 函数/类级 docstring | 包内 349 def/class 仅 53% 有；121 公开 def 无 | 可维护性差 | 中 |
| 9 | 开发者/贡献指南 | 全仓无 CONTRIBUTING/DEVELOPMENT | 协作无规范 | 中 |
| 10 | 本地环境/测试运行指南 | 如何装依赖/起服务/`pytest` 无文档 | 新人无法独立跑通 | 中 |
| 11 | 文档组织混乱/无索引 | 散落 docs/deliverables/FAFU/.workbuddy | 检索难、过时稿混权威稿 | 中 |
| 12 | `CHANGELOG.md` | 无 | 版本不可追溯 | 低 |
| 13 | 术语表 | 散落 | 跨角色沟通成本高 | 低 |
| 14 | 新人入职指南 | 无 | 上手周期长 | 低 |
| 15 | 架构图维护机制 | `docs/*.mermaid` 未同步 | 图失真 | 低 |
| 16 | 部署与回滚 Runbook | 无 Dockerfile/compose/start 子命令 | 无法可靠部署 | 高 |
| 17 | `.env.example` | 无 | 新环境配置无从下手 | 高 |
| 18 | 容器化/进程管理说明 | 无 Dockerfile；多 worker 行为未定义 | 水平扩展语义不明 | 中 |
| 19 | CI/CD 流水线文档 | **更正**：`.github/workflows/ci.yml` 实际存在（见 §6），缺的是覆盖率门禁与 CI 说明 | 优先级降为**中** |

**建议文档结构**（Docu 原案）：`README.md` + `docs/{README,getting-started,architecture/{overview,adr/*},api/{auth,errors,endpoints},operations/{runbook,deployment,config-reference},development/{contributing,local-setup,testing},glossary}.md` + 根级 `Dockerfile`/`docker-compose.yml`/`.env.example` + `archive/competition-artifacts/`（FAFU 移入）。Docu 另附了可直接落地的 `.env.example`/`Dockerfile`/`docker-compose.yml`/`runbook.md` 草案（未写盘）。

---

## 🔎 六、事实冲突核查与更正说明（主理人实测复核）

多库（Docu）的静态扫描基于 Glob/文件清点，因工具**默认跳过以 `.` 开头的隐藏目录**，导致其判定 `.github/` 不存在。主理人用 `ls`/`find` 实测复核结果如下：

| 冲突项 | 多库判断 | 主理人实测 | 处置 |
|--------|----------|-----------|------|
| `.github/workflows/ci.yml` | 不存在（grep 0） | **存在**（627 B） | 多库漏判；文档债 #19 降级为"中"（CI 存在，缺覆盖率门禁与说明） |
| `scripts/guard_passive.py` | 不存在（grep 0） | **存在**（`./scripts/guard_passive.py`） | 多库漏判；"CI 门禁未落地"论断不成立 |
| `config.json` 明文密钥 + 无 `.gitignore` | 属实 | **属实**（已确认 hunter/qichacha 明文） | 保留 🔴 |
| 根 `.gitignore` / `Dockerfile` / `.env.example` | 不存在 | **确实不存在** | 保留 |
| `docs/system_design.md` 过期 | 描述状态不符 | 部分已落地（CI/guard_passive 已存在），但 FAFU 未归档等仍不符 | 仍属**误导性过期文档**，需更新或降级为历史蓝图 |

**结论**：泰莎实测结论（CI 存在、旧采集零测试、鉴权默认 OFF、总覆盖 62%）经核实更可信，已据此更正文档债相关条目；其余成员结论与实测一致，不做改动。

---

## 💰 七、技术债优先级总排序（Priority = (Impact + Risk) × (6 - Effort)）

> 阿奇债用原值；其余维度债由主理人按严重度合理估算 I/R/E（标注"估"）。按 Priority 降序取 Top 20。

| 排名 | 债务项 | I | R | E | Priority | 来源 |
|------|--------|---|---|---|----------|------|
| 1 | API 鉴权未接线 + 回环绕过 | 5 | 5 | 2 | 40 | Cody |
| 2 | config.json 明文密钥入库（无 gitignore） | 5 | 5 | 2 | 40 | Rex/Docu |
| 3 | 认证默认 OFF + CI 假绿 | 5 | 5 | 2 | 40 | Tessa |
| 4 | 全局频控失效（RateLimiter 每请求新建） | 5 | 4 | 2 | 36 | Rex |
| 5 | 设计文档过期误导（需更新/降级） | 3 | 4 | 1 | 35 | Docu |
| 6 | 采集结果写空 {} 吞异常 | 4 | 4 | 2 | 32 | Cody |
| 7 | 前端 innerHTML XSS | 4 | 4 | 2 | 32 | Cody |
| 8 | 审批未拦截出站 | 4 | 4 | 2 | 32 | Cody |
| 9 | common↔compliance 循环依赖 | 4 | 4 | 2 | 32 | Archi D3 |
| 10 | DNS 解析挂死线程 | 4 | 3 | 2 | 28 | Cody |
| 11 | 旧采集子系统零测试（manager/sources/adapters） | 5 | 4 | 3 | 27 | Tessa |
| 12 | 无 README / 部署 runbook | 4 | 3 | 2 | 28 | Docu |
| 13 | 依赖未锁定无 lockfile | 3 | 4 | 2 | 28 | Cody |
| 14 | 死代码 adapters.py 被遮蔽分叉 | 4 | 4 | 3 | 24 | Archi D1 |
| 15 | collector↔enumerator 循环依赖 | 4 | 4 | 3 | 24 | Archi D2 |
| 16 | run_company 同步阻塞长任务 | 4 | 4 | 3 | 24 | Cody/Rex |
| 17 | 限流实现与文档不符 | 3 | 3 | 2 | 24 | Cody |
| 18 | 健康检查空壳 | 3 | 3 | 2 | 24 | Rex |
| 19 | 容错永久降级无恢复 | 3 | 3 | 2 | 24 | Rex |
| 20 | 无优雅停机（shutdown 钩子） | 3 | 3 | 2 | 24 | Rex |

（SQLite 全局单例锁 Priority 21、异常抑制文化 18、惰性 import 20、上帝文件 12 等见各维度章节）

---

## 🩺 八、分阶段修复计划

**P0 — 止血（1–2 周，聚焦 8 个 🔴 + 高频 🟠）**
- 鉴权落地：接线 `require_auth` 全局依赖 + 修复回环绕过（排名 1）
- 凭证治理：轮换 config.json 密钥、加 `.gitignore`、改 env 注入、CI 接 gitleaks（排名 2）
- 前端安全：innerHTML → textContent/DOM（排名 7）
- 数据可信：采集结果真实落库 + 移除吞异常（排名 6）
- 长任务异步化：run_company 移出请求链路（排名 16）
- 频控生效：RateLimiter 单例 + 压测验证（排名 4）
- 测试止血：旧采集补单测 + CI 鉴权 ON 作业 + 覆盖门禁（排名 11、3）

**P1 — 架构与文档（2–4 周）**
- 删死代码 `collector/adapters.py`、解两处循环依赖（排名 14、15、9）
- SQLite 解耦全局态 + busy_timeout + 持久卷（排名 21）
- 更新过期设计文档 / 补 README + 部署 runbook + ADR（排名 5、12）
- API 端点对拍至 ≥80% + 引入 respx + 外部契约测试（Tessa Phase 1）

**P2 — 加固（持续）**
- 拆 orchestrator/loop 巨型函数、收敛双采集引擎、知识库外置
- 可观测性接 Prometheus、配置语义校验、断路器半开、优雅停机 lifespan
- 文档索引/归档整理、CHANGELOG、术语表

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责角色 | 紧急度 | 预期完成 |
|---|------|---------|--------|---------|
| 1 | 全局接线 `require_auth` 依赖 + 修复回环免鉴权绕过 | Cody + 人类负责人 | P0 | 3 天内 |
| 2 | 轮换 config.json 明文密钥、加 `.gitignore`、`config.example.json`、env 注入、CI 接 gitleaks | Rex + 人类负责人 | P0 | 3 天内 |
| 3 | 前端 `innerHTML` 拼接改 `textContent`/DOM，`task_id` 编码传参 | Cody | P0 | 1 周内 |
| 4 | 采集结果真实序列化落库，移除 `except: pass` 吞异常 | Cody | P0 | 1 周内 |
| 5 | `run_company` 改 BackgroundTasks/任务队列 + 限并发 + HTTP 超时 | Cody + Rex | P0 | 1 周内 |
| 6 | `RateLimiter` 改进程单例（多 worker 用 Redis），压测验证频控非 0 | Rex | P0 | 1 周内 |
| 7 | 旧采集子系统补单测（manager≥70%/sources≥60%）+ CI 拆"鉴权 ON"作业 + `--fail-under=70` | Tessa | P0 | 2 周内 |
| 8 | 删除被遮蔽死代码 `collector/adapters.py`，解 common↔compliance 与 collector↔enumerator 循环依赖 | Archi | P1 | 3 周内 |
| 9 | 更新/降级 `docs/system_design.md`；补根 README + 部署 runbook + ADR | Docu | P1 | 3 周内 |
| 10 | SQLite 解耦全局单例 + `busy_timeout` + 持久卷；多 worker 方案明确 | Rex + Archi | P1 | 3 周内 |
| 11 | 依赖锁定（pip-tools/poetry + lockfile + hash）+ CI 跑 pip-audit | Cody | P1 | 3 周内 |
| 12 | 健康检查拆 liveness/readiness + `lifespan` 优雅停机 + 断路器半开恢复 | Rex | P1 | 4 周内 |

---

## ⚠️ 待完善 / 已知局限

- **工具漏判已更正**：多库静态扫描因 Glob 跳过隐藏目录，误判"无 CI/无 guard_passive"，主理人已实测更正；其余文档债结论保留。
- **覆盖率未重跑**：泰莎基于工作区已有 `.coverage` 实测（62%），未重跑 180+ 套件；如需精确逐模块数字可重跑 `coverage run -m pytest && coverage report`。
- **静态分析为主**：本次活动以成员静态分析 + 主理人文件实测为主，未做动态渗透测试/负载压测/生产环境验证。
- **I/R/E 估算**：除 Archi 原始三值外，其余债的 Impact/Risk/Effort 由主理人按严重度估算，仅供排序参考，精确值需人类负责人确认。
- **FAFU 归档未最终确认**：设计文档称 FAFU 移至 archive，实测未确认，建议人工核对。

---

## 📚 数据来源 & 成员产出索引

- **Cody（代码审查师）原始产出**：代码审查 16 项发现（安全/性能/正确性/可维护性）+ 代码债清单 + 依赖债清单。结论：分层与合规红线达标，4 处"能演示但生产不可信"硬伤。
- **Archi（架构师）原始产出**：架构债 D1–D10（含 I/R/E）+ Top 5 改进建议。结论：分层骨架清晰，循环依赖/死代码/全局状态为关键债。
- **Rex（SRE 工程师）原始产出**：可运维性风险评估 15 项 + Top 5 护航建议 + 7 条部署前检查验收口径。结论：合规与容错设计扎实，运行态/部署态三类风险。
- **Tessa（测试专家）原始产出**：测试健康度报告（实测 62% 覆盖 + 12 测试债 + Phase 0–2 计划 + 示例用例）。关键更正：P1 加固已落地，API/CI 部分覆盖，旧采集零测试 + 鉴权默认 OFF 为最高危债务。
- **Docu（技术文档师）原始产出**：文档债报告 19 项 + 部署补遗（#16–#19）+ 建议文档结构 + `.env.example`/`Dockerfile`/`runbook` 草案。核心：内联注释尚可，工程化文档体系缺失。
- **主理人（甄宇航）复核**：实测核实 `.github/workflows/ci.yml`、`scripts/guard_passive.py`、`config.json` 明文密钥、缺失 `.gitignore`/Dockerfile/`.env.example`；更正文档债冲突条目；统一去重合并 + 技术债优先级排序。

---

> 本报告由工程保障团队 AI 协作生成，关键决策请由人类工程负责人复核。
