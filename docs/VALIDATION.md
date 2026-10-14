# Validation record

Local checks on 2026-10-13:

- 69 Python behavioral tests passed on Python 3.14.7 and Python 3.9.6.
- Full Go tests and vet passed locally, including the cloud bridge and CLI adapter. Two package integration tests passed: MCP discovery through both plugin manifest formats and actionable missing-binary errors with clean stdout.
- The official MCP Python SDK 1.23.1 negotiated protocol 2025-11-25, discovered 13 tools, and passed status/error calls.
- Ruff passed for the shared package and tests. Claude plugin and marketplace manifests passed strict validation. The updated skill passed Skill Creator validation.

Tests use synthetic accounts and cloud history. Coverage includes private persisted login, current reads, paging, sparse writes, dates/reminders, checklist/container relationships, complete/cancel/reopen/Trash/restore, replay-safe IDs, rejection/uncertain outcomes, account isolation, credential redaction, and the existing CLI's Cloud adapter.

Ubuntu build/tests, vet, and installer smoke checks passed with Python 3.9 and 3.14. The earlier Mac CI failure was dyld aborting Go 1.22.2 test executables for a missing LC_UUID header, before their tests ran. CI now selects stable Go and keeps all matrix jobs running independently. Current PR checks are the authoritative CI result.

On 2026-10-14, after network access was enabled, terminal login through the Go binary authenticated successfully and downloaded cloud history. A task was created through the Go MCP server using the official MCP client, read back, and found in Inbox. Notes, deadline, area placement, moving back to Inbox, and Trash were subsequently verified through cloud read-back. Checklist entries added in the user's Things app downloaded correctly. The test task was left in Trash at the user's request.

This establishes the exercised account and task round trips, not every operation in the broad acceptance runner. Reminder delivery, recurring-task edits, all entity/checklist mutation variants, and direct phone/Mac UI observation remain unverified.

CLI archives are built for Linux/macOS on x86-64 and ARM64. The native Mac archive's installer, CLI version, and disconnected status were verified after extraction. Archives and the portable plugin ZIP use a file allowlist and exclude credentials, caches, cloud history, and Git metadata. Agent Plugins schemas and strict Claude manifest validation passed; Codex loaded and installed the marketplace package. Cursor local-plugin files are installed and require a window reload for discovery.

Run the explicit live acceptance script in an unrestricted terminal:

```bash
python3 scripts/live_verify.py --env-file .env --data-dir .local-state
```

It authenticates, exercises every MCP action on disposable entities, verifies cloud read-back, removes its own entities, and saves an owner-only `live-verification.json` report. It records pending cleanup instead of blindly retrying uncertain writes. A green CI run establishes offline behavior and platform builds; a successful live report establishes account authentication and tested cloud round trips.
