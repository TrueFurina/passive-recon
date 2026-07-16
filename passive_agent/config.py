"""全局配置（pydantic-settings）：优先级 env > config.json > default。

关键项：MAX_ENUM_DEPTH / FREQ_BUFFER / EGRESS_IPS / DB_PATH / LOG_PATH。
蓝图 §7 / §8 默认建议值均不阻塞开发，真实参数到位后仅改此处或适配器。

P1 增量（T-P1-1）：新增 API 鉴权配置（API_AUTH_ENABLED / API_TOKENS / API_KEY），
令牌仅经环境变量注入，不落盘 config.json。
"""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource


class _JsonConfigSource(PydanticBaseSettingsSource):
    """从 config.json 读取配置；文件缺失时返回空 dict（回退到默认值）。"""

    def __init__(self, settings_cls: type, json_file: str = "config.json") -> None:
        super().__init__(settings_cls)
        self.json_file = json_file
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.json_file):
            return {}
        try:
            with open(self.json_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get_field_value(self, field, field_name: str):
        if field_name in self._data:
            return self._data[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict:
        result: dict = {}
        for field_name in self.settings_cls.model_fields:
            value, _key, _ = self.get_field_value(None, field_name)
            if value is not None:
                result[field_name] = value
        return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PASSIVE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # —— 核心参数（蓝图 §7 / §8）——
    MAX_ENUM_DEPTH: int = 3
    FREQ_BUFFER: float = 0.95
    EGRESS_IPS: List[str] = ["127.0.0.1"]
    DB_PATH: str = "data/agent.db"
    LOG_PATH: str = "data/audit.jsonl"

    # —— 频控 / 网关 ——
    RATE_CAPACITY: int = 1000        # 单 IP 单窗口容量
    RATE_WINDOW: float = 1.0         # 滑动窗口秒数
    API_BASE_URL: str = "https://mock.gateway.local"

    # —— T-P1 频控全局化（跨 worker 硬闸）——
    # 集中式频控 Redis 地址：非空且 redis 库可用+可达时，启用 RedisRateLimiter，
    # 多 worker 共享同一后端，全局聚合吞吐仍受 ≤95% 硬闸约束。
    # 留空 → 回退进程内单例（仅单 worker 语义）。env: PASSIVE_RATE_REDIS_URL
    RATE_REDIS_URL: str = ""
    # 单 worker 显式声明：默认 True（即「当前部署为单 worker，进程内频控即全局」）。
    # 若部署为多 worker（--workers>1）须设为 False 并配置 RATE_REDIS_URL，否则启动告警。
    # env: PASSIVE_SINGLE_WORKER_MODE
    SINGLE_WORKER_MODE: bool = True
    # 已配置 Redis 但不可达时是否启动即失败：True=fail-fast（避免「以为全局实则单 worker」
    # 的静默降级）；False=告警后回退进程内单例。env: PASSIVE_RATE_REDIS_FAIL_FAST
    RATE_REDIS_FAIL_FAST: bool = False

    # —— P1 鉴权（API 层令牌，T-P1-1）——
    # 总开关：默认开启；测试会话由 conftest autouse 置 False 保 180 绿。
    API_AUTH_ENABLED: bool = True
    # 反代鉴权显式开关（F-10 生产加固）：False（默认，生产推荐）时 loopback 不豁免鉴权，
    # 外部请求（含经本机 nginx 未加 X-Forwarded-For）必须携带 token；
    # True 仅本地开发/演示：来源 IP 为 127.0.0.1/::1 且无转发头时豁免鉴权。
    TRUST_LOCALHOST: bool = False
    # 合法令牌列表：仅经环境变量 PASSIVE_API_TOKENS（逗号分隔）注入，不落盘。
    API_TOKENS: List[str] = []
    # 单 key 回退：环境变量 PASSIVE_API_KEY；自动并入 API_TOKENS（去重）。
    API_KEY: str = ""

    # —— R4 高价值判定关键词（命中即 HIGH 强制人工复核）——
    HIGH_VALUE_KEYWORDS: List[str] = [
        "工控", "政务", "能源", "电网", "矿山", "电力", "水利", "军工", "核",
    ]

    # —— 出站强制审批总开关（R4 合规加强，T-P1 增量）——
    # True 时所有出站提交强制进入 REVIEWING（HIGH 人工复核），未经人工 approve 严禁出站；
    # 默认 False（保留演示态：仅命中 HIGH_VALUE_KEYWORDS 才强制人工复核）。
    # 注：即便为 False，命中高价值关键词仍会强制人工复核（service._elevate_risk）。
    OUTBOUND_REQUIRE_APPROVAL: bool = False
    # 出站白名单强制模式（F-5 生产加固）：True 时出站目标必须命中 EGRESS_IPS；
    # False（默认）时仅做 HTTPS + 内网/链路本地拦截，不破坏既有外部情报源功能。
    EGRESS_ENFORCE: bool = False

    # —— PII 保护（F-6 生产加固）——
    # 脱敏盐/加密密钥：建议经环境变量注入（PASSIVE_PII_SALT / PASSIVE_PII_KEY），不落盘。
    # PII_KEY 为 hex（32/64 字节）或任意字符串（SHA-256 派生）；未配置则降级为盐哈希。
    PII_SALT: str = ""
    PII_KEY: str = ""
    # 留存期限（天）：>0 时超出期限的 PII 记录可由 purge_expired_pii 清理；0=不自动清理。
    RETENTION_DAYS: int = 0

    # —— 数据源 API 密钥（FAFU 实战淬炼）——
    # 格式: {"hunter": ["key1","key2",...], "securitytrails": "key", "otx": "key"}
    # 免费源(crt.sh/HackerTarget/URLScan)无需密钥
    # Hunter 支持多 Key 轮询（限频自动切换）
    API_KEYS: dict = {}

    # ===== P1 增量配置项（追加，不覆盖 P0 项）=====
    # —— R9 加权算力调度 ——
    COMPUTE_WEIGHTS: dict = {"A": 60, "B": 30, "C": 10}   # A:B:C 算力配额
    IDLE_RECLAIM_MINUTES: int = 25                         # 零新增回收阈值（分钟）
    LEADERBOARD_INTERVAL: int = 300                        # 看榜间隔（秒，=5 分钟）

    # —— R7 适配器 / R8 容错 ——
    SOURCE_TIMEOUT: int = 10                               # 适配器出站调用超时（秒）
    FAULT_MAX_RETRIES: int = 3                             # 连续失败降级阈值
    CRTSH_API_URL: str = "https://crt.sh/?q=%25{}&output=json"  # crt.sh API 模板

    @model_validator(mode="after")
    def _post_init_validate(self) -> "Settings":
        """P1 校验：RATE_CAPACITY 必须为正整数；API_KEY 并入 API_TOKENS。

        - RATE_CAPACITY <= 0 → 启动即失败（fail-fast），避免频控形同虚设。
        - API_KEY 单 key 回退自动并入 API_TOKENS（去重）。
        - 兼容 env 逗号分隔未被框架拆分的情况（防御性摊平）。
        """
        if not isinstance(self.RATE_CAPACITY, int) or self.RATE_CAPACITY <= 0:
            raise ValueError("RATE_CAPACITY 必须为正整数 (>0)")

        # 兼容 env 逗号分隔未拆分的情况
        flattened: List[str] = []
        for t in self.API_TOKENS:
            if isinstance(t, str) and "," in t:
                flattened.extend(s.strip() for s in t.split(","))
            else:
                flattened.append(t)
        self.API_TOKENS = flattened

        # API_KEY 单 key 回退并入
        if self.API_KEY and self.API_KEY.strip():
            key = self.API_KEY.strip()
            if key not in self.API_TOKENS:
                self.API_TOKENS = [*self.API_TOKENS, key]

        # 去空白
        self.API_TOKENS = [t.strip() for t in self.API_TOKENS if isinstance(t, str) and t.strip()]
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # 优先级：init > env > dotenv > config.json > secret
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _JsonConfigSource(settings_cls, "config.json"),
            file_secret_settings,
        )


settings = Settings()
