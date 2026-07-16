"use strict";

const $ = (id) => document.getElementById(id);
const api = (path, opts) => fetch("/api/v1" + path, opts);

function log(msg) {
  const el = $("log");
  const ts = new Date().toISOString().slice(11, 19);
  el.textContent = `[${ts}] ${msg}\n` + el.textContent;
}

function statusPill(s) {
  const map = { APPROVED: "ok", REVIEWING: "warn", REMINDING: "warn", REJECTED: "bad", PENDING: "warn" };
  const cls = map[s] || "warn";
  return `<span class="pill ${cls}">${s}</span>`;
}

function riskPill(r) {
  const map = { HIGH: "bad", MID: "warn", LOW: "ok" };
  return `<span class="pill ${map[r] || "warn"}">${r}</span>`;
}

async function refresh() {
  try {
    const [inv, quota] = await Promise.all([
      api("/inventory/proof").then((r) => r.json()),
      api("/gateway/quota").then((r) => r.json()),
    ]);
    const ratio = inv.data.ratio;
    $("selfdev").textContent = (ratio.self_dev_pct ?? "—") + "%";
    $("oss").textContent = (ratio.open_source_pct ?? "—") + "%";
    const q = quota.data;
    const pct = q.usage_pct ?? 0;
    $("usage").textContent = pct + "%";
    $("used").textContent = `${q.used}/${q.limit}`;
    $("queued").textContent = q.queued;
    const bar = $("usageBar");
    bar.style.width = Math.min(pct, 100) + "%";
    bar.className = pct > 95 ? "bad" : pct > 80 ? "warn" : "";
    log("态势刷新：频控 " + pct + "% · 自研 " + ratio.self_dev_pct + "%");
    await loadQueue();
  } catch (e) {
    log("刷新失败：" + e.message);
  }
}

async function loadQueue() {
  const res = await api("/approval/queue").then((r) => r.json());
  const tb = $("queueTbl").querySelector("tbody");
  tb.replaceChildren();
  (res.data || []).forEach((t) => {
    const tr = document.createElement("tr");
    const tdId = document.createElement("td");
    tdId.textContent = t.task_id ?? "";
    const tdRisk = document.createElement("td");
    tdRisk.innerHTML = riskPill(t.risk_level); // 受控枚举值，安全
    const tdStatus = document.createElement("td");
    tdStatus.innerHTML = statusPill(t.status); // 受控枚举值，安全
    const tdSubject = document.createElement("td");
    tdSubject.textContent = t.subject_id || "—";
    const tdActions = document.createElement("td");
    ["APPROVE", "REVIEW", "REJECT"].forEach((action) => {
      const btn = document.createElement("button");
      btn.className = "sec";
      btn.textContent = action === "APPROVE" ? "通过" : action === "REVIEW" ? "复核" : "驳回";
      btn.addEventListener("click", () => decide(t.task_id, action));
      tdActions.appendChild(btn);
      tdActions.appendChild(document.createTextNode(" "));
    });
    tr.append(tdId, tdRisk, tdStatus, tdSubject, tdActions);
    tb.appendChild(tr);
  });
}

async function decide(taskId, action) {
  await api("/approval/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, action, risk_level: "LOW", operator: "web" }),
  });
  log(`审批 ${taskId} -> ${action}`);
  await refresh();
}

async function runCompany() {
  const ent = $("ent").value.trim();
  if (!ent) { log("请先输入企业全称"); return; }
  $("loopOut").style.display = "block";
  $("loopOut").textContent = "运行中…";
  log("启动单企业闭环：" + ent);
  try {
    const res = await api("/console/run-company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enterprise: ent, max_depth: 3 }),
    }).then((r) => r.json());
    const d = res.data || {};
    const out = document.createElement("div");
    const line1 = document.createElement("div");
    line1.append("企业：");
    const ent = document.createElement("b");
    ent.textContent = d.enterprise ?? "—";
    line1.append(ent);
    const line2 = document.createElement("div");
    line2.append("主体数：");
    const s1 = document.createElement("b"); s1.textContent = d.subjects ?? 0; line2.append(s1);
    line2.append(" · 核验通过：");
    const s2 = document.createElement("b"); s2.textContent = d.verified ?? 0; line2.append(s2);
    line2.append(" · 挂起：");
    const s3 = document.createElement("b"); s3.textContent = d.suspended ?? 0; line2.append(s3);
    const line3 = document.createElement("div");
    line3.append("提交成功：");
    const s4 = document.createElement("b"); s4.textContent = d.submitted ?? 0; line3.append(s4);
    line3.append(" · 审批任务：");
    const s5 = document.createElement("b"); s5.textContent = (d.approvals || []).length; line3.append(s5);
    out.append(line1, line2, line3);
    $("loopOut").replaceChildren(out);
    log(`闭环完成：${d.subjects} 主体 / ${d.verified} 通过 / ${d.submitted} 提交`);
  } catch (e) {
    $("loopOut").textContent = "运行失败：" + e.message;
    log("闭环失败：" + e.message);
  }
  await refresh();
}

window.decide = decide;
window.runCompany = runCompany;
window.refresh = refresh;

// ===== P1 新增：M5/M6 渲染 + 5min 自动刷新 =====

async function loadMetrics() {
  try {
    const res = await api("/metrics/snapshot").then((r) => r.json());
    const d = res.data || {};
    // M2 深化：WNSR
    const wnsr = d.wnsr ?? 0;
    $("wnsr").textContent = wnsr.toFixed(1) + "%";
    const wbar = $("wnsrBar");
    wbar.style.width = Math.min(wnsr, 100) + "%";
    wbar.className = wnsr > 80 ? "" : wnsr > 50 ? "warn" : "bad";
    // A/B/C 占比
    const cr = d.compute_ratio || {};
    $("ratioA").textContent = (cr.A ?? 60) + "%";
    $("ratioB").textContent = (cr.B ?? 30) + "%";
    $("ratioC").textContent = (cr.C ?? 10) + "%";
    // 6 项指标
    $("mCoverage").textContent = (d.coverage ?? 0).toFixed(1) + "%";
    $("mAccuracy").textContent = (d.accuracy ?? 0).toFixed(1) + "%";
    $("mInvalid").textContent = (d.invalid_rate ?? 0).toFixed(1) + "%";
    $("mSched").textContent = (d.schedule_efficiency ?? 0).toFixed(1) + "%";
    $("mCompliance").textContent = (d.compliance_rate ?? 100).toFixed(0) + "%";
    $("mApi").textContent = (d.api_efficiency ?? 0).toFixed(1) + "%";
    // 红线状态
    $("rViolations").textContent = d.violations ?? 0;
    $("rBans").textContent = d.bans ?? 0;
    $("rFreq").textContent = (d.freq_buffer_pct ?? 0).toFixed(1) + "%";
    const isRed = (d.violations > 0) || (d.bans > 0) || ((d.freq_buffer_pct ?? 0) > 95);
    $("redlinePill").className = "pill " + (isRed ? "bad" : "ok");
    $("redlinePill").textContent = isRed ? "红线告警" : "绿区";
  } catch (e) {
    log("度量加载失败：" + e.message);
  }
}

async function loadFaultLog() {
  try {
    const res = await api("/metrics/fault-events").then((r) => r.json());
    const tb = $("faultTbl").querySelector("tbody");
    tb.innerHTML = "";
    (res.data || []).forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${(e.ts || "").slice(0, 19)}</td>` +
        `<td>${e.source || "—"}</td>` +
        `<td>${e.action || "—"}</td>` +
        `<td>${e.decision || "—"}</td>` +
        `<td>${e.reason_code || "—"}</td>` +
        `<td>${(e.msg || "").slice(0, 80)}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) {
    log("容错日志加载失败：" + e.message);
  }
}

async function loadConsoleOverview() {
  try {
    const res = await api("/console/metrics-overview").then((r) => r.json());
    const d = res.data || {};
    // 回收事件
    const reclaimTbl = $("reclaimTbl").querySelector("tbody");
    if (reclaimTbl) {
      reclaimTbl.innerHTML = "";
      const events = (d.metrics && d.metrics.fault_events) || [];
      events.filter((e) => e.reason_code === "030001").forEach((e) => {
        const tr = document.createElement("tr");
        tr.innerHTML =
          `<td>${e.source || e.task_id || "—"}</td>` +
          `<td>${e.enterprise || e.subject_id || "—"}</td>` +
          `<td>${e.idle_minutes ?? "—"}</td>` +
          `<td>${e.snapshot_saved ? "是" : "—"}</td>` +
          `<td>${(e.reclaimed_at || e.ts || "").slice(0, 19)}</td>`;
        reclaimTbl.appendChild(tr);
      });
    }
  } catch (e) {
    // 静默
  }
}

async function refreshAll() {
  await Promise.all([refresh(), loadMetrics(), loadFaultLog(), loadConsoleOverview()]);
}

// 5 分钟自动刷新（与 R9 看榜节奏对齐）
setInterval(refreshAll, 300000);

(async () => {
  const h = await api("/health").then((r) => r.json()).catch(() => null);
  $("health").textContent = h ? "● 在线" : "● 离线";
  $("health").className = "pill " + (h ? "ok" : "bad");
  await refresh();
})();
