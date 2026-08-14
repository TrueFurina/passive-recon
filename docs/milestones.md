# 🎯 GitHub Milestones 里程碑规划

> 仓库：https://github.com/TrueFurina/passive-recon
> 规划日期：2026-08-14

---

## 一、里程碑总览

| 里程碑 | 时间 | 目标 | 状态 |
|--------|------|------|------|
| **M1: 核心可用** | 已完成 | 20 数据源 + CLI + AI + Web 面板 | ✅ 已达成 |
| **M2: 企业级加固** | 2026-08 | RBAC + 合规报表 + Docker + PDF | ✅ 已达成（本次推送） |
| **M3: 社区增长** | 2026-09 | 100 Star + awesome-osint 收录 + 首批贡献者 | 🎯 进行中 |
| **M4: 千星目标** | 2026-12 | 1000 Star + 企业版部署方案 | 📅 规划中 |

---

## 二、M3：社区增长（2026-09）

### 目标
- 100+ GitHub Stars
- awesome-osint 列表收录（PR #1052 确认）
- 3+ 外部贡献者

### 任务清单（创建 Issue 并关联本里程碑）

| # | Issue 标题 | 类型 | 预计 |
|---|-----------|------|------|
| 1 | 发布 v0.1.0 Release（CHANGELOG + 归档） | 发布 | 1 天 |
| 2 | Reddit r/netsec 技术分享 | 推广 | 1 天 |
| 3 | Hacker News Show HN 发帖 | 推广 | 1 天 |
| 4 | awesome-osint PR 状态确认与跟进 | 社区 | 2 小时 |
| 5 | 新增 2 个免费数据源（无 Key） | 功能 | 2 天 |
| 6 | Web 面板暗色主题完善 | UI | 1 天 |
| 7 | 首个外部 PR 合并（打上 first-timers-only 标签） | 社区 | — |

### 验收标准
- [ ] Stars ≥ 100
- [ ] awesome-osint 收录
- [ ] 至少 1 个外部贡献者 PR 合并

---

## 三、M4：千星目标（2026-12）

### 目标
- 1000+ GitHub Stars
- 企业版部署方案（Docker Compose + 文档）
- 3 个核心模块达到专利/论文水平

### 任务清单

| # | 标题 | 类型 | 预计 |
|---|------|------|------|
| 1 | 企业版特性：多租户隔离 | 功能 | 1 周 |
| 2 | 合规报表导出完善（PDF 版） | 功能 | 2 天 |
| 3 | 定时任务 Webhook 告警完善 | 功能 | 1 天 |
| 4 | Docker 部署文档 + 演示视频 | 发布 | 2 天 |
| 5 | 专利技术交底书提交（多 Key 轮询） | 专利 | — |
| 6 | 英文技术博客（Medium/Dev.to） | 推广 | 1 周 |
| 7 | 知识图谱可视化（Mermaid → 交互图） | 功能 | 1 周 |

### 验收标准
- [ ] Stars ≥ 1000
- [ ] 2 篇技术博客发布
- [ ] 企业版部署文档可复制可用

---

## 四、创建 Milestones（需要你在 GitHub 手动操作）

> ⚠️ 以下操作需在你的浏览器完成（AI 无法代持 Token 调用 GitHub API）

### 方式一：网页操作

1. 打开 https://github.com/TrueFurina/passive-recon/milestones
2. 依次创建：

```
标题: M3 社区增长
描述: 100 Star + awesome-osint 收录 + 首批贡献者
截止日期: 2026-09-30
```

```
标题: M4 千星目标
描述: 1000 Star + 企业版部署方案 + 专利提交
截止日期: 2026-12-31
```

3. 创建 Issue 时在右侧勾选对应 Milestone

### 方式二：GitHub CLI（你本机终端）

```powershell
# 需要先安装 gh CLI 并登录（gh auth login）
gh api repos/TrueFurina/passive-recon/milestones -f title="M3 社区增长" -f description="100 Star + awesome-osint 收录" -f due_on="2026-09-30T00:00:00Z"
gh api repos/TrueFurina/passive-recon/milestones -f title="M4 千星目标" -f description="1000 Star + 企业版" -f due_on="2026-12-31T00:00:00Z"
```

---

## 五、发布节奏建议

```
2026-08: M2 完成（本次）→ 发 v0.1.0 Release
2026-09: M3 社区增长 → Reddit/HN/awesome-osint 三线推进
2026-10: 中期复盘 → 数据源 25 个、Star 300+
2026-11: 企业版特性冲刺 → Docker + 多租户
2026-12: M4 千星 → 发布总结 + 技术博客
```

---

*Passive Recon — 从工具到平台，从 1 星到千星*
