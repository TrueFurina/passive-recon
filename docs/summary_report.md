# 🕵️ Passive Recon 项目总结报告
## 大会总结与分享

---

## 一、项目定位

**Passive Recon** — 企业级纯被动 OSINT/EASM/CTEM 外部资产信息收集平台

核心理念：**零接触目标系统**，不发送任何探测流量，不产生目标日志，仅通过 15+ 公开数据源交叉验证完成资产发现与风险分析。

---

## 二、项目规模

| 指标 | 数值 |
|------|------|
| Python 代码文件 | 102 个 |
| 测试文件 | 28 个 |
| 总代码行数 | ~10,300 行 |
| 模块数 | 22 个 |
| Git 提交次数 | 15 次有效提交 |
| GitHub Stars | 1（持续增长中） |

---

## 三、数据源矩阵（15 个）

### 免费免密钥（8 个）

| 数据源 | 能力 |
|--------|------|
| **crt.sh** | 证书透明日志 → 子域名 |
| **HackerTarget** | DNS 查询、子域名、反向 DNS |
| **AlienVault OTX** | 被动 DNS / 威胁情报 |
| **URLScan.io** | 历史网页快照 → 子域名 |
| **Wayback Machine** | 历史存档 → 子域名 / URL |
| **DNSDumpster** | DNS 映射 / MX/NS 记录 |
| **CommonCrawl** | 海量历史网页数据 |
| **GitHub** | 代码泄露搜索 |

### 需 API Key（7 个）

| 数据源 | 能力 |
|--------|------|
| **Hunter（鹰图）** | 网络空间测绘，支持多 Key 自动轮询 |
| **FOFA** | 网络空间搜索引擎 |
| **SecurityTrails** | 子域名 / 被动 DNS |
| **Shodan** | 互联网设备搜索 |
| **VirusTotal** | 被动 DNS / 子域名 |
| **ZoomEye** | 网络空间测绘 |
| **Qichacha（企查查）** | 中国企业工商信息 |

---

## 四、核心能力

### 1. 采集 → 分析 → 报告 全链路

```
输入目标（任意名称）
    ↓
AI 域名推断（查表 + DeepSeek 回退）
    ↓
15 个数据源并行采集（ThreadPoolExecutor）
    ↓
去重 + DNS 补全 + 风险检测
    ↓
Markdown 报告 + 自动保存
    ↓
AI 风险评分（0-100） + AI 分析报告
```

### 2. 安全合规体系

| 安全层 | 机制 |
|--------|------|
| **R1 合规闸门** | 每次出站调用必经检查，fail-closed |
| **频控保护** | 滑动窗口 ≤95%，排队不丢任务 |
| **审批流** | 高危出站需人工审批 |
| **审计日志** | 全操作记录 |
| **静态闸门** | CI 自动扫描，禁止主动探测代码进入生产路径 |
| **密钥管理** | 环境变量注入，不落盘 |

### 3. CLI 命令矩阵（20 个命令）

| 分类 | 命令 | 说明 |
|------|------|------|
| **采集** | `collect` | 全能被动资产采集（自动推断域名 + 15 源） |
| | `batch` | 批量采集 |
| | `schedule` | 定时每日自动采集 |
| **分析** | `ask` | 🤖 AI 对话查询 |
| | `diff` | 资产变化追踪 |
| | `domain-info` | 域推断查询 |
| **导出** | `export` | JSON/CSV/Markdown 导出 |
| | `inventory-export` | 台账导出 |
| **面板** | `serve` | 一键启动 Web 面板 |
| **数据源** | `list-sources` | 列出可用数据源及状态 |
| **企查查** | `qichacha-detail/verify2/verify3` | 企业工商信息查询与核验 |
| **合规** | `audit-queue` / `compliance-status` / `submit-status` | 合规审计与状态 |
| **其他** | `icp` / `enumerate` / `import-path` / `resume` | ICP 备案、枚举、导入、断点续跑 |

---

## 五、AI 能力（DeepSeek 驱动）

| AI 功能 | 说明 | 触发方式 |
|---------|------|---------|
| **AI 域名推断** | 对任意目标推断域名，不限知识库 | `collect` 自动 |
| **AI 风险评分** | 0-100 分，可视化进度条，含修复建议 | `collect` 自动 |
| **AI 分析报告** | 采集后自动生成自然语言分析 | `collect` 自动 |
| **AI 对话查询** | 用自然语言查询资产数据库 | `ask` 命令 |
| **跳过 AI** | `--no-ai` 参数可跳过 | 手动指定 |

---

## 六、架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     CLI (cli.py)                         │
│  20 commands · argparse · 统一入口                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ collector │  │    ai    │  │ gateway  │  │ audit   │ │
│  │ 15 数据源  │  │ DeepSeek │  │ 频控/代理 │  │ 审计日志 │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ compliance│  │ approval │  │ scheduler│  │ storage │ │
│  │ 合规闸门   │  │ 审批流   │  │ 定时调度 │  │ SQLite  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ verifier │  │ inventory│  │   api    │              │
│  │ DNS 验证  │  │ 资产台账  │  │ REST API │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                   FastAPI Web 面板                        │
│  python cli.py serve → http://127.0.0.1:8000            │
└─────────────────────────────────────────────────────────┘
```

---

## 七、国际化与推广

| 事项 | 状态 |
|------|------|
| 英文 README | ✅ 已上线 |
| 中文 README | ✅ 已保留（README.zh-CN.md） |
| CLI 英文帮助 | ✅ 全部翻译 |
| GitHub Pages 主页 | ✅ https://truefurina.github.io/passive-recon |
| GitHub Topics | ✅ 15 个标签（osint, easm, ctem, security...） |
| Discussions | ✅ 已开启 |
| awesome-osint PR | ✅ 已提交（PR #1052） |
| 推广帖草稿 | ✅ 已保存（Reddit/HN/Twitter） |

---

## 八、环境变量清单

| 变量 | 用途 | 状态 |
|------|------|------|
| `PASSIVE_API_KEYS` | 数据源 API 密钥（Hunter/Qichacha） | ✅ 已设置 |
| `GITHUB_TOKEN` | GitHub 认证 | ✅ 已设置 |
| `DEEPSEEK_API_KEY` | DeepSeek AI API | ✅ 已设置 |
| `XF_API_KEY` | 讯飞星火 API | ✅ 已设置 |
| `XF_API_SECRET` | 讯飞星火密钥 | ✅ 已设置 |
| `XF_APPID` | 讯飞星火 APPID | ✅ 已设置 |

---

## 九、Git 提交历史（15 次有效提交）

```
3e89e11  feat: AI 集成到 CLI
035ca80  feat: AI 模块（域名推断 + 风险评分 + 对话查询）
1656cb5  feat: DeepSeek AI 报告生成
c8301c1  feat: export 命令
e3bc73b  docs: GitHub Pages 主页 + 推广帖草稿
f1bd08a  i18n: 英文 README + CLI
7d53a6a  docs: 15 个数据源清单
d08bc8a  feat: 集成 7 个新数据源（8→15）
8d31051  feat: 输出优化 + serve + 调度器
428ff68  chore: CI 升级到 Python 3.13
9094708  fix: 移除 FAFU 无效链接
4400723  chore: 完善文档与环境变量配置
c88762f  chore: 完善文档与环境变量配置
a5766fa  Initial commit
1931796  baseline-empty
```

---

## 十、后续规划

### 短期（1-2 周）
- 完善 Web 面板（资产搜索/筛选/可视化）
- 集成更多被动数据源（如有价值的）
- 完善测试覆盖

### 中期（1 个月）
- 定时任务自动报告推送
- 资产变化告警通知
- PDF 报告导出

### 长期（3 个月+）
- 千星目标 → 走向 GitHub Trending
- 完善社区贡献流程
- 企业级部署方案

---

## 十一、一句话总结

> **一个 10,000 行 Python 代码、15 个被动数据源、4 个 AI 功能、20 个 CLI 命令的企业级 OSINT 平台，从零到一，已上线 GitHub。**
>
> https://github.com/TrueFurina/passive-recon