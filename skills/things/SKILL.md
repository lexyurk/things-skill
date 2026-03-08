---
name: things
description: Use this skill to manage Things 3 tasks via the local `things` Go CLI. It supports inbox-first listing, task/project create-update-delete (soft delete via cancel), search, tags, areas, headings, and Things app navigation commands.
license: MIT
metadata:
  author: lexyurk
  version: "1.0.0"
---

# Things CLI Skill

Use this skill whenever you need to operate on a user's Things 3 data from the terminal using the `things` command.

Structured reads come from the Things database. The Things URL scheme is still used
for create/update/navigation flows, but its documented `show` and `search` commands
do not return task payloads.

## When to use

- User asks to list inbox/today/upcoming/anytime/someday/logbook/trash tasks.
- User asks to create or update todos or projects.
- User asks to delete an item in Things (implemented as cancel / soft delete).
- User asks to run advanced search/filtering on Things tasks.
- User asks to open a list/item/search in the Things app.

## Quick command examples

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

# Soft-delete todo (canceled=true)
things todo delete --id <todo-uuid>
```

## Command references

- `references/commands.md` for full command matrix and flags.
- `references/limitations.md` for platform and delete semantics.

## Execution notes

Run the wrapper script:

```bash
bash skills/things/scripts/things <args...>
```

This wrapper runs the Go CLI from source (`go run ./cmd/things`).

