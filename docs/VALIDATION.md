# Validation record

Local checks on 2026-10-13:

- 69 Python behavioral tests passed on Python 3.14.7 and Python 3.9.6.
- Full Go tests and vet passed locally, including the cloud bridge and CLI adapter. Two package integration tests passed: MCP discovery through both plugin manifest formats and actionable missing-binary errors with clean stdout.
- The official MCP Python SDK 1.23.1 negotiated protocol 2025-11-25, discovered 13 tools, and passed status/error calls.
- Ruff passed for the shared package and tests. Claude plugin and marketplace manifests passed strict validation. The updated skill passed Skill Creator validation.

Tests use synthetic accounts and cloud history. Coverage includes private persisted login, current reads, paging, sparse writes, dates/reminders, checklist/container relationships, complete/cancel/reopen/Trash/restore, replay-safe IDs, rejection/uncertain outcomes, account isolation, credential redaction, and the existing CLI's Cloud adapter.

All four Ubuntu/macOS CI jobs passed with Python 3.9 and 3.14, including Go tests, vet, Python behavior tests, package integration tests, and installer smoke checks. CI selects stable Go and keeps all matrix jobs running independently. See [GitHub Actions](https://github.com/lexyurk/things-skill/actions/workflows/test.yml) for results tied to each commit.

On 2026-10-14, after network access was enabled, terminal login through the Go binary authenticated successfully and downloaded cloud history. A task was created through the Go MCP server using the official MCP client, read back, and found in Inbox. Notes, deadline, area placement, moving back to Inbox, and Trash were subsequently verified through cloud read-back. Checklist entries added in the user's Things app downloaded correctly. The test task was left in Trash at the user's request.

The broad live acceptance runner also passed on 2026-10-14. It exercised all 13 MCP tool handlers against the live account: authentication, sync/status, every list view, search/details, area/tag/project/heading/task creation, entity edits/lists, title and Unicode notes, scheduling/deadlines/reminder fields, Evening, clearing fields, ordering, checklist creation/edit/completion/reopening, task completion/cancellation/reopening, Trash/restore, container moves, and permanent deletion. It removed all six disposable entities it created; zero cleanup items remained. Its credential and task identifiers stay in the private local report and are not published.

The broad runner calls the shared MCP handlers directly; the separate official-client test establishes stdio transport through the installed Go binary. These checks verify cloud acceptance and history read-back. Actual reminder delivery, direct phone/Mac UI observation, broad concurrent multi-device behavior, and every possible input combination remain unverified. Recurring-task edits and desktop notification delivery are unsupported.

CLI archives are built for Linux/macOS on x86-64 and ARM64. The native Mac archive's installer, CLI version, and disconnected status were verified after extraction. Archives and the portable plugin ZIP use a file allowlist and exclude credentials, caches, cloud history, and Git metadata. Agent Plugins schemas and strict Claude manifest validation passed. Codex and Claude Code installed and enabled the marketplace package. All three installed host launchers started the same authenticated CLI with a GUI-style PATH. Cursor local-plugin files are installed; discovery in the host UI requires a window reload.

Run the explicit live acceptance script in an unrestricted terminal:

```bash
python3 scripts/live_verify.py --env-file .env --data-dir .local-state
```

It authenticates, exercises every MCP action on disposable entities, verifies cloud read-back, removes its own entities, and saves an owner-only `live-verification.json` report. It records pending cleanup instead of blindly retrying uncertain writes. A green CI run establishes offline behavior and platform builds; a successful live report establishes account authentication and tested cloud round trips.
