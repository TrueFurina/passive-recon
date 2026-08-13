# Contributing to Passive Recon

First off, thanks for taking the time to contribute! 🎉

Passive Recon is a purely passive OSINT/EASM/CTEM platform. We welcome all contributions — new data source adapters, bug fixes, documentation, dashboard improvements, tests, and more.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [What We're Building](#what-were-building)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
  - [Report a Bug](#report-a-bug)
  - [Suggest a Feature](#suggest-a-feature)
  - [Add a New Data Source](#add-a-new-data-source)
  - [Fix a Bug](#fix-a-bug)
  - [Improve Documentation](#improve-documentation)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)

---

## Code of Conduct

Be respectful and constructive. This is a security tool — please use it responsibly and only on systems you own or have explicit permission to test.

**Core principle: purely passive.** Never send probes to target systems. Contributions that introduce active scanning will be rejected.

---

## What We're Building

```
Passive Recon — 20 passive data sources, zero-touch asset discovery
├── Data sources: crt.sh, HackerTarget, OTX, URLScan, Wayback, DNSDumpster,
│   CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan,
│   VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge
├── AI features: domain inference, risk scoring, asset classification, chat
├── Web dashboard: FastAPI + static panel
└── Scheduler: daily auto-collection with Webhook alerts
```

---

## Getting Started

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/<your-username>/passive-recon.git
cd passive-recon

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys (optional, most free sources work without keys)
#    Windows PowerShell:
#    $json='{"hunter":["key1"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'
#    [Environment]::SetEnvironmentVariable('PASSIVE_API_KEYS', $json, 'User')
#    Linux/macOS:
#    export PASSIVE_API_KEYS='{"hunter":["key1"],"qichacha":{"app_key":"xxx","secret_key":"xxx"}}'

# 5. Verify it works
python cli.py collect "Tsinghua University"
```

---

## How to Contribute

### Report a Bug

Open an issue with:
- **Description**: What happened vs what you expected
- **Steps to reproduce**: Commands run, target, environment
- **Environment**: Python version, OS, installed packages
- **Logs**: Error output (redact any API keys!)

### Suggest a Feature

Open an issue describing:
- **Problem**: What can't you do today?
- **Proposed solution**: How should it work?
- **Alternative**: Other approaches you considered

### Add a New Data Source

The most valuable contribution! A new passive data source. See [Adding a data source](#adding-a-data-source).

### Fix a Bug

1. Open an issue describing the bug
2. Comment "I'll fix this" to claim it
3. Submit a PR referencing the issue

### Improve Documentation

Typos, unclear instructions, missing examples — all welcome. Update the relevant file in `docs/` or the README.

---

## Adding a Data Source

New data sources use the **adapter pattern** — each source is one class. Typically 80-150 lines.

### Step 1: Add the enum value

`passive_agent/collector/model.py`:

```python
class AssetSourceEnum(str, Enum):
    ...
    MYSOURCE = "mysource"  # My Source - short description
```

### Step 2: Add the collector class

`passive_agent/collector/sources.py`:

```python
class MySourceCollector(BaseCollector):
    """My Source — what it does (free or needs key)."""

    SOURCE = AssetSourceEnum.MYSOURCE
    BASE_URL = "https://api.example.com"

    def collect(self, domain: str) -> List[AssetRecord]:
        _r1_pass(source="mysource")  # ALWAYS pass compliance gate first
        records: List[AssetRecord] = []
        try:
            resp = httpx.get(f"{self.BASE_URL}/search?q={domain}", timeout=self.timeout)
            if resp.status_code == 200:
                # parse and append AssetRecord entries
                ...
        except Exception as e:
            self._errors.append(f"MySource 失败: {e}")
        return records
```

### Step 3: Register in the manager

`passive_agent/collector/manager.py`:

```python
from passive_agent.collector.sources import MySourceCollector  # import

SUPPORTED_SOURCES = { ..., "mysource": "My Source (free/needs key)" }  # list

all_collectors = [ ..., ("mysource", MySourceCollector(timeout=15, api_key=api_keys.get("mysource", ""))) ]  # register
```

### Requirements for a new source

- ✅ **Purely passive**: queries public APIs only, never connects to the target
- ✅ **Compliance gate**: calls `_r1_pass(source=...)` before any outbound request
- ✅ **Error tolerant**: failures are caught, don't crash the whole collection
- ✅ **Tests**: add a test case in `tests/test_collector.py` or a new test file
- ✅ **README**: add the source to the data sources table

---

## Development Workflow

```
1. Create a branch: git checkout -b feat/my-feature
2. Make changes (one logical change per branch)
3. Run tests: pytest -q
4. Run the static guard: python scripts/guard_passive.py
5. Commit (see guidelines below)
6. Push and open a PR
```

---

## Coding Standards

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Type hints required on function signatures
- Docstrings in Chinese or English (match surrounding code)
- Keep functions small and focused

### Hard Rules

1. **Never import active-scan libraries** (nmap, scapy, paramiko, masscan...)
2. **Never use `socket.connect` on resolved target IPs**
3. **All outbound calls must pass `compliance_client.check()` / `_r1_pass()`**
4. **Never hardcode API keys** — use environment variables only
5. **Never commit `config.json` or `.env`**

These are enforced by the CI static guard (`scripts/guard_passive.py`).

### Data Source Rules

- Passive only (no probes to targets)
- Error tolerant (single source failure doesn't stop others)
- Cache results where possible (24h TTL via `collector/cache.py`)
- Register health tracking (auto-degrade on repeated failures via `collector/health.py`)

---

## Testing

```bash
# Run all tests
pytest -q

# Run the passive egress red-line test
pytest tests/test_passive_egress.py -v

# Run the static guard (blocks active-scan code)
python scripts/guard_passive.py
```

When you add a feature, add tests for it. At minimum:
- Happy path (source returns data)
- Failure path (source errors → caught, doesn't crash)
- Red-line compliance (active action → blocked)

---

## Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

<optional body>
```

**Types:**

| Type | Use for |
|------|---------|
| `feat` | New feature or data source |
| `fix` | Bug fix |
| `docs` | Documentation |
| `test` | Tests |
| `refactor` | Code refactor (no behavior change) |
| `chore` | Build/tooling |

**Examples:**

```
feat: add Censys data source
fix: handle 429 rate limit with key rotation
docs: update data sources table
test: add collector failure path test
```

Keep commits small and focused — one logical change per commit.

---

## Pull Request Process

1. **Update the README** if you added a data source or command
2. **Run tests and static guard** locally before pushing
3. **Describe your changes** in the PR body
4. **Reference the issue** if one exists (`Closes #123`)
5. Wait for review — the maintainer will review and may request changes

### PR Title Format

```
<type>: <short description>
```

---

## Resources

- [README](README.md) — project overview and usage
- [中文版 README](README.zh-CN.md)
- [System Design](docs/system_design.md)
- [Patent Disclosure](docs/patent_disclosure.md) — our multi-key rotation method

---

*Made with ❤️ for the OSINT / EASM / CTEM community*
