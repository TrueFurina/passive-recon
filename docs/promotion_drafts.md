# 推广帖草稿

---

## 1. Hacker News — Show HN

**Title:**
Show HN: Passive Recon – Zero-touch OSINT with 15 data sources, one command

**Body:**
I built a purely passive external asset discovery platform that queries 15 public data sources without ever touching the target system.

Key features:
- 15 data sources: crt.sh, HackerTarget, OTX, URLScan, SecurityTrails, Shodan, VirusTotal, ZoomEye, Wayback Machine, CommonCrawl, DNSDumpster, GitHub, Hunter, FOFA, Qichacha
- Zero-touch: Never sends a single packet to the target
- One command: `pip install -r requirements.txt && python cli.py collect "target"` 
- Auto domain inference: Just type "Tsinghua University" → auto-resolves to tsinghua.edu.cn
- Built-in compliance guardrail with fail-closed behavior
- Multi-key rotation: Automatically switches API keys when rate-limited
- Web dashboard: `python cli.py serve`
- Daily scheduler: `python cli.py schedule --targets targets.txt`

Sample run on Tsinghua University:
- 270 subdomains, 178 IPs, 6 risk findings (VPN, OA, email exposure)

This started as a competition project at DBAPPSecurity and evolved into a full OSINT/EASM/CTEM tool. All written in Python, pip install, zero external dependencies beyond the standard Python ecosystem.

Looking for feedback on the architecture, missing data sources, and general usability!

https://github.com/TrueFurina/passive-recon

---

## 2. Reddit — r/netsec

**Title:**
Passive Recon – purely passive OSINT/EASM platform with 15 data sources

**Body:**
Hey r/netsec,

I've been working on a purely passive external asset discovery tool called Passive Recon. It queries 15 public data sources to discover subdomains, IPs, exposed services, and security risks without ever touching the target system.

**Key design decisions:**
- Purely passive: No active scanning, no probes sent to targets
- Fail-closed compliance: Every outbound call is checked against R1 rules
- Multi-key rotation: When rate-limited, automatically switches to the next API key
- Human-readable output: Clean terminal reports, not JSON log noise

**Data sources (15 total):**
Free: crt.sh, HackerTarget, OTX, URLScan, Wayback Machine, DNSDumpster, CommonCrawl, GitHub
API Key: Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha

**Quick start:**
```bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
python cli.py serve  # web dashboard
```

Output includes: subdomain enumeration, IP/C-segment clustering, port detection, risk findings (VPN, OA, email exposure, etc.)

Would love to hear what data sources you'd add, or any architectural feedback!

https://github.com/TrueFurina/passive-recon

---

## 3. Reddit — r/OSINT

**Title:**
I built a passive OSINT platform with 15 data sources — looking for feedback

**Body:**
I wanted a tool that could do comprehensive passive recon without any of the complexity of setting up 15 different tools. So I built one.

**What it does:**
- Input: "Tsinghua University" → auto-infers domain tsinghua.edu.cn
- Queries 15 sources in parallel (crt.sh, HackerTarget, OTX, URLScan, Wayback, DNSDumpster, CommonCrawl, GitHub, Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha)
- Returns: subdomains, IPs, ports, tech stacks, risk findings
- Zero connections to the target system

**Why I built it:**
Most OSINT tools are either:
- CLI tools that do one thing well (subfinder, amass, etc.)
- Heavy platforms that need Docker/Redis/etc. (SpiderFoot, etc.)

I wanted something in between — pip install, one command, 15 sources.

**Try it:**
```bash
git clone https://github.com/TrueFurina/passive-recon
cd passive-recon
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
```

No API keys needed to start — 8 of the 15 sources are free and keyless.

https://github.com/TrueFurina/passive-recon

---

## 4. Twitter / X

**Post 1 (Launch):**
🕵️ Passive Recon is live!

Zero-touch OSINT/EASM/CTEM platform with 15 data sources.
One command, any target. No probes sent.

`pip install -r requirements.txt && python cli.py collect "target"`

👉 https://github.com/TrueFurina/passive-recon
#osint #infosec #cybersecurity #opensource

**Post 2 (Sample Output):**
Collected 270 subdomains, 178 IPs, and 6 risk findings from Tsinghua University in under 60 seconds.

All passive. Zero packets sent to the target.

https://github.com/TrueFurina/passive-recon
#osint #recon #bugbounty

**Post 3 (Dev Story):**
I built a passive recon tool with 15 data sources over 2 weeks of competition prep.

Key lessons:
- Multi-key rotation is essential (Hunter API hits 429 constantly)
- Fail-closed compliance is non-negotiable for enterprise use
- Human-readable output > JSON log noise

Full story: https://github.com/TrueFurina/passive-recon
#osint #devstory #security