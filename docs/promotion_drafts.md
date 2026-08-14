# 推广帖草稿（v0.1.0 · 20 数据源）

---

## 1. Hacker News — Show HN

**Title:**
Show HN: Passive Recon – Zero-touch OSINT with 20 data sources, one command

**Body:**
I built a purely passive external asset discovery platform that queries 20 public data sources without ever touching the target system.

Key features:
- 20 data sources: crt.sh, HackerTarget, OTX, URLScan, Wayback Machine, DNSDumpster, CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge
- Zero-touch: Never sends a single packet to the target
- One command: `pip install -r requirements.txt && python cli.py collect "target"`
- Auto domain inference: Just type "Tsinghua University" → auto-resolves to tsinghua.edu.cn
- 🤖 AI-powered: domain inference, risk scoring (0-100), asset classification, natural language chat (`python cli.py ask "What VPNs does Tsinghua have?"`)
- Multi-key rotation: Automatically switches API keys when rate-limited (with exponential cooldown)
- Source health monitoring: auto-degrade unhealthy sources, 5-min cooldown recovery
- Query cache: 24h TTL to reduce API cost
- RBAC: admin/user token roles (enterprise)
- Compliance reports: periodic audit with violation analysis
- Web dashboard: `python cli.py serve`
- Daily scheduler: `python cli.py schedule --targets targets.txt` with Webhook alerts
- Docker: `docker compose up -d`

Sample run on Tsinghua University:
- 270 subdomains, 178 IPs, 6 risk findings (VPN, OA, email exposure)

This started as a competition project at DBAPPSecurity and evolved into a full OSINT/EASM/CTEM tool. All written in Python, pip install, zero external dependencies beyond the standard Python ecosystem. 217+ tests passing.

Looking for feedback on the architecture, missing data sources, and general usability!

https://github.com/TrueFurina/passive-recon

---

## 2. Reddit — r/netsec

**Title:**
Passive Recon – purely passive OSINT/EASM platform with 20 data sources

**Body:**
Hey r/netsec,

I've been working on a purely passive external asset discovery tool called Passive Recon. It queries 20 public data sources to discover subdomains, IPs, exposed services, and security risks without ever touching the target system.

**Key design decisions:**
- Purely passive: No active scanning, no probes sent to targets
- Fail-closed compliance: Every outbound call is checked against R1 rules
- Multi-key rotation: When rate-limited, automatically switches to the next API key with exponential cooldown
- AI risk scoring: Each finding scored 0-100 with remediation advice (DeepSeek)
- Health monitoring: unhealthy sources auto-degrade, recover after cooldown
- Human-readable output: Clean terminal reports, not JSON log noise

**Data sources (20 total):**
Free: crt.sh, HackerTarget, OTX, URLScan, Wayback Machine, DNSDumpster, CommonCrawl, GitHub, NVD, OSV
API Key: Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge

**Quick start:**
```bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
python cli.py serve  # web dashboard
python cli.py compliance-report  # periodic audit report
```

Output includes: subdomain enumeration, IP/C-segment clustering, port detection, risk findings (VPN, OA, email exposure, etc.), CVE correlation, asset importance scoring.

Would love to hear what data sources you'd add, or any architectural feedback!

https://github.com/TrueFurina/passive-recon

---

## 3. Reddit — r/OSINT

**Title:**
I built a passive OSINT platform with 20 data sources — looking for feedback

**Body:**
I wanted a tool that could do comprehensive passive recon without any of the complexity of setting up 20 different tools. So I built one.

**What it does:**
- Input: "Tsinghua University" → auto-infers domain tsinghua.edu.cn
- Queries 20 sources in parallel (crt.sh, HackerTarget, OTX, URLScan, Wayback, DNSDumpster, CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge)
- Returns: subdomains, IPs, ports, tech stacks, risk findings, CVE correlation
- Zero connections to the target system

**Why I built it:**
Most OSINT tools are either:
- CLI tools that do one thing well (subfinder, amass, etc.)
- Heavy platforms that need Docker/Redis/etc. (SpiderFoot, etc.)

I wanted something in between — pip install, one command, 20 sources, with AI analysis on top.

**New in v0.1.0:**
- 🤖 AI: domain inference, risk scoring, asset classification, chat query
- 🛡️ RBAC for enterprise deployments
- 📊 Compliance reports
- 🐳 Docker one-command deploy

**Try it:**
```bash
git clone https://github.com/TrueFurina/passive-recon
cd passive-recon
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
```

No API keys needed to start — 10 of the 20 sources are free and keyless.

https://github.com/TrueFurina/passive-recon

---

## 4. Twitter / X

**Post 1 (Launch):**
🕵️ Passive Recon v0.1.0 is live!

Zero-touch OSINT/EASM/CTEM platform with 20 data sources + 🤖 AI analysis.
One command, any target. No probes sent.

`pip install -r requirements.txt && python cli.py collect "target"`

👉 https://github.com/TrueFurina/passive-recon
#osint #infosec #cybersecurity #opensource

**Post 2 (AI):**
🤖 Passive Recon now has AI built in:
- Domain inference for ANY target
- Risk scoring 0-100 with fix advice
- Asset classification (vpn/oa/api/mail...)
- Natural language query: "What VPNs does Tsinghua have?"

https://github.com/TrueFurina/passive-recon
#osint #ai #recon

**Post 3 (Dev Story):**
I built a passive recon tool with 20 data sources over 2 weeks of competition prep.

Key lessons:
- Multi-key rotation is essential (Hunter API hits 429 constantly)
- Fail-closed compliance is non-negotiable for enterprise use
- AI risk scoring > static rules for filtering false positives

Full story: https://github.com/TrueFurina/passive-recon
#osint #devstory #security
