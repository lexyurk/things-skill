# Things CLI command matrix

`things-cli` is the primary installed command; `things` accepts the same arguments.

## Cloud login and MCP

- `things-cli login [--email EMAIL | --env-file .env]`: hidden password prompt or explicit private file; persists account access and performs initial sync.
- `things-cli status`: cached connection and unresolved-write diagnostic.
- `things-cli sync`: download and reconcile cloud changes.
- `things-cli logout`: remove local access and cache.
- `things-cli serve`: stdio MCP server, using the same persisted login.
- `things-cli cloud --help`: shared cloud package command reference.
- `things-cli cloud call TOOL 'JSON'`: any documented MCP action, including entities, checklist edits, restore, and permanent leaf deletion.

## Read operations

- `things list [view]`
  - Views: `inbox` (default), `today`, `upcoming`, `anytime`, `someday`, `logbook`, `trash`
- `things todos [--project UUID] [--heading UUID] [--include-items]`
- `things projects [--include-items]`
- `things areas [--include-items]`
- `things tags [--include-items]`
- `things tagged --tag <title>`
- `things headings [--project UUID]`
- `things search --query <text>`
- `things search-advanced [--status ... --start-date ... --deadline ... --tag ... --area ... --type ... --last ...]`
- `things recent --period <Xd|Xw|Xm|Xy>`

## Write operations

- `things todo add --title ... [--notes ... --when ... --deadline ... --tags ... --checklist-items ... --list-id ... --list ... --heading ... --heading-id ...]`
- `things todo update --id ... [fields...]`
- `things todo delete --id ...`
- `things project add --title ... [--notes ... --when ... --deadline ... --tags ... --area-id ... --area ... --to-dos ...]`
- `things project update --id ... [fields...]`
- `things project delete --id ...`

## App navigation operations

- `things show --id <id> [--query <text>] [--filter-tags <tag1,tag2>]`
- `things app-search --query <text>`
- `things json --data '<json-payload>' [--reveal]`

## Global options

- `--backend auto|cloud|local`: auto selects Cloud on Linux or after login on Mac; explicit DB/dry-run options retain the local backend.
- `--cloud-data-dir PATH`: private state shared by CLI and MCP (or THINGS_CLOUD_DATA_DIR).
- `--cloud-python PATH`: Python 3.9+ executable (or THINGS_CLOUD_PYTHON).
- `--request-id ID`: task/project write flag; stable ID for Cloud retries (1..100 ASCII letters, digits, dots, underscores, hyphens).

- `--db-path <path>`: override DB location
- `--format text|json`: output mode (default `text`)
- `--dry-run`: print URL for write/navigation commands without executing

