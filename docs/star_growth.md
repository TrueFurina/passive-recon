# ⭐ Passive Recon Star 增长策略

> 目标：千星（1000+ Star）
> 仓库：https://github.com/TrueFurina/passive-recon

---

## 一、当前状态（2026-08-14）

| 指标 | 现状 |
|------|------|
| GitHub Stars | ~1（持续增长中） |
| awesome-osint PR | #1052（已提交，当前无开放 PR——可能已合并或关闭，需确认） |
| 个人主页 | 已含被动侦察推荐 + 千星目标 |
| GitHub Pages | ✅ 已恢复（truefurina.github.io/passive-recon） |

---

## 二、落地动作（已完成）

### 2.1 本地可落地的增长基础设施

- ✅ 英文 README（全球开发者可读）
- ✅ GitHub Pages 项目主页
- ✅ 15+ Topics 标签
- ✅ 个人主页 🔥 Featured Open Source 板块 + 千星目标
- ✅ 公告 Issue #1（2026-07-17 创建）

### 2.2 专利技术交底书

- ✅ docs/patent_disclosure.md —— 多 Key 轮询与限频协同方法

---

## 三、需要手动操作（GitHub 认证步骤）

> ⚠️ 以下步骤需要你在浏览器/GitHub 网页端手动完成（AI 无法代持你的 Token 调用 API）

### 3.1 置顶 passive-recon 仓库

1. 打开 https://github.com/TrueFurina
2. 点击顶部 **"Customize your pins"**
3. 勾选 `passive-recon`
4. 保存

### 3.2 发布 GitHub Discussions 公告

1. 打开 https://github.com/TrueFurina/passive-recon/discussions
2. 点击 **"New discussion"**
3. 分类选择 **Announcements**
4. 标题：`🎉 Passive Recon is live — 20 passive data sources, zero-touch asset discovery`
5. 正文（可直接复制）：

```markdown
## 🕵️ What is Passive Recon?

Purely passive OSINT/EASM/CTEM platform — **20 data sources**, one command,
zero probes sent to targets.

## ✨ Features

- **20 data sources**: crt.sh, HackerTarget, OTX, URLScan, Wayback, DNSDumpster,
  CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan,
  VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge
- **Zero-touch**: Never sends a single packet to the target
- **🤖 AI**: domain inference, risk scoring, asset classification, chat query
- **Multi-key rotation**: auto-failover when rate-limited
- **Health monitoring**: auto-degrade unhealthy sources
- **Query cache**: 24h TTL, reduced API cost
- **Web dashboard**: `python cli.py serve`

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
```

👉 https://github.com/TrueFurina/passive-recon
```

### 3.3 确认 awesome-osint PR 状态

- 打开 https://github.com/jivoi/awesome-osint/pulls
- 搜索 #1052 或 "Passive Recon"
- 若被合并：✅ 在 README「相关项目」中引用列表链接
- 若被关闭：重新提交（附上新增的 20 源能力说明）

---

## 四、推广渠道计划

| 渠道 | 内容 | 时机 |
|------|------|------|
| Reddit r/netsec | 技术分享帖（docs/promotion_drafts.md 已有草稿） | PR 合并后 |
| Hacker News | Show HN | Star 破 10 后 |
| Twitter/X | 简短推文 + 采集截图 | 每周 |
| 知乎/掘金 | 中文技术帖（可选，你之前排除） | 可选 |

---

## 五、里程碑

```
⭐ 1 → 10  发布 Discussions 公告 + 置顶仓库
⭐ 10 → 50 Reddit/HN 发帖
⭐ 50 → 200 awesome-osint 列表曝光 + 社区 PR
⭐ 200 → 1000 持续迭代 + 企业版特性 + Docker 化
```

---

*Passive Recon — 从工具到平台，从 1 星到千星*
