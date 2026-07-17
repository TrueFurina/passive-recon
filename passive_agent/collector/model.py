"""被动采集数据模型（FAFU 实战提炼 + P1 增量）。

P0/FAFU: AssetRecord / AssetSourceEnum / AssetType / CollectReport
P1 增量: CollectQuery / CollectItem / CollectResult
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from passive_agent.common.enums import CollectorCluster


class AssetSourceEnum(str, Enum):
    """数据源枚举 — 被动信息收集全数据源。"""
    CRTSH = "crt.sh"               # 证书透明日志
    HACKERTARGET = "hackertarget"  # HackerTarget API
    OTX = "otx"                    # AlienVault OTX
    URLSCAN = "urlscan"            # URLScan.io
    SECURITYTRAILS = "securitytrails"  # SecurityTrails
    REVERSE_DNS = "reverse_dns"    # IP 反查 DNS
    HUNTER = "hunter"              # 鹰图 Hunter API
    FOFA = "fofa"                  # FOFA 空间搜索引擎
    QICHACHA = "qichacha"          # 企查查 企业工商信息
    WAYBACK = "wayback"            # Wayback Machine 历史存档
    DNSDUMPSTER = "dnsdumpster"    # DNSDumpster DNS 映射
    SHODAN = "shodan"              # Shodan 互联网设备搜索
    VIRUSTOTAL = "virustotal"      # VirusTotal 威胁情报
    GITHUB = "github"              # GitHub 代码搜索
    COMMONCRAWL = "commoncrawl"    # CommonCrawl 网页数据
    ZOOMEYE = "zoomeye"            # ZoomEye 网络空间测绘
    CUSTOM = "custom"              # 自定义导入


class AssetType(str, Enum):
    """资产类型。"""
    DOMAIN = "domain"             # 域名
    SUBDOMAIN = "subdomain"       # 子域名
    IP = "ip"                     # IP 地址
    CIDR = "cidr"                 # IP 段
    EMAIL = "email"               # 邮箱
    WECHAT_ACCOUNT = "wechat_account"  # 公众号
    WECHAT_MINIAPP = "wechat_miniapp"  # 小程序
    MOBILE_APP = "mobile_app"     # 移动 APP
    ORGANIZATION = "organization" # 组织/企业
    TECHNOLOGY = "technology"     # 技术栈
    UNKNOWN = "unknown"


class AssetRecord(BaseModel):
    """一条被动采集的资产记录。"""
    value: str                     # 资产值（域名 / IP / 邮箱...）
    asset_type: AssetType = AssetType.UNKNOWN
    source: AssetSourceEnum        # 来自哪个数据源
    source_extra: str = ""         # 来源附加信息（如 crt.sh 的证书 ID）
    ip: Optional[str] = None       # 解析到的 IP（域名类资产）
    port: Optional[int] = None     # 端口
    tech_stack: List[str] = Field(default_factory=list)  # 技术栈标记
    title: str = ""                # HTTP 标题
    tags: List[str] = Field(default_factory=list)  # 标签
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CollectReport(BaseModel):
    """一次完整采集任务的报告。"""
    enterprise: str                # 目标企业名称
    domain: str                    # 主域名
    total_records: int = 0
    sources_used: List[str] = Field(default_factory=list)
    records: List[AssetRecord] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""

    def merge(self, other: CollectReport) -> None:
        """合并另一个报告（去重）。"""
        existing = {(r.value, r.asset_type.value) for r in self.records}
        for r in other.records:
            key = (r.value, r.asset_type.value)
            if key not in existing:
                self.records.append(r)
                existing.add(key)
        self.sources_used = list(set(self.sources_used + other.sources_used))
        self.errors.extend(other.errors)
        self.total_records = len(self.records)

    def to_table(self) -> str:
        """生成 Markdown 全维度资产报告（类 FAFU 格式）。"""
        lines = [
            f"# {self.enterprise} 被动资产收集报告",
            f"> 主域: {self.domain} | 数据源: {', '.join(self.sources_used)}",
            f"> 时间: {self.started_at} | 总数: {self.total_records}",
            "",
            "## 📊 资产总览",
            f"| 类型 | 数量 |",
            f"|------|------|",
        ]
        type_counts: Dict[str, int] = {}
        ips: set = set()
        techs: set = set()
        ports: set = set()
        for r in self.records:
            type_counts[r.asset_type.value] = type_counts.get(r.asset_type.value, 0) + 1
            if r.ip:
                ips.add(r.ip)
            for t in r.tech_stack:
                if isinstance(t, str) and t:
                    techs.add(t)
            if r.port:
                ports.add(r.port)
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {t} | {c} |")
        lines.append(f"| IP 地址 | {len(ips)} |")
        lines.append(f"| 技术栈 | {len(techs)} |")
        lines.append(f"| 端口 | {len(ports)} |")
        lines.append(f"| **合计** | **{self.total_records}** |")
        lines.append("")

        # IP 集群分布
        if ips:
            lines.append("## 🌐 IP 地址分布")
            # 按 C 段分组
            c_segments: Dict[str, List[str]] = {}
            for ip in sorted(ips):
                c = ".".join(ip.split(".")[:3]) + ".0/24"
                c_segments.setdefault(c, []).append(ip)
            lines.append(f"| C 段 | IP 数 |")
            lines.append(f"|------|-------|")
            for seg, iplist in sorted(c_segments.items(), key=lambda x: -len(x[1])):
                lines.append(f"| {seg} | {len(iplist)} |")
            lines.append("")

        # 技术栈统计
        if techs:
            lines.append("## 🔧 技术栈概览")
            for t in sorted(techs):
                lines.append(f"- {t}")
            lines.append("")

        # 风险发现
        has_risks = any("🔴" in e or "P0" in e or "P1" in e or "P2" in e for e in self.errors)
        if has_risks:
            lines.append("## 🚨 风险发现")
            for e in self.errors:
                if "🔴" in e or "P0" in e or "P1" in e or "P2" in e:
                    lines.append(f"- {e}")
            lines.append("")

        if self.errors and not has_risks:
            lines.append("## ⚠️ 采集日志")
            for e in self.errors:
                lines.append(f"- {e}")

        return "\n".join(lines)


# ===== P1 增量数据模型（R7 多源采集调度）=====


class CollectQuery(BaseModel):
    """采集查询参数（R7 调度内核按集群拆子任务）。"""
    enterprise: str                         # 目标企业名称
    subject_name: str                       # 主体名称（子公司/分公司）
    cluster: CollectorCluster               # 所属采集集群
    trace_id: str = ""                      # 全链路追踪 ID


class CollectItem(BaseModel):
    """单条采集结果项。"""
    item_type: str                          # 资产类型（domain/wechat_account/mini_program/equity_relation）
    value: str                              # 资产值
    source_name: str                        # 来源适配器名
    raw: dict = Field(default_factory=dict) # 原始数据


class CollectResult(BaseModel):
    """单个集群采集结果。"""
    query: CollectQuery                     # 对应的查询参数
    items: List[CollectItem] = Field(default_factory=list)  # 采集项列表
    source_name: str = ""                   # 实际使用的源名
    success: bool = False                   # 是否成功
    error: str = ""                         # 错误信息
    collected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
