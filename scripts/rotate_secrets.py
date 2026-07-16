#!/usr/bin/env python3
"""密钥轮换辅助脚本（被动信息搜集 Agent）。

用途：在外部平台（Hunter / 企查查）轮换密钥之后，本脚本帮助把本地产明文密钥
从 config.json 清出，改为经环境变量 PASSIVE_API_KEYS 注入，并产出 .env 模板。

默认 dry-run（只报告，不改文件）。加 --apply 才真正改写，且会先备份 config.json。

步骤见同目录 SECRET_ROTATION.md。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime

DEFAULT_CONFIG = "config.json"
ENV_FILE = ".env"


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def summarize(cfg: dict) -> None:
    keys = cfg.get("API_KEYS", {})
    hunter = keys.get("hunter", [])
    qcc = keys.get("qichacha", {})
    print("== 当前 config.json 中的密钥 ==")
    print(f"  hunter 密钥数          : {len(hunter) if isinstance(hunter, list) else 'n/a'}")
    print(f"  qichacha app_key 非空  : {bool(qcc.get('app_key')) if isinstance(qcc, dict) else False}")
    print(f"  qichacha secret_key 非空: {bool(qcc.get('secret_key')) if isinstance(qcc, dict) else False}")


def apply(cfg: dict, config_path: str) -> None:
    # 1) 备份
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{config_path}.bak.{ts}"
    shutil.copy2(config_path, backup)
    print(f"已备份 config.json -> {backup}")

    # 2) 清出明文密钥
    sanitized = dict(cfg)
    sanitized["API_KEYS"] = {}
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(sanitized, fh, ensure_ascii=False, indent=2)
    print(f"已改写 {config_path}：API_KEYS 置空（明文密钥已移除）")

    # 3) 产出 .env 模板
    if os.path.exists(ENV_FILE):
        print(f"注意：{ENV_FILE} 已存在，未覆盖。请手动把 PASSIVE_API_KEYS 填入。")
    else:
        with open(ENV_FILE, "w", encoding="utf-8") as fh:
            fh.write("# 被动信息搜集 Agent 环境变量（勿入库）\n")
            fh.write("# 真实数据源密钥统一经 PASSIVE_API_KEYS 注入（JSON 字符串）\n")
            fh.write("# 占位为合法空 JSON；填入新密钥后形如：\n")
            fh.write("# PASSIVE_API_KEYS='{\"hunter\":[\"NEW_KEY\"],\"qichacha\":{\"app_key\":\"NEW\",\"secret_key\":\"NEW\"}}'\n")
            fh.write("PASSIVE_API_KEYS={}\n")
            fh.write("PASSIVE_API_AUTH_ENABLED=true\n")
        print(f"已生成 {ENV_FILE} 模板；请在 PASSIVE_API_KEYS 填入轮换后的密钥 JSON")

    # 4) 后续人工步骤提示
    print("\n== 后续必做（人工）==")
    print("1) 已在 Hunter / 企查查 平台轮换并作废旧密钥")
    print("2) 在 .env 的 PASSIVE_API_KEYS 填入新密钥 JSON，例如：")
    print('   PASSIVE_API_KEYS=\'{"hunter":["NEW_KEY"],"qichacha":{"app_key":"NEW","secret_key":"NEW"}}\'')
    print("3) 从 git 历史清除旧 config.json（破坏性，需团队协同）：")
    print("   git filter-repo --path config.json --invert-paths")
    print("   或使用 BFG：java -jar bfg.jar --delete-files config.json")
    print("4) 强制推送并通知协作者重拉")


def main() -> None:
    ap = argparse.ArgumentParser(description="密钥轮换辅助（默认 dry-run）")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="config.json 路径")
    ap.add_argument("--apply", action="store_true", help="真正改写文件（默认仅报告）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if not cfg:
        print(f"未找到 {args.config}，无需处理。")
        return

    summarize(cfg)
    if args.apply:
        apply(cfg, args.config)
    else:
        print("\n[dry-run] 未做任何改动。确认已在外平台轮换密钥后，加 --apply 执行。")


if __name__ == "__main__":
    main()
