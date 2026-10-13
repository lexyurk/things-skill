# Things Cloud protocol source research

Investigated on 2026-10-13. These are community implementations and static
analysis of the installed app. They are evidence for a bounded implementation,
not an official Cultured Code API specification. No account credentials or
personal task data were inspected, and no cloud mutations were performed by
this investigation.

## Pinned source identities

Commit identities were obtained through the GitHub connector's public
`GET /repos/{owner}/{repo}/commits/{branch}` endpoint. Source reads used the
commit hash, avoiding the differently dated cached `main` pages returned by web
search.

| Repository | Commit | Commit date | Assessment |
| --- | --- | --- | --- |
| [evanpurkhiser/things3-cloud](https://github.com/evanpurkhiser/things3-cloud/commit/db49137ff1153a074e942cbf2d9923f4e8af8daf) | `db49137ff1153a074e942cbf2d9923f4e8af8daf` | 2026-10-05 | Useful current Rust wire types and CLI behavior; some safety differences from the verified Go writer. |
| [arthursoares/things-cloud-sdk](https://github.com/arthursoares/things-cloud-sdk/commit/6919edc62da7ac98dbd8afbdffccc48fcd0807ed) | `6919edc62da7ac98dbd8afbdffccc48fcd0807ed` | 2026-09-06 | v0.6.0 contains explicit Task7 write validation and disposable-account verification. |
| [nicolai86/things-cloud-sdk](https://github.com/nicolai86/things-cloud-sdk/commit/e0534c6b1739cf88787bead367282306eedfa3ee) | `e0534c6b1739cf88787bead367282306eedfa3ee` | 2022-07-16 | Historical protocol discovery; too old to reuse unchanged for modern writes. |
| [mattydsmith/things-cloud-mcp](https://github.com/mattydsmith/things-cloud-mcp/commit/3164e8a5e09423ff7b1a77db160c15ff59150bf5) | `3164e8a5e09423ff7b1a77db160c15ff59150bf5` | 2026-03-16 | MCP/REST bridge over an older embedded SDK. Repository archived on 2026-09-27. |

All four projects declare MIT licensing. Relevant source snapshots are also
saved under `/private/tmp/things-protocol-sources/`; those temporary files are
research material, not a project runtime dependency.

## Authentication and selecting the user's existing history

The pinned Rust [client](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/client.rs#L104)
uses HTTPS at `cloud.culturedcode.com/version/1`. It percent-encodes the account
email in `GET /account/{email}`, supplies `Authorization: Password {percent-encoded password}`,
and selects the response's `history-key`. Subsequent history reads and commits
use that secret key in the URL without an Authorization header. Therefore the
history key must be treated like an account access secret in caches and logs.

The current community sources provide **version/1 endpoint evidence**, corroborated
by the native endpoint strings. This is not a complete live trace of every native
sync exchange. The Go
[verification method](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/verify.go)
uses a raw password header; the Rust percent-encoding behavior agrees with the
native authentication evidence reported by the main investigation.

Use the selected existing history. `CreateHistory` is an account-management
operation and should never be used as part of connecting an existing account.

## History replay and commit protocol

The Go [items reader](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/items.go)
reads `/version/1/history/{history-key}/items?start-index=N`. `items` is an ordered
array of commit maps. Each map's keys are entity identifiers and its values
carry `e` (entity kind), `t` (operation), and `p` (property dictionary). A commit
can contain several entities; increment the cursor by the number of maps, not
the number of entities. `current-item-index` is the server head, which can lie
beyond the current page. Preserve pagination progress until all commits through
the selected head are replayed. An empty page before that point is incomplete,
not success.

The Go [history writer](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/histories.go#L227)
posts one UUID-keyed map to `/history/{key}/commit?ancestor-index=HEAD&_cnt=1`.
It supplies `Schema: 301`, `App-Id: com.culturedcode.ThingsMac`, an app-instance
identifier, and `Push-Priority` (Go 5; Rust 10). A successful response contains
`server-head-index`. Duplicate entity IDs in a commit must be rejected because
JSON maps cannot retain two operations for the same key.

The writer's Task7 preflight replays a fixed history snapshot and writes against
that checked head. It posts once. On HTTP 409, return a conflict and let the
caller refresh and reconsider; changing the ancestor and automatically
reposting the same edit could overwrite a concurrent change.

Local state should be installed atomically only after a page has been validated.
Store raw properties, merge sparse modifications, and distinguish an omitted
field from explicit null. A projected task must never be serialized back as a
complete replacement, because projections omit unknown properties.

## Identifiers

The Go [identifier codec](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/base58.go)
uses Bitcoin Base58 over exactly 16 bytes, with one leading `1` for each leading
zero byte. Generate IDs from random UUID bytes. Validate decoding length and
canonical re-encoding for every outgoing ID, including relationships and
tombstone targets. Hexadecimal or hyphenated UUID text is unsuitable for modern
writes.

Older task/area/tag histories can use legacy text identifiers. Current IDs are
derived by Base58-encoding the first 16 bytes of SHA-1 of the exact legacy text.
Legacy recurrence IDs ending in `-YYYYMMDD` use a two-step hash: first hash the
UUID prefix, then hash its first 16 digest bytes followed by the suffix. Preserve
original case and bytes; normalize only the known legacy kinds while replaying.

## Ordinary Task7 creation

Prefer the complete shape in the Go
[CLI builder](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/cmd/things-cli/main.go#L302).
It includes all 34 properties. Creation uses `md: null`; the Rust new-task
builder currently uses a non-null modification date, so it should not be copied
unchanged. The Go native verification covered the complete ordinary creation
shape. The following is a protocol example with a placeholder timestamp:

```json
{
  "e": "Task7",
  "t": 0,
  "p": {
    "tp": 0, "sr": null, "dds": null, "rt": [], "rmd": null,
    "ss": 0, "tr": false, "dl": [], "icp": false, "st": 0,
    "ar": [], "tt": "Example task", "do": 0, "lai": null,
    "tir": null, "tg": [], "agr": [], "ix": 0, "cd": 1791849600.0,
    "lt": false, "icc": 0, "md": null, "ti": 0, "dd": null,
    "ato": null, "nt": {"_t": "tx", "ch": 0, "v": "", "t": 1},
    "icsd": null, "pr": [], "rp": null, "acrd": null, "sp": null,
    "sb": 0, "rr": null, "xx": {"_t": "oo", "sn": {}}
  }
}
```

The [Task7 validation contract](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/task_write.go#L153)
limits creation to ordinary tasks (`tp=0`), projects (`tp=1`), and headings
(`tp=2`). Projects/headings use Anytime (`st=1`). Updates are sparse and include
`md` with the current fractional Unix timestamp. Full-note replacement,
scheduling, relationships, tags, completion/reopening, and trash/restoration
are within the verified scope. Do not infer a task is nonrecurring unless raw
state explicitly establishes empty/null `rr`, `rp`, and `rt`, and no active
`icsd` or `acrd`.

## Dates, completion, and task organization

Calendar dates in the CLI are UTC-midnight Unix seconds representing the
**user's local calendar date**; do not convert local midnight to UTC. `st=0`
is Inbox, `st=1` is started/Anytime, and `st=2` is deferred/Someday. Today uses
`st=1` and `sr=tir=today`; future scheduling uses `st=2` and the selected day.
Clearing dates writes explicit nulls. `ss` is completion status, not schedule.

The Go [reader](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/task_read.go)
keeps `sr` (scheduled date) separate from `tir` (Today ordering reference).
Omitted properties preserve earlier values; null clears supported dates,
notes, and relationships. Complete writes `ss=3` with `sp=now`; reopen writes
`ss=0` with `sp=null`; recoverable trash writes `tr=true` and restore
`tr=false`. Native/Rust status value 2 means canceled, but it falls outside the
Go Task7 write acceptance matrix.

The [write policy](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/docs/task7-write-policy.md)
requires container moves to clear incompatible relationships. Moving to an
area sets `ar` and empties `pr`/`agr`. Moving to a project empties `ar`/`agr`;
moving under a heading preserves its project and sets `agr`. Reject ambiguous
area-plus-project/heading destinations. Recurrence templates/instances require
companion lifecycle changes and are deliberately outside reliable write scope.

## Notes and replay correctness

Modern full notes carry `_t="tx"`, `t=1`, full string `v`, and unsigned IEEE
CRC32 `ch` over UTF-8 bytes. Use `zlib.crc32(text.encode("utf-8"))` in Python.
The Go Task7 validator checks that full-text checksum.

The Rust [note decoder](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/wire/notes.rs)
defines `t=2` deltas with ordered patches (`p` byte position, `l` byte length,
`r` replacement, optional `ch` checksum of the resulting UTF-8 text). Its tests
reject invalid ranges, split multibyte characters, and checksum mismatches.
Apply every patch to bytes, then decode strictly. Plain historical strings and
explicit null must also be handled. Retain the raw note representation alongside
materialized text, and fail the sync transaction on unsupported formats.

The Go [live verification](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/docs/task7-write-verification.md)
confirmed UTF-8 byte offsets after Greek text and emoji; rune and UTF-16 offsets
were incorrect. It verified ordinary creation, note edits, Today/future dates,
clearing dates, completion/reopening, trash/restoration, and a specific batch of
project/heading/tag/checklist relationships. It did not establish every malformed
patch/checksum rule, broad concurrency, reminder delivery, permanent deletion,
or the recurrence lifecycle.

## Areas, tags, checklists, and permanent deletion

The current Rust [Area3 types](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/wire/area.rs)
define create fields `tt`, `tg`, `ix`, `xx`; sparse updates accept `tt`, `tg`,
`ix`, and `md`. Use the modern Area3 kind; the Go types document that legacy
Area2 creates can produce duplicate areas in Things.

The [Tag4 types](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/wire/tags.rs)
define create fields `tt`, `sh` (nullable shortcut), `ix`, `pn` (parent IDs),
and `xx`. Sparse updates accept those user properties plus `md`, preserving
omitted fields and allowing `sh=null`. The Go CLI's observed create ordering
example uses `ix=-1237`; this is an ordering value, not a magic validity token.

The [ChecklistItem3 types](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/wire/checklist.rs)
define title `tt`, status `ss`, stop timestamp `sp`, parent task array `ts`,
ordering `ix`, and creation/modification timestamps. The Go complete creation
shape includes nine properties: `cd=now`, `md=null`, `tt`, `ss=0`, `sp=null`,
`ix`, `ts=[parent]`, `lt=false`, `xx={"_t":"oo","sn":{}}`. Updates can remain
sparse. Completion/reopening uses the task status/stop-date convention.

[Tombstone2](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/wire/tombstone.rs)
creates a new tombstone entity whose properties identify the deleted target
(`dloid`) and deletion timestamp (`dld`). Distinguish this permanent deletion
from `tr=true`. The reviewed source does not prove server-side cascading
deletion of children: an implementation should reject a parent purge while
dependent tasks, headings, checklist items, or tag children remain unless it
constructs an explicitly authorized complete deletion batch.

## Native reminder and evening mapping

Static REA/Hopper analysis covered the arm64 slices of the installed frameworks:

| Framework | SHA-256 | Evidence bundle |
| --- | --- | --- |
| ThingsModel | `6b8547b85b8b8643d5a41c1e16cb76343b33ff9f34d788449cb947360dae534e` | [reminder-analysis.json](../evidence/reminder-analysis.json) |
| Base | `550893a8352db3a3be210bfd0611984cf5f2aa788c91e773638697771da1c4be` | [reminder-encoder-analysis.json](../evidence/reminder-encoder-analysis.json) |
| FoundationAdditions | `2ff2f293098fc071cfdc40dc9596f454cd3003c10775261805f581c34316933a` | [reminder-time-analysis.json](../evidence/reminder-time-analysis.json) |

- `sub_6ac1c`, assembly `0x6b620`–`0x6b66c`, registers task property
  `reminderTime` with sync name `ato` and FATime value type. The same method at
  `0x6b4f4`–`0x6b540` registers `startBucket` with sync name `sb`.
  Evidence: `ev_f9ce44b92b5f33eca79d45e5cba39583c8e847f002ca6e077495fc58af19ed81`.
- Native `_THMTaskStartBucket.description` maps 0 to default and 1 to evening.
  Evidence: `ev_2f0b6ef4b2985f79a91649ed6e106ad9b854c11ebc35ac6ab37b4f4336bfee6e`.
- Base's `BSSyncValueEncoder.encode` handles FATime by calling the
  `deprecatedTimeOffsetAbortingIfLossy` converter and serializing an integer;
  its decoder uses the inverse deprecated-offset initializer.
  Evidence: `ev_d6c560b3cd060757420fbc7702560b5d2b369192fcc6fbdea7485b1b02b8e373`,
  `ev_d2c1d2166290b99b18211d4de3be4775bcf0c794b7d872d7cb7438e21e630606`,
  and converter thunk `ev_94478c8ea1e876bc5608429f94e12a5891935e589883d35ba51b7aa6d5b63361`.
- FoundationAdditions' converter explicitly computes
  `hour*3600 + minute*60 + second`; the inverse clamps to 0–86399 and builds
  the packed FATime. Thus the cloud `ato` value is **seconds since local
  midnight**, not that packed internal value.
  Evidence: `ev_740006a7a10eda86d4f85ac367b7945870342d235ff317efd184601bd1306d28`
  and `ev_25215a2570d763721e5f88da2b36048092b58118e0a28eea21bf05281e74bc45`.
- The native combined schedule/reminder setter resets
  `lastReminderInteractionDate` when reminder time changes and marks the user
  modification date for update. Its sync key is `lai`. A corresponding sparse
  ordinary-task edit can therefore carry `ato=seconds`, `lai=null`, and
  `md=now`, with a calendar start date supplying the reminder's day.
  Evidence: `ev_c66de17776c32b4f34390e0e0dbcc70b8c11a3cf5369f0947f8b06024eb18289`.

These observations establish the native field mapping and encoding. They do
not observe a live cloud commit or notification delivery. Setting/removing
reminder time and evening placement can be implemented with that static basis,
but should be described as awaiting account/device round-trip verification.
Do not mistake `rmd` for a reminder: it is repeater migration metadata.

## Reuse decision

Reuse protocol facts and the verified Go complete creation shape. Keep the new
plugin's authentication, transport, storage, and MCP adapters small and separate.
Validate IDs, dates, relationships, recurrence state, and sparse payloads before
any POST. Commit once against the inspected head, then pull the resulting event
back from cloud before reporting success. Preserve unknown raw properties.

The broad feature claims in older README files exceed the recent verified
write contract. Recurring-task mutation, broad conflict convergence, and true
multi-device round trips remain unresolved until exercised in an account.
