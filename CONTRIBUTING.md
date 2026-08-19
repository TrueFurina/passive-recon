# Contributing to Passive Recon

Thanks for your interest in contributing! 🎉

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Before You Submit

1. **Run the test suite**: `pytest -q`
2. **Keep it passive**: this is a zero-touch tool — no outbound probes may be added.
3. **Fail closed**: any new data source must respect the compliance guardrail.

## Commit Style

- Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- Keep each commit focused on a single intent
- Reference issues where applicable
- Avoid committing secrets — run `gitleaks detect` before pushing (CI will block leaks)

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] No secrets or API keys committed
- [ ] Docs updated if behavior changed
- [ ] New data source connectors include `fail-closed` compliance handling

## Reporting Issues

Include: command used, expected vs actual output, and whether the target is
reachable from your network (the tool may be blocked by network policies).
