# Pull Request

## Description

<!-- What does this PR do? -->

## Related Issue

<!-- Closes #123 -->

## Type of Change

- [ ] 🆕 New data source
- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 📝 Documentation
- [ ] 🧪 Tests
- [ ] ♻️ Refactor

## Checklist

### Compliance (MUST ALL PASS)

- [ ] **Purely passive**: no probes sent to target systems
- [ ] **Compliance gate**: all outbound calls pass `_r1_pass()` / `compliance_client.check()`
- [ ] **No active-scan libraries**: no nmap/scapy/paramiko/masscan imports
- [ ] **No socket.connect** on resolved target IPs
- [ ] **No hardcoded API keys**: env vars only
- [ ] **No config.json/.env committed**

### Quality

- [ ] Tests pass locally: `pytest -q`
- [ ] Static guard passes: `python scripts/guard_passive.py`
- [ ] Code follows PEP 8 with type hints
- [ ] README updated if adding data source/command

### New Data Source (if applicable)

- [ ] Added enum in `model.py`
- [ ] Added collector class in `sources.py`
- [ ] Registered in `manager.py` (import + SUPPORTED_SOURCES + _build_collectors)
- [ ] Added test case
- [ ] Updated README data sources table

## Screenshots (if UI change)

<!-- Optional -->

## Notes for Reviewers

<!-- Anything the reviewer should know -->
