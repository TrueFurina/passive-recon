# 🕵️ 企业被动信息搜集 Agent

> **DBAPPSecurity Ltd — 被动信息收集 Agent for enterprises**
>
> 纯被动（零接触目标系统）OSINT/EASM/CTEM 企业级资产信息收集平台

---

## 项目定位

本 Agent 采用**纯被动方式**（不向目标系统发送任何探测流量，不产生日志），通过对 15+ 公开数据源（证书透明日志、DNS 记录、搜索引擎、空间测绘、GitHub、Whois、Wayback Machine 等）的交叉验证，完成企业外部资产信息收集与风险发现。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API Key（鹰图 Hunter、企查查）
cp config.example.json config.json
# 编辑 config.json 填入你的 Key

# 一通百通：任意目标 → 自动推断域名 → 全源采集
python cli.py collect 北京大学
python cli.py collect --domain example.com 某企业
```

## 目录结构

```
├── cli.py                          ← 命令行入口（一通百通）
├── config.example.json             ← 配置文件模板
├── requirements.txt                ← Python 依赖
│
├── passive_agent/                  ← 🎯 核心源码
│   ├── main.py                     ← FastAPI 入口 + 面板 API
│   ├── config.py                   ← 配置加载（env > config.json）
│   ├── api/                        ← REST API 路由
│   ├── collector/                  ← 被动数据源采集器
│   ├── enumerator/                 ← 主体枚举引擎
│   ├── verifier/                   ← 验证管线（DNS-only）
│   ├── compliance/                 ← 合规护栏（R1 红线）
│   ├── gateway/                    ← 代理网关 + 频控（R6）
│   ├── orchestrator/               ← 编排调度（R4）
│   ├── approval/                   ← 审批流（R4）
│   ├── audit/                      ← 审计日志（R5）
│   ├── inventory/                  ← 资产台账（R5）
│   ├── graph/                      ← 知识图谱（规划）
│   ├── metrics/                    ← 指标采集（规划）
│   ├── scheduler/                  ← 定时任务（规划）
│   ├── storage/                    ← 持久化（SQLite + JSON）
│   ├── common/                     ← 公共组件（安全、合规客户端、枚举）
│   └── static/                     ← 面板前端
│
├── deliverables/                   ← 交付物与报告
│   ├── FAFU/                       ← 🏆 福建农林大学比赛成果
│   │   ├── competition-raw/        ← 比赛原始材料（12 篇分析文档、脚本、数据）
│   │   └── osint-report/           ← 正式交付报告（HTML/PPT/XLSX）
│   ├── architecture/               ← 架构设计文档
│   ├── product-strategy/           ← 产品 PRD 与策略
│   ├── engineering-assurance/      ← 工程保障与质量门禁
│   ├── gstack/                     ← 全栈安全审查
│   ├── sql-analysis/               ← 数据库探查报告
│   ├── 软著材料/                   ← 软件著作权申报材料
│   └── ...                          ← 各类报告与方案
│
├── tests/                          ← 测试套件
│   ├── api/                        ← API 鉴权与端点测试
│   ├── gateway/                    ← 网关与频控测试
│   └── test_*.py                   ← 单元/集成/压力/红线测试
│
├── scripts/
│   └── guard_passive.py            ← 纯被动静态闸门（CI 扫描）
│
├── docs/                           ← 系统设计文档
│   ├── system_design.md
│   ├── class-diagram.mermaid
│   └── sequence-diagram.mermaid
│
├── data/                           ← 运行期数据（已 gitignore）
│   ├── agent.db                    ← 控制/元数据平面（SQLite）
│   └── _recon_demo.db              ← 演示数据库
│
└── .github/workflows/              ← CI 流水线
```

## 核心能力

| 能力 | 说明 |
|------|------|
| **被动资产采集** | 15+ 数据源交叉验证，自动推断目标域名 |
| **主体枚举** | 子域名、IP、端口、邮箱、公众号、小程序、APP |
| **DNS 验证** | 仅 DNS-only 验证，不触碰目标系统 |
| **合规护栏** | 出站必经 R1 合规检查，fail-closed |
| **频控保护** | 按源 IP 限流 ≤95%，排队不丢任务 |
| **审批流** | 高危操作需审批 |
| **审计追踪** | 全操作审计日志 |
| **资产台账** | 结构化资产导出 |
| **静态闸门** | CI 自动扫描，禁止主动探测代码进入生产路径 |

## 红线原则

1. **纯被动** — 禁止向目标系统发送任何探测流量
2. **零日志** — 不触碰目标日志系统
3. **合规出站** — 所有出站调用必须经 `compliance_client.check()`

## 运行测试

```bash
# 全量测试
pytest

# 红线专项测试
pytest tests/test_passive_egress.py -v

# 静态闸门（检查生产路径是否混入主动探测代码）
python scripts/guard_passive.py
```

## 相关项目

- [🏆 FAFU 比赛全记录](./deliverables/FAFU/competition-raw/README.md) — 福建农林大学被动信息收集比赛（🥇 第一名）
- [📊 FAFU 正式报告](./deliverables/FAFU/osint-report/) — 整理后的交付报告（HTML/PPT/XLSX）

---

*DBAPPSecurity Ltd — Passive Information Collection Agent for Enterprises*