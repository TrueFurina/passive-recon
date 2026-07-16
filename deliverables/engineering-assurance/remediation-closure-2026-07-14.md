# 收尾闭环报告 · Passive Agent（出站立项 + 密钥轮换体系）

**日期**：2026-07-14
**工作流**：部署前检查 / 技术债收尾（P0 之后续收口）
**参与成员**：Rex（SRE，密钥/CI 体系）、Cody（代码审查，手动提交闸门）、Archi（架构，开关设计）— 主理人甄宇航汇编

---

## 📌 TL;DR（执行摘要）

- **本轮收口两项**：① 出站强制审批总开关 `OUTBOUND_REQUIRE_APPROVAL`；② 手动 `/gateway/submit` 端点接入审批闸门（与自动流同口径）。
- **B 路径落地**：密钥轮换工具链 + CI gitleaks 门禁——`.gitleaks.toml` + `scripts/rotate_secrets.py` + `scripts/SECRET_ROTATION.md` + `.github/workflows/ci.yml` 增 gitleaks 步骤 + `config.example.json` 清空密钥占位。
- **唯一仍须人工的动作**：在 Hunter / 企查查 平台**真正轮换并作废旧密钥**、把 `config.json` 历史从 git 清除（破坏性，需团队协同）。代码与文档已就绪。
- 全部改动通过 `py_compile` 与 venv 导入冒烟（`routes_gateway` + `ApprovalService.get` 均 OK）。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🟢 代码层可修项全部清零；密钥轮换待人工执行 |
| 本次收口项 | 4 处代码改动 + 4 个新增/修订交付物 |
| 关键行动项 | 1 条人工（密钥轮换）+ 历史清除 |
| 建议下一步 | 执行 `SECRET_ROTATION.md` 六步，跑通 CI（pytest + gitleaks + guard_passive） |

---

## ✅ 一、两项出站立项（收尾）

### 1.1 出站强制审批总开关 `OUTBOUND_REQUIRE_APPROVAL`
**文件**：`passive_agent/config.py` + `passive_agent/orchestrator/loop.py:244`

- `config.py` 新增 `OUTBOUND_REQUIRE_APPROVAL: bool = False`。
- `loop.py` 创建审批任务时：`risk_level = HIGH if settings.OUTBOUND_REQUIRE_APPROVAL else LOW`。
- 效果：置 `True` 时**全部出站**进入 `REVIEWING`（HIGH 人工复核），未经人工 `decide(APPROVE)` 严禁出站；默认 `False` 保留演示态（仅命中 `HIGH_VALUE_KEYWORDS` 才强制人工）。
- 与既有 `HIGH_VALUE_KEYWORDS` 提升逻辑（`approval.service._elevate_risk`）叠加，不冲突。

### 1.2 手动 `/gateway/submit` 接入审批闸门
**文件**：`passive_agent/api/routes_gateway.py` + `passive_agent/approval/service.py` + `passive_agent/common/result.py`

- `approval/service.py` 新增 `get(task_id)` 查询方法（不存在返回 `None`）。
- `routes_gateway.submit`：由 `biz_req_no`（`{result_id}-{idx}`）反推 `result_id`，查关联审批任务 `AP-{result_id}`；若其状态为 `REVIEWING`/`REJECTED` → 返回错误码 `020002`（新增于 `result.ERROR_CODES`）拦截出站。
- 效果：手动运营入口与自动流**同一套合规闸门**，杜绝「自动流被拦、手动端点绕过」的缺口。
- `APPROVED`/`REMINDING` 放行；无关联审批任务时不拦截（兼容历史/其他业务类型手动提交）。

---

## ✅ 二、B 路径：密钥轮换 + 防回写体系

| 交付物 | 作用 |
|--------|------|
| `.gitleaks.toml` | 密钥扫描规则（Hunter / 企查查 + 默认规则），排除 `config.example.json`/`docs` 等 |
| `scripts/rotate_secrets.py` | 轮换辅助：dry-run 报告 → `--apply` 备份并清空 `config.json` 明文、生成 `.env` 模板 |
| `scripts/SECRET_ROTATION.md` | 六步可执行清单（外部轮换 → 本地清出 → 填 `.env` → 校验 → 清 git 历史 → 验证） |
| `.github/workflows/ci.yml` | 新增 `Gitleaks 密钥扫描` 步骤（fail-closed，密钥回写即红） |
| `config.example.json` | 密钥占位清空（空数组/空串），真实密钥走 `PASSIVE_API_KEYS` 环境变量 |

> ⚠️ **CI 预期**：新增 gitleaks 步骤会在 `config.json` 仍含明文密钥时**让 CI 变红**——这是预期 fail-closed 态。执行 `SECRET_ROTATION.md` 清出明文后转绿。

---

## ✅ 行动清单（按优先级）

| # | 行动 | 负责角色 | 紧急度 | 预期完成 |
|---|------|---------|--------|---------|
| 1 | Hunter / 企查查 平台轮换并作废旧密钥 | 你（人工） | P0 | 立即 |
| 2 | `python scripts/rotate_secrets.py --apply` 清出本地明文 + 生成 `.env` | 你（照脚本） | P0 | 步骤 1 后 |
| 3 | `.env` 填 `PASSIVE_API_KEYS`（新密钥 JSON） | 你（人工） | P0 | 步骤 2 后 |
| 4 | `git filter-repo` / BFG 清除 `config.json` 历史 + 强制推送 | 你（协同团队） | P1 | 步骤 2 后 |
| 5 | 本地 `gitleaks detect` + 跑 CI 验证三绿 | 你 / CI | P1 | 步骤 4 后 |
| 6 | 如需「全部出站强制人工」，置 `OUTBOUND_REQUIRE_APPROVAL=true` | 你（配置） | P2 | 按需 |

---

## ⚠️ 待完善 / 已知局限

- **真实密钥轮换未代执行**：外部平台作废 + 历史清除属人工/破坏性操作，脚本仅辅助本地清出与注入改造。
- **gitleaks 默认扫描整体仓库**（非 git 历史）：历史提交中的旧密钥需步骤 4 单独清除；CI 步骤只挡「新提交回写」。
- **手动 submit 无关联任务时不拦**：保留此行为以兼容非采集类手动提交；若要求绝对严格，可改为「无任务即 403」，属产品决策未硬改。
- **`OUTBOUND_REQUIRE_APPROVAL` 默认 False**：演示态下仍只有高价值关键词强制人工；生产全量强制需显式开启（见行动 #6）。

---

## 📚 数据来源 & 成员产出索引

- 原体检报告：`health-check-passive-agent-2026-07-13.md`（Cody/Archi/Rex/Tessa/Docu）
- P0 七项止血：`p0-remediation-passive-agent-2026-07-14.md`
- 中等重构 A（审批前置 + 死代码清理）：`remediation-approval-gate-deadcode-2026-07-14.md`
- 本轮代码改动：config.py / loop.py / approval/service.py / api/routes_gateway.py / common/result.py
- 本轮交付物：.gitleaks.toml / scripts/rotate_secrets.py / scripts/SECRET_ROTATION.md / ci.yml（增步）/ config.example.json

---

> 本报告由工程保障团队 AI 协作生成，关键决策（尤其密钥轮换与历史清除）请由人类工程负责人复核后执行。
