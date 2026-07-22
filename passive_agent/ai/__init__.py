"""AI 核心模块 — DeepSeek API 统一封装。

提供：
- domain_infer.infer_domain(): AI 域名推断（替代查表）
- risk_scorer.score_risks(): AI 风险评分（替代硬编码规则）
- risk_scorer.filter_risks(): AI 风险过滤
- client.ai_chat(): 通用 AI 对话
"""
from passive_agent.ai.client import get_api_key, ai_chat, ai_chat_json
from passive_agent.ai.domain_infer import infer_domain
from passive_agent.ai.risk_scorer import score_risks, filter_risks
from passive_agent.ai.chat import ask
from passive_agent.ai.enricher import enrich_assets

__all__ = ["get_api_key", "ai_chat", "ai_chat_json", "infer_domain", "score_risks", "filter_risks", "ask", "enrich_assets"]