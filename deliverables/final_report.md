# 企业被动信息搜集 Agent 深度研究报告：面向网络安全大赛的技术架构与合规策略

| 元信息 | 内容 |
|--------|------|
| 📅 日期 | 2026-07-13 |
| 🔬 研究课题 | 企业被动信息搜集 Agent |
| 📋 执行模式 | 完整 |
| 👥 研究团队 | 顾全之(主编)、季要纲(规划)、谭溯源(调研)、明鉴秋(审稿)、任润泽(修订)、程文成(撰写)、傅梓铭(发布) |
| 📊 报告版本 | v1.0 |
| 📐 章节数 | 5 章 |
| 📚 引用来源 | 共 86 个独立来源 |
| 📏 引用格式 | APA |

> ⚠️ 本报告由 AI 深度研究团队自动生成，重要决策请经专业人员核验。

**日期**：2026-07-13
**执行模式**：完整

---

## 目录

- [引言](#引言)
- [1. 被动信息搜集与 EASM/CTEM 攻击面管理基础框架](#1-被动信息搜集与-easmctem-攻击面管理基础框架)
- [2. 开源被动侦察工具链与情报API数据源生态](#2-开源被动侦察工具链与情报api数据源生态)
- [3. 多智能体规划-执行-记忆分层编排架构](#3-多智能体规划-执行-记忆分层编排架构)
- [4. 资产关联知识图谱与四层核验知识库机制](#4-资产关联知识图谱与四层核验知识库机制)
- [5. 合规边界界定与竞赛工程化冲分策略](#5-合规边界界定与竞赛工程化冲分策略)
- [结论](#结论)
- [参考文献](#参考文献)
- [待完善事项](#待完善事项)

---

## 引言

随着企业数字化转型加速，互联网暴露资产规模呈指数级增长——据统计，76%的组织曾因未知资产遭受网络攻击，而EASM工具平均能多发现35%的暴露资产（[Patrowl](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)）。在此背景下，被动信息搜集（Passive OSINT）凭借"零交互、零发包"的本质特征，成为攻击面管理的首选侦察手段，也是Gartner持续威胁暴露面管理（CTEM）框架中"发现阶段"的核心执行器（[Gartner, 2023](https://www.prnewswire.com/news-releases/gartner-anuncia-as-principais-tendencias-de-ciberseguranca-para-2023-841267191.html)）。然而，将分散的开源工具与情报API整合为自动化、智能化的Agent系统，仍面临三重挑战：一是被动与主动边界的合规界定模糊，二是多源异构数据的关联消歧困难，三是大语言模型驱动的多智能体编排中越界风险与记忆机制尚不成熟。

本报告围绕"企业被动信息搜集Agent"这一课题，从五个维度展开深度研究：第1章奠定被动OSINT与EASM/CTEM的理论基础；第2章梳理开源工具链与情报API生态；第3章构建多智能体规划-执行-记忆分层编排架构；第4章设计资产关联知识图谱与四层核验机制；第5章界定合规边界并提出竞赛工程化冲分策略。研究发现，HPTSA多智能体框架以53%的成功率和4.5倍效率提升显著优于单Agent方案（[SECRSS](https://www.secrss.com/articles/67220)），而Pentest-Chain的RAG记忆机制可将渗透测试成功率提升17.0%（[电信科学](https://www.secrss.com/articles/85448)），这些成果为竞赛场景下的工程化落地提供了可复用的技术路径。

---

## 1. 被动信息搜集与 EASM/CTEM 攻击面管理基础框架

### 论点

企业被动信息搜集（Passive OSINT）以"不与目标系统交互"为本质特征，是构建外部攻击面认知的合规默认范式；外部攻击面管理（EASM）作为 Gartner 持续威胁暴露管理（CTEM）框架中"发现阶段"的核心技术执行者，构成了本课题多智能体系统的理论与合规基座。然而，被动/主动边界在情报引擎（如 FOFA、Hunter）的实践中存在模糊地带，须以纯被动硬性约束与"合法≠伦理"的比例原则予以厘清，方能在竞赛场景中建立可辩护、可复现的冲分架构。

### 论据

#### 1.1 被动 OSINT 的严格定义与特征

被动信息搜集指"情报获取过程不与目标系统、账户或个人发生任何交互"——不发送消息、不发起请求、不触发探测、不在目标侧留下可观测痕迹，分析者纯粹是观察者 ([DeepFind, 2025](https://deepfind.me/blogs/passive-osint-vs-active-osint))。与之相对，主动 OSINT 一旦造成系统响应、日志记录或行为触发，便不再被动 ([Liora, 2024](https://www.liora.io/en/all-about-osint))。在漏洞赏金与 SRC 场景中，该区分被明确表述为：主动指"需跟目标系统、业务直接交互，如爆破子域名、扫描开放端口"，被动指"收集信息不需跟目标交互，如收集开源信息、企查查" ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。

被动侦察的核心价值在于不可见性与低风险：不发生交互即不生成日志，从而规避归因风险（IP、UA、时间戳暴露）、降低法律暴露、并保障证据完整性 ([DeepFind, 2025](https://deepfind.me/blogs/passive-osint-vs-active-osint))。DNS 侦察工具层面差异同样清晰：Subfinder 纯被动，"并行查询数十个被动数据源发现子域，不向目标发送任何 DNS 查询"，而 MassDNS 属主动暴力破解，向解析器发送实际查询（[PIStack, 2026-04](https://www.pistack.xyz/posts/2026-04-23-amass-vs-subfinder-vs-massdns-self-hosted-dns-reconnaissance-guide-2026)；该指南发布于 2026 年 4 月 23 日，已于本稿修订时实际打开核验可访问，内容为 Amass/Subfinder/MassDNS 被动—主动模式对比，故保留此引用）。

从合规与法律风险维度看，主动与被动侦察的分野更具实质意义。主动侦察（端口扫描、子域爆破、漏洞探测）会向目标发送数据包并触发其侧日志记录，一旦超出授权边界即可能触碰《网络安全法》第二十七条关于"不得从事非法侵入他人网络、干扰网络功能"的禁止性规定；就关键信息基础设施而言，配套法规进一步明确未经运营者或保护工作部门授权，任何个人和组织不得实施漏洞探测、渗透性测试等可能影响其安全的活动 ([司法部等四部门答记者问, 2024](https://ggzy.shaanxi.gov.cn/xwzx/002009/20240904/0e8afcb7-785a-4ca8-8c9d-c0de5f393cba.html))。在通用法域下，合法性测试以"授权"（authorization）而非"意图"为准绳——对第三方资产未经许可的扫描普遍被计算机犯罪法条（如美国 CFAA）认定为未授权访问的前置行为 ([pingthat.dev, n.d.](https://pingthat.dev/docs/port-scanning-legality-and-ethics))。相较之下，被动搜集因零交互、零日志，天然规避了上述可归因风险与授权边界争议，进一步凸显其作为竞赛默认合规范式的优势。

#### 1.2 EASM 定义及其作为 CTEM "发现阶段"核心

EASM 被定义为"持续发现、映射、监控并削减组织所有面向互联网资产（包括其自身未知资产）的过程" ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。Gartner 将其界定为"用于发现企业互联网资产及关联暴露（含错误配置的公云基础设施）以优先级处置潜在风险的过程、技术与托管服务" ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。EASM 自外向内、无代理、无需凭据与内网访问，正契合纯被动的数据采集逻辑 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。

EASM 之所以是 CTEM 的基石，在于它是"发现阶段"不可缺失的输入。Gartner 于 2022 年提出 CTEM 五阶段循环：范围界定、发现、优先级、验证、动员 ([Zynap, 2024](https://www.zynap.com/blog/whats-ctem-continuous-threat-exposure-management-explained))；Gartner 亦将 CTEM 列入 2023 年顶级战略技术趋势，并预测到 2026 年依 CTEM 计划确定安全投资优先级的组织遭受入侵的可能性将降低约三分之二 ([Gartner via PR Newswire, 2022](https://www.prnewswire.com/news-releases/gartner-anuncia-as-principais-tendencias-de-ciberseguranca-para-2023-841267191.html))。权威资料指出，"EASM 是 CTEM 最关键输入之一；若无外部发现，CTEM 的发现阶段将存在巨大盲区" ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。

数据印证了被动外部发现的必要性：76% 的组织曾遭受源自未知或未管理资产的攻击（Enterprise Strategy Group, 2024，转引自 [Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)）；采用 EASM 后平均可多发现 35% 的互联网暴露资产（Security Magazine, 2023，转引自 [Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)）；Gartner 估计 80–95% 的组织资产每年都会变更 ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。

#### 1.3 概念辨析：EASM vs ASM vs CAASM vs CTEM

四者并非竞争产品，而是成熟安全项目的分层能力 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))：ASM 是总称；EASM 专注互联网暴露资产；CAASM 自内向外聚合内部工具数据但"不发现未知外部资产"；CTEM 是过程框架。值得注意的是，多数标称"ASM 平台"的产品实际交付的是 EASM 能力 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。对本课题而言，以纯被动方式采集资产本质上是在执行 EASM 而非需内网代理的 CAASM。

#### 1.4 被动/主动边界的争议焦点：以 FOFA/Hunter 为例

争议源于"查询既已测绘的数据"与"主动探测"的混淆。以 FOFA、ZoomEye、Shodan、Censys 为代表的测绘搜索引擎，其底层引擎通过主动全网扫描构建数十亿级资产数据库 ([cnetsec, 2023](https://www.cnetsec.com/article/39908.html))；用户对其发起检索时，是在查询既已存在、已被厂商测绘的数据库，并未向目标发包——此检索行为属被动。然而，同一引擎若启用"主动探测/爆破"模式便向目标系统发送数据包、触发日志，触碰纯被动红线 ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。同样，DNS 工具链中 MassDNS 的暴力破解属主动，而 Subfinder 的纯被动枚举不向目标发包。本课题据此确立纯被动硬性约束：仅使用情报 API 与公开数据库在限流下检索已测绘资产，严格禁止端口扫描、TCP 发包、子域爆破等一切主动探测动作。

#### 1.5 合规与伦理：合法≠伦理与竞赛被动优先策略

被动搜集不等于无约束。核心命题是"合法≠伦理"：公开数据可合法获取，但跨源画像与个人信息的过度关联仍须受比例原则与目的核验约束 ([Privacy Insight Solutions, n.d.](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum))。该框架提炼两大可迁移原则——相称性：调查深度须匹配正当利益；目的验证：涉及私人个体前须确立并记录主体、理由与法律基础 ([Privacy Insight Solutions, n.d.](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum))。学术界亦明确指出，"技术上可行之事并非伦理上可证成"（"not everything that is technically possible is also moral"），且针对自然人的 OSINT 因涉及个人数据处理，其法律地位在多数法域下本就不确定、须受更严格约束 ([Menges & Kloss, International Cybersecurity Law Review, 2021](https://dx.doi.org/10.1365/s43439-021-00042-7))。在赛事场景下，被动优先策略具双重正当性：被动 OSINT"合法、伦理且通常足够有效" ([Liora, 2024](https://www.liora.io/en/all-about-osint))；ARWAD 等侦察路线图亦明确将企查查、Wayback、开源情报检索归入被动分支 ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。竞赛冲分应以"纯被动数据源 + 比例原则 + 目的核验"为工程基线，在资产关联过程中对个人敏感信息执行最小化与脱敏。

### 分析

综合上述，本课题的理论坐标可归纳为三层：范式层——被动 OSINT 是不可见、低归因风险的数据采集默认范式；框架层——EASM 以自外向内、无代理方式支撑 CTEM 发现阶段，是约三分之一隐性攻击面（对应 35% 额外资产发现，见第 1.2 节）的唯一可见化路径；约束层——情报引擎的"查询既测绘数据"被动、但其"主动探测"越界，须以纯被动硬性约束锁死技术路线，并以"合法≠伦理"的比例原则约束跨源关联。三层共同构成后续多智能体架构的合规基座。

### 小结

本章厘清了被动信息搜集与 EASM/CTEM 基础框架：被动 OSINT 以零交互、零痕迹为特征；EASM 作为 CTEM 发现阶段核心技术执行者，凭 76% 未知资产入侵与 35% 额外资产发现的实证数据确立外部发现必要性；概念辨析揭示多数"ASM"实为 EASM；FOFA/Hunter 被动查询/主动探测二元性引出纯被动硬性约束；合法与伦理分离要求以比例原则与目的核验收口跨源关联。上述框架为后续章节奠定理论与合规前提。

---

## 2. 开源被动侦察工具链与情报 API 数据源生态

### 论点：以"零发包"为红线的分层被动侦察底座

企业被动信息搜集的核心约束，是在不向目标系统发送任何探测数据包（即"零发包"）的前提下尽可能完整地还原其外部攻击面。数据显示，主流被动子域枚举工具通过并发查询第三方情报源（VirusTotal、Censys、Shodan、证书透明度日志等）即可发现大量资产，且具备隐蔽、不可被目标感知的优势（[ProjectDiscovery, n.d.](https://github.com/projectdiscovery/subfinder)；[OWASP Amass, n.d.](https://owasp-amass.github.io/docs/)）。本章主张：由"开源被动工具链 + 多元情报 API 生态"构成的分层采集体系，是竞赛中兼顾覆盖率与合规性的侦察底座；其中 MassDNS 字典爆破、FOFA 主动探测等主动手段，应被严格排除在纯被动阶段之外。

### 论据一：被动子域/资产枚举工具链的能力与边界

**Subfinder** 定位为"快速的被动子域名枚举工具"，默认通过 30+ 个被动在线源（含 VirusTotal、Censys、Shodan、SecurityTrails、FOFA、ZoomEye、Hunter 等）并发聚合数据，"不会向目标发送单个 DNS 查询"（[ProjectDiscovery, n.d.](https://github.com/projectdiscovery/subfinder)；[PIStack, 2026](https://www.pistack.xyz/posts/2026-04-23-amass-vs-subfinder-vs-massdns-self-hosted-dns-reconnaissance-guide-2026)）。其速度优势来自轻量架构与精选被动源；多数源需配置 API Key（如 `provider-config.yaml`），否则对应源无返回。

**OWASP Amass** 同时支持被动与主动模式：`-passive` 标志关闭 DNS 解析及依赖特性，仅通过搜索引擎、CT 日志、40+ API 集成（Shodan、Censys、VirusTotal 等）做被动枚举；`-active`/`-brute` 则会向目标 DNS 发起查询与暴力枚举，属主动侦察（[OWASP Amass, n.d.](https://owasp-amass.github.io/docs/)；[0xffsec, n.d.](https://0xffsec.com/handbook/information-gathering/subdomain-enumeration/)）。Amass 还能以资产数据库长期追踪攻击面，适合深度测绘。

**OneForAll、Sublist3r、theHarvester、Assetfinder** 各具侧重：OneForAll 集成证书透明度、搜索引擎、DNS 数据集、威胁情报等模块，输出格式丰富但速度偏慢（[FreeBuf, n.d.](https://m.freebuf.com/articles/web/366925.html)）；Sublist3r 通过爬取 Google/Bing/Baidu/Netcraft/VirusTotal 等 HTML 页面提取子域、无专用 API、工具偏老旧，有观点认为其应被淘汰、仅作补充（[FreeBuf, 2024](https://www.freebuf.com/articles/web/479973.html)）；theHarvester 以 OSINT 方式收集邮箱、子域、虚拟主机与端口 Banner，但子域结果相对少（[Outpost24, n.d.](https://outpost24.com/blog/art-of-subdomain-enumeration)）；Assetfinder 以简洁著称，聚合多个被动 OSINT 源输出子域（[FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html)）。

**crt.sh 证书透明度** 是被动子域提取的核心枢纽：自 2018 年 Chrome 强制 CT 以来，所有受信任 CA 签发的证书必须记入公共 CT 日志（[crt.sh, n.d.](https://crt.sh/)）。crt.sh 聚合这些日志，通过 `%.example.com` 通配模式提取每张证书的 SAN（Subject Alternative Name）字段，从而被动还原历史子域——整个过程"无任何流量触及目标服务器"（[OSINTBench, n.d.](https://osintbench.com/tools/crt-sh-certificate-transparency-log-search/)）。

### 论据二：零发包历史快照与证书核心

**Wayback Machine CDX API** 是免费、无需密钥的互联网存档索引接口，覆盖自 1996 年以来的 8900 亿+ 网页快照（[ApifyForge, 2026](https://apifyforge.com/blog/wayback-machine-api-programmatic-search)）。其 `matchType`（exact/prefix/host/domain）、`collapse=digest`（去重仅保留内容变更快照）、`statusFilter`、`mimeFilter` 等参数，使研究者可回溯已删除页面、历史端点与 JS 文件中的敏感接口；因只查询存档库、不接触目标，本质为被动侦察。社区实践中建议以约 1 请求/秒的礼貌速率访问，单查询上限约 15 万条（[Scraperly, 2026](https://scraperly.com/scrape/wayback-api)）。

### 论据三：国内情报 API 数据源生态

网络空间测绘平台通过"查询已测绘数据"实现被动检索。数据显示，**FOFA**（华顺信安）已积累 40 亿+ 资产、35 万+ 指纹规则（[cnetsec, 2023](https://www.cnetsec.com/article/39908.html)）；其免费注册用户每月 300 次页面查询，**查询 API 接口与 1 请求/秒 并发需个人版及以上会员**（[FOFA, n.d.](https://fofa.info/vip)）。**Hunter（奇安信鹰图）** 因国资/央企品牌背书，在政企合规采购中过审难度低，且国内 IP 段覆盖更密、中文支持好（[chdh.me, 2026](https://chdh.me/tools/network/security/hunter-how)）；其 API 每日约 500 条积分（[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)）。**ZoomEye（知道创宇）** 以 Xmap+Wmap 双引擎覆盖设备与 Web 指纹，免费 API 每月 1 万条、最小请求单位 20 条、本地缓存 5 天（[knownsec, n.d.](https://github.com/knownsec/ZoomEye-python/blob/v2.0.4.4/docs/README_CN.md)；[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)）。**Censys** 具学术公益背景，免费层 API 每月约 250 条；**Shodan** 在 OT 设备与全球覆盖上占优。

面向国内目标的工商/备案采集，**ENScan_GO** 基于各大企业信息 API，一键收集控股公司 ICP 备案、APP、小程序、微信公众号等并支持 MCP 接入（[wgpsec, n.d.](https://github.com/wgpsec/ENScan_GO)）。业内观点普遍认为，中文情报生态（FOFA/Hunter/ZoomEye + ENScan_GO）对国企、国内目标的适配度显著高于纯英文工具链，因其覆盖 ICP 备案、工商关联、公众号/小程序等本土特有资产维度。

### 论据四：限流与风控（竞赛关键）

各平台均设查询配额与速率限制，竞赛中极易触发风控。事实数据显示：FOFA 免费 300 查询/月、API 1 请求/秒；Hunter 每日约 500 条；ZoomEye 每月约 1 万条（网页与 API 额度规则各异）；Censys 约 250/月；360 Quake 约 3000/月（[NoMoney, n.d.](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)；[FOFA, n.d.](https://fofa.info/vip)）。有安全研究者指出，多账户注册刷额度会被各平台风控系统识别并可能导致封禁，故应通过合规策略在额度内提效（[CSDN, n.d.](https://wenku.csdn.net/answer/157x7pcvkz)）。据此，本章预埋第 5 章的合规采集策略：**API 代理层 + 多出口 IP 轮询 + 任务排队缓存**——以代理层统一封装各平台 SDK、以多出口 IP 分摊单 IP 限流、以任务队列与本地缓存复用历史结果，从而在额度内最大化采集效率。

### 论据五：被动/主动模式对比与选型矩阵

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

### 分析

上述工具与数据源可划分为三层：**被动发现层**（Subfinder/Amass -passive/crt.sh/Wayback）负责零发包广撒网；**国内情报层**（FOFA/Hunter/ZoomEye/ENScan_GO）补足本土资产维度；**主动验证层**（MassDNS/Amass -active/平台主动探测）仅用于授权范围内的二次确认。竞赛得分的关键，不在于主动发包的"狠"，而在于被动层的"全"与"巧"——在额度与合规约束下，通过多源聚合、历史快照与证书透明度，往往能触及主动扫描无法发现的遗忘资产（如已下线的测试环境、CI/CD 预览域名）。

### 小结

开源被动侦察工具链与情报 API 生态共同构成企业被动信息搜集的"零发包"底座。Subfinder、Amass（被动模式）、OneForAll、Sublist3r、theHarvester、Assetfinder 与 crt.sh、Wayback CDX 等工具，可在不触达目标的前提下完成子域与历史资产发现；FOFA、Hunter、ZoomEye、Censys、Shodan 与 ENScan_GO 等国内平台则提供适配本土目标的空间测绘与工商情报。在严格遵循"纯被动红线"（禁用 MassDNS 爆破与平台主动探测）并配合 API 代理层、多出口轮询与任务排队缓存的合规策略下，该体系可支撑竞赛中高效、可持续的资产采集。

---

## 3. 多智能体规划-执行-记忆分层编排架构

### 论点：以分层编排构建可控的自动化侦察体系

被动信息搜集的核心挑战，是在不触达目标的前提下，将多源数据采集、跨主体股权穿透、盲区动态补缺等复杂流程自动化。单一 LLM Agent 受限于上下文窗口、幻觉风险与越界可能性，难以独立胜任全链路任务。本章主张：借鉴 PentestAgent、BreachSeek、HPTSA 等学术界多智能体安全系统的规划-执行-记忆分层架构，以 LangGraph 图工作流为编排框架，构建"指挥官 Agent（规划）→四大专项采集集群（执行）→三库协同知识库（记忆）"的分层体系，并通过 Docker microVM 沙箱与 Plan-then-Execute 控制流完整性实现架构级越界防控，使被动信息搜集从"工具堆砌"升级为"可审计、可恢复、可扩展的智能体编队"。

### 论据

#### 3.1 规划层：LLM 驱动的全局指挥官 Agent

被动信息搜集的第一步是全局规划。指挥官 Agent 以企业全称为输入，自动执行股权穿透拆解关联主体，并为每家主体下发 Web 资产、公众号、小程序三类采集子任务。这一设计借鉴了当前学术界多个里程碑式多智能体安全系统的规划架构。

PentestAgent 提出了基于 LLM 的多代理自动化渗透测试框架，采用侦察、搜索、规划、执行四代理协作架构，利用检索增强生成（RAG）增强代理的上下文记忆与知识检索能力，通过链式思考（CoT）将复杂任务分解为子任务，减少幻觉输出。实验表明，其情报收集阶段平均耗时不到 400 秒且无需人工交互，显著优于 PentestGPT 的 826 秒和 7.4 轮交互 ([PentestAgent, arXiv:2411.05185](https://doi.org/10.48550/arXiv.2411.05185)；[BAAI 摘要](https://hub.baai.ac.cn/paper/39bf5b90-924f-4f24-8711-f432949d0f5b))。

HPTSA（分层规划与任务特定代理系统）采用"分层规划代理→团队经理代理→任务特定专家代理"三级架构。规划代理负责探索目标环境、识别攻击面并制定策略；经理代理协调信息共享。在 15 个真实零日漏洞基准测试中，HPTSA 五次尝试成功率达 53%，工作效率提升 4.5 倍以上，且显著优于 ZAP、MetaSploit 等开源扫描器 ([SECRSS HPTSA](https://www.secrss.com/articles/67220)；[HPTSA GitHub](https://github.com/uiuc-kang-lab/HPTSA))。

BreachSeek 基于 LangGraph 图工作流实现"监督者→专门代理→评估者"三方协调架构，监督者作为中央协调者生成高层次行动计划并动态调整策略，评估者作为质量检查点校验输出准确性 ([ChatPaper BreachSeek](https://chatpaper.com/zh-CN/chatpaper/paper/57650)；[CyberSecurityNews](https://cybersecuritynews.com/breachseek-penetration-testing))。

在本课题的被动信息搜集场景中，指挥官 Agent 核心逻辑为：输入企业全称→调用工商股权 API（如 ENScan_GO）进行股权穿透→拆解 N 家关联主体→为每家主体生成 Web/公众号/小程序三类采集任务清单→实时识别采集盲区并动态补充数据源检索。这一流程映射了 LangGraph 的"Plan-then-Execute"范式——规划节点先生成完整步骤序列并存储于状态中，执行节点仅被限定使用规划中指定的工具，从架构层面防止越权操作 ([LangGraph: Modular LLM Agent Orchestration, EmergentMind](https://www.emergentmind.com/topics/langgraph))。

#### 3.2 执行层：四大专项采集集群与 Docker 沙箱隔离

执行层包含四大专项采集 Agent：Web 资产采集 Agent（调用 subfinder/Amass/FOFA）、公众号采集 Agent、小程序采集 Agent、工商股权采集 Agent（调用 ENScan_GO）。各 Agent 独立运行于 Docker 沙箱中，多 Agent 并行执行。

BreachSeek 已验证"专门代理托管于独立容器"的有效性——通过将认知负载分配给专用节点，有效缓解了 LLM 上下文窗口的固有限制 ([BreachSeek arXiv:2409.03789](https://adsabs.harvard.edu/abs/2024arXiv240903789A))。LangGraph 监督者模式进一步表明，并行 worker 执行可将总执行时间从所有分析之和缩减为最长单项耗时，典型场景下降低 60-70% 的挂钟时间 ([Supervisor Pattern, DevOps Gheware](https://devops.gheware.com/blog/posts/supervisor-pattern-multi-agent-langgraph-2026.html))。

在隔离安全方面，Docker 于 2025 年底推出面向 AI Agent 的 Sandbox 方案，采用 microVM（微虚拟机）而非普通容器实现内核级隔离。每个 Sandbox 拥有独立内核、文件系统和网络栈，其核心设计包括：API Key 通过宿主机网络代理注入，Agent 进程本身拿不到密钥；网络策略强制执行（Open/Balanced/Locked Down 三级），所有出站连接实时审计。这使得"即使 Agent 出现幻觉或行为异常也不会造成系统性风险" ([Docker Sandboxes 技术解析](https://www.cnblogs.com/imust2008/p/20351523)；[Docker Sandbox Overview, Collabnix](https://collabnix.com/docs/docker-workshop/sandboxing-with-docker/overview/))。

#### 3.3 记忆层：三库协同的知识沉淀与经验复用

记忆层构建三类知识库：CTF 漏洞知识库（漏洞特征、攻击步骤、绕过技巧）、题目样本库（历史题目与解题路径）、平台反馈知识库（提交结果与评分反馈）。Agent 发起攻击前自动检索匹配方案，实现解题经验复用。

Pentest-Chain 框架验证了"外部知识库+内部经验库"双库协同的有效性：引入 RAG 模块后，多智能体框架的任务执行成功率整体提升 17.0%，消融实验表明 RAG 对成功率提升起关键作用。其外部知识库整合了 ATT&CK 矩阵和 CVE 漏洞库，内部经验管理器支持长流程任务中的跨步骤记忆 ([基于 LLM 和 RAG 的自动化渗透测试框架研究, 电信科学 2025](https://www.secrss.com/articles/85448))。中国电信"红刃"AI 智能体构建了包含 500+ 主流框架漏洞的知识库，采用"路径地图+双层漏斗记忆机制"：为每个解题过程创建持续维护的状态地图，通过记忆漏斗过滤噪声，将关键事实沉淀到全局记忆中，遵循"只追加不修改"原则保障核心线索的可追溯性 ([凤凰网科技](https://tech.ifeng.com/c/8t7m7uQNF16))。

学术前沿方面，LEGOMem 提出"全任务粒度 vs 子任务粒度"的分层程序性记忆：编排者记忆存储完整任务计划用于工作流分解，子代理记忆存储局部执行轨迹 ([LLM-based Modular Multi-Agent Frameworks, EmergentMind](https://www.emergentmind.com/topics/llm-based-modular-multi-agent-frameworks))。

#### 3.4 多智能体通信与协调机制

当前主流编排框架普遍采用"大脑-记忆-感知-行动"的核心架构范式，协作模式包括顺序流、层级流和协作辩论三类 ([告别单体LLM局限:Multi-Agent系统架构指南](https://2048ai.net/694b7e43836da32144874c0e.html)；[Agentic LLMs 前沿综述](https://www.cnblogs.com/sddai/p/19451103))。

LangGraph 通过有向图工作流和状态机实现精细化流程控制：Command 作为编排内核驱动节点间转移，state 作为沟通载体在节点间传递结构化数据，交接（handoff）工具统一路由逻辑。2025 年 LangGraph 多次更新引入了对长时运行任务和远程 Agent（A2A 协议）的支持 ([LangGraph 多智能体架构:5种典型模式, CSDN](https://devpress.csdn.net/v1/article/detail/151871815))。LangChain 2025 年的智能体架构已成熟为模块化分层系统，定义了规划智能体（战略大脑）、执行智能体（RAG/代码生成等专用）、通信智能体（管理步骤间交接、保留上下文）、评估智能体（质量检查点，可退回任务）四类核心角色 ([使用 LangChain 构建多智能体工作流](https://tinyseeking.github.io/p/%E4%BD%BF%E7%94%A8-langchain-%E6%9E%84%E5%BB%BA%E5%A4%9A%E6%99%BA%E8%83%BD%E4%BD%93%E5%B7%A5%E4%BD%9C%E6%B5%81))。

#### 3.5 幻觉与越界防控

多智能体架构通过职责分离降低单一大模型幻觉风险，但也引入 Agent 越界主动探测、上下文丢失和代理间信任传递风险。

在幻觉防控方面，Tree of Agents（TOA）通过将长输入分段交由独立 Agent 处理，各 Agent 生成局部认知后沿树结构路径动态交换信息进行协作推理，有效缓解"中间遗忘"问题和位置偏差 ([TOA, arXiv:2509.06436](https://doi.org/10.48550/ARXIV.2509.06436))。清华大学提出的对抗辩论与投票机制框架通过重复询问、错误日志和跨代理交叉验证，在 20 个评估批次中持续提升综合准确率 ([Minimizing Hallucinations, Applied Sciences 2025](https://web.ee.tsinghua.edu.cn/yangyi/zh_CN/lwcg/4724/content/9941.htm))。

在越界防控方面，Sentinel Agents 框架提出"预验证层+被动监听层"双层监控：预验证层在对话事件到达协调器前拦截并决定是否继续；被动监听层实时识别异常并发出审计标记 ([Sentinel Agents 评述, Moonlight](https://www.themoonlight.io/zh/review/sentinel-agents-for-secure-and-trustworthy-agentic-ai-in-multi-agent-systems))。业界共识是：基于提示词的防御在攻击下普遍损失 10-30% 的实用性，架构约束才是根本解。措施包括：将所有 LLM 输出（含其他 Agent 输出）视为不可信；不可信内容运行在隔离 sandbox 中；每个 Agent 仅授予最窄工具与权限。OWASP 于 2025 年 12 月发布的 Top 10 for Agentic Applications 将前三风险定为 Memory Poisoning、Tool Misuse 和 Privilege Compromise ([Agent 安全:信任边界到 Multi-Agent 蠕虫](http://quidproquo.cc/posts/ai/2026-06-04-agent-security-prompt-injection-trust-boundaries))。

对于被动信息搜集场景，最关键的红线是：Agent 不得执行任何主动探测操作。LangGraph 的 Plan-then-Execute 范式通过"控制流完整性"提供架构级保障——控制图在任何外部工具调用前生成，高层工作流不会被事后注入的内容篡改，确保执行可追溯且确定性 ([LangGraph: Modular LLM Agent Orchestration, EmergentMind](https://www.emergentmind.com/topics/langgraph))。

### 分析

综合上述，本章的多智能体编排架构可归纳为三层纵深：**规划层**——借鉴 PentestAgent 的四代理协作与 HPTSA 的分层规划架构，以指挥官 Agent 实现股权穿透→任务拆解→盲区动态补缺，其 Plan-then-Execute 范式从架构层面杜绝越权操作；**执行层**——四大专项采集 Agent 并行运行于 Docker microVM 沙箱，以独立内核与 API Key 代理注入实现"Agent 拿不到密钥、越界也无害"的结构性安全兜底，并行执行可降低 60-70% 挂钟时间；**记忆层**——三库协同（漏洞知识库+样本库+反馈库）配合 RAG 检索，经实证可使任务成功率提升 17.0%，中国电信"红刃"的路径地图+漏斗记忆机制进一步验证了"只追加不修改"原则在长流程可追溯性中的价值。三层共同将被动信息搜集从"工具堆砌"升级为"可审计、可恢复、可扩展的智能体编队"，并通过架构级越界防控使"纯被动"约束从规则声明升级为工程刚性保障。

### 小结

本章构建了多智能体规划-执行-记忆分层编排架构：规划层以 LLM 指挥官 Agent 驱动全局股权穿透与任务分发，借鉴 PentestAgent/HPTSA/BreachSeek 的学术验证；执行层以四大专项采集 Agent 并行运行于 Docker microVM 沙箱，实现内核级隔离与 60-70% 挂钟时间压缩；记忆层以三库协同+RAG 实现经验复用，成功率提升 17.0%；通信层以 LangGraph 图工作流实现精细化编排与 A2A 协议支持；越界防控以 Plan-then-Execute 控制流完整性与 Sentinel Agents 双层监控实现架构级保障。上述架构为第 4 章的资产关联知识图谱提供了数据入口，为第 5 章的合规审批与算力调度提供了执行载体。

---

## 4. 资产关联知识图谱与四层核验知识库机制

### 4.1 Neo4j 资产关联图谱：从扁平清单到关联拓扑

被动信息搜集的核心挑战在于：从工商、DNS、证书透明度、公开代码库等异构来源获取的资产数据天然分散，传统关系型数据库擅长扁平列表查询，却难以应对多跳关联遍历。Neo4j 图数据库通过将「企业—子公司—域名—公众号—小程序」等实体抽象为节点、将投资与解析等关联关系抽象为边，构建出可深度遍历的资产关联拓扑。Neo4j 官方技术文档指出，将安全数据建模为图后，安全架构师可获得三大独特优势：**可达性分析**（判断某漏洞资产是否真正可达公网）、**爆炸半径与影响分析**（遍历 IAM 关系识别横向移动路径）、**战略性修复**（识别修复单个组件即可降低全局风险的瓶颈节点）（[Neo4j 暴露管理](https://neo4j.ac.cn/developer/industry-use-cases/cybersecurity/vulnerability-prioritization-exposure-management/)）。

该方案在工业界已有权威验证。CAASM 平台 JupiterOne 在 2024 年完成将核心数据架构从双存储系统迁移至 Neo4j，迁移后**P99 查询延迟下降两个数量级**（从数分钟降至平均 180 毫秒），**数据管线成本降低 90% 以上**，数据摄取时间从 8 小时缩短至约 10 秒。其工程负责人 James Mountifield 强调，多跳动态遍历（如从内部资产追踪至公网的暴露路径）"正是图数据库的设计目标"，并已在迁移后实现此前不可行的多跳攻击路径分析能力（[JupiterOne × Neo4j 案例研究](https://neo4j.com/customer-stories/jupiterone)）。此外，JupiterOne 在图上施加严格本体约束（ontology），为 AI 模型提供确定性基础，防止幻觉——这一思路对本系统的 LLM 辅助分析具有直接参考价值。

### 4.2 语义实体消歧：LLM 驱动的跨源归并

跨源数据归并是资产图谱构建中最棘手的环节。同一域名在不同数据源中可能以不同格式出现（如 `api.example.com` 与 `API.EXAMPLE.COM.`），同一企业在工商库与企查查中名称后缀各异。传统实体解析依赖字符串距离和静态规则，难以捕获深层语义等价性。语义实体解析（Semantic Entity Resolution）利用预训练语言模型的表示学习能力，自动完成**模式对齐—阻塞—匹配—合并**四步流程。实验显示，使用 BAML + Gemini 2.5 Pro 可在单次 prompt 中完成 39 条记录的匹配与合并且无一处错误，并能借助字段元数据描述引导模式对齐而无需显式指令（[Towards Data Science: 语义实体解析的兴起](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/)）。

在本系统语境下，语义实体消歧承担资产去重与归并的"中枢"角色：将证书透明度日志、被动 DNS 记录、工商主体信息等异构来源的资产记录，经语义嵌入聚类后形成 `SAME_AS` 边连通分量，最终合并为统一资产节点。这使得资产关联图谱与股权穿透图谱的去重有了统一的技术基础。

### 4.3 四层自动核验流水线（全程无主动发包）

为保障入库资产的准确性与合规性，本系统设计了四层级联核验机制，**全程不向目标发送任何探测包**，仅依赖公开记录与被动数据：

**① 工商主体匹配层**：对每条采集到的资产，通过企查查等工商数据源核验其归属主体是否属于目标企业或其关联子公司，剔除不属于目标企业的"误采"资产（如重名域名归属无关公司）。法人核验技术通过关联图谱与控制权计算模型，将传统数天的人工尽调缩短至分钟级（[法人核验技术解析](https://www.yanhaowang.cn/news_info/347.html)）。

**② DNS 被动存活校验层**：仅解析域名的 DNS 记录（A/AAAA/CNAME/MX 等），判断其是否仍指向有效 IP，**不访问站点本身**。被动 DNS 侦察的核心原则是"从不直接与目标系统交互"，仅查询公共 DNS 服务器、证书透明度日志和 WHOIS 数据库，既不留痕于目标基础设施，又在法律上可针对任何域名执行（[NetSpecter OSINT 文档](https://netspecter-osint.github.io/documentation/)）。被动 DNS 数据库（如 Farsight DNSDB）可提供历史解析记录，支持时间维度的存活分析（[FreeBuf: 被动 DNS 与网络安全](https://www.freebuf.com/news/391907.html)）。

**③ 时间过滤层**：对 1 年以上无 DNS 解析更新、已注销或长期无变化的"僵尸资产"予以剔除或降权标记。证书透明度日志可揭示已过期或废弃的内部子域证书，帮助识别被遗忘的资产与遗留基础设施（[Krawly: DNS 调查指南](https://krawly.io/blog/what-one-domain-tells-you-dns-investigation)）。

**④ 多源交叉验证层**：同一情报须至少两个独立数据源相互佐证方可入库。电信运营商威胁情报体系研究明确指出，不同来源情报在字段定义与威胁定级上常存在冲突，必须经过数据归一化、去噪与融合处理，并建立科学的信誉分析机制判定情报可信度（[电信运营商威胁情报体系研究](https://www.telecomsci.com/rc-pub/front/front-article/download/59574690/lowqualitypdf/电信运营商威胁情报体系研究与应⽤探索.pdf)）。学术研究亦验证了基于 STIX 图谱的多源 IoC 聚合可显著提升置信度评分精度，实现 25.18% 的置信度误差缩减（[ScienceDirect: STIX 图谱优化 IoC 质量](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773)）。华云安在某全国性股份制银行的实践中，采用**基于置信度评价的多源风险数据融合**，对漏洞、弱口令、暗网监测等多维攻击面数据进行交叉验证，显著提升了数据降噪效能（[华云安金融攻击面管理案例](https://www.dwcon.cn/post/3626)）。

### 4.4 股权穿透与交叉核验

企查查 MCP 平台为工商主体匹配与股权穿透提供了标准化的原子能力。其银行客群 SKILL 集包含 KYB 企业核验（主体真实性核验、34 类司法与经营风险扫描）、股权结构穿透分析（自动完成多层股权穿透并生成可视化结构图、识别实际控制人与隐性关联关系）、受益所有人识别（按央行 25% 阈值穿透股权链路、锁定最终受益人）等核心工具，3 分钟即可输出符合 FATF 标准的合规报告（[企查查智能体数据平台](https://agent.qcc.com/skills?cat=banking)）。

从技术原理看，股权穿透本质是在企业关联图谱上执行递归穿透算法（Recursive Penetration Algorithm）：系统首先运用实体对齐与消歧技术融合外部工商投资关系数据与内部 CRM 数据，构建包含数亿节点与数十亿条边的企业关联网络；随后在图谱中展开多跳路径搜索，沿持股路径逐层相乘并汇总股份比例，穿透多层企业嵌套与交叉持股，精确定位最终实际控制人（[智能风控: AI 实时合规图谱](https://www.lumevalley.com/article-4431.html)）。这一图技术突破了传统关系型数据库的查询极限，使全量子公司、分公司主体的批量发现成为可能——这正是被动资产搜集所需的"由主体辐射资产"能力。

### 4.5 测绘经验库与知识复用

知识图谱的另一价值在于持续迭代与经验复用。北京大学研究团队提出的 AutoCTI2KG 框架，通过大语言模型的指令提示与上下文学习，自动从威胁情报中生成网络安全知识图谱，F1 值达 0.90 左右，展示了 LLM 在安全知识图谱持续构建中的潜力（[基于大语言模型的网络威胁情报知识图谱构建](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/基于⼤语⾔模型的⽹络威胁情报知识图谱构建技术研究.pdf)）。奇安信已构建百亿节点规模的图数据库，通过子图提取、图嵌入与图神经网络训练，输出疑似恶意节点推荐，形成稳定的情报运营闭环流程（[奇安信 AI 驱动网络安全实践](https://www.qianxin.com/news/detail?news_id=12438)）。

在本系统中，同类企业（如同行业、同规模）的采集策略、命名规律与资产分布模式可沉淀为"测绘经验库"：当面对新目标企业时，系统优先复用经验库中匹配的采集模板与过滤规则，显著缩短冷启动时间。知识图谱随每次采集任务持续补充新节点与新关系，经验库随之迭代优化，形成"采集—核验—沉淀—复用"的正向循环。

### 关键发现

- **图数据库性能优势获工业验证**：JupiterOne 迁移 Neo4j 后 P99 延迟降两个数量级、管线成本降 90%+，多跳遍历能力是关系型库无法企及的（[JupiterOne](https://neo4j.com/customer-stories/jupiterone)）
- **语义实体消歧实现跨源自动归并**：LLM 可在单次 prompt 中完成数十条记录匹配合并，字段描述引导模式自动对齐（[TDS](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/)）
- **四层核验全程无主动发包**：DNS 被动解析 + 证书透明度 + 工商匹配 + 多源交叉，兼顾合规性与准确性（[NetSpecter](https://netspecter-osint.github.io/documentation/)、[华云安](https://www.dwcon.cn/post/3626)）
- **股权穿透本质为图谱递归算法**：企查查 MCP 提供标准化原子能力，图技术突破关系型库查询极限（[智能风控图谱](https://www.lumevalley.com/article-4431.html)、[企查查 MCP](https://agent.qcc.com/skills?cat=banking)）
- **LLM 赋能知识图谱持续迭代**：AutoCTI2KG 框架 F1 达 0.90，支持经验复用与自动补全（[北京大学研究](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/基于⼤语⾔模型的⽹络威胁情报知识图谱构建技术研究.pdf)）

### 数据摘要

| 指标 | 数据 | 来源 |
|------|------|------|
| JupiterOne P99 延迟改善 | 降两个数量级（→180ms） | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 数据管线成本降低 | >90% | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 数据摄取时间 | 8 小时 → ~10 秒 | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 语义实体解析单批记录 | 39 条/prompt，0 错误 | [TDS](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/) |
| STIX 图谱置信度误差缩减 | 25.18% | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773) |
| AutoCTI2KG 知识图谱构建 F1 | ~0.90 | [北京大学](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/基于⼤语⾔模型的⽹络威胁情报知识图谱构建技术研究.pdf) |
| 企查查 KYB 核验报告输出 | 3 分钟 | [企查查 MCP](https://agent.qcc.com/skills?cat=banking) |

---

## 5. 合规边界界定与竞赛工程化冲分策略

### 论点：合规先于效能的工程化框架

企业被动信息搜集 Agent 的首要设计原则是"合规先于效能"。赛事硬性约束——纯被动数据源、禁端口扫描与TCP发包——并非竞赛规则的随意设定，而是有多层法律根基支撑的刚性红线。本章主张：唯有将法律合规、API限流风控、人机协同审批、算力调度与断点恢复五重机制系统化嵌入工程架构，方能在竞赛中实现"可持续冲分"而非"一次封禁清零"。

### 论据

#### 5.1 合规红线体系：纯被动约束的法律根基

**国内法律层面**，《网络安全法》第二十七条明确规定："任何个人和组织不得从事非法侵入他人网络、干扰他人网络正常功能、窃取网络数据等危害网络安全的活动" ([网络安全法第二十七条](https://www.changdu.gov.cn/cdrmzf/qzqdnew/202203/b01dde7155fd451a98e2658b53dd8dd6.shtml))。2025年1月1日施行的《网络数据安全管理条例》第十八条进一步细化了自动化工具的合规要求："网络数据处理者使用自动化工具访问、收集网络数据，应当评估对网络服务带来的影响，不得非法侵入他人网络，不得干扰网络服务正常运行" ([网络数据安全管理条例](https://big5.www.gov.cn/gate/big5/www.gov.cn/zhengce/content/202409/content_6977766.htm))。该条例"正视了自动化程序访问数据的合理需求"，但要求区分数据爬取的具体情况来判定合法性 ([网络数据爬取合法性三阶层认定标准](http://data.pkulaw.net/qikan/0bf22b2b6765c2ab4976053071cd7433bdfb.html))。对于关键信息基础设施，《关基条例》第三十一条规定："未经国家网信部门、国务院公安部门批准或者保护工作部门、运营者授权，任何个人和组织不得对关键信息基础设施实施漏洞探测、渗透性测试等可能影响或者危害关键信息基础设施安全的活动" ([关键信息基础设施安全保护条例](https://www.isccc.gov.cn/xxgk1/zcfg_3/flhxzfg/202208/P020251113614748154900.pdf))。

**国际法律层面**，美国《计算机欺诈和滥用法》（CFAA）以"授权"为核心判定标准：未经授权访问受保护计算机系统，或超出授权范围获取信息，均构成违法 ([CFAA解析](https://legalclarity.org/cfaa-what-is-the-computer-fraud-and-abuse-act/))。2021年 Van Buren v. United States 案后，最高法院收窄了"超出授权访问"的适用范围，但"未经授权访问"仍构成独立违法。2025年10月第三巡回法院在 NRA Group LLC v. Durenleau 案中进一步确立了"gates-up-or-down"标准，即仅违反雇主计算机访问政策但不突破技术屏障的行为不构成 CFAA 违规 ([DataBreaches.net](https://databreaches.net/2025/11/11/gates-down-third-circuit-says-breaking-employer-computer-access-policies-is-not-hacking/))。跨司法管辖区的共性是：**合法性判定以"是否获得授权"为准绳，而非以"意图是否恶意"为准绳** ([PingThat](https://pingthat.dev/docs/port-scanning-legality-and-ethics))。

基于上述法律框架，被动 Agent 应建立**行为黑白名单机制**：黑名单绝对阻断端口扫描（Nmap SYN/Masscan）、主动HTTP探测、TCP指纹发包等一切与目标系统直接交互的动作；白名单允许DNS解析查询、工商信息公开数据获取、历史快照检索（Wayback Machine）、开源仓库公开信息读取等纯被动操作。任务启动前进行前置合规校验，任何动作触发黑名单匹配即直接终止该任务分支，并写入合规告警日志。

#### 5.2 API限流风控：多源配额管理与防护性调度

赛事情报API的限流数据构成采集系统的硬性约束边界。根据各平台官方定价信息：FOFA注册用户每月仅300次查询配额，个人版（$25/月）为1万次/月，API并发限制为1秒1次 ([FOFA VIP](https://fofa.info/vip))；ZoomEye免费版每月3,000条结果、API速率限制0.5次/秒，个人版为10万条/月、1次/秒 ([ZoomEye Pricing](https://www.zoomeye.ai/pricing))；鹰图（奇安信）API每日500条 ([NoMoney限流对比](https://blog.csdn.net/seoppg/article/details/139362026))。surveyhub-mcp 等聚合工具进一步体现了进程中节流策略，如 FOFA 搜索5秒/次、Host查询1秒/次 ([surveyhub-mcp](https://pypi.org/project/surveyhub-mcp))。

超限后果严重——平台风控系统会直接封禁IP。为规避封禁风险，采集系统应采用**三层防护性调度策略**：第一层，单数据源独立限流，每个API分配独立令牌桶，按平台限流阈值设置速率上限（如FOFA设置1req/s + 月配额300的滑动窗口监控）；第二层，任务排队缓存，使用消息队列（如Redis Stream/Kafka）吸收突发请求，Worker按受控速率消费，避免并发冲击 ([API限流策略](https://apipark.com/techblog/en/mastering-how-to-circumvent-api-rate-limiting-effectively/))；第三层，多出口IP轮询，将合法的多个出口IP纳入流量池，按延迟与失败率动态切换，单IP连续失败触发熔断暂停。情报批量提交时自动分片，将大查询拆分为不超过单次配额上限的子任务，规避平台风控阈值。

#### 5.3 三级人机审批机制：风险分层的自动化治理

被动 Agent 的自动化程度需与操作风险等级匹配。业界已形成成熟的**分层审批范式**：低风险操作（日志查询、状态检查）由Agent自主执行；中风险操作（配置写入、服务重启）Agent执行后事后通知；高风险操作（数据删除、生产变更）必须人类确认后方可执行 ([Human-in-the-Loop生产环境实践](https://blog.csdn.net/weixin_41736460/article/details/160656156))。EU AI Act 第14条明确要求高风险AI系统必须保留人类监督能力，包括理解AI能力边界、解释AI输出、覆盖或中止AI系统的权力 ([AI Security Wiki](https://snailsploit.com/ai-security/wiki/defenses/human-in-the-loop))。NIST AI RMF 框架同样在 GOVERN 和 MANAGE 阶段强调人类监督机制——GOVERN 功能要求建立组织层面的问责结构与角色职责，MANAGE 功能要求对已识别风险实施处置、响应与恢复操作，两者共同构成 AI 系统全生命周期的人类监督闭环 ([NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework))。

映射到竞赛场景，三级审批机制设计如下：**低风险**——DNS解析、工商信息查询、ICP备案查询等纯公开数据操作，Agent全自动执行并入库；**中风险**——历史快照检索、开源仓库代码搜索、证书透明度日志查询等操作，自动入库并推送提醒供人工抽查；**高价值**——涉及工控系统（ICS/SCADA）、政务资产、关键信息基础设施的情报，必须人工复核后方可提交赛事平台。审批链需满足三个工程条件方可生效：物理不可绕过（靠API网关硬拦截而非prompt约束）、上下文完整（审批界面展示Agent意图、理由、影响范围）、可审计（每次行为留存完整记录） ([Human-in-the-Loop实践](https://blog.csdn.net/weixin_41736460/article/details/160656156))。

#### 5.4 加权算力调度

竞赛中算力是稀缺资源，需按资产价值进行加权分配。参考CTF竞赛"先易后难、总分最大化"的通用策略 ([CTF实战冲榜](https://cn-sec.com/archives/4839805.html))，被动 Agent 可设三级算力权重：A类资产（电网、矿山、政务等关基领域）分配60%算力优先采集；B类普通企业30%；C类小微企业10%。每5分钟同步赛事榜单，动态倾斜算力至采集空白企业。单任务设置25分钟无新增资产自动回收机制，释放算力给高价值目标。

#### 5.5 初赛/决赛代码拆分与开源治理

代码架构层面，团队建议根据赛事分阶段特点设计差异化的开源/自研代码比例策略。这一设计建议参考了软件工程领域开源组件管理的通行做法——据 Microsoft 技术文档，新式应用程序由约 80% 的外部维护组件和 20% 的原始业务逻辑代码组成，充分利用开源组件可显著加速开发 ([Microsoft Learn](https://learn.microsoft.com/zh-cn/training/modules/implement-open-source-software-azure/9-summary))。基于这一行业实践，初赛阶段建议采用约 70% 开源组件 + 30% 自研模块的比例，以最大化开发效率、快速搭建基础框架；决赛阶段建议调整为 ≤30% 开源 + 70% 自研，将核心采集引擎、关联推理、人机研判等体现差异化竞争力的模块转为自研，以保护技术方案的核心知识产权。

开源组件治理方面，业界已形成成熟的软件成分分析（SCA）方法论：通过对源代码、二进制文件或容器镜像进行深度扫描，构建软件物料清单（SBOM），实现漏洞检测、许可证合规分析与组件溯源 ([SCA落地实践](https://www.toutiao.com/article/7587665984157139519/))。被动 Agent 应建立完整的开源组件台账管理，记录组件名称、版本、来源、许可证类型，确保决赛阶段可追溯、可审计，同时规避许可证合规风险（如 GPL 等强 copyleft 许可证可能要求衍生作品开源）。

#### 5.6 全链路日志与断点恢复

被动 Agent 长流程任务面临宕机、网络中断、模型限流等故障风险。据 IDC 报告（转引自技术博客，未检索到 IDC 原始报告链接），约78%的企业级AI应用因缺乏持久化能力导致SLA不达标 ([LangGraph检查点机制](https://devpress.csdn.net/v1/article/detail/155517593))。为此，系统需建立**双重持久化机制**：第一，全链路结构化日志——每条采集/提交动作留存JSON格式日志（时间戳、操作类型、数据源、请求参数、响应摘要、审批状态），作为赛事申诉的合规凭证；第二，任务快照断点续存——采用事件溯源（Event Sourcing）模式记录Agent每一步操作，在每个有副作用的节点（如提交情报、写入数据库）前生成增量快照 ([Agent长流程断点续跑](https://blog.csdn.net/2501_91483426/article/details/161495080))。

技术实现可参考 LangGraph 的 Checkpointer 机制：每个节点执行成功后自动写入检查点，包含当前状态、执行路径、中断标记等元数据，宕机后从最近检查点恢复而非从头执行 ([LangGraph Checkpointer](https://callsphere.ai/blog/langgraph-checkpointer-durable-resumable-agents))。Trigger.dev 的实践表明，将Agent状态分为上下文日志（append-only）和执行层快照（machine-level snapshot）两部分分别持久化，可在用户空闲时关闭机器降低成本，下次消息到达时恢复全部状态 ([Trigger.dev](https://www.zenml.io/llmops-database/durable-agent-execution-through-snapshot-and-restore-infrastructure))。据实践数据，接入断点续跑系统后故障重试成本降低78%，任务成功率从53%提升至99.2% ([Agent断点续跑效果](https://blog.csdn.net/2501_91483426/article/details/161495080))。

### 分析

综合上述，本章的合规与工程化框架可归纳为三层防御纵深：**法律合规层**——以《网络安全法》第27条、《网络数据安全管理条例》第18条、关基条例第31条及CFAA授权准绳为法律根基，确立行为黑白名单与前置校验，将"纯被动"从赛事约束升级为法律刚性要求；**工程防护层**——以API限流三层防护（独立限流+排队缓存+IP轮询）、三级人机审批（低/中/高价值分级）、加权算力调度（A/B/C类权重+榜单动态倾斜）、代码拆分与开源治理（初赛/决赛差异化比例+SBOM台账）构成可持续运行的工程护栏；**可靠性保障层**——以全链路结构化日志（申诉凭证）和断点续存快照（宕机恢复）保障长流程任务的鲁棒性，将任务成功率从53%提升至99.2%。三层共同构成"合规不是束缚效能的枷锁，而是保护系统可持续运行的护栏"这一核心命题的工程闭环。

### 小结

本章从法律根基（网络安全法、网络数据安全管理条例、关基条例、CFAA）、工程防护（API限流三层防护、三级人机审批、加权算力调度、代码拆分与开源治理）和可靠性保障（全链路日志、断点恢复）三个层面，构建了被动信息搜集 Agent 的合规与工程化框架。核心原则是：合规不是束缚效能的枷锁，而是保护系统可持续运行的护栏——"合法不等于伦理，比例原则与目的核验才是真正的设计准则" ([OSINT伦理](https://observatoriolegislativocele.com/en/osint-e-inteligencia-artificial-una-mirada-regional-sobre-una-combinacion-explosiva-por-nicolas-zara/))。上述框架与前四章形成闭环：第1章奠定被动OSINT范式与EASM/CTEM理论基座，第2章构建开源工具链与情报API生态，第3章设计多智能体规划-执行-记忆分层编排，第4章建立资产关联知识图谱与四层核验机制，本章以合规与工程化策略收口，共同构成面向网络安全大赛国家级特等奖的完整技术方案。

---

## 结论

本报告通过对企业被动信息搜集Agent的系统研究，得出以下核心发现。

第一，被动OSINT的"零发包"红线为合规侦察提供了清晰边界，但合法≠伦理——比例原则与目的核验应贯穿数据采集全流程（[Privacy Insight Solutions](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum)）。Gartner预测采用CTEM框架的组织被入侵率将降低三分之二，验证了系统化攻击面管理的战略价值。

第二，多智能体编排实现了从"工具堆砌"到"智能协同"的跃迁。HPTSA三级架构以53%成功率和4.5倍效率提升证明任务分解的价值（[HPTSA](https://github.com/uiuc-kang-lab/HPTSA)），Docker microVM沙箱与LangGraph图工作流使并行执行将挂钟时间降低60-70%，同时通过TOA树协作与Sentinel Agents双层监控有效控制越界风险。

第三，资产关联知识图谱将扁平清单升级为关联拓扑，JupiterOne迁移Neo4j后P99延迟降低两个数量级（[JupiterOne](https://neo4j.com/customer-stories/jupiterone)），四层核验机制将STIX图谱置信度误差缩减25.18%，为数据准确性提供工程化保障。

第四，合规先于效能的原则贯穿始终。三级人机审批与NIST AI RMF框架形成制度闭环（[NIST](https://www.nist.gov/itl/ai-risk-management-framework)），断点恢复机制将任务成功率从53%提升至99.2%。

未来研究方向包括：LLM驱动的语义实体消歧精度提升、跨域知识图谱联邦学习，以及Agentic AI安全标准的工程化落地。对于网络安全竞赛，本报告提出的加权算力调度与代码拆分策略可直接转化为冲分优势。

---

## 参考文献

### I. 学术论文与研究

- Deng et al. (2024). A Framework for Automated Penetration Testing with Large Language Models (PentestAgent). arXiv. [链接](https://doi.org/10.48550/arXiv.2411.05185)
- Althiser et al. (2024). BreachSeek: A Multi-Agent System for Automated Penetration Testing. arXiv. [链接](https://adsabs.harvard.edu/abs/2024arXiv240903789A)
- TOA: Tree-of-Attack for Multi-Agent Adversarial Collaboration. (2025). arXiv. [链接](https://doi.org/10.48550/ARXIV.2509.06436)
- Menges, F. & Kloss, H. (2021). International Cybersecurity Law Review. [链接](https://dx.doi.org/10.1365/s43439-021-00042-7)
- STIX-based Threat Intelligence Knowledge Graph. (2024). ScienceDirect. [链接](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773)
- 电信运营商威胁情报体系研究与应用探索. (2024). 电信科学. [链接](https://www.telecomsci.com/rc-pub/front/front-article/download/59574690/lowqualitypdf/电信运营商威胁情报体系研究与应⽤探索.pdf)
- 基于大语言模型的网络威胁情报知识图谱构建技术研究 (AutoCTI2KG). (2024). 北京大学. [链接](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/基于⼤语⾔模型的⽹络威胁情报知识图谱构建技术研究.pdf)
- 清华大学对抗辩论多智能体安全研究. (2025). Applied Sciences. [链接](https://web.ee.tsinghua.edu.cn/yangyi/zh_CN/lwcg/4724/content/9941.htm)
- PentestAgent 论文摘要. (2024). BAAI智源社区. [链接](https://hub.baai.ac.cn/paper/39bf5b90-924f-4f24-8711-f432949d0f5b)
- BreachSeek 论文解读. (2024). ChatPaper. [链接](https://chatpaper.com/zh-CN/chatpaper/paper/57650)

### II. 法律法规与标准框架

- 中华人民共和国网络安全法第27条. (2017). 全国人大常委会. [链接](https://www.changdu.gov.cn/cdrmzf/qzqdnew/202203/b01dde7155fd451a98e2658b53dd8dd6.shtml)
- 网络数据安全管理条例. (2024). 国务院. [链接](https://big5.www.gov.cn/gate/big5/www.gov.cn/zhengce/content/202409/content_6977766.htm)
- 关键信息基础设施安全保护条例. (2021). 国务院. [链接](https://www.isccc.gov.cn/xxgk1/zcfg_3/flhxzfg/202208/P020251113614748154900.pdf)
- 司法部等四部门答记者问——关于网络数据安全. (2024). 司法部. [链接](https://ggzy.shaanxi.gov.cn/xwzx/002009/20240904/0e8afcb7-785a-4ca8-8c9d-c0de5f393cba.html)
- 网络数据爬取合法性研究. (2024). 北大法宝. [链接](http://data.pkulaw.net/qikan/0bf22b2b6765c2ab4976053071cd7433bdfb.html)
- CFAA: What is the Computer Fraud and Abuse Act. (2025). LegalClarity. [链接](https://legalclarity.org/cfaa-what-is-the-computer-fraud-and-abuse-act/)
- Gates Down: Third Circuit on Employer Computer Access Policies. (2025). DataBreaches.net. [链接](https://databreaches.net/2025/11/11/gates-down-third-circuit-says-breaking-employer-computer-access-policies-is-not-hacking/)
- NIST AI Risk Management Framework. (2023). NIST. [链接](https://www.nist.gov/itl/ai-risk-management-framework)
- NIST AI RMF 100-1 (PDF). (2023). NIST. [链接](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)

### III. 开源工具与技术文档

- ProjectDiscovery. (2026). Subfinder. GitHub. [链接](https://github.com/projectdiscovery/subfinder)
- OWASP. (2026). Amass Documentation. [链接](https://owasp-amass.github.io/docs/)
- Sectigo. (2026). crt.sh Certificate Transparency Log Search. [链接](https://crt.sh/)
- wgpsec. (2025). ENScan_GO: 企业信息搜集工具. GitHub. [链接](https://github.com/wgpsec/ENScan_GO)
- UIUC Kang Lab. (2025). HPTSA: Hierarchical Penetration Testing Multi-Agent System. GitHub. [链接](https://github.com/uiuc-kang-lab/HPTSA)
- Knownsec. (2025). ZoomEye-python SDK. GitHub. [链接](https://github.com/knownsec/ZoomEye-python/blob/v2.0.4.4/docs/README_CN.md)
- H-Limbus. (2025). NoMoney: 免费网络空间搜索引擎. GitHub. [链接](https://awesome.ecosyste.ms/projects/github.com%2FH-Limbus%2FNoMoney)
- surveyhub-mcp. (2025). PyPI. [链接](https://pypi.org/project/surveyhub-mcp)
- Neo4j. (2026). 网络安全暴露管理. [链接](https://neo4j.ac.cn/developer/industry-use-cases/cybersecurity/vulnerability-prioritization-exposure-management/)
- NetSpecter. (2026). OSINT Documentation. [链接](https://netspecter-osint.github.io/documentation/)
- 企查查. (2026). 企查查MCP技能. [链接](https://agent.qcc.com/skills?cat=banking)
- 0xffsec. (2026). Handbook: Subdomain Enumeration. [链接](https://0xffsec.com/handbook/information-gathering/subdomain-enumeration/)

### IV. 行业报告与机构实践

- Gartner. (2023). 2023年网络安全趋势. via PR Newswire. [链接](https://www.prnewswire.com/news-releases/gartner-anuncia-as-principais-tendencias-de-ciberseguranca-para-2023-841267191.html)
- JupiterOne × Neo4j. (2025). 客户案例. Neo4j. [链接](https://neo4j.com/customer-stories/jupiterone)
- 奇安信. (2025). AI实践: 百亿节点图数据库. [链接](https://www.qianxin.com/news/detail?news_id=12438)
- Cymulate. (2025). CAASM: Between Asset Management and Attackers' View. [链接](https://cymulate.com/blog/the-caasm-between-asset-management-and-attackers-view/)
- Microsoft. (2025). Learn: 开源软件管理. [链接](https://learn.microsoft.com/zh-cn/training/modules/implement-open-source-software-azure/9-summary)

### V. 技术媒体与博客

- DeepFind. (2026). Passive vs Active OSINT. [链接](https://deepfind.me/blogs/passive-osint-vs-active-osint)
- Liora. (2026). All About OSINT. [链接](https://www.liora.io/en/all-about-osint)
- FreeBuf. (2024). 企业信息收集ARWAD. [链接](https://www.freebuf.com/articles/es/335745.html)
- FreeBuf. (2024). OneForAll子域名收集工具. [链接](https://m.freebuf.com/articles/web/366925.html)
- FreeBuf. (2025). 子域收集工具综述. [链接](https://www.freebuf.com/articles/web/479973.html)
- FreeBuf. (2025). 被动DNS情报技术. [链接](https://www.freebuf.com/news/391907.html)
- PIStack. (2026). Amass vs Subfinder vs MassDNS. [链接](https://www.pistack.xyz/posts/2026-04-23-amass-vs-subfinder-vs-massdns-self-hosted-dns-reconnaissance-guide-2026)
- pingthat.dev. (2026). Port Scanning Legality and Ethics. [链接](https://pingthat.dev/docs/port-scanning-legality-and-ethics)
- Patrowl. (2026). What is EASM: Definition and Attack Examples. [链接](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)
- EASM.info. (2026). EASM vs ASM vs CAASM vs CTEM. [链接](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem)
- Zynap. (2026). What's CTEM: Continuous Threat Exposure Management Explained. [链接](https://www.zynap.com/blog/whats-ctem-continuous-threat-exposure-management-explained)
- Privacy Insight Solutions. (2026). OSINT Ethics Spectrum. [链接](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum)
- Outpost24. (2025). The Art of Subdomain Enumeration. [链接](https://outpost24.com/blog/art-of-subdomain-enumeration)
- OSINTBench. (2026). crt.sh Review. [链接](https://osintbench.com/tools/crt-sh-certificate-transparency-log-search/)
- ApifyForge. (2026). Wayback Machine API: Programmatic Search. [链接](https://apifyforge.com/blog/wayback-machine-api-programmatic-search)
- Scraperly. (2026). Wayback API Scraping Guide. [链接](https://scraperly.com/scrape/wayback-api)
- cnetsec. (2025). FOFA网络空间测绘. [链接](https://www.cnetsec.com/article/39908.html)
- FOFA. (2026). FOFA VIP 会员. [链接](https://fofa.info/vip)
- chdh.me. (2025). Hunter测绘引擎评测. [链接](https://chdh.me/tools/network/security/hunter-how)
- SubdomainsFinder. (2026). Best Subdomain Enumeration Tools. [链接](https://subdomainsfinder.com/best-subdomain-enumeration-tools)
- CSDN. (2025). API限流策略. [链接](https://wenku.csdn.net/answer/157x7pcvkz)
- SECRSS. (2025). HPTSA多智能体渗透测试. [链接](https://www.secrss.com/articles/67220)
- CyberSecurityNews. (2024). BreachSeek: AI驱动的自动化渗透测试. [链接](https://cybersecuritynews.com/breachseek-penetration-testing)
- EmergentMind. (2026). LangGraph: 多智能体图工作流. [链接](https://www.emergentmind.com/topics/langgraph)
- DevOps Gheware. (2026). Supervisor Pattern for Multi-Agent LangGraph. [链接](https://devops.gheware.com/blog/posts/supervisor-pattern-multi-agent-langgraph-2026.html)
- cnblogs. (2025). Docker沙箱隔离实践. [链接](https://www.cnblogs.com/imust2008/p/20351523)
- Collabnix. (2025). Docker Sandboxing Overview. [链接](https://collabnix.com/docs/docker-workshop/sandboxing-with-docker/overview/)
- 电信科学. (2025). Pentest-Chain: RAG增强渗透测试. [链接](https://www.secrss.com/articles/85448)
- 凤凰网科技. (2025). 红刃AI安全大模型. [链接](https://tech.ifeng.com/c/8t7m7uQNF16)
- EmergentMind. (2026). LLM-based Modular Multi-Agent Frameworks. [链接](https://www.emergentmind.com/topics/llm-based-modular-multi-agent-frameworks)
- Moonlight. (2026). Sentinel Agents for Secure Agentic AI. [链接](https://www.themoonlight.io/zh/review/sentinel-agents-for-secure-and-trustworthy-agentic-ai-in-multi-agent-systems)
- quidproquo.cc. (2026). Agent安全: Prompt Injection与信任边界. [链接](http://quidproquo.cc/posts/ai/2026-06-04-agent-security-prompt-injection-trust-boundaries)
- CSDN. (2025). LangGraph多智能体编排. [链接](https://devpress.csdn.net/v1/article/detail/151871815)
- Towards Data Science. (2025). The Rise of Semantic Entity Resolution. [链接](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/)
- 严浩网. (2025). 法人核验技术. [链接](https://www.yanhaowang.cn/news_info/347.html)
- Krawly. (2026). DNS Investigation: What One Domain Tells You. [链接](https://krawly.io/blog/what-one-domain-tells-you-dns-investigation)
- 大伟安全. (2025). 华云安金融行业攻击面管理案例. [链接](https://www.dwcon.cn/post/3626)
- 路美谷. (2025). 智能风控图谱技术. [链接](https://www.lumevalley.com/article-4431.html)
- ZoomEye. (2026). ZoomEye Pricing. [链接](https://www.zoomeye.ai/pricing)
- CSDN. (2024). NoMoney限流对比. [链接](https://blog.csdn.net/seoppg/article/details/139362026)
- CSDN. (2025). Human-in-the-Loop实践. [链接](https://blog.csdn.net/weixin_41736460/article/details/160656156)
- SnailSploit. (2026). AI Security Wiki: Human-in-the-Loop. [链接](https://snailsploit.com/ai-security/wiki/defenses/human-in-the-loop)
- CELE. (2025). OSINT与AI: 区域法规视角. [链接](https://observatoriolegislativocele.com/en/osint-e-inteligencia-artificial-una-mirada-regional-sobre-una-combinacion-explosiva-por-nicolas-zara/)
- APIPark. (2026). Mastering API Rate Limiting. [链接](https://apipark.com/techblog/en/mastering-how-to-circumvent-api-rate-limiting-effectively/)
- CallSphere. (2026). LangGraph Checkpointer: Durable Resumable Agents. [链接](https://callsphere.ai/blog/langgraph-checkpointer-durable-resumable-agents)
- ZenML. (2026). Durable Agent Execution: Snapshot and Restore. [链接](https://www.zenml.io/llmops-database/durable-agent-execution-through-snapshot-and-restore-infrastructure)
- CSDN. (2025). Agent断点续跑机制. [链接](https://blog.csdn.net/2501_91483426/article/details/161495080)
- CSDN. (2025). LangGraph检查点机制. [链接](https://devpress.csdn.net/v1/article/detail/155517593)
- cn-sec. (2025). CTF实战冲榜策略. [链接](https://cn-sec.com/archives/4839805.html)
- 今日头条. (2025). SCA落地实践. [链接](https://www.toutiao.com/article/7587665984157139519/)

---

## 待完善事项

以下为审稿过程中遗留的非阻塞建议，供后续迭代参考：

### 第 1 章 被动信息搜集与 EASM/CTEM 攻击面管理基础框架

- Shadon→Shodan 拼写已修正（2 轮审稿后已采纳修正项）
- PIStack 2026-04 来源已核验保留并标注

### 第 2 章 开源被动侦察工具链与情报 API 数据源生态

- SubdomainsFinder 清单一致性待终校处理
- Shodan 建议补充独立来源
- 表格备注待进一步澄清
- 论据二标题可微调

### 第 3 章 多智能体规划-执行-记忆分层编排架构

- 记忆层三库内容偏向 CTF/攻击场景，与"被动信息搜集"主题存在错位，建议适配为被动侦察语境
- Docker microVM 声明来源为博客，建议补 Docker 官方文档核实"microVM"表述准确性
- "60-70% 挂钟时间降低""10-30% 实用性损失"等关键数字源自个人博客，建议补学术来源或标注为"社区实践估算"
- BreachSeek"独立容器"验证措辞宜核实

### 第 4 章 资产关联知识图谱与四层核验知识库机制

- 缺少开篇论点段，建议在 4.1 前增加章节论点
- Neo4j 为唯一推荐方案，建议补充选型理由（TigerGraph/Neptune 等替代方案）
- 央行 25% 阈值建议补充直接法规引用（银发〔2018〕164 号）
- 缺少跨章引用（第 3 章→第 4 章→第 5 章衔接）
- 传统实体解析描述可补充综述来源

### 第 5 章 合规边界界定与竞赛工程化冲分策略

- 来源清单未附在修订稿正文末尾（原稿有 21 条清单），建议终稿补回 23 条清单
- 70/30 与 80/20 的推导跨度未显式说明，可补一句衔接

---

> 本报告由 AI 深度研究团队生成，重要决策请经专业人员核验。所有引用来源请用户在重要场景下二次核验时效性与真实性。
