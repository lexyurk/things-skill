# Things Skill (Go CLI)

This repository contains a Go implementation of a Things 3 command-line tool and skill package.

- CLI binary/alias: `things`
- Core goal: MCP-equivalent Things operations through a fast local CLI
- Skill compatibility: Agent Skills / skills.sh format

## What this implements

The CLI mirrors the practical feature set of the Things MCP server:

- Read views: Inbox, Today, Upcoming, Anytime, Someday, Logbook, Trash
- Data operations: todos, projects, areas, tags, headings, tagged-items
- Search: simple and advanced filters
- Time-based: recent items
- Write operations: add/update todo/project
- Delete operations: implemented as **soft delete** (`canceled=true`)
- App navigation: show item/list, app search, JSON URL command passthrough

### Inbox-first behavior

- `things list` defaults to Inbox.
- `things todo add` without explicit destination/schedule follows Things default add behavior (Inbox).

### Someday project behavior

This port includes Someday inheritance behavior to align with Things MCP:

- Tasks in Someday projects are filtered out of Today/Upcoming/Anytime.
- Someday includes inherited tasks from Someday projects (including heading-based membership).

## Requirements

- Go 1.22+
- Things 3 database available locally (or provide `--db-path`)
- For write/navigation commands: macOS + Things URL scheme enabled

## Install `things` command (recommended)

```bash
# installs to ~/.local/bin/things by default
make install
```

Then run directly:

```bash
things list today
```

If `things` is not found, add your install directory to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Install to a different directory:

```bash
# e.g. /usr/local/bin/things
make install BINDIR=/usr/local/bin
```

Alternative installer script (auto-picks a writable PATH dir, or uses provided dir):

```bash
bash scripts/install.sh
# or
bash scripts/install.sh /usr/local/bin
```

Uninstall:

```bash
make uninstall
```

## Build (manual)

```bash
go build -o things ./cmd/things
```

## Test

```bash
go test ./...
```

## CLI quickstart

```bash
# Inbox (default)
things list

# Todos in a project
things todos --project <project-uuid>

# Create todo
things todo add --title "Buy milk" --notes "2%"

# Update todo
things todo update --id <todo-uuid> --when tomorrow

# Soft delete (cancel)
things todo delete --id <todo-uuid>
```

## Delete semantics

Things URL scheme does not support permanent delete.

- `things todo delete`
- `things project delete`

both map to cancel operations (`canceled=true`).

## Skill package layout

Skill files are in:

```text
skills/things/
├── SKILL.md
├── scripts/things
└── references/
    ├── commands.md
    └── limitations.md
```

Invoke through wrapper:

```bash
bash skills/things/scripts/things list
```

