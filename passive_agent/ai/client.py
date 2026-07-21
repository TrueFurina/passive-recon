"""DeepSeek API 统一封装 — 读取密钥、调用 AI、解析结果。

所有 AI 功能统一走此模块，避免重复代码。
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

import httpx

from passive_agent.common.compliance_client import check as _r1_pass

# DeepSeek API 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
_TIMEOUT = 30


def get_api_key() -> str:
    """获取 DeepSeek API Key，支持环境变量 + Windows 注册表回退。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    try:
        r = subprocess.run(
            ["powershell.exe", "-Command",
             '[System.Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY","User")'],
            capture_output=True, text=True, timeout=5,
        )
        key = r.stdout.strip()
    except Exception:
        pass
    return key


def ai_chat(
    messages: List[Dict[str, str]],
    max_tokens: int = 1000,
    temperature: float = 0.3,
    timeout: float = _TIMEOUT,
) -> Optional[str]:
    """通用 AI 对话调用。

    Args:
        messages: [{"role": "user", "content": "..."}]
        max_tokens: 最大输出 token
        temperature: 温度（0-1，越低越确定）

    Returns:
        AI 回复文本，失败返回 None
    """
    # R1 合规检查：AI 出站调用属于被动情报收集
    _r1_pass(source="deepseek")
    api_key = get_api_key()
    if not api_key:
        return None
    try:
        resp = httpx.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None


def ai_chat_json(
    messages: List[Dict[str, str]],
    max_tokens: int = 1000,
    temperature: float = 0.1,
    timeout: float = _TIMEOUT,
) -> Optional[Any]:
    """AI 对话调用，返回 JSON 解析结果。

    要求 AI 以 JSON 格式回复，自动解析返回。
    """
    result = ai_chat(
        [*messages, {"role": "user", "content": "请只输出 JSON，不要包含其他说明文字。"}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if not result:
        return None
    # 尝试提取 JSON（去除可能的 ```json 包裹）
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[-1]
        result = result.rsplit("```", 1)[0].strip()
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None