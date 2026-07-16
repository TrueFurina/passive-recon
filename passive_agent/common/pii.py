"""PII 脱敏与加密工具（F-6 生产加固）。

- hash_pii：HMAC-SHA256 + 盐，确定性不可逆，用于去重/比对（无法还原原文）。
- encrypt_pii / decrypt_pii：AES-256-GCM（cryptography），密钥从 PASSIVE_PII_KEY 注入；
  无密钥时降级为盐哈希并加 "h:" 前缀，保证不落明文。
- 配置项见 config.py：PII_SALT / PII_KEY / RETENTION_DAYS。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Optional

from passive_agent.config import settings

_HASH_PREFIX = "h:"
_ENC_PREFIX = "e:"


def _salt() -> bytes:
    s = (settings.PII_SALT or "").encode("utf-8")
    # 无显式盐时用固定默认（仍比明文好，但建议 env 注入随机盐）
    return s or b"passive-agent-default-pii-salt"


def _key() -> Optional[bytes]:
    k = (settings.PII_KEY or "").strip()
    if not k:
        return None
    try:
        return bytes.fromhex(k)
    except ValueError:
        return hashlib.sha256(k.encode("utf-8")).digest()


def hash_pii(value: Optional[str]) -> Optional[str]:
    """确定性加盐哈希（不可逆），用于脱敏存储/去重。"""
    if value is None:
        return None
    digest = hmac.new(_salt(), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return _HASH_PREFIX + digest


def encrypt_pii(value: Optional[str]) -> Optional[str]:
    """加密 PII；无密钥则降级为盐哈希（不落明文）。"""
    if value is None:
        return None
    key = _key()
    if key is None:
        return hash_pii(value)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os as _os

        raw = value.encode("utf-8")
        nonce = _os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, raw, None)
        return _ENC_PREFIX + base64.b64encode(nonce + ct).decode("ascii")
    except Exception:
        return hash_pii(value)


def decrypt_pii(value: Optional[str]) -> Optional[str]:
    """还原 PII；哈希值不可逆返回 None，无密钥的密文无法还原。"""
    if value is None:
        return None
    if value.startswith(_HASH_PREFIX):
        return None
    if value.startswith(_ENC_PREFIX):
        key = _key()
        if key is None:
            return None
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            blob = base64.b64decode(value[len(_ENC_PREFIX):])
            nonce, ct = blob[:12], blob[12:]
            return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
        except Exception:
            return None
    # 非标记值视为明文（兼容历史数据）
    return value
