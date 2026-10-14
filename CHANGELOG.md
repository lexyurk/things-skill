# Changelog

## 2.0.2 — 2026-10-14

The existing Things Go CLI now connects directly to Things Cloud on Linux and
macOS. Terminal commands and the bundled MCP server share one persisted login
and synchronize task reads and writes automatically.

- `things-cli login` prompts for an email and hidden password, saves the returned
  access key in private local state, and discards the password.
- Task actions cover creation, lists/search/details, title and notes edits,
  scheduling, deadlines, reminder fields, tags and placement, completion,
  cancellation, reopening, Trash, restore, and permanent leaf deletion.
- Projects, areas, tags, headings, and checklists use the same Cloud service.
- `things-cli serve` exposes 13 stdio MCP tools. Sparse writes, a shared process
  lock, read-back verification, and stable request IDs support safe recovery
  without blind retries.
- Installable archives cover macOS and Linux on x86-64 and ARM64. A portable
  plugin ZIP includes Codex, Claude Code, and Cursor manifests and marketplace
  catalogs. Packages exclude credentials, task history, and generated caches.
- README and installation instructions cover binary/source installation,
  plugin setup, updates, removal, authentication, and backend selection.
- The original local macOS SQLite/Things URL backend remains available.

Python 3.9+ is required at runtime; no Go installation or pip dependencies are
needed for binary packages. Repeating-task mutations, desktop notifications,
calendar integration, and attachments are unsupported. Cloud read-back does
not establish actual reminder delivery or phone/Mac UI convergence.

Validation includes four Linux/macOS CI jobs with Python 3.9 and 3.14, Go tests
and vet, 69 Python behavior tests, package/launcher checks, and a successful
live run through all MCP handlers with zero disposable entities left behind.
See [the validation record](docs/VALIDATION.md) and [protocol evidence](docs/EVIDENCE.md).

## 2.0.1 Cloud preview

Initial packaged preview of the Cloud CLI, MCP server, and three host plugins.
The `cloud-v2.0.1` prerelease remains available for comparison.
