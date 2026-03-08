# Things CLI command matrix

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

- `--db-path <path>`: override DB location
- `--format text|json`: output mode (default `text`)
- `--dry-run`: print URL for write/navigation commands without executing

