# 密钥轮换与防回写步骤清单（Passive Agent）

> 当前状态：`config.json` 仍含明文 Hunter / 企查查 密钥且已曾入版本库（风险 🔴）。
> 目标：密钥移出版本库、改由环境变量注入、CI 自动扫描、历史清除。

## 步骤（严格按顺序）

1. **外部平台轮换（必须最先做）**
   - Hunter：登录后台，逐个作废并重新生成 API Key（多 Key 轮换）。
   - 企查查：在开放平台重置 `app_key` / `secret_key`。
   - 旧密钥立即作废，确保即便历史泄漏也不可用。

2. **本地清出明文**
   ```bash
   python scripts/rotate_secrets.py --apply
   ```
   - 自动备份 `config.json` -> `config.json.bak.<时间戳>`
   - 改写 `config.json`：`API_KEYS` 置空
   - 生成 `.env` 模板（已存在则不覆盖）

3. **填充新密钥到 `.env`**
   编辑 `.env`，把 `PASSIVE_API_KEYS` 设为轮换后的 JSON：
   ```dotenv
   PASSIVE_API_KEYS={"hunter":["NEW_KEY_1"],"qichacha":{"app_key":"NEW","secret_key":"NEW"}}
   ```
   （pydantic-settings 会读 `PASSIVE_API_KEYS` 覆盖 config.json 的 `API_KEYS`）

4. **确认防护到位**
   - `.gitignore` 已含 `config.json` 与 `data/`（已落地）。
   - CI 已加 gitleaks 步骤（`.github/workflows/ci.yml` + `.gitleaks.toml`）。
   - 本地校验：`gitleaks detect --source . --config .gitleaks.toml` 应无命中
     （注意：在步骤 2 清出明文之前，此举会报 config.json 命中，属预期）。

5. **清除 git 历史中的旧密钥（破坏性，需团队协同）**
   ```bash
   # 方式 A：git-filter-repo（推荐）
   pip install git-filter-repo
   git filter-repo --path config.json --invert-paths
   # 方式 B：BFG
   java -jar bfg.jar --delete-files config.json
   git reflog expire --expire=now --all && git gc --prune=now
   git push --force --all
   ```
   ⚠️ 强制推送会改变所有人本地历史，务必提前通知协作者。

6. **轮换后验证**
   - 本地 `uvicorn passive_agent.main:app` 启动，确认数据源调用能正常鉴权（日志无 401）。
   - CI 跑通：pytest + gitleaks + guard_passive 全绿。

## 防回写纪律（长期）
- 严禁把真实密钥写回 `config.json`；`config.json` 仅放非敏感默认值。
- 新增密钥一律走 `PASSIVE_API_KEYS`（或密钥管理系统）。
- 每次 PR 由 CI gitleaks 兜底拦截。
