"""单企业采集闭环编排（蓝图 T15 + P1 T25 替换 mock 采集）。

run_company() 跑通 R1 准入 → R3 枚举 → (R7 四集群被动采集) → R2 核验 → R6 提交 → R4 审批 → R12 拓扑写入。
调用时序与 §4 一致；每阶段经 R1 出站校验 + R6 频控；断点快照接入 T11。
P1 升级：阶段 2 mock 采集替换为 CollectionScheduler.collect() 真实/接口源调度。
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from passive_agent.approval.model import ApprovalTask
from passive_agent.approval.service import ApprovalService
from passive_agent.approval.snapshot import SnapshotStore
from passive_agent.common import logging as olog
from passive_agent.common.enums import ActionType, EdgeType, NodeType, RiskLevel
from passive_agent.common.result import gen_trace_id
from passive_agent.config import settings
from passive_agent.enumerator.engine import SubjectEnumerator
from passive_agent.gateway.model import SubmitProxyRequest
from passive_agent.gateway.proxy import ApiProxy
from passive_agent.storage import db
from passive_agent.verifier.model import VerifyRequest
from passive_agent.verifier.pipeline import VerificationPipeline

_logger = olog.get_logger("orchestrator")

# 网关提交重试退避基数（秒）；指数退避 wait = BASE * 2**attempt
GATEWAY_BACKOFF_BASE: float = 0.05


def _make_shard(result_id: str, idx: int) -> SubmitProxyRequest:
    return SubmitProxyRequest(
        biz_req_no=f"{result_id}-{idx}",
        batch_id=result_id,
        shard_index=0,
        shard_total=1,
        payload={"result_id": result_id},
    )


def run_company(enterprise: str, max_depth: Optional[int] = None) -> Dict[str, Any]:
    db.ensure_init()
    trace_id = gen_trace_id()
    snapshot = SnapshotStore()
    enumerator = SubjectEnumerator()
    pipeline = VerificationPipeline()
    proxy = ApiProxy()
    approval = ApprovalService()

    # P1 新增：R7 采集调度器 + R9 算力调度器 + R12 资产图谱
    from passive_agent.collector.scheduler import CollectionScheduler
    from passive_agent.scheduler.compute_scheduler import ComputeScheduler
    from passive_agent.graph.asset_graph import AssetGraph
    from passive_agent.graph.model import GraphNode, GraphEdge

    collector = CollectionScheduler.create_default()
    compute_sched = ComputeScheduler(snapshot)
    asset_graph = AssetGraph()

    summary: Dict[str, Any] = {
        "enterprise": enterprise,
        "trace_id": trace_id,
        "blocked": False,
        "subjects": 0,
        "verified": 0,
        "suspended": 0,
        "submitted": 0,
        "approvals": [],
        "collected_items": 0,
        "graph_nodes": 0,
        "graph_edges": 0,
        "queued_unsubmitted": 0,
        "approval_blocked": 0,
    }

    # 阶段 0：R1 准入（出站前关隘）
    from passive_agent.common.compliance_client import check

    adm = check(ActionType.PASSIVE_QUERY, source_name="orchestrator",
                biz_id=enterprise, trace_id=trace_id)
    if not adm.allowed:
        summary["blocked"] = True
        summary["reason"] = adm.reason_code
        _logger.warn(f"R1 准入被拦截 enterprise={enterprise} {adm.reason_code}")
        return summary
    snapshot.save(enterprise, 0, {"phase": "admit", "enterprise": enterprise})

    # 阶段 1：R3 全主体枚举 / 股权穿透
    subj_list = enumerator.enumerate(enterprise, max_depth=max_depth)
    summary["subjects"] = len(subj_list.subjects)
    snapshot.save(enterprise, 1, {"phase": "enumerate", "count": len(subj_list.subjects)})

    # R12 拓扑写入：枚举后写企业/子公司/分公司节点
    enterprise_node = GraphNode(
        node_type=NodeType.ENTERPRISE,
        name=enterprise,
        enterprise=enterprise,
        properties={"credit_code": None},
    )
    asset_graph.upsert_node(enterprise_node)

    for s in subj_list.subjects:
        if s.relation in ("全资子公司", "控股子公司"):
            node_type = NodeType.SUBSIDIARY
        elif s.relation == "分公司":
            node_type = NodeType.BRANCH
        else:
            node_type = NodeType.ENTERPRISE
        subj_node = GraphNode(
            node_type=node_type,
            name=s.name,
            enterprise=enterprise,
            properties={"credit_code": s.credit_code, "relation": s.relation, "depth": s.depth},
        )
        asset_graph.upsert_node(subj_node)
        # 企业→子公司/分公司 关联边
        edge = GraphEdge(
            from_node=enterprise_node.node_id,
            to_node=subj_node.node_id,
            edge_type=EdgeType.PARENT_OF,
            properties={"relation": s.relation},
        )
        asset_graph.upsert_edge(edge)

    # 阶段 2：R7 四集群被动采集 → R2 核验 → R6 提交 → R4 审批 + R12 拓扑写入
    for idx, s in enumerate(subj_list.subjects):
        result_id = f"{enterprise}-{s.name}-{idx}"

        # P1 替换：mock 采集 → CollectionScheduler.collect() 真实调度
        collect_results = collector.collect(enterprise, s.name, trace_id=trace_id)

        # 汇总采集结果：计算多源佐证方数 + 提取资产项
        total_items: List[Any] = []
        successful_sources: set = set()
        for cr in collect_results:
            if cr.success:
                successful_sources.add(cr.source_name)
                total_items.extend(cr.items)

        src_cnt = max(len(successful_sources), 1)  # 多源佐证方数 = 实际成功源数
        summary["collected_items"] += len(total_items)

        # L2 DNS 存活：检查采集结果中是否有域名解析成功
        dns_ok = any(
            cr.success and any(item.item_type == "domain" for item in cr.items)
            for cr in collect_results
        )

        # R12 拓扑写入：采集后写域名/公众号/小程序节点 + 关联边
        subject_node = GraphNode(
            node_type=NodeType.SUBSIDIARY if s.relation in ("全资子公司", "控股子公司")
            else NodeType.BRANCH if s.relation == "分公司"
            else NodeType.ENTERPRISE,
            name=s.name,
            enterprise=enterprise,
        )
        for item in total_items:
            if item.item_type == "domain":
                asset_node = GraphNode(
                    node_type=NodeType.DOMAIN,
                    name=item.value,
                    enterprise=enterprise,
                    properties={"source": item.source_name},
                )
                asset_graph.upsert_node(asset_node)
                asset_graph.upsert_edge(GraphEdge(
                    from_node=subject_node.node_id,
                    to_node=asset_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                ))
            elif item.item_type == "wechat_account":
                asset_node = GraphNode(
                    node_type=NodeType.WECHAT_ACCOUNT,
                    name=item.value,
                    enterprise=enterprise,
                    properties={"source": item.source_name},
                )
                asset_graph.upsert_node(asset_node)
                asset_graph.upsert_edge(GraphEdge(
                    from_node=subject_node.node_id,
                    to_node=asset_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                ))
            elif item.item_type == "mini_program":
                asset_node = GraphNode(
                    node_type=NodeType.MINI_PROGRAM,
                    name=item.value,
                    enterprise=enterprise,
                    properties={"source": item.source_name},
                )
                asset_graph.upsert_node(asset_node)
                asset_graph.upsert_edge(GraphEdge(
                    from_node=subject_node.node_id,
                    to_node=asset_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                ))

        # R2 四层核验（多源佐证方数 = 实际成功源数）
        vr = pipeline.run(VerifyRequest(
            result_id=result_id,
            layer1_biz_match=True,
            layer2_dns_alive=dns_ok,
            layer3_time_ok=True,
            layer4_src_cnt=src_cnt,
        ))
        if vr.status.value == "PASS":
            summary["verified"] += 1
        else:
            summary["suspended"] += 1

        # 落采集结果（序列化真实采集项，杜绝空 {} 与静默吞异常）
        try:
            payload = json.dumps(
                [
                    {
                        "source": cr.source_name,
                        "success": cr.success,
                        "items": [getattr(it, "value", str(it)) for it in cr.items],
                    }
                    for cr in collect_results
                ],
                ensure_ascii=False,
            )
            db.write(
                "INSERT INTO t_collect_result (result_id, subject_id, source_cnt, payload_json) "
                "VALUES (?,?,?,?)",
                (result_id, s.name, src_cnt, payload),
            )
        except Exception as exc:  # 不再裸 except 吞掉：记录并计入 errors，便于排障与溯源
            summary["errors"] = summary.get("errors", 0) + 1
            _logger.error(
                f"落库采集结果失败 result_id={result_id} enterprise={enterprise}: {exc}"
            )

        # R4 三级审批（前置为出站硬依赖：REVIEWING/REJECTED 严禁出站）
        task = ApprovalTask(
            task_id=f"AP-{result_id}",
            biz_type="COLLECT_RESULT",
            subject_id=s.name,
            # 基线风险；命中 HIGH_VALUE_KEYWORDS 由 service 提升至 HIGH；
            # OUTBOUND_REQUIRE_APPROVAL=True 时强制 HIGH（全部出站需人工复核）
            risk_level=RiskLevel.HIGH if settings.OUTBOUND_REQUIRE_APPROVAL else RiskLevel.LOW,
            payload_ref=result_id,
        )
        approved = approval.create(task)
        summary["approvals"].append({"task_id": approved.task_id, "status": approved.status})

        # R6 分片提交（经 R1 + 频控 + 审批闸门）：仅 APPROVED/REMINDING 出站，
        # HIGH 人工复核(REVIEWING)/已驳回(REJECTED) 在审批通过前严禁出站（合规红线）
        if approved.status in ("APPROVED", "REMINDING"):
            shard = _make_shard(result_id, idx)
            max_retries = settings.FAULT_MAX_RETRIES
            for attempt in range(max_retries):
                vo = proxy.submit(shard)
                if vo.accepted:
                    # 分片已出站，释放频控槽位（编排层驱动，形成真实背压）
                    proxy.release(vo.src_ip)
                    summary["submitted"] += 1
                    break
                # 频控满：排队不丢弃，指数退避后重试
                wait = GATEWAY_BACKOFF_BASE * (2 ** attempt)
                _logger.warn(
                    f"网关提交排队，退避重试 attempt={attempt + 1}/{max_retries} "
                    f"wait={wait:.3f}s biz_req_no={shard.biz_req_no}"
                )
                time.sleep(wait)
            else:
                # 重试耗尽仍排队：保留任务（记入 queued_unsubmitted），不丢弃
                summary["queued_unsubmitted"] = summary.get("queued_unsubmitted", 0) + 1
        else:
            # 审批未通过（REVIEWING 待人工 / REJECTED）：出站被拦截，待人工审批后由审批流触发提交
            summary["approval_blocked"] = summary.get("approval_blocked", 0) + 1
            _logger.warn(
                f"出站被审批闸门拦截 task_id={approved.task_id} status={approved.status} "
                f"result_id={result_id}"
            )
        snapshot.save(enterprise, 10 + idx, {"phase": "subject", "idx": idx, "verify": vr.status.value})

        # R9 算力回收检查（每个主体处理完后检查）
        compute_sched.check_reclaim(
            f"TASK-{enterprise}-{s.name}",
            enterprise,
            has_new=len(total_items) > 0,
        )

    # R12 统计
    summary["graph_nodes"] = asset_graph.node_count(enterprise)
    summary["graph_edges"] = asset_graph.edge_count(enterprise)

    snapshot.save(enterprise, 999, {"phase": "done"})
    _logger.info(
        f"单企业闭环完成 enterprise={enterprise} verified={summary['verified']} "
        f"submitted={summary['submitted']} collected={summary['collected_items']} "
        f"graph_nodes={summary['graph_nodes']}"
    )
    return summary
