# 中等重构实施：审批拦截出站 + 死代码清理

**日期**：2026-07-14
**关联**：全维度体检报告 `health-check-passive-agent-2026-07-13.md` 高优跟进项（原 🟠#6 审批未拦截出站、架构债 D1 死代码）
**执行**：工程保障团队主理人甄宇航（直接实施；体检报告成员产出为本次改动的依据，非代写）

---

## 📌 TL;DR（执行摘要）

- 落地 2 项中等重构：① 审批前置为出站硬依赖；② 清理被遮蔽的死代码文件。
- **审批流修复**：`proxy.submit()` 原本在 `approval.create()` **之前**执行且从不读审批状态 → 已改为「审批前置、出站受审批状态硬约束」。
- **死代码清理**：删除被同名包 `collector/adapters/` 遮蔽的顶层 `collector/adapters.py`（472 行）；其独有 4 个适配器（HackerTarget/OTX/URLScan/Hunter）全仓零引用。
- **验证**：`py_compile` 全过；项目 `.qa_venv` 完整导入冒烟通过（适配器包 8 类 + `loop.run_company` 均可导入）。

---

## ✅ 改动清单

| # | 文件 | 改动 | 验证 |
|---|------|------|------|
| A1 | `passive_agent/collector/adapters.py`（已删除） | 删除被 `collector/adapters/` 包目录遮蔽的死代码文件。Python 包目录优先于同名模块文件，该文件自项目存在起即不可达；其独有 4 个适配器全仓零引用 | py_compile + 包导入 OK |
| A2 | `passive_agent/orchestrator/loop.py` | 将 `approval.create()` 前置到 `proxy.submit()` 之前；出站受审批状态硬约束（仅 `APPROVED`/`REMINDING` 放行，`REVIEWING`/`REJECTED` 拦截并计入 `summary["approval_blocked"]`）；`summary` 增加 `approval_blocked` 计数 | py_compile + `loop` 导入 OK |

---

## 🔍 关键设计说明

- **闸门语义保 MID「提交+提醒」**：仅阻断 `REVIEWING`（HIGH 人工复核）与 `REJECTED`，不误伤 `REMINDING`（中危仍出站+提醒）。直接关闭原「HIGH 人工复核不阻断出站」的合规缺口。
- **激活 HIGH 拦截**：在 `config.py` 的 `HIGH_VALUE_KEYWORDS` 中填充高价值主体关键字，命中即由 `ApprovalService._elevate_risk` 升级为 `HIGH`→`REVIEWING`→出站被拦截，待人工 `decide(APPROVE)` 后放行。
- **死代码删除安全依据**：
  - Python 导入规则——同目录下包目录（`adapters/`）优先于同名模块文件（`adapters.py`），故该文件永远不可达。
  - `collector/scheduler.py:114` 与全部测试（`tests/conftest.py`、`test_collector.py` 等）的 `from passive_agent.collector.adapters import (...)` 均解析到**包目录**，`__init__.py` 已导出 8 个类。
  - 删前 `grep` 确认：`HackerTargetAdapter/OTXAdapter/URLScanAdapter/HunterAdapter` 仅在被删文件内定义，全仓无其他引用。

---

## ⚠️ 残留 / 已知局限

- **基线风险仍硬编码 `LOW`**：非 `HIGH_VALUE_KEYWORDS` 主体保持自动 `APPROVED`（保留演示行为），审批闸门对普通主体不拦截。若需「所有出站强制人工审批」，需新增配置开关（如 `OUTBOUND_REQUIRE_APPROVAL`）或调整基线风险——属产品决策，未在本轮改动。
- **手动 submit 端点未加审批校验**：`api/routes_gateway.py:31` 的 `_proxy.submit(req)` 属人工运营入口（已受 P0 鉴权保护），未接入审批状态校验；如需严格合规可后续补「提交前校验关联审批任务状态」。
- **真实密钥轮换仍为人工步骤**：见 `p0-remediation-passive-agent-2026-07-14.md`。

---

## 📚 验证记录

- `py_compile`：`loop.py` / `scheduler.py` / `adapters/__init__.py` / `adapter.py` → 全部 OK
- 导入冒烟（`.qa_venv`）：`from passive_agent.collector.adapters import CrtshAdapter, DnsAdapter, FofaAdapter, SubfinderAdapter, WechatAdapter, MiniappAdapter, EquityAdapter, MockAdapter` → OK；`from passive_agent.orchestrator.loop import run_company` → OK
- 裸运行时 `pydantic` 缺失属环境缺依赖，与本次改动无关。

---

> 本报告由工程保障团队 AI 协作生成，关键决策请由人类工程负责人复核。
