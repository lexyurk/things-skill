# Things backend behavior

Cloud needs Python 3.9+, network access to cloud.culturedcode.com, and a persisted Things Cloud login. It runs on Linux and macOS without the Things app. The bundled protocol package is dependency-free and uses owner-only account/cache files and a process-shared write lock.

Cloud `todo delete` and `project delete` move items to Trash. Restore with `things-cli cloud update ID '{"trashed":false}'`. Permanent deletion is limited to leaves; containers with children must be emptied first. Entity deletion similarly requires removing references first.

Task titles, notes, scheduling, deadlines, reminder times, tags, placement, ordering, completion, cancellation, checklists, projects, headings, areas, and tags have protocol implementations. Repeating tasks remain read-only. Headings support title, parent, and order edits. Account management, Apple push, Linux desktop notifications, calendar integration, attachments, and repeat-rule mutation are unsupported. Read-back verifies cloud history; it does not verify notification delivery or that a phone has downloaded a change.

Project/heading creation uses the verified Anytime/Today snapshot. A project's future or Someday schedule can be set afterward with an update. Headings have no independent schedule or completion action.

Cloud `show`/`app-search` return matching data. The Things URL `json` batch command requires `--backend local`; use documented cloud tools for individual mutations. Creation with reminders or child items consists of separate verified commits. Use a stable request ID to resume it without duplicating items; partial or uncertain outcomes stop further writes until reconciled.

The native macOS backend reads Things SQLite and writes through Things URLs. Its deletes cancel the item (`canceled=true`) and its update/delete operations require the URL auth token in TMSettings. `--dry-run` previews URLs. Existing native view semantics remain available with `--backend local`.

This is an unofficial protocol integration. See [evidence and coverage](../../../docs/EVIDENCE.md) for the basis of each operation and the live-test boundary.
