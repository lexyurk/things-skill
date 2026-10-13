# Validation record

Local checks on 2026-10-13:

- 69 Python behavioral tests passed on Python 3.14.7 and Python 3.9.6.
- Five Go cloud bridge tests passed: embedded runtime extraction/cleanup, isolated imports, MCP stdio discovery, disconnected errors, missing Python.
- The official MCP Python SDK 1.23.1 negotiated protocol 2025-11-25, discovered 13 tools, and passed status/error calls.
- Ruff passed for the shared package and tests. Claude plugin and marketplace manifests passed strict validation. The updated skill passed Skill Creator validation.

Tests use synthetic accounts and cloud history. Coverage includes private persisted login, current reads, paging, sparse writes, dates/reminders, checklist/container relationships, complete/cancel/reopen/Trash/restore, replay-safe IDs, rejection/uncertain outcomes, account isolation, credential redaction, and the existing CLI's Cloud adapter.

Full Go CLI build/tests and vet require downloading the original repository's Go dependencies. Local execution cannot resolve network hosts in this sandbox; GitHub CI runs these checks and installer smoke tests on Ubuntu and macOS with Python 3.9 and 3.14. The PR's current checks are the authoritative CI result.

Live login and writes with the supplied account have not succeeded in this environment: DNS/network access to cloud.culturedcode.com is unavailable and sandbox escalation was rejected by the approval policy. No existing personal tasks were modified. Phone/Mac convergence and notification delivery remain unverified.

Run the explicit live acceptance script in an unrestricted terminal:

```bash
python3 scripts/live_verify.py --env-file .env --data-dir .local-state
```

It authenticates, exercises every MCP action on disposable entities, verifies cloud read-back, removes its own entities, and saves an owner-only `live-verification.json` report. It records pending cleanup instead of blindly retrying uncertain writes. A green CI run establishes offline behavior and platform builds; a successful live report establishes account authentication and tested cloud round trips.
