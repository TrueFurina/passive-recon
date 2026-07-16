# 第 3 章 多智能体规划-执行-记忆分层编排架构

## 论点：以分层编排构建可控的自动化侦察体系

被动信息搜集的核心挑战，是在不触达目标的前提下，将多源数据采集、跨主体股权穿透、盲区动态补缺等复杂流程自动化。单一 LLM Agent 受限于上下文窗口、幻觉风险与越界可能性，难以独立胜任全链路任务。本章主张：借鉴 PentestAgent、BreachSeek、HPTSA 等学术界多智能体安全系统的规划-执行-记忆分层架构，以 LangGraph 图工作流为编排框架，构建"指挥官 Agent（规划）→四大专项采集集群（执行）→三库协同知识库（记忆）"的分层体系，并通过 Docker microVM 沙箱与 Plan-then-Execute 控制流完整性实现架构级越界防控，使被动信息搜集从"工具堆砌"升级为"可审计、可恢复、可扩展的智能体编队"。

## 论据

### 3.1 规划层：LLM 驱动的全局指挥官 Agent

被动信息搜集的第一步是全局规划。指挥官 Agent 以企业全称为输入，自动执行股权穿透拆解关联主体，并为每家主体下发 Web 资产、公众号、小程序三类采集子任务。这一设计借鉴了当前学术界多个里程碑式多智能体安全系统的规划架构。

PentestAgent 提出了基于 LLM 的多代理自动化渗透测试框架，采用侦察、搜索、规划、执行四代理协作架构，利用检索增强生成（RAG）增强代理的上下文记忆与知识检索能力，通过链式思考（CoT）将复杂任务分解为子任务，减少幻觉输出。实验表明，其情报收集阶段平均耗时不到 400 秒且无需人工交互，显著优于 PentestGPT 的 826 秒和 7.4 轮交互 ([PentestAgent, arXiv:2411.05185](https://doi.org/10.48550/arXiv.2411.05185); [BAAI 摘要](https://hub.baai.ac.cn/paper/39bf5b90-924f-4f24-8711-f432949d0f5b))。

HPTSA（分层规划与任务特定代理系统）采用"分层规划代理→团队经理代理→任务特定专家代理"三级架构。规划代理负责探索目标环境、识别攻击面并制定策略；经理代理协调信息共享。在 15 个真实零日漏洞基准测试中，HPTSA 五次尝试成功率达 53%，工作效率提升 4.5 倍以上，且显著优于 ZAP、MetaSploit 等开源扫描器 ([SECRSS HPTSA](https://www.secrss.com/articles/67220); [HPTSA GitHub](https://github.com/uiuc-kang-lab/HPTSA))。

BreachSeek 基于 LangGraph 图工作流实现"监督者→专门代理→评估者"三方协调架构，监督者作为中央协调者生成高层次行动计划并动态调整策略，评估者作为质量检查点校验输出准确性 ([ChatPaper BreachSeek](https://chatpaper.com/zh-CN/chatpaper/paper/57650); [CyberSecurityNews](https://cybersecuritynews.com/breachseek-penetration-testing))。

在本课题的被动信息搜集场景中，指挥官 Agent 核心逻辑为：输入企业全称→调用工商股权 API（如 ENScan_GO）进行股权穿透→拆解 N 家关联主体→为每家主体生成 Web/公众号/小程序三类采集任务清单→实时识别采集盲区并动态补充数据源检索。这一流程映射了 LangGraph 的"Plan-then-Execute"范式——规划节点先生成完整步骤序列并存储于状态中，执行节点仅被限定使用规划中指定的工具，从架构层面防止越权操作 ([LangGraph: Modular LLM Agent Orchestration, EmergentMind](https://www.emergentmind.com/topics/langgraph))。

### 3.2 执行层：四大专项采集集群与 Docker 沙箱隔离

执行层包含四大专项采集 Agent：Web 资产采集 Agent（调用 subfinder/Amass/FOFA）、公众号采集 Agent、小程序采集 Agent、工商股权采集 Agent（调用 ENScan_GO）。各 Agent 独立运行于 Docker 沙箱中，多 Agent 并行执行。

BreachSeek 已验证"专门代理托管于独立容器"的有效性——通过将认知负载分配给专用节点，有效缓解了 LLM 上下文窗口的固有限制 ([BreachSeek arXiv:2409.03789](https://adsabs.harvard.edu/abs/2024arXiv240903789A))。LangGraph 监督者模式进一步表明，并行 worker 执行可将总执行时间从所有分析之和缩减为最长单项耗时，典型场景下降低 60-70% 的挂钟时间 ([Supervisor Pattern, DevOps Gheware](https://devops.gheware.com/blog/posts/supervisor-pattern-multi-agent-langgraph-2026.html))。

在隔离安全方面，Docker 于 2025 年底推出面向 AI Agent 的 Sandbox 方案，采用 microVM（微虚拟机）而非普通容器实现内核级隔离。每个 Sandbox 拥有独立内核、文件系统和网络栈，其核心设计包括：API Key 通过宿主机网络代理注入，Agent 进程本身拿不到密钥；网络策略强制执行（Open/Balanced/Locked Down 三级），所有出站连接实时审计。这使得"即使 Agent 出现幻觉或行为异常也不会造成系统性风险" ([Docker Sandboxes 技术解析](https://www.cnblogs.com/imust2008/p/20351523); [Docker Sandbox Overview, Collabnix](https://collabnix.com/docs/docker-workshop/sandboxing-with-docker/overview/))。

### 3.3 记忆层：三库协同的知识沉淀与经验复用

记忆层构建三类知识库：CTF 漏洞知识库（漏洞特征、攻击步骤、绕过技巧）、题目样本库（历史题目与解题路径）、平台反馈知识库（提交结果与评分反馈）。Agent 发起攻击前自动检索匹配方案，实现解题经验复用。

Pentest-Chain 框架验证了"外部知识库+内部经验库"双库协同的有效性：引入 RAG 模块后，多智能体框架的任务执行成功率整体提升 17.0%，消融实验表明 RAG 对成功率提升起关键作用。其外部知识库整合了 ATT&CK 矩阵和 CVE 漏洞库，内部经验管理器支持长流程任务中的跨步骤记忆 ([基于 LLM 和 RAG 的自动化渗透测试框架研究, 电信科学 2025](https://www.secrss.com/articles/85448))。中国电信"红刃"AI 智能体构建了包含 500+ 主流框架漏洞的知识库，采用"路径地图+双层漏斗记忆机制"：为每个解题过程创建持续维护的状态地图，通过记忆漏斗过滤噪声，将关键事实沉淀到全局记忆中，遵循"只追加不修改"原则保障核心线索的可追溯性 ([凤凰网科技](https://tech.ifeng.com/c/8t7m7uQNF16))。

学术前沿方面，LEGOMem 提出"全任务粒度 vs 子任务粒度"的分层程序性记忆：编排者记忆存储完整任务计划用于工作流分解，子代理记忆存储局部执行轨迹 ([LLM-based Modular Multi-Agent Frameworks, EmergentMind](https://www.emergentmind.com/topics/llm-based-modular-multi-agent-frameworks))。

### 3.4 多智能体通信与协调机制

当前主流编排框架普遍采用"大脑-记忆-感知-行动"的核心架构范式，协作模式包括顺序流、层级流和协作辩论三类 ([告别单体LLM局限:Multi-Agent系统架构指南](https://2048ai.net/694b7e43836da32144874c0e.html); [Agentic LLMs 前沿综述](https://www.cnblogs.com/sddai/p/19451103))。

LangGraph 通过有向图工作流和状态机实现精细化流程控制：Command 作为编排内核驱动节点间转移，state 作为沟通载体在节点间传递结构化数据，交接（handoff）工具统一路由逻辑。2025 年 LangGraph 多次更新引入了对长时运行任务和远程 Agent（A2A 协议）的支持 ([LangGraph 多智能体架构:5种典型模式, CSDN](https://devpress.csdn.net/v1/article/detail/151871815))。LangChain 2025 年的智能体架构已成熟为模块化分层系统，定义了规划智能体（战略大脑）、执行智能体（RAG/代码生成等专用）、通信智能体（管理步骤间交接、保留上下文）、评估智能体（质量检查点，可退回任务）四类核心角色 ([使用 LangChain 构建多智能体工作流](https://tinyseeking.github.io/p/%E4%BD%BF%E7%94%A8-langchain-%E6%9E%84%E5%BB%BA%E5%A4%9A%E6%99%BA%E8%83%BD%E4%BD%93%E5%B7%A5%E4%BD%9C%E6%B5%81))。

### 3.5 幻觉与越界防控

多智能体架构通过职责分离降低单一大模型幻觉风险，但也引入 Agent 越界主动探测、上下文丢失和代理间信任传递风险。

在幻觉防控方面，Tree of Agents（TOA）通过将长输入分段交由独立 Agent 处理，各 Agent 生成局部认知后沿树结构路径动态交换信息进行协作推理，有效缓解"中间遗忘"问题和位置偏差 ([TOA, arXiv:2509.06436](https://doi.org/10.48550/ARXIV.2509.06436))。清华大学提出的对抗辩论与投票机制框架通过重复询问、错误日志和跨代理交叉验证，在 20 个评估批次中持续提升综合准确率 ([Minimizing Hallucinations, Applied Sciences 2025](https://web.ee.tsinghua.edu.cn/yangyi/zh_CN/lwcg/4724/content/9941.htm))。

在越界防控方面，Sentinel Agents 框架提出"预验证层+被动监听层"双层监控：预验证层在对话事件到达协调器前拦截并决定是否继续；被动监听层实时识别异常并发出审计标记 ([Sentinel Agents 评述, Moonlight](https://www.themoonlight.io/zh/review/sentinel-agents-for-secure-and-trustworthy-agentic-ai-in-multi-agent-systems))。业界共识是：基于提示词的防御在攻击下普遍损失 10-30% 的实用性，架构约束才是根本解。措施包括：将所有 LLM 输出（含其他 Agent 输出）视为不可信；不可信内容运行在隔离 sandbox 中；每个 Agent 仅授予最窄工具与权限。OWASP 于 2025 年 12 月发布的 Top 10 for Agentic Applications 将前三风险定为 Memory Poisoning、Tool Misuse 和 Privilege Compromise ([Agent 安全:信任边界到 Multi-Agent 蠕虫](http://quidproquo.cc/posts/ai/2026-06-04-agent-security-prompt-injection-trust-boundaries))。

对于被动信息搜集场景，最关键的红线是：Agent 不得执行任何主动探测操作。LangGraph 的 Plan-then-Execute 范式通过"控制流完整性"提供架构级保障——控制图在任何外部工具调用前生成，高层工作流不会被事后注入的内容篡改，确保执行可追溯且确定性 ([LangGraph: Modular LLM Agent Orchestration, EmergentMind](https://www.emergentmind.com/topics/langgraph))。

## 分析

综合上述，本章的多智能体编排架构可归纳为三层纵深：**规划层**——借鉴 PentestAgent 的四代理协作与 HPTSA 的分层规划架构，以指挥官 Agent 实现股权穿透→任务拆解→盲区动态补缺，其 Plan-then-Execute 范式从架构层面杜绝越权操作；**执行层**——四大专项采集 Agent 并行运行于 Docker microVM 沙箱，以独立内核与 API Key 代理注入实现"Agent 拿不到密钥、越界也无害"的结构性安全兜底，并行执行可降低 60-70% 挂钟时间；**记忆层**——三库协同（漏洞知识库+样本库+反馈库）配合 RAG 检索，经实证可使任务成功率提升 17.0%，中国电信"红刃"的路径地图+漏斗记忆机制进一步验证了"只追加不修改"原则在长流程可追溯性中的价值。三层共同将被动信息搜集从"工具堆砌"升级为"可审计、可恢复、可扩展的智能体编队"，并通过架构级越界防控使"纯被动"约束从规则声明升级为工程刚性保障。

## 小结

本章构建了多智能体规划-执行-记忆分层编排架构：规划层以 LLM 指挥官 Agent 驱动全局股权穿透与任务分发，借鉴 PentestAgent/HPTSA/BreachSeek 的学术验证；执行层以四大专项采集 Agent 并行运行于 Docker microVM 沙箱，实现内核级隔离与 60-70% 挂钟时间压缩；记忆层以三库协同+RAG 实现经验复用，成功率提升 17.0%；通信层以 LangGraph 图工作流实现精细化编排与 A2A 协议支持；越界防控以 Plan-then-Execute 控制流完整性与 Sentinel Agents 双层监控实现架构级保障。上述架构为第 4 章的资产关联知识图谱提供了数据入口，为第 5 章的合规审批与算力调度提供了执行载体。

---

## 本章新增来源清单（19条）
1. PentestAgent, arXiv:2411.05185 — https://doi.org/10.48550/arXiv.2411.05185
2. Pentest-Chain, 电信科学 2025 — https://www.secrss.com/articles/85448
3. HPTSA GitHub — https://github.com/uiuc-kang-lab/HPTSA
4. BreachSeek arXiv:2409.03789 — https://adsabs.harvard.edu/abs/2024arXiv240903789A
5. LangGraph: Modular LLM Agent Orchestration, EmergentMind — https://www.emergentmind.com/topics/langgraph
6. Supervisor Pattern, DevOps Gheware — https://devops.gheware.com/blog/posts/supervisor-pattern-multi-agent-langgraph-2026.html
7. Docker Sandboxes 技术解析, cnblogs — https://www.cnblogs.com/imust2008/p/20351523
8. Docker Sandbox Overview, Collabnix — https://collabnix.com/docs/docker-workshop/sandboxing-with-docker/overview/
9. TOA, arXiv:2509.06436 / EMNLP 2025 — https://doi.org/10.48550/ARXIV.2509.06436
10. 对抗辩论与投票机制, Applied Sciences 2025 — https://web.ee.tsinghua.edu.cn/yangyi/zh_CN/lwcg/4724/content/9941.htm
11. Sentinel Agents 评述, Moonlight — https://www.themoonlight.io/zh/review/sentinel-agents-for-secure-and-trustworthy-agentic-ai-in-multi-agent-systems
12. Agent安全:信任边界到Multi-Agent蠕虫 — http://quidproquo.cc/posts/ai/2026-06-04-agent-security-prompt-injection-trust-boundaries
13. LLM-based Modular Multi-Agent Frameworks, EmergentMind — https://www.emergentmind.com/topics/llm-based-modular-multi-agent-frameworks
14. Agentic LLMs前沿综述, cnblogs — https://www.cnblogs.com/sddai/p/19451103
15. LangGraph多智能体5种模式, CSDN — https://devpress.csdn.net/v1/article/detail/151871815
16. 使用LangChain构建多智能体工作流 — https://tinyseeking.github.io/p/%E4%BD%BF%E7%94%A8-langchain-%E6%9E%84%E5%BB%BA%E5%A4%9A%E6%99%BA%E8%83%BD%E4%BD%93%E5%B7%A5%E4%BD%9C%E6%B5%81
17. 红刃AI智能体, 凤凰网科技 — https://tech.ifeng.com/c/8t7m7uQNF16
18. 告别单体LLM局限:Multi-Agent系统架构指南 — https://2048ai.net/694b7e43836da32144874c0e.html
19. Graph增强Agent实战指南 — https://blog.csdn.net/2401_85725028/article/details/156001033

> 状态：草稿（Phase 3.1 完成），待审稿
