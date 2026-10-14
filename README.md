# Things Cloud: CLI, MCP server, and agent plugins

Manage Things Cloud from **Linux and macOS**, in your terminal or through **Codex, Claude Code, and Cursor**. [Download the installable CLI and plugin packages](https://github.com/lexyurk/things-skill/releases/latest), then follow the [installation guide](docs/INSTALL.md). All three hosts launch this repository's Go CLI and share its persisted login. Python 3.9+ is required at runtime.

Create, read, search, edit, schedule, complete, and delete tasks with `things-cli` or any stdio MCP host. Login persists across CLI invocations and MCP sessions. Every task read downloads current changes; every write synchronizes first, commits once, then verifies the resulting event in cloud history. Projects, areas, tags, headings, and checklists are supported too.

The Go CLI bundles the dependency-free Python protocol package. Both interfaces use its account access key, SQLite cache, write journal, and process lock. This repository also retains its original macOS SQLite/Things URL backend.

## Install and log in

Download the archive matching your OS and CPU from [Releases](https://github.com/lexyurk/things-skill/releases/latest), extract it, and run:

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
things-cli login
```

The binary package needs Python 3.9+ and network access to Things Cloud. No Go installation, pip packages, or Things app is required to use it on Linux. Each CLI archive also includes the plugin files for all three hosts.

To build from source, install Go 1.22.2+ (current stable Go is recommended on macOS) and Python 3.9+, then run:

```bash
git clone https://github.com/lexyurk/things-skill.git
cd things-skill
make install
export PATH="$HOME/.local/bin:$PATH"
things-cli login
```

Enter your Things Cloud email and password when prompted. The password is hidden and discarded after authentication. The client saves the returned account access key with permissions `0600`, inside a `0700` state directory. Subsequent commands reuse it without prompting:

```bash
things-cli list today
things-cli todo add --title "Call Anna" --when tomorrow@14:30 --request-id call-anna-1
things-cli todo update --id TASK_ID --when 2026-10-20 --deadline 2026-10-22
things-cli todo update --id TASK_ID --completed
things-cli todo delete --id TASK_ID
```

`things` is installed as a compatible alias. `things-cli list` defaults to Inbox. Default state is `${XDG_DATA_HOME:-$HOME/.local/share}/things-cloud-plugin`; override with `--cloud-data-dir /absolute/path` or `THINGS_CLOUD_DATA_DIR`. CLI and MCP must use the same state directory. `things-cli logout` removes local account access and the task cache, without deleting your cloud account.

For an explicit credential file, copy `.env.example` to `.env`, enter `USERNAME` and `PASSWORD`, then run:

```bash
chmod 600 .env
things-cli login --env-file .env
```

The file is ignored by Git and never loaded automatically. No password belongs in an MCP configuration. `things-cli status` reports cached diagnostics and unresolved writes; `things-cli sync` downloads and reconciles changes.

Alternative installation: `bash scripts/install.sh /your/bin/directory`. Uninstall both commands with `make uninstall`.

## Connect an MCP host

For native plugins, follow [Codex, Claude Code, or Cursor setup](docs/INSTALL.md). The repository includes portable `plugin.json`/`mcp.json`, all three host manifests, and Codex/Claude marketplace catalogs. Direct MCP registration is also supported:

After terminal login, register the installed server:

```bash
codex mcp add things -- things-cli serve
claude mcp add --transport stdio --scope user things -- things-cli serve
```

Use the absolute binary path if the host does not inherit your shell's PATH. These commands register **this repository's server**. It speaks newline-delimited JSON-RPC on stdout and shares the CLI's persisted login. Codex setup follows its [official MCP documentation](https://developers.openai.com/codex/mcp).

Install the CLI first, then add the repository's marketplace to your host:

```bash
codex plugin marketplace add lexyurk/things-skill
codex plugin add things@lexyurk-things

claude plugin marketplace add lexyurk/things-skill
claude plugin install things@lexyurk-things
```

For Cursor, copy the packaged `plugin/` folder to `~/.cursor/plugins/local/things` and reload the window. See [the install guide](docs/INSTALL.md) for local-package setup, updates, and removal. Plugin packaging follows the [Agent Plugins documentation](https://developers.openai.com/plugins/build/plugins) and [Claude manifest reference](https://code.claude.com/docs/en/plugins-reference). Use either direct MCP registration or the plugin's MCP entry to avoid registering the same server twice.

The 13 tools cover status, sync, task lists/search, task details, task create/update/complete/delete, entity list/create/update/delete, and checklist create/update/delete. Connected tool calls synchronize automatically. Additional fields are available through the shared CLI:

```bash
things-cli cloud update TASK_ID '{"when":"evening","reminder":"18:30","trashed":false}'
things-cli cloud call things_create_entity '{"kind":"tag","title":"Focus"}'
things-cli cloud call things_checklist '{"action":"create","task_id":"TASK_ID","title":"Prepare"}'
things-cli cloud tools
```

## Existing commands and backend selection

All existing read and task/project write commands have Cloud adapters: views, todos, projects, headings, areas, tags, tagged items, search, advanced search, and recent items. Names resolve only when unique; otherwise provide full IDs. `--format json` retains the existing CLI's data shape.

`--backend auto` selects Cloud on Linux and after login on macOS. `--backend local`, an explicit database path, `THINGSDB`, or URL `--dry-run` selects the original local backend. Use `--backend cloud` to force Cloud when a local DB environment variable is set. Cloud `show` and `app-search` return data; native UI navigation and raw Things URL JSON batches require the local backend.

Cloud deletion moves tasks/projects to Trash. The native backend retains cancellation semantics. Restore Cloud items with `{"trashed":false}`; permanent deletion is restricted to leaves. Creating reminders or child items uses separate verified commits. Supply a stable `--request-id` to resume a partial creation without duplicating its parent or children.

## Evidence and verification

Things Cloud has [no public API](https://culturedcode.com/things/support/articles/2967034/). This client uses the researched protocol: authenticate over HTTPS, save the returned history capability, replay ordered history pages, and submit sparse commits against the synchronized ancestor index. See [evidence](docs/EVIDENCE.md), [source research](docs/source-research.md), and [validation](docs/VALIDATION.md).

Recurring task mutations, repeat rules, calendar integration, attachments, Linux notifications, and Apple's background push are unsupported. Cloud read-back does not prove phone/Mac convergence or reminder delivery. The supplied live acceptance runner operates only on disposable entities it creates and records cleanup; no credentials run in CI.

```bash
make test
go vet ./...
# Explicit live test with your private credentials, from this checkout:
python3 scripts/live_verify.py --env-file .env --data-dir .local-state
```

Agent Skill references are in [skills/things](skills/things/SKILL.md).
