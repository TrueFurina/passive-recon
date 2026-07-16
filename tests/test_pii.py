"""F-6 PII 保护回归测试：脱敏/加密工具 + 删除/匿名化接口。

- 无密钥时降级为盐哈希（不可逆，库内非明文，读取返回 None）；
- 配置 PASSIVE_PII_KEY 时 AES-256-GCM 可逆还原。
- 验证 insert_subject 落库非明文、get_subject 解密、delete/anonymize 接口。
"""
import pytest

from passive_agent import config as cfg
from passive_agent.common import pii
from passive_agent.storage import db


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test_pii.db")
    db.configure(db_path)
    db.init()


def test_hash_pii_deterministic():
    assert pii.hash_pii("张三") == pii.hash_pii("张三")
    assert pii.hash_pii("张三") != "张三"
    assert pii.hash_pii("张三").startswith("h:")
    assert pii.hash_pii(None) is None


def test_no_key_stores_non_plaintext(tmp_path):
    _setup_db(tmp_path)
    db.insert_subject("阿里巴巴", "马云", "法人", "91330xxx", 0)
    rows = db.query("SELECT id, name, credit_code FROM t_subject WHERE deleted=0")
    assert len(rows) == 1
    assert rows[0]["name"] != "马云"            # 库内非明文（哈希）
    assert rows[0]["credit_code"] != "91330xxx"
    rid = rows[0]["id"]
    got = db.get_subject(rid)
    assert got["name"] is None                   # 哈希不可逆
    db.delete_subject(rid)
    assert db.get_subject(rid) is None


def test_with_key_roundtrip(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    monkeypatch.setattr(cfg.settings, "PII_KEY", "0" * 64)
    _setup_db(tmp_path)
    db.insert_subject("腾讯", "马化腾", "法人", "91440yyy", 0)
    rows = db.query("SELECT id, name FROM t_subject WHERE deleted=0")
    assert rows[0]["name"] != "马化腾"           # 库内密文
    rid = rows[0]["id"]
    got = db.get_subject(rid)
    assert got["name"] == "马化腾"                # 可逆还原
    assert got["credit_code"] == "91440yyy"
    db.anonymize_subject(rid)
    assert db.get_subject(rid)["name"] == "REDACTED"
