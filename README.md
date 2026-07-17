# 🕵️ Passive Recon — Enterprise OSINT/EASM/CTEM Agent

> **Zero-touch, purely passive external asset discovery platform**
>
> No probes sent to targets. No logs generated on their side. Just 15+ public data sources cross-validated.

[![CI](https://github.com/TrueFurina/passive-recon/actions/workflows/ci.yml/badge.svg)](https://github.com/TrueFurina/passive-recon/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/TrueFurina/passive-recon/pulls)

[🇨🇳 中文版](./README.zh-CN.md)

---

## 🌟 What is Passive Recon?

Passive Recon is a **purely passive** OSINT/EASM/CTEM platform that discovers an organization's external assets by querying **15+ public data sources** — certificate transparency logs, DNS records, search engines, network mapping, GitHub, Wayback Machine, and more — **without ever touching the target's systems**.

**One command, any target:**
```bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
python cli.py collect --domain example.com "Acme Corp"
```

The system auto-infers the target domain, runs all 15 sources in parallel, and produces a comprehensive asset report with risk findings.

---

## ✨ Features

| Capability | Description |
|------------|-------------|
| **Passive Asset Discovery** | 15+ cross-validated data sources, auto domain inference |
| **Subdomain Enumeration** | crt.sh, HackerTarget, URLScan, Wayback, DNSDumpster, and more |
| **IP & Port Mapping** | C-segment clustering, exposed port detection |
| **Risk Detection** | VPN exposure, OA systems, weak ciphers, known vulnerabilities |
| **Compliance Guardrail** | R1 compliance check on every outbound call — fail-closed |
| **Rate Limiting** | Per-IP sliding window ≤95%, queue never drops tasks |
| **Approval Workflow** | High-risk outbound requires manual approval |
| **Audit Trail** | Full operation audit log |
| **Static Guard** | CI scan that blocks active-scan code from entering production |
| **Web Dashboard** | `python cli.py serve` — one-click panel |
| **Scheduled Tasks** | `python cli.py schedule --targets targets.txt` — daily auto-collection |
| **Auto-save Reports** | Markdown report saved to `data/report_<target>_<domain>.md` |

---

## 📡 Data Sources

| Source | Key Required | Type |
|--------|-------------|------|
| **crt.sh** | ❌ Free | Certificate Transparency |
| **HackerTarget** | ❌ Free | DNS / Subdomain |
| **URLScan.io** | ❌ Free | Historical Snapshots |
| **AlienVault OTX** | ❌ Free | Passive DNS / Threat Intel |
| **Wayback Machine** | ❌ Free | Historical URLs / Subdomains |
| **DNSDumpster** | ❌ Free | DNS Mapping / MX/NS Records |
| **CommonCrawl** | ❌ Free | Web Crawl Archive |
| **GitHub** | ❌ Free (rate-limited) | Code Leak Search |
| **Hunter (Yingtu)** | ✅ Required | Network Space Mapping |
| **FOFA** | ✅ Required | Network Space Search |
| **SecurityTrails** | ✅ Required | Subdomain / Passive DNS |
| **Shodan** | ✅ Required | Internet Device Search |
| **VirusTotal** | ✅ Required | Passive DNS / Subdomain |
| **ZoomEye** | ✅ Required | Network Space Mapping |
| **Qichacha** | ✅ Required | Chinese Enterprise Registry |

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys (choose one)

**Option A: Environment Variables** (recommended — never written to disk)
```bash
# Linux / macOS
export PASSIVE_API_KEYS='{"hunter":["key1","key2"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'

# Windows PowerShell
$json='{"hunter":["key1","key2"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'
[Environment]::SetEnvironmentVariable('PASSIVE_API_KEYS', $json, 'User')
```

**Option B: config.json**
```bash
cp config.example.json config.json
# Edit config.json with your keys
```

### 3. Run Asset Discovery
```bash
# One-shot: any target, auto domain inference
python cli.py collect "Tsinghua University"
python cli.py collect --domain example.com "Acme Corp"

# Batch mode
python cli.py batch targets.txt

# One-click web dashboard
python cli.py serve

# Daily scheduled collection (2:00 AM)
python cli.py schedule --targets targets.txt
```

---

## 📊 Sample Output

After running `python cli.py collect "Tsinghua University"`:

```
🎯 目标: Tsinghua University
🌐 自动推断域名: tsinghua.edu.cn

# Tsinghua University 被动资产收集报告
> 主域: tsinghua.edu.cn | 数据源: 15 sources
> 总数: 285

## 📊 资产总览
| 类型 | 数量 |
|------|------|
| subdomain | 270 |
| IP 地址 | 178 |
| 端口 | 2 |
| **合计** | **285** |

## 🚨 风险发现
- 🔴 [P1] VPN 入口暴露: vpn.tsinghua.edu.cn
- 🔴 [P1] WebVPN 远程接入暴露: webvpn.tsinghua.edu.cn
```

---

## 🔧 Environment Variables

| Variable | Type | Description | Required |
|----------|------|-------------|----------|
| `PASSIVE_API_KEYS` | JSON string | Data source API keys (see below) | ✅ For some sources |
| `PASSIVE_API_TOKENS` | Comma-separated | REST API auth tokens | Optional |
| `PASSIVE_API_KEY` | String | Single token fallback | Optional |
| `PASSIVE_DB_PATH` | Path | SQLite path (default: `data/agent.db`) | Optional |
| `PASSIVE_LOG_PATH` | Path | Audit log path (default: `data/audit.jsonl`) | Optional |
| `PASSIVE_PII_SALT` | String | PII de-identification salt | Optional |
| `PASSIVE_PII_KEY` | String | PII encryption key | Optional |

### API Key JSON Format
```json
{
  "hunter": ["key1", "key2"],
  "qichacha": {
    "app_key": "your_app_key",
    "secret_key": "your_secret_key"
  },
  "shodan": "your_shodan_key",
  "virustotal": "your_vt_key",
  "zoomeye": "your_zoomeye_key"
}
```

---

## 📁 Project Structure

```
├── cli.py                          ← CLI entry point (one command to rule them all)
├── config.example.json             ← Config template
├── requirements.txt                ← Python dependencies
│
├── passive_agent/                  ← 🎯 Core source
│   ├── main.py                     ← FastAPI app + dashboard API
│   ├── config.py                   ← Config loader (env > config.json)
│   ├── api/                        ← REST API routes
│   ├── collector/                  ← 15 passive data source collectors
│   ├── enumerator/                 ← Subject enumeration engine
│   ├── verifier/                   ← DNS-only verification pipeline
│   ├── compliance/                 ← Compliance guardrail
│   ├── gateway/                    ← Proxy gateway + rate limiter
│   ├── orchestrator/               ← Orchestration scheduler
│   ├── approval/                   ← Approval workflow
│   ├── audit/                      ← Audit logging
│   ├── inventory/                  ← Asset inventory
│   ├── graph/                      ← Knowledge graph (planned)
│   ├── metrics/                    ← Metrics (planned)
│   ├── scheduler/                  ← Daily scheduled tasks
│   ├── storage/                    ← SQLite + JSON persistence
│   ├── common/                     ← Shared components
│   └── static/                     ← Frontend static files
│
├── tests/                          ← Test suite
├── scripts/                        ← CI guard scripts
├── docs/                           ← Design documents
└── data/                           ← Runtime data (gitignored)
```

---

## 🧪 Running Tests

```bash
# Full test suite
pytest

# Passive egress guard (CI gate)
pytest tests/test_passive_egress.py -v

# Static guard — ensures no active-scan code enters production
python scripts/guard_passive.py
```

---

## 🛡️ Core Principles

1. **Purely Passive** — Never send a single packet to the target
2. **Zero Logs** — Never touch the target's logging systems
3. **Compliant Egress** — Every outbound call must pass `compliance_client.check()`
4. **Fail-Closed** — If in doubt, deny; if misconfigured, deny; if no token, deny

---

## 🤝 Contributing

PRs are welcome! Whether it's adding a new data source adapter, improving the dashboard, or fixing a bug — all contributions help make passive recon more powerful.

---

## 📜 License

MIT

---

<p align="center">
  <b>Passive Recon</b> — Star ⭐ on <a href="https://github.com/TrueFurina/passive-recon">GitHub</a>
  <br>
  Made with ❤️ for the OSINT / EASM / CTEM community
</p>