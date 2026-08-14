# Passive Recon v0.1.0 Release Notes

> **Purely passive OSINT/EASM/CTEM platform — 20 data sources, zero-touch asset discovery.**
>
> https://github.com/TrueFurina/passive-recon

---

## 🎉 Highlights

- **20 passive data sources** — certificate transparency, DNS records, search engines, network mapping, threat intel, and more
- **Zero-touch**: never sends a single packet to the target system
- **🤖 AI-powered analysis**: domain inference, risk scoring, asset classification, natural language chat query
- **Enterprise features**: RBAC, compliance reports, Docker deployment

---

## ✨ Features

### 🔍 Data Sources (20)

**Free / no key:**
crt.sh, HackerTarget, AlienVault OTX, URLScan.io, Wayback Machine, DNSDumpster, CommonCrawl, GitHub, NVD, OSV.dev

**Require API key:**
Hunter (multi-key rotation), FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge

### 🤖 AI Capabilities (DeepSeek)

| Feature | Description |
|---------|-------------|
| AI Domain Inference | Auto-infers domain for ANY target, not just lookup tables |
| AI Risk Scoring | Scores risks 0-100, filters false positives, suggests fixes |
| AI Asset Classification | Categorizes assets (web_admin, api, mail, vpn, oa...) |
| AI Chat Query | `python cli.py ask "What VPNs does Tsinghua have?"` |
| AI Report Summary | Auto-generated analysis after each collection |

### 🛡️ Enterprise Features

| Feature | Description |
|---------|-------------|
| **RBAC** | Admin/user token roles; approval routes require admin (`PASSIVE_ADMIN_TOKENS` or `:admin` suffix) |
| **Compliance Report** | `python cli.py compliance-report --days 30` — periodic audit with violation analysis |
| **Multi-Key Rotation** | Auto-failover when rate-limited, exponential cooldown (patent-pending) |
| **Source Health Monitoring** | Auto-degrade unhealthy sources with 5-min cooldown recovery |
| **Query Cache** | 24h TTL to reduce API cost |
| **Asset Change Alerts** | Detect new high-risk assets, push to WeCom/DingTalk webhook |
| **Webhook Notifications** | Scheduled task reports pushed to WeCom / DingTalk / generic webhook |

### 🌐 Platform

- **Web Dashboard**: `python cli.py serve` — asset browsing, risk & CVE views, detail panels
- **Scheduled Tasks**: `python cli.py schedule --targets targets.txt` — daily auto-collection
- **Docker Deployment**: `docker compose up -d`
- **Export**: JSON / CSV / Markdown / Nuclei templates / **PDF report**

---

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/TrueFurina/passive-recon.git
cd passive-recon
pip install -r requirements.txt

# Configure API keys (optional for free sources)
# Windows PowerShell:
$json='{"hunter":["key1"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'
[Environment]::SetEnvironmentVariable('PASSIVE_API_KEYS', $json, 'User')
# Linux/macOS:
export PASSIVE_API_KEYS='{"hunter":["key1"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'

# One-command asset discovery
python cli.py collect "Tsinghua University"

# Web dashboard
python cli.py serve
```

---

## 📦 Installation

```bash
# From source
pip install -r requirements.txt

# Docker
docker compose up -d
# → http://localhost:8000
```

---

## 🧪 Testing

```bash
pytest -q                          # full test suite (217+ tests)
python scripts/guard_passive.py    # passive egress red-line guard
```

---

## 📊 v0.1.0 Metrics

| Metric | Value |
|--------|-------|
| Data sources | 20 |
| CLI commands | 27 |
| AI features | 5 |
| Tests | 217+ passed |
| Code size | ~14,000 lines |

---

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](https://github.com/TrueFurina/passive-recon/blob/main/CONTRIBUTING.md)

- Add a new passive data source (adapter pattern, ~100 lines)
- Improve the web dashboard
- Fix bugs / write tests
- Translate documentation

---

## 📜 License

MIT

---

*Made with ❤️ for the OSINT / EASM / CTEM community*
