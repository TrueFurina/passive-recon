"""R1 合规引擎：所有出站动作的统一关隘（fail-closed）。

- 主动动作（ACTIVE_SCAN/ACTIVE_HTTP/TCP_SEND）一律 BLOCK + 010001 + 审计 + 任务置 BLOCKED。
- PASSIVE_QUERY + 白名单被动源 → ALLOW 并打 source_tag。
- 未知动作默认拦截（fail-closed）。
- 规则可从 t_compliance_rule 加载（内存默认集 + DB 重载）。
"""
from __future__ import annotations

import ipaddress
import socket
import threading
from typing import List, Optional
from urllib.parse import urlparse

from passive_agent.common import logging as clog
from passive_agent.common.enums import ActionType, Decision
from passive_agent.compliance.model import ComplianceCheckRequest, ComplianceDecision
from passive_agent.config import settings
from passive_agent.compliance.rules import ACTIVE_ACTIONS, Rule, default_rules

_logger = clog.get_logger("compliance")

# 主动动作字符串值集合（硬编码兜底，不依赖 DB）
ACTIVE_VALUES = {a.value for a in ACTIVE_ACTIONS}
PASSIVE_VALUE = ActionType.PASSIVE_QUERY.value


class ComplianceEngine:
    def __init__(self) -> None:
        self._rules: List[Rule] = []
        self._lock = threading.Lock()
        self.reload_rules()

    def reload_rules(self) -> None:
        """从内存默认集 + 数据库 t_compliance_rule 重新加载规则。"""
        rules = default_rules()
        try:
            from passive_agent.storage import db

            rows = db.query(
                "SELECT rule_name, action_type, decision, reason_code, enabled "
                "FROM t_compliance_rule WHERE deleted=0"
            )
            for r in rows:
                try:
                    rules.append(
                        Rule(
                            name=r["rule_name"],
                            action_type=ActionType(r["action_type"]),
                            decision=Decision(r["decision"]),
                            reason_code=r["reason_code"] or "000000",
                            enabled=bool(r["enabled"]),
                        )
                    )
                except Exception:
                    continue
        except Exception:
            # DB 未就绪时使用默认集，不阻塞
            pass
        with self._lock:
            self._rules = rules

    def check(self, req: ComplianceCheckRequest, trace_id: Optional[str] = None) -> ComplianceDecision:
        # 1) 主动动作：架构红线，物理不可达的拦截
        if req.action_type in ACTIVE_VALUES:
            decision = ComplianceDecision(
                allowed=False,
                decision=Decision.BLOCK,
                reason_code="010001",
                rule_hit="active-block",
                reason="主动动作被架构红线拦截",
            )
            self._audit(decision, req, trace_id)
            return decision

        # 2) 白名单被动放行（来源规则可经 DB 扩展）
        with self._lock:
            rules = list(self._rules)
        allow_actions = {
            r.action_type.value for r in rules if r.enabled and r.decision == Decision.ALLOW
        }
        if req.action_type == PASSIVE_VALUE or req.action_type in allow_actions:
            # F-5 修复：即便动作被放行，仍须校验出站目标（target_url），
            # 杜绝"动作白名单但目标指向内网/非 HTTPS"的 SSRF 短板。
            if req.target_url:
                ok_egress, reason = _validate_egress(req.target_url)
                if not ok_egress:
                    decision = ComplianceDecision(
                        allowed=False,
                        decision=Decision.BLOCK,
                        reason_code="010002",
                        rule_hit="egress-block",
                        reason=reason,
                    )
                    self._audit(decision, req, trace_id)
                    return decision
            decision = ComplianceDecision(
                allowed=True,
                decision=Decision.ALLOW,
                reason_code="000000",
                rule_hit="allow-passive-query",
                reason="被动查询白名单放行",
            )
            self._audit(decision, req, trace_id)
            return decision

        # 3) 默认 fail-closed：未知动作一律拦截
        decision = ComplianceDecision(
            allowed=False,
            decision=Decision.BLOCK,
            reason_code="010001",
            rule_hit="default-fail-closed",
            reason="未知动作默认拦截(fail-closed)",
        )
        self._audit(decision, req, trace_id)
        return decision

    def _audit(self, decision: ComplianceDecision, req: ComplianceCheckRequest, trace_id: Optional[str]) -> None:
        try:
            from passive_agent import audit

            audit.log(
                trace_id=trace_id,
                action=req.action_type,
                source=req.source_name,
                decision=decision.decision.value,
                reason_code=decision.reason_code,
                msg=f"R1 合规判定: {decision.reason}",
            )
        except Exception:
            pass


def _is_private_ip(ip: str) -> bool:
    """判定 IP 是否为私网/回环/链路本地/保留地址（防 SSRF 到内网）。"""
    try:
        obj = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return obj.is_private or obj.is_loopback or obj.is_link_local or obj.is_reserved


def _validate_egress(target_url: str) -> "tuple[bool, str]":
    """出站目标安全校验（F-5）。

    始终执行：① 仅允许 HTTPS；② 拒绝解析到的内网/链路本地/保留地址（SSRF 防护）。
    当 settings.EGRESS_ENFORCE=True 且 EGRESS_IPS 非空（非通配）时，额外要求目标主机
    命中白名单（支持精确 IP / CIDR / 域名字符串）。
    返回 (是否放行, 拒绝原因)。
    """
    try:
        parsed = urlparse(target_url)
    except Exception:
        return False, "target_url 解析失败"
    if parsed.scheme.lower() != "https":
        return False, f"仅允许 HTTPS 出站，拒绝 scheme={parsed.scheme}"
    host = parsed.hostname
    if not host:
        return False, "target_url 缺少 host"

    # 解析主机到 IP，逐个判定私网/链路本地
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False, f"无法解析目标主机 {host}"
    for info in infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            return False, f"拒绝内网/链路本地出站目标 {ip}"

    # 白名单强制模式（可选）
    egress = [e.strip() for e in settings.EGRESS_IPS if e and e.strip()]
    if settings.EGRESS_ENFORCE and egress and not any(
        e in ("*", "0.0.0.0/0", "::/0") for e in egress
    ):
        allowed_nets = []
        for e in egress:
            try:
                allowed_nets.append(ipaddress.ip_network(e, strict=False))
            except ValueError:
                allowed_nets.append(e)  # 域名字符串，走下方字符串比对
        hit = host in egress
        if not hit:
            for info in infos:
                ip = info[4][0]
                for n in allowed_nets:
                    if isinstance(n, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                        try:
                            if ipaddress.ip_address(ip) in n:
                                hit = True
                                break
                        except ValueError:
                            continue
                    elif isinstance(n, str) and n == ip:
                        hit = True
                        break
                if hit:
                    break
        if not hit:
            return False, f"目标 {host} 不在出站白名单 EGRESS_IPS 内"
    return True, ""


_engine: Optional[ComplianceEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> ComplianceEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ComplianceEngine()
    return _engine
