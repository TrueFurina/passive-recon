"""R5 台账 / 导出 / 自研占比。"""
import json
import os

from passive_agent.inventory.model import OssTool
from passive_agent.inventory.registry import InventoryRegistry


def test_proof_ratio():
    reg = InventoryRegistry()
    reg.seed_defaults()
    proof = reg.export_proof()
    assert proof.ratio["self_dev_pct"] > 0
    assert proof.ratio["open_source_pct"] > 0
    self_dev = [t for t in proof.tools if t.boundary_tag == "自研"]
    assert len(self_dev) >= 6  # R1–R6 自研内核


def test_register_and_export(tmp_path):
    reg = InventoryRegistry()
    reg.seed_defaults()
    reg.register(OssTool(name="custom", version="1.0",
                          boundary_tag="自研", module_ref="R9"))
    p = str(tmp_path / "inv.json")
    reg.export_json(p)
    assert os.path.exists(p)
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    assert any(t["name"] == "custom" for t in data)
