---
name: things
description: Manage Things 3 tasks through the things-cli Cloud client or its MCP server on Linux and macOS; also supports the local macOS database and URL backend.
license: MIT
metadata:
  author: lexyurk
  version: "2.0.2"
---

# Things CLI Skill

Use the `things-cli` command (`things` is a compatible alias) or the connected Things MCP tools. Cloud operations synchronize before reading or writing and verify accepted changes by downloading them again.

## When to use

- User asks to list inbox/today/upcoming/anytime/someday/logbook/trash tasks.
- User asks to create or update todos or projects.
- User asks to delete an item in Things (Cloud moves it to Trash; local macOS mode cancels it).
- User asks to run advanced search/filtering on Things tasks.
- User asks to open a list/item/search in the Things app.

## Quick command examples

The user logs in once in their own terminal with `things-cli login`, which prompts for an email and hidden password. Do not request or put their password in a chat, argument, MCP configuration, or shell history. `things-cli login --env-file .env` supports an explicitly supplied owner-only credential file. Later processes reuse the saved access key and task cache.

```bash
# Inbox by default
things list

# View-specific list
things list today

# Get todos for a project
things todos --project <project-uuid>

# Create todo (defaults to inbox if no list/when set)
things todo add --title "Buy milk" --notes "2%"

# Update todo
things todo update --id <todo-uuid> --when tomorrow --tags errands,home

# Move todo to Trash through Cloud
things todo delete --id <todo-uuid>
```

## Command references

- `references/commands.md` for full command matrix and flags.
- `references/limitations.md` for platform and delete semantics.

## Execution notes

Use the installed command when available. `--backend auto` uses Cloud on Linux and after Cloud login on macOS; `--backend local`, `--db-path`, and URL `--dry-run` retain native behavior. `things-cli serve` runs this repository's MCP server and shares the login. `things-cli status` is a cached diagnostic; connected MCP status synchronizes.

Keep a stable `--request-id` for a create with children or a command being recovered. If a write is accepted but unconfirmed, or its outcome is unknown, run `sync` and inspect `status` before another write; do not repeat it with a fresh ID. Recurring tasks are readable but their mutations are unsupported. Read [limitations](references/limitations.md) for native-only commands and unverified features.

Run the wrapper script:

```bash
bash skills/things/scripts/things <args...>
```

This wrapper prefers the installed CLI and falls back to the Go source.

