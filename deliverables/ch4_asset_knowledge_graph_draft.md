## 第 4 章：资产关联知识图谱与四层核验知识库机制

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

**④ 多源交叉验证层**：同一情报须至少两个独立数据源相互佐证方可入库。电信运营商威胁情报体系研究明确指出，不同来源情报在字段定义与威胁定级上常存在冲突，必须经过数据归一化、去噪与融合处理，并建立科学的信誉分析机制判定情报可信度（[电信运营商威胁情报体系研究](https://www.telecomsci.com/rc-pub/front/front-article/download/59574690/lowqualitypdf/%E7%94%B5%E4%BF%A1%E8%BF%90%E8%90%A5%E5%95%86%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E4%BD%93%E7%B3%BB%E7%A0%94%E7%A9%B6%E4%B8%8E%E5%BA%94%E7%94%A8%E6%8E%A2%E7%B4%A2.pdf)）。学术研究亦验证了基于 STIX 图谱的多源 IoC 聚合可显著提升置信度评分精度，实现 25.18% 的置信度误差缩减（[ScienceDirect: STIX 图谱优化 IoC 质量](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773)）。华云安在某全国性股份制银行的实践中，采用**基于置信度评价的多源风险数据融合**，对漏洞、弱口令、暗网监测等多维攻击面数据进行交叉验证，显著提升了数据降噪效能（[华云安金融攻击面管理案例](https://www.dwcon.cn/post/3626)）。

### 4.4 股权穿透与交叉核验

企查查 MCP 平台为工商主体匹配与股权穿透提供了标准化的原子能力。其银行客群 SKILL 集包含 KYB 企业核验（主体真实性核验、34 类司法与经营风险扫描）、股权结构穿透分析（自动完成多层股权穿透并生成可视化结构图、识别实际控制人与隐性关联关系）、受益所有人识别（按央行 25% 阈值穿透股权链路、锁定最终受益人）等核心工具，3 分钟即可输出符合 FATF 标准的合规报告（[企查查智能体数据平台](https://agent.qcc.com/skills?cat=banking)）。

从技术原理看，股权穿透本质是在企业关联图谱上执行递归穿透算法（Recursive Penetration Algorithm）：系统首先运用实体对齐与消歧技术融合外部工商投资关系数据与内部 CRM 数据，构建包含数亿节点与数十亿条边的企业关联网络；随后在图谱中展开多跳路径搜索，沿持股路径逐层相乘并汇总股份比例，穿透多层企业嵌套与交叉持股，精确定位最终实际控制人（[智能风控: AI 实时合规图谱](https://www.lumevalley.com/article-4431.html)）。这一图技术突破了传统关系型数据库的查询极限，使全量子公司、分公司主体的批量发现成为可能——这正是被动资产搜集所需的"由主体辐射资产"能力。

### 4.5 测绘经验库与知识复用

知识图谱的另一价值在于持续迭代与经验复用。北京大学研究团队提出的 AutoCTI2KG 框架，通过大语言模型的指令提示与上下文学习，自动从威胁情报中生成网络安全知识图谱，F1 值达 0.90 左右，展示了 LLM 在安全知识图谱持续构建中的潜力（[基于大语言模型的网络威胁情报知识图谱构建](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E8%AF%AD%E8%A8%80%E6%A8%A1%E5%9E%8B%E7%9A%84%E7%BD%91%E7%BB%9C%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E6%9E%84%E5%BB%BA%E6%8A%80%E6%9C%AF%E7%A0%94%E7%A9%B6.pdf)）。奇安信已构建百亿节点规模的图数据库，通过子图提取、图嵌入与图神经网络训练，输出疑似恶意节点推荐，形成稳定的情报运营闭环流程（[奇安信 AI 驱动网络安全实践](https://www.qianxin.com/news/detail?news_id=12438)）。

在本系统中，同类企业（如同行业、同规模）的采集策略、命名规律与资产分布模式可沉淀为"测绘经验库"：当面对新目标企业时，系统优先复用经验库中匹配的采集模板与过滤规则，显著缩短冷启动时间。知识图谱随每次采集任务持续补充新节点与新关系，经验库随之迭代优化，形成"采集—核验—沉淀—复用"的正向循环。

### 关键发现

- **图数据库性能优势获工业验证**：JupiterOne 迁移 Neo4j 后 P99 延迟降两个数量级、管线成本降 90%+，多跳遍历能力是关系型库无法企及的（[JupiterOne](https://neo4j.com/customer-stories/jupiterone)）
- **语义实体消歧实现跨源自动归并**：LLM 可在单次 prompt 中完成数十条记录匹配合并，字段描述引导模式自动对齐（[TDS](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/)）
- **四层核验全程无主动发包**：DNS 被动解析 + 证书透明度 + 工商匹配 + 多源交叉，兼顾合规性与准确性（[NetSpecter](https://netspecter-osint.github.io/documentation/)、[华云安](https://www.dwcon.cn/post/3626)）
- **股权穿透本质为图谱递归算法**：企查查 MCP 提供标准化原子能力，图技术突破关系型库查询极限（[智能风控图谱](https://www.lumevalley.com/article-4431.html)、[企查查 MCP](https://agent.qcc.com/skills?cat=banking)）
- **LLM 赋能知识图谱持续迭代**：AutoCTI2KG 框架 F1 达 0.90，支持经验复用与自动补全（[北京大学研究](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E8%AF%AD%E8%A8%80%E6%A8%A1%E5%9E%8B%E7%9A%84%E7%BD%91%E7%BB%9C%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E6%9E%84%E5%BB%BA%E6%8A%80%E6%9C%AF%E7%A0%94%E7%A9%B6.pdf)）

### 数据摘要

| 指标 | 数据 | 来源 |
|------|------|------|
| JupiterOne P99 延迟改善 | 降两个数量级（→180ms） | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 数据管线成本降低 | >90% | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 数据摄取时间 | 8 小时 → ~10 秒 | [JupiterOne × Neo4j](https://neo4j.com/customer-stories/jupiterone) |
| 语义实体解析单批记录 | 39 条/prompt，0 错误 | [TDS](https://towardsdatascience.com/the-rise-of-semantic-entity-resolution/) |
| STIX 图谱置信度误差缩减 | 25.18% | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773) |
| AutoCTI2KG 知识图谱构建 F1 | ~0.90 | [北京大学](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E8%AF%AD%E8%A8%80%E6%A8%A1%E5%9E%8B%E7%9A%84%E7%BD%91%E7%BB%9C%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E6%9E%84%E5%BB%BA%E6%8A%80%E6%9C%AF%E7%A0%94%E7%A9%B6.pdf) |
| 企查查 KYB 核验报告输出 | 3 分钟 | [企查查 MCP](https://agent.qcc.com/skills?cat=banking) |

---

## 本章新增来源清单（13条）
1. [NetSpecter: 开源被动 OSINT 侦察工具文档](https://netspecter-osint.github.io/documentation/) — 被动侦察定义与原则：仅查询公共 DNS/CT/WHOIS，不直接交互目标系统
2. [FreeBuf: 如何利用被动 DNS(Passive DNS)加强网络安全](https://www.freebuf.com/news/391907.html) — 被动 DNS 数据库（DNSDB 等）的采集原理与时间维度的存活分析价值
3. [Krawly: What One Domain Can Tell You — DNS Investigation Walkthrough](https://krawly.io/blog/what-one-domain-tells-you-dns-investigation) — 证书透明度日志揭示过期/废弃子域证书，时间过滤依据
4. [电信运营商威胁情报体系研究与应用探索](https://www.telecomsci.com/rc-pub/front/front-article/download/59574690/lowqualitypdf/%E7%94%B5%E4%BF%A1%E8%BF%90%E8%90%A5%E5%95%86%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E4%BD%93%E7%B3%BB%E7%A0%94%E7%A9%B6%E4%B8%8E%E5%BA%94%E7%94%A8%E6%8E%A2%E7%B4%A2.pdf) — 多源情报融合评估机制：归一化/去噪/融合与情报信誉分析
5. [ScienceDirect: Improving quality of IoCs using STIX graphs](https://www.sciencedirect.com/science/article/abs/pii/S0167404824002773) — STIX 图谱聚合多源情报，置信度误差缩减 25.18%（学术论文）
6. [华云安: 2024 年中国金融行业网络安全案例集](https://www.dwcon.cn/post/3626) — 基于置信度评价的多源风险数据融合与交叉验证实践（某全国性股份制银行）
7. [FreeBuf: 金融业网络空间资产攻击面管理实践分享](https://www.freebuf.com/articles/system/395463.html) — 知图谱构建攻击面知识工程，僵尸资产/影子资产标记与持续监测
8. [法人核验技术解析: 精准识别企业实控人的技术路径](https://www.yanhaowang.cn/news_info/347.html) — 股权穿透计算、社区发现算法与控制权推理模型，尽调从数天缩至分钟级
9. [智能风控: AI 实时合规图谱行业报告](https://www.lumevalley.com/article-4431.html) — 递归穿透算法原理：多跳路径搜索+逐层股份相乘汇总，数亿节点规模图谱
10. [基于大语言模型的网络威胁情报知识图谱构建技术研究（北京大学）](https://www.joconline.com.cn/rc-pub/front/front-article/download/79661066/lowqualitypdf/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E8%AF%AD%E8%A8%80%E6%A8%A1%E5%9E%8B%E7%9A%84%E7%BD%91%E7%BB%9C%E5%A8%81%E8%83%81%E6%83%85%E6%8A%A5%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E6%9E%84%E5%BB%BA%E6%8A%80%E6%9C%AF%E7%A0%94%E7%A9%B6.pdf) — AutoCTI2KG 框架，LLM 自动生成安全知识图谱，F1≈0.90（学术论文）
11. [奇安信: AI 驱动网络安全运营实践](https://www.qianxin.com/news/detail?news_id=12438) — 百亿节点图数据库+图神经网络推荐恶意节点，稳定情报运营闭环
12. [Cymulate: What is CAASM?](https://cymulate.com/blog/the-caasm-between-asset-management-and-attackers-view/) — CAASM 定义：聚合/归一化/去重多源资产数据，47% 安全专业人员缺乏完整资产可见性
13. [网络安全知识图谱研究综述（国防科技大学）](http://aipub.cn/1A03KP8k) — 网络安全数据多源异构/缺失/噪声/不一致问题，知识图谱统一融合推理特性（学术论文）

> 状态：草稿（Phase 3.1 完成），待审稿
