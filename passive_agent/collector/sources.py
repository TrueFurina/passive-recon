"""真实被动数据源采集器 — 从 FAFU 实战中提取并工程化。

所有采集器：
  1. 纯被动（零连接目标系统、零产生目标日志）
  2. 出站前经 R1 合规关隘（fail-closed）
  3. 异常容忍（单源失败不影响其他源）
"""
from __future__ import annotations

import json
import socket
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from passive_agent.collector.model import AssetRecord, AssetSourceEnum, AssetType, CollectReport
from passive_agent.common import logging as clog
from passive_agent.common.compliance_client import check
from passive_agent.common.enums import ActionType

_logger = clog.get_logger("collector-sources")

# ──────────────────────────────────────────────
# 基础工具
# ──────────────────────────────────────────────


def _resolve_domain(domain: str, timeout: float = 3.0) -> Optional[str]:
    """纯被动 DNS 解析（仅 A 记录，不连接目标）。"""
    try:
        addrs = socket.getaddrinfo(domain, 80, socket.AF_INET)
        ips = list(set(a[4][0] for a in addrs))
        return ips[0] if ips else None
    except Exception:
        return None


def _r1_pass(action: ActionType = ActionType.PASSIVE_QUERY,
             source: str = "collector") -> None:
    """R1 合规关隘：不通过则抛异常（fail-closed）。"""
    decision = check(action, source_name=source)
    if not decision.allowed:
        raise PermissionError(f"R1 拦截 {source}: {decision.reason_code} {decision.reason}")


# ──────────────────────────────────────────────
# 采集器核心
# ──────────────────────────────────────────────


class BaseCollector:
    """所有采集器的基类。"""
    SOURCE: AssetSourceEnum

    def __init__(self, timeout: float = 15.0, api_key: str = ""):
        self.timeout = timeout
        self.api_key = api_key
        self._errors: List[str] = []

    def collect(self, domain: str) -> List[AssetRecord]:
        """子类实现此方法。"""
        raise NotImplementedError

    def _make_record(self, value: str, asset_type: AssetType = AssetType.SUBDOMAIN,
                     ip: Optional[str] = None, port: Optional[int] = None,
                     extra: str = "", tags: Optional[List[str]] = None) -> AssetRecord:
        return AssetRecord(
            value=value,
            asset_type=asset_type,
            source=self.SOURCE,
            source_extra=extra,
            ip=ip or _resolve_domain(value),
            port=port,
            tags=tags or [],
        )


class CrtshCollector(BaseCollector):
    """crt.sh 证书透明日志 — 查询通配符证书获取子域名列表。"""

    SOURCE = AssetSourceEnum.CRTSH
    BASE_URL = "https://crt.sh"

    def collect(self, domain: str) -> List[AssetRecord]:
        # R1 关隘
        _r1_pass(source="crt.sh")
        records: List[AssetRecord] = []
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/?q=%25.{domain}&output=json",
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                self._errors.append(f"crt.sh HTTP {resp.status_code}")
                return records
            data = resp.json()
            seen: Set[str] = set()
            for entry in data:
                name: str = entry.get("name_value", "")
                for sub in name.split("\n"):
                    sub = sub.strip().lower()
                    if not sub or sub in seen or sub.startswith("*"):
                        continue
                    seen.add(sub)
                    records.append(self._make_record(
                        sub, AssetType.SUBDOMAIN,
                        extra=f"crt.sh id={entry.get('id', '')}",
                        tags=["certificate", "ssl"],
                    ))
            _logger.info(f"crt.sh: {domain} → {len(records)} 子域名")
        except Exception as e:
            self._errors.append(f"crt.sh 失败: {e}")
            _logger.warn(f"crt.sh 采集异常: {e}")
        return records


class HackerTargetCollector(BaseCollector):
    """HackerTarget API — 免费主机/DNS 查询（10次/分钟免费）。"""

    SOURCE = AssetSourceEnum.HACKERTARGET
    BASE_URL = "https://api.hackertarget.com"

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="hackertarget")
        records: List[AssetRecord] = []
        try:
            # 子域名查询
            resp = httpx.get(
                f"{self.BASE_URL}/hostsearch/?q={domain}",
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                for line in resp.text.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        subdomain, ip = parts[0].strip(), parts[1].strip()
                        records.append(self._make_record(
                            subdomain, AssetType.SUBDOMAIN, ip=ip,
                            tags=["hackertarget"],
                        ))
            # 额外 DNS 信息
            for qtype in ["dnsreverse", "dnslookup"]:
                try:
                    resp2 = httpx.get(
                        f"{self.BASE_URL}/{qtype}/?q={domain}",
                        timeout=self.timeout,
                    )
                    if resp2.status_code == 200:
                        _logger.debug(f"hackertarget/{qtype}: {len(resp2.text)} bytes")
                except Exception:
                    pass
            _logger.info(f"HackerTarget: {domain} → {len(records)} 记录")
        except Exception as e:
            self._errors.append(f"HackerTarget 失败: {e}")
            _logger.warn(f"HackerTarget 采集异常: {e}")
        return records


class OTXCollector(BaseCollector):
    """AlienVault OTX — 被动 DNS / 情报。"""

    SOURCE = AssetSourceEnum.OTX
    BASE_URL = "https://otx.alienvault.com"

    def __init__(self, timeout: float = 15.0, api_key: str = ""):
        super().__init__(timeout, api_key)
        self._headers = {
            "User-Agent": "Mozilla/5.0",
        }
        if api_key:
            self._headers["X-OTX-API-KEY"] = api_key

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="otx")
        records: List[AssetRecord] = []
        try:
            url = f"{self.BASE_URL}/api/v1/indicators/domain/{domain}/passive_dns"
            resp = httpx.get(url, headers=self._headers, timeout=self.timeout)
            if resp.status_code != 200:
                self._errors.append(f"OTX HTTP {resp.status_code}")
                return records
            data = resp.json()
            seen: Set[str] = set()
            for entry in data.get("passive_dns", []):
                hostname: str = entry.get("hostname", "").strip().lower()
                if hostname and hostname not in seen and hostname.endswith(f".{domain}"):
                    seen.add(hostname)
                    records.append(self._make_record(
                        hostname, AssetType.SUBDOMAIN,
                        ip=entry.get("address", ""),
                        extra=f"OTX record_type={entry.get('record_type', '')}",
                        tags=["otx", "passive_dns"],
                    ))
            _logger.info(f"OTX: {domain} → {len(records)} 子域名")
        except Exception as e:
            self._errors.append(f"OTX 失败: {e}")
            _logger.warn(f"OTX 采集异常: {e}")
        return records


class URLScanCollector(BaseCollector):
    """URLScan.io — 搜索结果（历史页面截图/域名映射）。"""

    SOURCE = AssetSourceEnum.URLSCAN
    BASE_URL = "https://urlscan.io"

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="urlscan")
        records: List[AssetRecord] = []
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/api/v1/search/?q=domain:{domain}",
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                self._errors.append(f"URLScan HTTP {resp.status_code}")
                return records
            data = resp.json()
            seen: Set[str] = set()
            for result in data.get("results", []):
                page: Dict = result.get("page", {})
                sub = page.get("domain", "").strip().lower()
                if sub and sub not in seen and sub.endswith(f".{domain}"):
                    seen.add(sub)
                    records.append(self._make_record(
                        sub, AssetType.SUBDOMAIN,
                        ip=page.get("ip", ""),
                        extra=f"urlscan uuid={result.get('_id', '')}",
                        tags=["urlscan"],
                    ))
            _logger.info(f"URLScan: {domain} → {len(records)} 子域名")
        except Exception as e:
            self._errors.append(f"URLScan 失败: {e}")
            _logger.warn(f"URLScan 采集异常: {e}")
        return records


class SecurityTrailsCollector(BaseCollector):
    """SecurityTrails API — 子域名枚举（需要 API Key）。"""

    SOURCE = AssetSourceEnum.SECURITYTRAILS
    BASE_URL = "https://api.securitytrails.com/v1"

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="securitytrails")
        records: List[AssetRecord] = []
        if not self.api_key:
            _logger.info("SecurityTrails: 无 API Key，跳过")
            return records
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/domain/{domain}/subdomains",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "APIKEY": self.api_key,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                self._errors.append(f"SecurityTrails HTTP {resp.status_code}")
                return records
            data = resp.json()
            for sub in data.get("subdomains", []):
                full = f"{sub}.{domain}"
                records.append(self._make_record(
                    full, AssetType.SUBDOMAIN,
                    tags=["securitytrails"],
                ))
            _logger.info(f"SecurityTrails: {domain} → {len(records)} 子域名")
        except Exception as e:
            self._errors.append(f"SecurityTrails 失败: {e}")
            _logger.warn(f"SecurityTrails 采集异常: {e}")
        return records


class HunterCollector(BaseCollector):
    """鹰图 Hunter API — 空间搜索引擎（支持多Key轮询限频切换）。

    API 端点: https://hunter.qianxin.com/openApi/search
    参数: api-key (不是 key), search 需 base64 编码
    """

    SOURCE = AssetSourceEnum.HUNTER
    BASE_URL = "https://hunter.qianxin.com/openApi/search"
    _key_index = 0  # 类级别轮询指针

    def __init__(self, timeout: float = 20.0, api_key: str = ""):
        super().__init__(timeout, api_key)
        self._keys: list = []
        if isinstance(api_key, list):
            self._keys = [k for k in api_key if k]
        elif isinstance(api_key, str) and api_key:
            self._keys = [api_key]

    def is_available(self) -> bool:
        return len(self._keys) > 0

    @staticmethod
    def _base64_encode_search(query: str) -> str:
        """Hunter API 要求 search 参数进行 RFC 4648 base64url 编码。"""
        import base64
        return base64.urlsafe_b64encode(query.encode()).decode()

    def collect(self, domain: str) -> List[AssetRecord]:
        """Hunter API 全量采集 — 自动迭代所有页面直到拉完或 Key 耗尽。"""
        _r1_pass(source="hunter")
        all_records: List[AssetRecord] = []
        if not self._keys:
            _logger.info("Hunter: 无 API Key，跳过")
            return all_records

        search_query = f'domain.suffix="{domain}"'
        encoded_search = self._base64_encode_search(search_query)

        tried_keys = []
        for _ in range(len(self._keys)):
            key = self._next_key()
            if key in tried_keys:
                break
            tried_keys.append(key)

            page = 1
            total = 0
            records_this_key = 0
            consecutive_errors = 0

            while True:
                try:
                    params = {
                        "api-key": key,
                        "search": encoded_search,
                        "page": str(page),
                        "page_size": "20",
                        "is_web": "1",
                    }
                    resp = httpx.get(self.BASE_URL, params=params, timeout=self.timeout)

                    if resp.status_code in (429, 403):
                        _logger.warn(f"Hunter Key 限频/封禁 page={page}，切换下一个 Key")
                        break
                    if resp.status_code != 200:
                        self._errors.append(f"Hunter HTTP {resp.status_code}")
                        break

                    data = resp.json()
                    if data.get("code") != 200:
                        _logger.warn(f"Hunter Key 返回 code={data.get('code')} page={page}")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            break
                        page += 1
                        continue

                    consecutive_errors = 0
                    total = data.get("data", {}).get("total", 0)
                    arr = data.get("data", {}).get("arr", [])

                    if not arr:
                        break  # 无更多数据

                    for item in arr:
                        sub = item.get("domain", "").strip().lower()
                        ip = item.get("ip", "").strip()
                        port = item.get("port")
                        tech = item.get("component", [])
                        title = item.get("title", "")
                        tags = item.get("tag", [])
                        city = item.get("city", "")
                        if sub:
                            all_records.append(AssetRecord(
                                value=sub, asset_type=AssetType.SUBDOMAIN,
                                source=self.SOURCE, ip=ip,
                                port=int(port) if port else None,
                                tech_stack=tech if isinstance(tech, list) else [tech],
                                title=title or "", tags=tags if isinstance(tags, list) else [tags],
                                source_extra=city,
                            ))

                    records_this_key += len(arr)
                    _logger.info(f"Hunter page={page}: +{len(arr)} 条 (累计 {records_this_key}/{total})")

                    # 判断是否还有下一页
                    if records_this_key >= total or len(arr) < 20:
                        break
                    page += 1

                except Exception as e:
                    _logger.warn(f"Hunter page={page} 异常: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        break
                    page += 1
                    continue

            _logger.info(f"Hunter Key 完成: {records_this_key}/{total} 条，切换下一个 Key 继续")
            # 在这个 Key 完成后，用下一个 Key 继续翻页
            continue

        # 去重（多 Key 间可能有重叠）
        seen = set()
        unique = []
        for r in all_records:
            if r.value not in seen:
                seen.add(r.value)
                unique.append(r)
        _logger.info(f"Hunter 最终: {domain} -> {len(unique)} 去重资产 (原始 {len(all_records)})")
        return unique

    def _next_key(self) -> str:
        """轮询取下一个 Key。"""
        if not self._keys:
            return ""
        idx = self.__class__._key_index % len(self._keys)
        self.__class__._key_index = (self.__class__._key_index + 1) % len(self._keys)
        return self._keys[idx]


class ReverseDnsCollector(BaseCollector):
    """IP 反查 DNS — 给定已知 IP 列表反向查询域名。"""

    SOURCE = AssetSourceEnum.REVERSE_DNS

    def __init__(self, target_ips: Optional[List[str]] = None, timeout: float = 15.0, api_key: str = ""):
        super().__init__(timeout, api_key)
        self.target_ips = target_ips or []

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="reverse_dns")
        records: List[AssetRecord] = []
        if not self.target_ips:
            # 如果没有预置 IP 列表，先解析域名本身
            ip = _resolve_domain(domain)
            if ip:
                self.target_ips = [ip]
        for ip in self.target_ips:
            try:
                hostname, _, _ = socket.gethostbyaddr(ip)
                if hostname and hostname != ip:
                    records.append(self._make_record(
                        hostname, AssetType.SUBDOMAIN, ip=ip,
                        tags=["reverse_dns"],
                    ))
            except Exception:
                pass
        _logger.info(f"ReverseDNS: {len(self.target_ips)} IPs → {len(records)} 域名")
        return records


# ──────────────────────────────────────────────
# 企查查 企业信息采集器
# ──────────────────────────────────────────────


class QichachaCollector(BaseCollector):
    """企查查 API — 企业工商信息采集（模糊搜索 + 详情 + 要素核验）。

    FAFU 实战反哺：补充股权结构、统一社会信用代码等工商维度。
    """

    SOURCE = AssetSourceEnum.QICHACHA
    BASE_URL = "https://api.qichacha.com"

    def __init__(self, timeout: float = 15.0, api_key: str = ""):
        super().__init__(timeout, api_key)
        self._app_key = ""
        self._secret_key = ""
        if isinstance(api_key, dict):
            self._app_key = api_key.get("app_key", "")
            self._secret_key = api_key.get("secret_key", "")
        elif isinstance(api_key, str):
            parts = api_key.split("|")
            if len(parts) >= 2:
                self._app_key = parts[0]
                self._secret_key = parts[1]
            else:
                self._app_key = api_key

    def is_available(self) -> bool:
        return bool(self._app_key) and bool(self._secret_key)

    @staticmethod
    def _sign(app_key: str, secret_key: str) -> tuple:
        """生成企查查 API 签名。"""
        import hashlib, time
        timespan = str(int(time.time()))
        origin = app_key + timespan + secret_key
        token = hashlib.md5(origin.encode()).hexdigest().upper()
        return token, timespan

    def collect(self, domain: str) -> List[AssetRecord]:
        """企查查企业模糊搜索（域名 → 企业名 → 工商信息）。"""
        _r1_pass(source="qichacha")
        records: List[AssetRecord] = []
        if not self.is_available():
            _logger.info("企查查: 无 API Key，跳过")
            return records

        # 从域名推断企业名称
        enterprise_name = self._domain_to_enterprise(domain)
        if not enterprise_name:
            return records

        token, ts = self._sign(self._app_key, self._secret_key)
        headers = {"Token": token, "Timespan": ts}

        try:
            # 1. 模糊搜索
            resp = httpx.get(
                f"{self.BASE_URL}/FuzzySearch/GetList",
                headers=headers,
                params={
                    "key": self._app_key,
                    "searchKey": enterprise_name,
                    "pageSize": "5",
                    "pageIndex": "1",
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                self._errors.append(f"企查查 HTTP {resp.status_code}")
                return records

            data = resp.json()
            if data.get("Status") != "200":
                self._errors.append(f"企查查 API 错误: {data.get('Message','')}")
                return records

            results = data.get("Result", [])

            # 2. 提取企业信息作为资产记录
            for r in results:
                name = r.get("Name", "")
                credit_code = r.get("CreditCode", "")
                oper_name = r.get("OperName", "")
                status = r.get("Status", "")
                address = r.get("Address", "")
                reg_no = r.get("No", "")
                start_date = r.get("StartDate", "")

                records.append(AssetRecord(
                    value=name,
                    asset_type=AssetType.ORGANIZATION,
                    source=self.SOURCE,
                    tags=["qichacha", "enterprise"],
                    source_extra=f"信用代码={credit_code} 法人={oper_name} 状态={status}",
                ))

                # 信用代码作为独立记录
                if credit_code:
                    records.append(AssetRecord(
                        value=credit_code,
                        asset_type=AssetType.UNKNOWN,
                        source=self.SOURCE,
                        tags=["qichacha", "credit_code"],
                        source_extra=f"企业={name}",
                    ))

                # 法人信息
                if oper_name:
                    records.append(AssetRecord(
                        value=f"法人:{oper_name}",
                        asset_type=AssetType.UNKNOWN,
                        source=self.SOURCE,
                        tags=["qichacha", "legal_person"],
                        source_extra=f"企业={name}",
                    ))

            _logger.info(f"企查查: {enterprise_name} -> {len(results)} 家企业, {len(records)} 条记录")

        except Exception as e:
            self._errors.append(f"企查查 异常: {e}")
            _logger.warn(f"企查查 采集异常: {e}")

        return records

    @staticmethod
    def _domain_to_enterprise(domain: str) -> str:
        """从域名推断企业名称（用于企查查搜索）。"""
        import re
        base = re.sub(r'\.(edu\.cn|com\.cn|com|cn|net|org)(\..*)?$', '', domain)
        return base

    # ── 新增：企业工商详情 ──

    def get_business_detail(self, search_key: str) -> dict:
        """企业工商详情查询（股东/法人/联系电话/分支机构）。"""
        _r1_pass(source="qichacha")
        token, ts = self._sign(self._app_key, self._secret_key)
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/ECIInfoVerify/GetInfo",
                headers={"Token": token, "Timespan": ts},
                params={"key": self._app_key, "searchKey": search_key},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            data = resp.json()
            if data.get("Status") != "200":
                return {"error": data.get("Message", "")}
            return data.get("Result", {})
        except Exception as e:
            return {"error": str(e)}

    # ── 新增：二要素核验 ──

    def verify_two_element(self, credit_code: str, verify_name: str,
                           verify_type: str = "1") -> dict:
        """企业二要素核验（信用代码+企业名/法人名是否匹配）。"""
        _r1_pass(source="qichacha")
        token, ts = self._sign(self._app_key, self._secret_key)
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/ECITwoElVerify/GetInfo",
                headers={"Token": token, "Timespan": ts},
                params={
                    "key": self._app_key, "creditCode": credit_code,
                    "verifyName": verify_name, "verifyType": verify_type,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            data = resp.json()
            if data.get("Status") != "200":
                return {"error": data.get("Message", "")}
            return data.get("Result", {})
        except Exception as e:
            return {"error": str(e)}

    # ── 新增：三要素核验 ──

    def verify_three_element(self, credit_code: str, company_name: str,
                             oper_name: str) -> dict:
        """企业三要素核验（信用代码+企业名+法人是否一致）。"""
        _r1_pass(source="qichacha")
        token, ts = self._sign(self._app_key, self._secret_key)
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/ECIThreeElVerify/GetInfo",
                headers={"Token": token, "Timespan": ts},
                params={
                    "key": self._app_key, "creditCode": credit_code,
                    "companyName": company_name, "operName": oper_name,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            data = resp.json()
            if data.get("Status") != "200":
                return {"error": data.get("Message", "")}
            return data.get("Result", {})
        except Exception as e:
            return {"error": str(e)}


# ──────────────────────────────────────────────
# FOFA 空间搜索引擎
# ──────────────────────────────────────────────


class FofaCollector(BaseCollector):
    """FOFA 空间搜索引擎（需要 email + API Key）。"""

    SOURCE = AssetSourceEnum.FOFA
    BASE_URL = "https://fofa.info"

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="fofa")
        records: List[AssetRecord] = []
        if not self.api_key:
            return records
        # api_key 格式: "email|key"
        parts = self.api_key.split("|") if isinstance(self.api_key, str) else ["", ""]
        email, key = parts[0], parts[-1]
        if not email or not key:
            return records
        import base64
        try:
            qbase64 = base64.b64encode(f'domain="{domain}"'.encode()).decode()
            resp = httpx.get(
                f"{self.BASE_URL}/api/v1/search/all",
                params={"email": email, "key": key, "qbase64": qbase64, "size": "100"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return records
            data = resp.json()
            if data.get("error", True):
                return records
            for item in data.get("results", []):
                if len(item) >= 2:
                    sub, ip = item[0], item[1] if len(item) > 1 else ""
                    records.append(AssetRecord(
                        value=sub, asset_type=AssetType.SUBDOMAIN,
                        source=self.SOURCE, ip=ip, tags=["fofa"],
                    ))
            _logger.info(f"FOFA: {domain} -> {len(records)} 条")
        except Exception as e:
            _logger.warn(f"FOFA 异常: {e}")
        return records


# ──────────────────────────────────────────────
# ICP备案查询
# ──────────────────────────────────────────────


class IcpCollector(BaseCollector):
    """ICP备案查询 — 查域名备案信息（免费，通过 beian.miit.gov.cn）。"""

    SOURCE = AssetSourceEnum.CUSTOM  # 使用 CUSTOM 源
    BASE_URL = "https://hlwicpfwc.miit.gov.cn"

    def collect(self, domain: str) -> List[AssetRecord]:
        records: List[AssetRecord] = []
        # R1 关隘：出站前必须 PASSIVE_QUERY 放行（fail-closed），与其他采集器一致
        if not _r1_pass(source="miit-icp"):
            return records
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/icpexternal/interface/icp/v1/tcpp/q/domain",
                params={"domain": domain},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if resp.status_code != 200:
                # Fallback: try the public query page
                return records
            data = resp.json()
            if data.get("code") == 200:
                for item in data.get("data", []):
                    records.append(AssetRecord(
                        value=f"ICP:{item.get('unitName','')}",
                        asset_type=AssetType.ORGANIZATION,
                        source=self.SOURCE,
                        source_extra=f"备案号:{item.get('mainLicence','')} 域名:{item.get('domain','')}",
                        tags=["icp"],
                    ))
            _logger.info(f"ICP: {domain} -> {len(records)} 条")
        except Exception:
            pass
        return records


# ──────────────────────────────────────────────
# 资产变化追踪 (工具函数，非采集器)
# ──────────────────────────────────────────────


def diff_reports(old: CollectReport, new: CollectReport) -> dict:
    """对比两次采集结果，返回新增/消失的资产。"""
    old_set = {(r.value, r.asset_type.value) for r in old.records}
    new_set = {(r.value, r.asset_type.value) for r in new.records}
    added = [r for r in new.records if (r.value, r.asset_type.value) not in old_set]
    removed = [r for r in old.records if (r.value, r.asset_type.value) not in new_set]
    return {
        "added": added,
        "removed": removed,
        "added_count": len(added),
        "removed_count": len(removed),
        "old_total": old.total_records,
        "new_total": new.total_records,
    }


# ──────────────────────────────────────────────
# 采集器工厂
# ──────────────────────────────────────────────

_COLLECTOR_REGISTRY: Dict[str, type] = {}


def register_collector(name: str, cls: type) -> None:
    _COLLECTOR_REGISTRY[name] = cls


def get_collector(name: str, **kwargs) -> BaseCollector:
    cls = _COLLECTOR_REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知采集器: {name}，可用: {list(_COLLECTOR_REGISTRY)}")
    return cls(**kwargs)


def all_collectors(**kwargs) -> List[str]:
    return list(_COLLECTOR_REGISTRY)


# 注册所有内置采集器
for _cls in [
    CrtshCollector, HackerTargetCollector, OTXCollector,
    URLScanCollector, SecurityTrailsCollector, HunterCollector, ReverseDnsCollector,
]:
    register_collector(_cls.SOURCE.value, _cls)
