# 最终交付确认：被动信息收集 Agent · 打包交出手检

**日期**：2026-07-15
**场景**：上线前检查收尾 + 交付就绪（handoff-readiness）
**评估方式**：主理人直接核查（团队调度工具 TeamCreate / gstack 子 Agent 当前报错不可用，按降级策略由主理人代行，结论透明、不冒充成员）

---

## 📌 TL;DR（执行摘要）

- **安全维度：🟢 已达标**——昨天两个 P0 阻塞（全 API 无鉴权、FAFU 主动扫描+关闭 TLS）均已修复。
- **打包交出手检：🔴 还不能直接交**——版本库与文件夹里混入了"编译字节码 + 真实数据库（PII） + 调试垃圾"，不清理就发，要么泄露数据、要么带一堆废文件。
- **测试维度：🟡 需修 hermetic**——单文件/小组合全绿，但全量 51 跑会崩（已知非 hermetic：全局 DB 单例 + WAL 锁争用），需隔离后才能稳定复跑。
- 下一步：按下方「清理清单」执行 4 步 git 清理 + zip 排除项，即可安全交付。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 安全 P0（鉴权） | 🟢 已修：`require_auth` 真校验，Bearer + 豁免白名单 + F-10 反代加固 |
| 安全 P0（FAFU） | 🟢 已修：`FAFU/` 目录已从项目移除 |
| 版本库卫生 | 🔴 污染：`data/agent.db`（PII）与 49 个 `.pyc` 被 git 跟踪 |
| 文件夹卫生 | 🔴 污染：根目录 ~30 个调试垃圾（diag*/bothrun*/qa_*/meas.db 等）未跟踪但会进 zip |
| 密钥安全 | 🟢 `config.json` 未被 git 跟踪（gitignore 生效）；但磁盘上存在，手动 zip 会带上 |
| 测试可靠性 | 🟡 全量崩、子集绿（非 hermetic，已知问题） |
| 依赖锁定 | 🟡 `requirements.txt` 用 `>=` 未锁版本，建议出 lock |
| 可否打包交付 | 🔴 否（先清理）；清理后 🟢 可交付 |

---

## 1. 已确认修复项（相对 7/13 报告）

1. **P0-1 全 API 无鉴权 → 已修**。`passive_agent/main.py` 所有 `/api/v1` router 均挂 `dependencies=[Depends(require_auth)]`，并新增 `AuthError`→401 处理器。`passive_agent/api/deps.py` 实现：Bearer 校验 + 豁免路径白名单 + loopback 豁免带 F-10 生产加固（生产默认 `TRUST_LOCALHOST=False`，存在 `X-Forwarded-For`/`X-Real-IP` 时拒绝 loopback 豁免）。**注意**：有总开关 `settings.API_AUTH_ENABLED`，测试会话默认关（保测试绿）——交付的生产配置必须显式设 `True`。
2. **P0-2 FAFU 主动扫描 + `verify=False` → 已修**。`FAFU/` 目录已删除，不在工作区也不在版本库（`grep FAFU/` 报无此目录；`git ls-files | grep FAFU` 无结果）。

---

## 2. 交付前必须清理的问题（按严重度）

| # | 严重度 | 位置 | 问题描述 | 建议 |
|---|--------|------|---------|------|
| 1 | 🔴 | `data/agent.db`（git 跟踪） | 真实采集库（含 PII）被 `git add` 进了版本库（`git ls-files` 含 `data/agent.db`），`git archive` 会把它发出去 | `git rm --cached data/agent.db`；确认 `.gitignore` 的 `data/` 生效；交付前清空或脱敏 |
| 2 | 🔴 | 根目录 ~30 个调试垃圾（未跟踪） | `diag*.py`×5、`*.log`（bothrun*/qa_*/comp.log/inv.log/iso_bg.log/newrun.log/runv.log/cov_run.log/diag*.log 等）、`meas.db`、`batch_test.txt`、`report_test.xlsx`、`overview.md`、`cov_summary.py` 均为 `??` 未跟踪；手动 `zip` 整文件夹会全卷进去 | 交付用 `git archive`（自动排除未跟踪项）；若手动 zip 须显式排除（见下方排除清单） |
| 3 | 🟠 | 49 个 `.pyc`（git 跟踪） | `__pycache__/*.pyc` 被 `git add` 进了版本库，`.gitignore` 未拦住（可能先 add 后加 ignore） | `git rm --cached -r --quiet $(git ls-files '*.pyc')`；确保 `.gitignore` 的 `__pycache__/`、`*.py[cod]` 生效 |
| 4 | 🟠 | `config.json`（磁盘存在，git 未跟踪） | 含密钥/API key，gitignore 已保护；但手动 zip 整文件夹会带上 | 只交付 `config.example.json`；zip 排除 `config.json`；或在交付前临时移走 |
| 5 | 🟡 | `requirements.txt`（用 `>=`） | 未锁版本/无哈希，对方环境可能装到不同版本导致行为漂移 | 生成 lock（`uv pip compile` 或 `pip-tools`），随包附 `requirements.lock` |
| 6 | 🟡 | 测试非 hermetic（全量崩） | 全局 DB 单例 + WAL 锁争用，全量 51 跑累积崩溃（单文件/小组合全绿，如 approval+compliance=12 passed） | conftest 改用每测试 `tmp_path` 隔离单例；或文档注明"按文件运行 pytest" |

---

## ✅ 清理 / 交付清单（照做即可安全交）

### A. 版本库清理（让 `git archive` 干净）
```bash
# 1. 移除被误跟踪的编译字节码与真实库
git rm --cached -r --quiet $(git ls-files '*.pyc')
git rm --cached data/agent.db
# 2. 确认 .gitignore 已含（当前已有）：__pycache__/  *.py[cod]  data/  config.json  .env
# 3. 交付前把本地真实库清空/脱敏（避免有人 --force 加回）
# 4. 重新提交清理后的索引
git add -A && git commit -m "chore: 移除误跟踪的 .pyc 与 data/agent.db，交付前清理"
```

### B. 推荐分发方式（二选一）
- **方式一（推荐）：`git archive` 导出**
  ```bash
  git archive --format=zip --prefix=passive-agent/ -o passive-agent-handoff.zip HEAD
  ```
  自动排除未跟踪垃圾（`diag*`/`*.log`/`meas.db` 等）与 `.gitignore` 项。
- **方式二：手动 zip，显式排除**
  ```
  排除：__pycache__/ *.pyc *.log data/ config.json meas.db diag* bothrun* batch_test.txt qa_* report_test.xlsx overview.md cov_* .pytest_cache/ .coverage .venv/ .qa_venv/
  ```
  只保留：`passive_agent/`、`cli.py`、`tests/`、`requirements.txt`、`config.example.json`、`README.md`、`docs/`、`deliverables/`（按需）。

### C. 交付物附带说明（README 或随包 notes）
- 运行：`pip install -r requirements.txt`（或 lock）→ 复制 `config.example.json` 为 `config.json` 并填密钥 → `python cli.py --help`。
- 生产必须：`config.json` 中 `API_AUTH_ENABLED=True`。
- 测试：`pytest tests/<单文件>`（全量套件需先修复 hermetic，见问题 #6）。

---

## ⚠️ 待完善 / 已知局限

- **成员工具不可用**：本评估由主理人直接完成；gstack 子 Agent（含质量门神）因 `Tool TaskStop not found` 报错无法派发，QA 维度的独立复核暂缺，建议工具恢复后由质量门神补一次。
- **测试全量崩溃未根因定位**：本次确认"单文件绿、全量崩"且为已知非 hermetic 现象，未深入修隔离——属测试质量债，不阻塞产品功能，但阻塞"声明测试全绿"。
- **依赖未锁版本**：对方 `pip install` 可能装到不同小版本。
- **`data/agent.db` 是否在他人机器重建**：交付应清空/脱敏该库，首次运行由 `db.ensure_init()` 自建空库。

---

> 本报告由软件工坊主理人直接核查生成（团队调度工具暂不可用，降级执行）。关键决策请由工程负责人复核。
