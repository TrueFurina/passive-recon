# 第 2 章 开源被动侦察工具链与情报 API 数据源生态

## 论点：以"零发包"为红线的分层被动侦察底座

企业被动信息搜集的核心约束，是在不向目标系统发送任何探测数据包（即"零发包"）的前提下尽可能完整地还原其外部攻击面。数据显示，主流被动子域枚举工具通过并发查询第三方情报源（VirusTotal、Censys、Shodan、证书透明度日志等）即可发现大量资产，且具备隐蔽、不可被目标感知的优势（[ProjectDiscovery, n.d.](https://github.com/projectdiscovery/subfinder)；[OWASP Amass, n.d.](https://owasp-amass.github.io/docs/)）。本章主张：由"开源被动工具链 + 多元情报 API 生态"构成的分层采集体系，是竞赛中兼顾覆盖率与合规性的侦察底座；其中 MassDNS 字典爆破、FOFA 主动探测等主动手段，应被严格排除在纯被动阶段之外。

## 论据一：被动子域/资产枚举工具链的能力与边界

**Subfinder** 定位为"快速的被动子域名枚举工具"，默认通过 30+ 个被动在线源（含 VirusTotal、Censys、Shodan、SecurityTrails、FOFA、ZoomEye、Hunter 等）并发聚合数据，"不会向目标发送单个 DNS 查询"（[ProjectDiscovery, n.d.](https://github.com/projectdiscovery/subfinder)；[PIStack, 2026](https://www.pistack.xyz/posts/2026-04-23-amass-vs-subfinder-vs-massdns-self-hosted-dns-reconnaissance-guide-2026)）。其速度优势来自轻量架构与精选被动源；多数源需配置 API Key（如 `provider-config.yaml`），否则对应源无返回。

**OWASP Amass** 同时支持被动与主动模式：`-passive` 标志关闭 DNS 解析及依赖特性，仅通过搜索引擎、CT 日志、40+ API 集成（Shodan、Censys、VirusTotal 等）做被动枚举；`-active`/`-brute` 则会向目标 DNS 发起查询与暴力枚举，属主动侦察（[OWASP Amass, n.d.](https://owasp-amass.github.io/docs/)；[0xffsec, n.d.](https://0xffsec.com/handbook/information-gathering/subdomain-enumeration/)）。Amass 还能以资产数据库长期追踪攻击面，适合深度测绘。

**OneForAll、Sublist3r、theHarvester、Assetfinder** 各具侧重：OneForAll 集成证书透明度、搜索引擎、DNS 数据集、威胁情报等模块，输出格式丰富但速度偏慢（[FreeBuf, n.d.](https://m.freebuf.com/articles/web/366925.html)）；Sublist3r 通过爬取 Google/Bing/Baidu/Netcraft/VirusTotal 等 HTML 页面提取子域、无专用 API、工具偏老旧，有观点认为其应被淘汰、仅作补充（[FreeBuf, 2024](https://www.freebuf.com/articles/web/479973.html)）；theHarvester 以 OSINT 方式收集邮箱、子域、虚拟主机与端口 Banner，但子域结果相对少（[Outpost24, n.d.](https://outpost24.com/blog/art-of-subdomain-enumeration)）；Assetfinder 以简洁著称，聚合多个被动 OSINT 源输出子域（[FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html)）。

**crt.sh 证书透明度** 是被动子域提取的核心枢纽：自 2018 年 Chrome 强制 CT 以来，所有受信任 CA 签发的证书必须记入公共 CT 日志（[crt.sh, n.d.](https://crt.sh/)）。crt.sh 聚合这些日志，通过 `%.example.com` 通配模式提取每张证书的 SAN（Subject Alternative Name）字段，从而被动还原历史子域——整个过程"无任何流量触及目标服务器"（[OSINTBench, n.d.](https://osintbench.com/tools/crt-sh-certificate-transparency-log-search/)）。

## 论据二：零发包历史快照与证书核心

**Wayback Machine CDX API** 是免费、无需密钥的互联网存档索引接口，覆盖自 1996 年以来的 8900 亿+ 网页快照（[ApifyForge, 2026](https://apifyforge.com/blog/wayback-machine-api-programmatic-search)）。其 `matchType`（exact/prefix/host/domain）、`collapse=digest`（去重仅保留内容变更快照）、`statusFilter`、`mimeFilter` 等参数，使研究者可回溯已删除页面、历史端点与 JS 文件中的敏感接口；因只查询存档库、不接触目标，本质为被动侦察。社区实践中建议以约 1 请求/秒的礼貌速率访问，单查询上限约 15 万条（[Scraperly, 2026](https://scraperly.com/scrape/wayback-api)）。

## 论据三：国内情报 API 数据源生态

网络空间测绘平台通过"查询已测绘数据"实现被动检索。数据显示，**FOFA**（华顺信安）已积累 40 亿+ 资产、35 万+ 指纹规则（[cnetsec, 2023](https://www.cnetsec.com/article/39908.html)）；其免费注册用户每月 300 次页面查询，**查询 API 接口与 1 请求/秒 并发需个人版及以上会员**（[FOFA, n.d.](https://fofa.info/vip)）。**Hunter（奇安信鹰图）** 因国资/央企品牌背书，在政企合规采购中过审难度低，且国内 IP 段覆盖更密、中文支持好（[chdh.me, 2026](https://chdh.me/tools/network/security/hunter-how)）；其 API 每日约 500 条积分（[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)）。**ZoomEye（知道创宇）** 以 Xmap+Wmap 双引擎覆盖设备与 Web 指纹，免费 API 每月 1 万条、最小请求单位 20 条、本地缓存 5 天（[knownsec, n.d.](https://github.com/knownsec/ZoomEye-python/blob/v2.0.4.4/docs/README_CN.md)；[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)）。**Censys** 具学术公益背景，免费层 API 每月约 250 条；**Shodan** 在 OT 设备与全球覆盖上占优。

面向国内目标的工商/备案采集，**ENScan_GO** 基于各大企业信息 API，一键收集控股公司 ICP 备案、APP、小程序、微信公众号等并支持 MCP 接入（[wgpsec, n.d.](https://github.com/wgpsec/ENScan_GO)）。业内观点普遍认为，中文情报生态（FOFA/Hunter/ZoomEye + ENScan_GO）对国企、国内目标的适配度显著高于纯英文工具链，因其覆盖 ICP 备案、工商关联、公众号/小程序等本土特有资产维度。

## 论据四：限流与风控（竞赛关键）

各平台均设查询配额与速率限制，竞赛中极易触发风控。事实数据显示：FOFA 免费 300 查询/月、API 1 请求/秒；Hunter 每日约 500 条；ZoomEye 每月约 1 万条（网页与 API 额度规则各异）；Censys 约 250/月；360 Quake 约 3000/月（[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)；[FOFA, n.d.](https://fofa.info/vip)）。有安全研究者指出，多账户注册刷额度会被各平台风控系统识别并可能导致封禁，故应通过合规策略在额度内提效（[CSDN, n.d.](https://wenku.csdn.net/answer/157x7pcvkz)）。据此，本章预埋第 5 章的合规采集策略：**API 代理层 + 多出口 IP 轮询 + 任务排队缓存**——以代理层统一封装各平台 SDK、以多出口 IP 分摊单 IP 限流、以任务队列与本地缓存复用历史结果，从而在额度内最大化采集效率。

## 论据五：被动/主动模式对比与选型矩阵

下表归纳主流工具的被动性、数据源、限流与是否向目标发包，明确纯被动红线：

| 工具 | 被动/主动模式开关 | 核心数据源 | 是否向目标发包 | 适用采集阶段 | 限流/备注 |
|------|------------------|-----------|---------------|-------------|-----------|
| Subfinder | 纯被动（默认） | 30+ 被动源（VT/Censys/Shodan/FOFA/ZoomEye/Hunter） | 否 | 快速被动基线 | 多源需 API Key |
| OWASP Amass | `-passive` / `-active` / `-brute` | CT 日志+40+ API+搜索引擎 | 被动模式否；`-active` 是 | 被动发现→深度测绘 | 免费可白嫖 20+ API |
| OneForAll | 被动为主（含 CT 模块） | CT/搜索引擎/DNS 数据集/威胁情报 | 否 | 全量被动收集 | 速度较慢 |
| Sublist3r | 被动为主（可 `-b` 爆破） | 搜索引擎/Netcraft/VT/SSL 证书 | 默认否；`-b` 是 | 补充枚举 | 工具偏老旧 |
| theHarvester | 被动 OSINT | 搜索引擎/PGP/Shodan | 否 | 邮箱+子域搜集 | 子域结果偏少 |
| Assetfinder | 纯被动 | 多被动 OSINT 源（crt.sh/VirusTotal 等） | 否 | 快速子域 | 输出简洁 |
| crt.sh | 纯被动（CT 查询） | 公共证书透明度日志 | 否 | 证书子域提取 | 仅含持证资产 |
| Wayback CDX | 纯被动（存档查询） | Internet Archive 快照 | 否 | 历史端点回溯 | ~1 req/s 礼貌 |
| MassDNS | 纯主动（暴力解析） | 字典+解析器 | **是** | 主动验证/爆破 | ⚠ 不在纯被动阶段 |
| FOFA/Hunter 主动探测 | 主动 | 自发包探测 | **是** | — | ⚠ 纯被动红线禁止 |

## 分析

上述工具与数据源可划分为三层：**被动发现层**（Subfinder/Amass -passive/crt.sh/Wayback）负责零发包广撒网；**国内情报层**（FOFA/Hunter/ZoomEye/ENScan_GO）补足本土资产维度；**主动验证层**（MassDNS/Amass -active/平台主动探测）仅用于授权范围内的二次确认。竞赛得分的关键，不在于主动发包的"狠"，而在于被动层的"全"与"巧"——在额度与合规约束下，通过多源聚合、历史快照与证书透明度，往往能触及主动扫描无法发现的遗忘资产（如已下线的测试环境、CI/CD 预览域名）。

## 小结

开源被动侦察工具链与情报 API 生态共同构成企业被动信息搜集的"零发包"底座。Subfinder、Amass（被动模式）、OneForAll、Sublist3r、theHarvester、Assetfinder 与 crt.sh、Wayback CDX 等工具，可在不触达目标的前提下完成子域与历史资产发现；FOFA、Hunter、ZoomEye、Censys、Shodan 与 ENScan_GO 等国内平台则提供适配本土目标的空间测绘与工商情报。在严格遵循"纯被动红线"（禁用 MassDNS 爆破与平台主动探测）并配合 API 代理层、多出口轮询与任务排队缓存的合规策略下，该体系可支撑竞赛中高效、可持续的资产采集。

---

## 本章新增来源清单
1. ApifyForge — Wayback Machine CDX API 指南 — https://apifyforge.com/blog/wayback-machine-api-programmatic-search
2. SubdomainsFinder — Best Subdomain Enumeration Tools 2026 — https://subdomainsfinder.com/best-subdomain-enumeration-tools
3. Outpost24 — The dangerous art of subdomain enumeration — https://outpost24.com/blog/art-of-subdomain-enumeration
4. NoMoney (GitHub) — 信息收集多平台限流对比 — https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney
5. knownsec ZoomEye-python README_CN — https://github.com/knownsec/ZoomEye-python/blob/v2.0.4.4/docs/README_CN.md
6. chdh.me — Hunter (hunter.how) 评测 2026 — https://chdh.me/tools/network/security/hunter-how
7. OSINTBench — crt.sh Review — https://osintbench.com/tools/crt-sh-certificate-transparency-log-search/
8. FreeBuf — 企业信息收集与资产测绘全流程 (2024) — https://www.freebuf.com/articles/web/479973.html

> 状态：草稿（Phase 3.1 完成），待审稿
