# GitHub 推送前核查清单：被动信息收集 Agent

**日期**：2026-07-16
**场景**：推送 GitHub 前的仓库卫生 / 泄密核查
**评估方式**：主理人直接只读核查（gstack 子 Agent 派发仍报 `Tool TaskStop not found`，降级代行）

---

## 📌 TL;DR

- **密钥未泄历史**：`config.json` / `.env` / `data/agent.db` 在 `git log --all` 均无提交记录，`-S "API_KEY"` 扫描为空 → 只要本次索引清干净再提交，push 不会泄密。
- **但索引（即将提交）里有脏东西**：`data/agent.db`（PII）与 49 个 `.pyc` 已被 `git add` 进暂存区；`.gitignore` 没覆盖根目录调试垃圾与 `.workbuddy/` 内部目录。
- **当前只有 `baseline-empty` 一个空基线提交**，首次实质提交尚未完成 → 现在清理索引正当时。
- 还差：无 LICENSE、未建 remote / GitHub 仓库。

---

## 🔴 必须在 push 前解决

| # | 问题 | 证据 | 后果 |
|---|------|------|------|
| 1 | `data/agent.db` 在 git 索引中（已 stage 未提交） | `git ls-files` 含 `data/agent.db` | 含真实采集 PII，push 即公开 |
| 2 | 49 个 `.pyc` 在索引中 | `git ls-files '*.pyc'` = 49 | 字节码进仓库，膨胀且难看 |
| 3 | `.gitignore` 未覆盖根目录调试垃圾 | `diag*.py`/`*.log`/`meas.db`/`bothrun*` 等均为 `??` 未跟踪 | 一旦 `git add -A` 全卷进库（含本次生成的 `pytest_*.log`） |
| 4 | `.workbuddy/` 内部目录被 stage | `git status` 显示 `.workbuddy/memory/`、`raw/`、`output/` 均为 `A` | 助手内部上下文（项目笔记/原始研究）随 push 泄露 |

## 🟡 推送前准备

| # | 问题 | 说明 |
|---|------|------|
| 5 | 无 LICENSE | 公开仓库建议补（MIT / Apache-2.0 等） |
| 6 | 未配 remote、未建 GitHub 仓库 | 需先在 GitHub 建空仓库，再 `git remote add` |

---

## ✅ 预推送清理脚本（复制即跑；只动索引与 .gitignore，不删你的文件）

```bash
cd "E:/Program/DBAPPSecurity Ltd/Passive information collection Agent for enterprises"

# 0. 从索引移除 PII 库 / 字节码 / 助手内部目录（工作区文件保留）
git rm --cached -r --quiet $(git ls-files '*.pyc')
git rm --cached data/agent.db
git rm --cached -r --quiet .workbuddy

# 1. 补全 .gitignore（覆盖根目录垃圾 + 助手目录 + 锁文件产物）
cat >> .gitignore <<'EOF'

# ===== 助手内部目录（禁止入库）=====
.workbuddy/

# ===== 调试 / 工具生成物（禁止入库）=====
*.log
pytest*.log
*.db
meas.db
diag*
bothrun*
batch_test.txt
cov_*
qa_*
newrun.log
runv.log
inv.log
iso_bg.log
comp.log
overview.md
cov_summary.py
per/
EOF

# 2. 自行补一个 LICENSE 文件（如 MIT）

# 3. 干净暂存 + 复核
git add -A
git status        # 确认无 .pyc / .db / config.json / .workbuddy / 调试垃圾

# 4. 首次实质提交
git commit -m "initial: 被动信息收集 Agent 源码与文档"

# 5. 在 GitHub 建好空仓库后，再执行（需你的仓库地址）：
# git remote add origin https://github.com/<你>/<repo>.git
# git push -u origin master
```

---

## ⚠️ 验证要点（push 前最后一道）

- `git ls-files | grep -iE "\.pyc$|\.db$|config\.json$|\.workbuddy"` 应为空。
- `git log --all -- config.json data/agent.db` 始终为空（历史干净）。
- `git remote -v` 确认 origin 指向正确仓库（私有库优先，敏感项目勿公开）。
- 若仓库须公开：再次人工确认 `config.json`（含 Hunter×5 / 企查查 唯一不可变密钥）绝不在任何提交中。
