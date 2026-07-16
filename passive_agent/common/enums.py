"""跨文件共享枚举（蓝图 §7）。"""
from __future__ import annotations

from enum import Enum


class ActionType(str, Enum):
    PASSIVE_QUERY = "PASSIVE_QUERY"   # 被动查询（放行 + 白名单打标）
    ACTIVE_SCAN = "ACTIVE_SCAN"       # 端口扫描 / 域传送（拦截）
    ACTIVE_HTTP = "ACTIVE_HTTP"       # 主动 HTTP 探测（拦截）
    TCP_SEND = "TCP_SEND"             # 主动 TCP 发包（拦截）


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class RiskLevel(str, Enum):
    LOW = "LOW"     # 低危：自动入库
    MID = "MID"     # 中危：入库 + 提醒
    HIGH = "HIGH"    # 高价值工控/政务：人工复核


class VerifyStatus(str, Enum):
    PASS = "PASS"
    SUSPEND = "SUSPEND"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVIEWING = "REVIEWING"
    REMINDING = "REMINDING"


# ===== P1 增量枚举（追加，不覆盖 P0 枚举）=====


class CollectorCluster(str, Enum):
    """四类被动采集集群（R7）。"""
    WEB = "WEB"                    # Web 域名/子域名集群
    WECHAT = "WECHAT"              # 公众号集群
    MINIAPP = "MINIAPP"            # 小程序集群
    EQUITY = "EQUITY"              # 工商股权集群


class SourceHealth(str, Enum):
    """源健康状态（R8 容错降级）。"""
    HEALTHY = "HEALTHY"            # 健康
    DEGRADED = "DEGRADED"          # 连续失败 1-2 次，降级
    UNAVAILABLE = "UNAVAILABLE"    # 连续失败 ≥3 次，不可用


class TaskState(str, Enum):
    """采集任务状态机（R7 调度内核）。"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"        # 全源不可用挂起
    COMPLETED = "COMPLETED"
    RECLAIMED = "RECLAIMED"        # 算力回收


class NodeType(str, Enum):
    """R12 资产图谱节点类型（兼容 Neo4j label 迁移）。"""
    ENTERPRISE = "ENTERPRISE"
    SUBSIDIARY = "SUBSIDIARY"
    BRANCH = "BRANCH"
    DOMAIN = "DOMAIN"
    WECHAT_ACCOUNT = "WECHAT_ACCOUNT"
    MINI_PROGRAM = "MINI_PROGRAM"


class EdgeType(str, Enum):
    """R12 资产图谱关系类型（兼容 Neo4j relationship type 迁移）。"""
    OWNS = "OWNS"                  # 持股关系
    RESOLVES_TO = "RESOLVES_TO"    # 域名解析
    BELONGS_TO = "BELONGS_TO"      # 资产归属
    PARENT_OF = "PARENT_OF"        # 母子公司
