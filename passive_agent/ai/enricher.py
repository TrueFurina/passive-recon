"""AI 资产丰富化 — 对采集结果进行智能分类和技术栈识别。

采集完成后，对每条资产调用 AI 分析：
1. 细粒度分类（Web管理后台、API网关、邮件服务、VPN入口...）
2. 技术栈识别（从域名/标题推断使用的技术）
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from passive_agent.ai.client import ai_chat_json
from passive_agent.collector.model import AssetRecord


def enrich_assets(records: List[AssetRecord], batch_size: int = 10) -> None:
    """对资产列表进行 AI 分类和技术栈识别（批量处理）。

    Args:
        records: 资产记录列表（原地修改，添加 tags 和 tech_stack）
        batch_size: 每批处理的资产数
    """
    if not records:
        return

    # 只对子域名和域名进行分类（IP/端口等不需要）
    targets = [
        r for r in records
        if r.asset_type.value in ("subdomain", "domain") and r.value
    ]
    if not targets:
        return

    # 分批处理，避免一次传太多
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        _enrich_batch(batch)


def _enrich_batch(batch: List[AssetRecord]) -> None:
    """对一批资产进行 AI 分类。"""
    items = []
    for r in batch:
        title = r.title or ""
        items.append({
            "asset": r.value,
            "title": title[:100],
        })

    prompt = (
        "你是一个网络安全资产分析专家。请分析以下资产列表，对每条资产进行：\n"
        "1. 细粒度分类（从以下类别中选择最匹配的一个）：\n"
        "   - web_main: 主站/官网\n"
        "   - web_admin: 管理后台\n"
        "   - web_api: API 接口\n"
        "   - mail: 邮件系统\n"
        "   - vpn: VPN/远程接入\n"
        "   - oa: OA 办公系统\n"
        "   - sso: 单点登录/认证\n"
        "   - cdn: CDN/静态资源\n"
        "   - dev: 开发/测试环境\n"
        "   - file: 文件存储/网盘\n"
        "   - db: 数据库服务\n"
        "   - monitor: 监控系统\n"
        "   - other: 其他\n\n"
        "2. 技术栈（从标题/域名中推断，如 nginx, Apache, Java, WordPress 等，最多3个）\n\n"
        "请只输出 JSON 数组，格式：\n"
        '[{"asset": "域名", "category": "web_main", "tech_stack": ["nginx","php"]}]\n\n'
        f"资产列表：\n" + "\n".join(
            f'- {item["asset"]} (标题: {item["title"]})' for item in items
        )
    )

    result = ai_chat_json(
        [{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.1,
    )

    if not result or not isinstance(result, list):
        return

    # 构建域名 → 分类/技术栈 映射
    mapping = {}
    for item in result:
        asset = item.get("asset", "")
        mapping[asset] = {
            "category": item.get("category", "other"),
            "tech_stack": item.get("tech_stack", []),
        }

    # 原地更新资产记录
    for r in batch:
        info = mapping.get(r.value)
        if not info:
            continue

        # 添加分类标签
        cat = info.get("category", "")
        if cat and cat != "other" and cat not in r.tags:
            r.tags.append(f"cat:{cat}")

        # 添加技术栈
        techs = info.get("tech_stack", [])
        for t in techs:
            if isinstance(t, str) and t and t not in r.tech_stack:
                r.tech_stack.append(t)