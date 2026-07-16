# 第 1 章 被动信息搜集与 EASM/CTEM 攻击面管理基础框架

## 论点
企业被动信息搜集（Passive OSINT）以"不与目标系统交互"为本质特征，是构建外部攻击面认知的合规默认范式；外部攻击面管理（EASM）作为 Gartner 持续威胁暴露管理（CTEM）框架中"发现阶段"的核心技术执行者，构成了本课题多智能体系统的理论与合规基座。然而，被动/主动边界在情报引擎（如 FOFA、Hunter）的实践中存在模糊地带，须以纯被动硬性约束与"合法≠伦理"的比例原则予以厘清，方能在竞赛场景中建立可辩护、可复现的冲分架构。

## 论据
### 1. 被动 OSINT 的严格定义与特征
被动信息搜集指"情报获取过程不与目标系统、账户或个人发生任何交互"——不发送消息、不发起请求、不触发探测、不在目标侧留下可观测痕迹，分析者纯粹是观察者 ([DeepFind, 2025](https://deepfind.me/blogs/passive-osint-vs-active-osint))。与之相对，主动 OSINT 一旦造成系统响应、日志记录或行为触发，便不再被动 ([Liora, 2024](https://www.liora.io/en/all-about-osint))。在漏洞赏金与 SRC 场景中，该区分被明确表述为：主动指"需跟目标系统、业务直接交互，如爆破子域名、扫描开放端口"，被动指"收集信息不需跟目标交互，如收集开源信息、企查查" ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。
被动侦察的核心价值在于不可见性与低风险：不发生交互即不生成日志，从而规避归因风险（IP、UA、时间戳暴露）、降低法律暴露、并保障证据完整性 ([DeepFind, 2025](https://deepfind.me/blogs/passive-osint-vs-active-osint))。DNS 侦察工具层面差异同样清晰：Subfinder 纯被动，"并行查询数十个被动数据源发现子域，不向目标发送任何 DNS 查询"，而 MassDNS 属主动暴力破解，向解析器发送实际查询（[PIStack, 2026-04](https://www.pistack.xyz/posts/2026-04-23-amass-vs-subfinder-vs-massdns-self-hosted-dns-reconnaissance-guide-2026)；该指南发布于 2026 年 4 月 23 日，已于本稿修订时实际打开核验可访问，内容为 Amass/Subfinder/MassDNS 被动—主动模式对比，故保留此引用）。
从合规与法律风险维度看，主动与被动侦察的分野更具实质意义。主动侦察（端口扫描、子域爆破、漏洞探测）会向目标发送数据包并触发其侧日志记录，一旦超出授权边界即可能触碰《网络安全法》第二十七条关于"不得从事非法侵入他人网络、干扰网络功能"的禁止性规定；就关键信息基础设施而言，配套法规进一步明确未经运营者或保护工作部门授权，任何个人和组织不得实施漏洞探测、渗透性测试等可能影响其安全的活动 ([司法部等四部门答记者问, 2024](https://ggzy.shaanxi.gov.cn/xwzx/002009/20240904/0e8afcb7-785a-4ca8-8c9d-c0de5f393cba.html))。在通用法域下，合法性测试以"授权"（authorization）而非"意图"为准绳——对第三方资产未经许可的扫描普遍被计算机犯罪法条（如美国 CFAA）认定为未授权访问的前置行为 ([pingthat.dev, n.d.](https://pingthat.dev/docs/port-scanning-legality-and-ethics))。相较之下，被动搜集因零交互、零日志，天然规避了上述可归因风险与授权边界争议，进一步凸显其作为竞赛默认合规范式的优势。

### 2. EASM 定义及其作为 CTEM "发现阶段"核心
EASM 被定义为"持续发现、映射、监控并削减组织所有面向互联网资产（包括其自身未知资产）的过程" ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。Gartner 将其界定为"用于发现企业互联网资产及关联暴露（含错误配置的公云基础设施）以优先级处置潜在风险的过程、技术与托管服务" ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。EASM 自外向内、无代理、无需凭据与内网访问，正契合纯被动的数据采集逻辑 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。
EASM 之所以是 CTEM 的基石，在于它是"发现阶段"不可缺失的输入。Gartner 于 2022 年提出 CTEM 五阶段循环：范围界定、发现、优先级、验证、动员 ([Zynap, 2024](https://www.zynap.com/blog/whats-ctem-continuous-threat-exposure-management-explained))；Gartner 亦将 CTEM 列入 2023 年顶级战略技术趋势，并预测到 2026 年依 CTEM 计划确定安全投资优先级的组织遭受入侵的可能性将降低约三分之二 ([Gartner via PR Newswire, 2022](https://www.prnewswire.com/news-releases/gartner-anuncia-as-principais-tendencias-de-ciberseguranca-para-2023-841267191.html))。权威资料指出，"EASM 是 CTEM 最关键输入之一；若无外部发现，CTEM 的发现阶段将存在巨大盲区" ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。
数据印证了被动外部发现的必要性：76% 的组织曾遭受源自未知或未管理资产的攻击（Enterprise Strategy Group, 2024，转引自 [Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)）；采用 EASM 后平均可多发现 35% 的互联网暴露资产（Security Magazine, 2023，转引自 [Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples)）；Gartner 估计 80–95% 的组织资产每年都会变更 ([Patrowl, 2024](https://patrowl.io/en/actualites/what-is-easm-definition-attack-examples))。

### 3. 概念辨析：EASM vs ASM vs CAASM vs CTEM
四者并非竞争产品，而是成熟安全项目的分层能力 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))：ASM 是总称；EASM 专注互联网暴露资产；CAASM 自内向外聚合内部工具数据但"不发现未知外部资产"；CTEM 是过程框架。值得注意的是，多数标称"ASM 平台"的产品实际交付的是 EASM 能力 ([EASM.info, 2024](https://easm.info/easm-vs-asm-vs-caasm-vs-ctem))。对本课题而言，以纯被动方式采集资产本质上是在执行 EASM 而非需内网代理的 CAASM。

### 4. 被动/主动边界的争议焦点：以 FOFA/Hunter 为例
争议源于"查询既已测绘的数据"与"主动探测"的混淆。以 FOFA、ZoomEye、Shodan、Censys 为代表的测绘搜索引擎，其底层引擎通过主动全网扫描构建数十亿级资产数据库 ([cnetsec, 2023](https://www.cnetsec.com/article/39908.html))；用户对其发起检索时，是在查询既已存在、已被厂商测绘的数据库，并未向目标发包——此检索行为属被动。然而，同一引擎若启用"主动探测/爆破"模式便向目标系统发送数据包、触发日志，触碰纯被动红线 ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。同样，DNS 工具链中 MassDNS 的暴力破解属主动，而 Subfinder 的纯被动枚举不向目标发包。本课题据此确立纯被动硬性约束：仅使用情报 API 与公开数据库在限流下检索已测绘资产，严格禁止端口扫描、TCP 发包、子域爆破等一切主动探测动作。

### 5. 合规与伦理：合法≠伦理与竞赛被动优先策略
被动搜集不等于无约束。核心命题是"合法≠伦理"：公开数据可合法获取，但跨源画像与个人信息的过度关联仍须受比例原则与目的核验约束 ([Privacy Insight Solutions, n.d.](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum))。该框架提炼两大可迁移原则——相称性：调查深度须匹配正当利益；目的验证：涉及私人个体前须确立并记录主体、理由与法律基础 ([Privacy Insight Solutions, n.d.](https://privacyinsightsolutions.com/blog/osint-ethics-spectrum))。学术界亦明确指出，"技术上可行之事并非伦理上可证成"（"not everything that is technically possible is also moral"），且针对自然人的 OSINT 因涉及个人数据处理，其法律地位在多数法域下本就不确定、须受更严格约束 ([Menges & Kloss, International Cybersecurity Law Review, 2021](https://dx.doi.org/10.1365/s43439-021-00042-7))。在赛事场景下，被动优先策略具双重正当性：被动 OSINT"合法、伦理且通常足够有效" ([Liora, 2024](https://www.liora.io/en/all-about-osint))；ARWAD 等侦察路线图亦明确将企查查、Wayback、开源情报检索归入被动分支 ([FreeBuf, 2022](https://www.freebuf.com/articles/es/335745.html))。竞赛冲分应以"纯被动数据源 + 比例原则 + 目的核验"为工程基线，在资产关联过程中对个人敏感信息执行最小化与脱敏。

## 分析
综合上述，本课题的理论坐标可归纳为三层：范式层——被动 OSINT 是不可见、低归因风险的数据采集默认范式；框架层——EASM 以自外向内、无代理方式支撑 CTEM 发现阶段，是约三分之一隐性攻击面（对应 35% 额外资产发现，见第 2 节）的唯一可见化路径；约束层——情报引擎的"查询既测绘数据"被动、但其"主动探测"越界，须以纯被动硬性约束锁死技术路线，并以"合法≠伦理"的比例原则约束跨源关联。三层共同构成后续多智能体架构的合规基座。

## 小结
本章厘清了被动信息搜集与 EASM/CTEM 基础框架：被动 OSINT 以零交互、零痕迹为特征；EASM 作为 CTEM 发现阶段核心技术执行者，凭 76% 未知资产入侵与 35% 额外资产发现的实证数据确立外部发现必要性；概念辨析揭示多数"ASM"实为 EASM；FOFA/Hunter 被动查询/主动探测二元性引出纯被动硬性约束；合法与伦理分离要求以比例原则与目的核验收口跨源关联。上述框架为后续章节奠定理论与合规前提。
