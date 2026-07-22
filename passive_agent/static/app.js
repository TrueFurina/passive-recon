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

// ===== 页面切换 =====
function switchPage(name, el) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  document.querySelectorAll("header nav a").forEach(a => a.classList.remove("active"));
  if (el) el.classList.add("active");
  if (name === "assets") { loadEnterprises(); loadAssetSources(); loadAssets(); }
  if (name === "risks") { loadEnterprises(); loadRisks(); }
}
window.switchPage = switchPage;

// ===== 资产浏览 =====
let _debounceTimer = null;
function debounceLoad() {
  clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(() => loadAssets(), 400);
}
window.debounceLoad = debounceLoad;

/** 填充下拉框的通用函数 */
function _populateSelect(selectId, items, valueKey, labelKey, selectedValue, showCount) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = '<option value="">全部</option>';
  (items || []).forEach(item => {
    const opt = document.createElement("option");
    opt.value = item[valueKey];
    const label = showCount ? `${item[labelKey]} (${item.count})` : item[labelKey];
    opt.textContent = label;
    if (opt.value === selectedValue) opt.selected = true;
    sel.appendChild(opt);
  });
}

async function loadEnterprises() {
  try {
    const res = await api("/assets/enterprises").then(r => r.json());
    const list = res.data.enterprises || [];
    _populateSelect("filterEnterprise", list, "enterprise", "enterprise",
      document.getElementById("filterEnterprise").value, true);
    _populateSelect("riskEnterprise", list, "enterprise", "enterprise",
      document.getElementById("riskEnterprise").value, false);
  } catch (e) { console.log("loadEnterprises:", e.message); }
}

async function loadAssetSources() {
  try {
    const res = await api("/assets/list?limit=1").then(r => r.json());
    const sources = new Set();
    if (res.data && res.data.assets) {
      res.data.assets.forEach(a => { if (a.source_name) sources.add(a.source_name); });
    }
    const sel = document.getElementById("filterSource");
    sel.innerHTML = '<option value="">全部</option>';
    sources.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s; opt.textContent = s; sel.appendChild(opt);
    });
  } catch (e) { console.log("loadAssetSources:", e.message); }
}

let _assetPage = 0;
const _assetLimit = 50;

async function loadAssets() {
  try {
    const enterprise = $("filterEnterprise").value;
    const type = $("filterType").value;
    const source = $("filterSource").value;
    const search = $("searchAsset").value.trim();
    const params = new URLSearchParams({ limit: _assetLimit, offset: _assetPage * _assetLimit });
    if (enterprise) params.set("enterprise", enterprise);
    if (type) params.set("asset_type", type);
    if (source) params.set("source", source);
    if (search) params.set("search", search);

    const res = await api("/assets/list?" + params.toString()).then(r => r.json());
    const data = res.data || {};
    const assets = data.assets || [];
    const total = data.total || 0;

    $("assetCount").textContent = `共 ${total} 条资产 (显示 ${_assetPage * _assetLimit + 1}-${Math.min((_assetPage + 1) * _assetLimit, total)})`;

    const tb = $("assetTbl").querySelector("tbody");
    tb.innerHTML = "";
    assets.forEach(a => {
      const tr = document.createElement("tr");
      const typeBadge = a.asset_type === "subdomain" ? "badge subdomain"
        : a.asset_type === "ip" ? "badge ip"
        : a.asset_type === "port" ? "badge port"
        : a.asset_type === "organization" ? "badge org" : "";
      tr.innerHTML =
        `<td>${a.asset_value || "—"}</td>` +
        `<td>${typeBadge ? `<span class="${typeBadge}">${a.asset_type}</span>` : a.asset_type || "—"}</td>` +
        `<td>${a.enterprise || "—"}</td>` +
        `<td>${a.ip || "—"}</td>` +
        `<td>${a.port || "—"}</td>` +
        `<td>${a.source_name || "—"}</td>`;
      tb.appendChild(tr);
    });

    // 分页
    const pag = $("assetPagination");
    const totalPages = Math.ceil(total / _assetLimit);
    pag.innerHTML = `
      <button class="sec" onclick="prevPage()" ${_assetPage === 0 ? "disabled" : ""}>← 上一页</button>
      <span>第 ${_assetPage + 1}/${totalPages} 页</span>
      <button class="sec" onclick="nextPage()" ${_assetPage >= totalPages - 1 ? "disabled" : ""}>下一页 →</button>
    `;
  } catch (e) { console.log("loadAssets:", e.message); }
}

function prevPage() { if (_assetPage > 0) { _assetPage--; loadAssets(); } }
function nextPage() { _assetPage++; loadAssets(); }
window.prevPage = prevPage;
window.nextPage = nextPage;

// ===== 风险页 =====
async function loadRiskEnterprises() {
  try {
    const res = await api("/assets/enterprises").then(r => r.json());
    const sel = $("riskEnterprise");
    const cur = sel.value;
    sel.innerHTML = '<option value="">所有企业</option>';
    (res.data.enterprises || []).forEach(e => {
      const opt = document.createElement("option");
      opt.value = e.enterprise;
      opt.textContent = e.enterprise;
      if (opt.value === cur) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) { console.log("loadRiskEnterprises:", e.message); }
}

async function loadRisks() {
  try {
    const enterprise = $("riskEnterprise").value;
    const params = new URLSearchParams();
    if (enterprise) params.set("enterprise", enterprise);
    // 从资产列表查询风险
    params.set("search", "risk");
    params.set("limit", "100");
    const res = await api("/assets/list?" + params.toString()).then(r => r.json());
    const assets = (res.data && res.data.assets) || [];

    const tb = $("riskTbl").querySelector("tbody");
    tb.innerHTML = "";
    assets.forEach(a => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${a.enterprise || "—"}</td>` +
        `<td>${a.asset_value || "—"}</td>` +
        `<td>${a.ip || "—"}</td>` +
        `<td>${a.source_name || "—"}</td>` +
        `<td>${a.title || "—"}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) { console.log("loadRisks:", e.message); }
}
window.loadRisks = loadRisks;

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
