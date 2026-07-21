"""AI 域名推断引擎 — 替代 domain_db.py 的查表 + 算法推算。

策略：
1. 先查本地知识库（已有的 400+ 映射，快速命中）
2. 未命中 → 调用 DeepSeek AI 推断
3. 结果缓存到 SQLite，下次直接命中
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from passive_agent.ai.client import ai_chat
from passive_agent.storage import db

# 确保缓存表存在
_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS t_domain_cache (
    name TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    source TEXT DEFAULT 'ai'
);
"""


def _ensure_cache() -> None:
    try:
        db.write(_CACHE_TABLE)
    except Exception:
        pass


def _cache_get(name: str) -> Optional[str]:
    """从缓存查询。"""
    try:
        rows = db.query(
            "SELECT domain FROM t_domain_cache WHERE name=?",
            (name,),
        )
        return rows[0]["domain"] if rows else None
    except Exception:
        return None


def _cache_set(name: str, domain: str, source: str = "ai") -> None:
    """写入缓存。"""
    try:
        db.write(
            "INSERT OR REPLACE INTO t_domain_cache (name, domain, source) VALUES (?,?,?)",
            (name, domain, source),
        )
    except Exception:
        pass


def infer_domain(name: str) -> str:
    """AI 域名推断 — 先查本地知识库，再查缓存，最后 AI 推断。

    Args:
        name: 目标名称，如 "北京大学"、"阿里巴巴"、"fafu.edu.cn"

    Returns:
        最可能的域名
    """
    name = name.strip()
    if not name:
        return "unknown"

    # 1. 已经是域名格式
    if "." in name:
        return name.lower()

    # 2. 查本地知识库（已有 domain_db 中的映射）
    domain = _infer_from_local_db(name)
    if domain:
        _cache_set(name, domain, "local")
        return domain

    # 3. 查 AI 缓存
    cached = _cache_get(name)
    if cached:
        return cached

    # 4. AI 推断
    domain = _infer_from_ai(name)
    if domain:
        _cache_set(name, domain, "ai")
        return domain

    # 5. 兜底：拼音首字母 + .com
    abbr = "".join([p[0] for p in name.split() if p]) if name.split() else name[:3]
    fallback = f"{abbr.lower()}.com" if abbr else f"{name.lower()}.com"
    return fallback


def _infer_from_local_db(name: str) -> Optional[str]:
    """从本地 domain_db 知识库查询。"""
    # 动态导入避免循环引用
    from passive_agent.collector.domain_db import infer_domain as local_infer
    try:
        result = local_infer(name)
        # 如果结果看起来是算法生成的（不是查表得到的），返回 None 让 AI 试试
        if "." in result:
            return result
    except Exception:
        pass
    return None


def _infer_from_ai(name: str) -> Optional[str]:
    """调用 DeepSeek 推断域名。"""
    prompt = (
        f"你是一个网络安全专家。请推断目标「{name}」最可能的官方主域名。\n\n"
        "规则：\n"
        "- 中国高校通常用 .edu.cn\n"
        "- 中国企业通常用 .com 或 .com.cn\n"
        "- 中国政府部门通常用 .gov.cn\n"
        "- 国际组织和国外企业通常用 .com / .org\n\n"
        "请只输出域名本身，不要包含任何其他文字。\n"
        "示例：北京大学 → pku.edu.cn，阿里巴巴 → alibaba.com"
    )
    result = ai_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.1,
    )
    if result:
        result = result.strip().lower()
        # 清理可能的标点
        result = result.strip(".").strip('"').strip("'").strip("`")
        if "." in result:
            return result
    return None