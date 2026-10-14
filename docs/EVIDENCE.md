# Evidence and implementation coverage

Investigation date: 2026-10-13. Installed Things version: **3.24.1**.
The implementation is a direct cloud client, rather than an AppleScript bridge.

## What is established

Cultured Code describes [Things Cloud as its sync service](https://culturedcode.com/things/support/articles/2803586/)
and says there is [no public API](https://culturedcode.com/things/support/articles/2967034/).
Its [local-device notification explanation](https://culturedcode.com/things/support/articles/9706121/)
says notifications tell other devices to fetch changes from cloud. Linux can
poll that cloud history without implementing Apple's device notifications.

| Finding | Evidence | Interpretation |
| --- | --- | --- |
| Native transport includes the cloud host, history pages, and ancestor-based commits | `ev_9fdb0c8acac8d6b110cc4d7cfef37a95cc00dad359388be2c795ed69927b3fd7`, Syncrony strings at `0x24138`, `0x2404f`, `0x2445f` | Static endpoint evidence, not an observed network exchange |
| Native request construction percent-escapes the password and puts it in an Authorization header | `ev_b767c007e0d471eb38649d73058b613a5e18357b3e51deffe973e0364d6e0b8f`, `+[SYConnectionUtilities requestWithMethod:onResource:parameters:body:password:additionalHeaders:]`, `0x1f410` | Pseudocode derives password-header construction; no credentials read |
| Commit success requires a decoded `server-head-index` | `ev_d5a3a69a5afd046ae427c2ee4642201296a648d4f31bc12196c91a769a714667`, commit response handler at `0x97e0` | Static success-path evidence |
| The installed task model contains `Task7` | `ev_62ed635379d85c3305ca682b38480480f1f015a024e8244c9e3fa9db5fabbd34`, ThingsModel string at `0x10f1da` | Establishes the current entity name; source verification supplies its complete payload |
| Reminder wire field is `ato`; encoding is seconds after midnight | ThingsModel, Base, and FoundationAdditions evidence listed in [source research](source-research.md#native-reminder-and-evening-mapping) | Static mapping, including encode/decode and native setter behavior; device notification delivery unobserved |

Syncrony SHA-256:
`b1f0ae860163737a6c92f89b6f9008585f9c4eb8c44797faf354e13a67b0aeb1`.
ThingsModel SHA-256:
`6b8547b85b8b8643d5a41c1e16cb76343b33ff9f34d788449cb947360dae534e`.
The compact bundle [native-analysis.json](../evidence/native-analysis.json)
preserves provider identity, referenced string observations, procedure
pseudocode, and limitations. The reminder bundles retain the referenced
framework procedures. Full raw exports and assembly are retained in the
original investigation workspace; this repository omits those bulky listings.

The current Rust client at
[db49137f](https://github.com/evanpurkhiser/things3-cloud/blob/db49137ff1153a074e942cbf2d9923f4e8af8daf/src/client.rs)
corroborates authentication and the `/version/1` history route. The Go writer at
[6919edc6](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/task_write.go)
supplies a strict ordinary-task contract. Its
[disposable-account verification](https://github.com/arthursoares/things-cloud-sdk/blob/6919edc62da7ac98dbd8afbdffccc48fcd0807ed/docs/task7-write-verification.md)
supports the chosen payloads. That report is upstream evidence, not a live test
of this Python implementation or the user's account.

## How authentication and sync work

1. An HTTPS account request supplies a percent-encoded email in its path and a
   percent-encoded password in `Authorization: Password ...`.
2. The response selects the existing `history-key`. The plugin stores that
   capability with permissions 0600 and discards the password. It never creates
   or resets a history during connection.
3. History pages contain ordered commit maps. Each object has `e` (entity), `t`
   (create/update/delete), and `p` (properties). The local cache replays them
   through a fixed head index and is installed atomically.
4. A validated write posts one sparse change map with `ancestor-index` equal to
   the inspected head. It includes schema 301 and the community clients'
   compatibility headers. Conflicts and uncertain outcomes are reported.
5. The plugin downloads and finds the resulting event in history. Apple clients
   pick up that same history through their own sync service.

Calendar days use UTC-midnight timestamps as a representation of the local day.
Reminders use local wall-clock seconds; notes use UTF-8 text and CRC32. Canonical
Base58 IDs represent exactly 16 bytes. Invalid modern IDs are rejected; known
legacy IDs use the documented byte-exact migration derivation.

## Coverage and unresolved work

| Operation | Implemented basis | Verification boundary |
| --- | --- | --- |
| Connect and read current lists/search/task details | Native authentication + source history readers | Live account login, history download, Inbox query, and task read-back verified |
| Create ordinary task/project/heading | Complete 34-property Task7 snapshot, `md:null` | Ordinary task creation verified live; project/heading coverage remains upstream + offline |
| Edit title, notes, dates, tags, placement, order | Sparse Task7 patches | Notes, deadline, area/Inbox placement verified live; other variants remain upstream + offline |
| Complete/reopen and Trash/restore | Status/date pairs and Trash bit | Trash verified live; other variants remain upstream + offline |
| Cancel | Source/native status 2 | Source-based; outside upstream Go live acceptance matrix |
| Reminder and Evening | Native field registration, time encoder, and schedule setter | Static evidence + offline tests; live notification delivery pending |
| Areas/tags/checklists | Current source entity shapes and strict parent checks | App-originated checklist reads verified live; mutations remain source-based + offline |
| Permanent leaf deletion | Tombstone2 | Source-based + offline tests; live purge pending |
| Repeating tasks | Read and preserve existing raw data | Mutations blocked; companion recurrence lifecycle unimplemented |
| Heading edits | Title, parent project, and order | Scheduling/completion excluded |
| Push/background sync | Polling and on-demand sync | Apple push and Linux reminder notifications unimplemented |
| Concurrency | Serialized local writers, fixed snapshot, sparse changes, no blind retries | Offline fault-injection tests; broad multi-device convergence unverified |

This does **not** establish full parity with the Things app or a completed
cross-device acceptance test. Unsupported future schemas stop sync without
advancing the cache. Incomplete recurrence markers remain read-only. Account
management, calendar integration, attachment support, repeat-rule mutation,
multi-action atomic batches, and Linux desktop notifications are outside this
implementation.
