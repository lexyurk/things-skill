# Things CLI limitations and behavior notes

## 1) Platform for write/navigation

- Create/update/delete/show/app-search/json operations rely on Things URL scheme execution via `open -g`.
- That execution path is available on **macOS only**.
- On non-macOS platforms, read operations still work against a valid Things DB path, while write/navigation returns a platform error.

## 2) Why reads still use the database

- The documented Things URL scheme does **not** provide structured task reads.
- `show` and `search` only navigate within the app and return no data on `x-success`.
- Update-style URL commands return changed item IDs, not full task payloads.
- As a result, CLI read commands (`list`, `todos`, `projects`, `search`, etc.) remain database-backed.

## 3) Delete semantics

- Things URL scheme does **not** provide permanent deletion commands.
- `things todo delete` and `things project delete` are implemented as:
  - `update` / `update-project` with `canceled=true`.
- This is a **soft delete** (item moves to Logbook semantics), not a hard delete.

## 4) Auth token requirement

- Update-style URL scheme operations require an auth token from Things.
- The CLI reads it from `TMSettings.uriSchemeAuthenticationToken`.
- If the token is unavailable, update/delete operations fail with actionable guidance.

## 5) Inbox-first defaults

- `things list` defaults to `inbox`.
- `things todo add` without explicit `--list/--list-id/--when` follows Things default add behavior (Inbox).

