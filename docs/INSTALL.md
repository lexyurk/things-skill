# Install Things Cloud on macOS or Linux

The CLI and all three plugin hosts use the same Go executable and the same persisted account. Python 3.9+ is required at runtime; no pip packages are needed. Go is required only to build from source.

## Binary package

Download version **2.0.2** from [GitHub Releases](https://github.com/lexyurk/things-skill/releases/tag/cloud-v2.0.2). Choose the archive for your machine:

| Machine | Archive |
| --- | --- |
| Apple Silicon Mac | `things-cli-2.0.2-darwin-arm64.tar.gz` |
| Intel Mac | `things-cli-2.0.2-darwin-amd64.tar.gz` |
| Intel/AMD Linux PC | `things-cli-2.0.2-linux-amd64.tar.gz` |
| ARM Linux machine | `things-cli-2.0.2-linux-arm64.tar.gz` |

`SHA256SUMS` contains the checksums of all packages. On Linux, download it alongside your chosen archive and run `sha256sum --ignore-missing --check SHA256SUMS`. On macOS, use `shasum -a 256 ARCHIVE` and compare the result to the matching line in `SHA256SUMS`.

Extract the matching archive into its own directory, then run:

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
things-cli login
things-cli list today
```

The installer adds `things-cli` and the compatible `things` alias to `~/.local/bin`. Pass another directory to `./install.sh /your/bin`. `THINGS_CLI_BINARY` can select a custom executable for the plugin. The package includes a `plugin/` folder containing the plugin and all marketplace files.

## Source package

Build from the repository's default branch:

```bash
git clone https://github.com/lexyurk/things-skill.git
cd things-skill
make install
export PATH="$HOME/.local/bin:$PATH"
things-cli login
```

Use current stable Go on recent macOS versions. Login asks for the Things Cloud email and a hidden password. It stores the returned account access key, not the password. The CLI and plugins share `${XDG_DATA_HOME:-$HOME/.local/share}/things-cloud-plugin`; `THINGS_CLOUD_DATA_DIR` selects another directory.

## Codex plugin

From the repository root or the binary package's `plugin/` folder:

```bash
codex plugin marketplace add .
codex plugin add things@lexyurk-things
```

To install directly from GitHub, use `codex plugin marketplace add lexyurk/things-skill` in place of the first command. Older Codex clients can use the Plugins Directory after adding the marketplace, or register the MCP server directly. The repository contains a portable Agent Plugins manifest, Codex compatibility manifest, and `.agents/plugins/marketplace.json` catalog. See the [official packaging documentation](https://developers.openai.com/plugins/build/plugins).

## Claude Code plugin

From the same plugin root:

```bash
claude plugin marketplace add .
claude plugin install things@lexyurk-things
```

To install directly from GitHub, use `claude plugin marketplace add lexyurk/things-skill` in place of the first command. For development, `claude --plugin-dir /absolute/path/to/things-skill` loads the checkout. The repository includes `.claude-plugin/plugin.json`, its marketplace, and the shared MCP entry. See the [Claude manifest reference](https://code.claude.com/docs/en/plugins-reference).

## Cursor plugin

Copy the binary package's `plugin/` folder, or an exported plugin archive, to `~/.cursor/plugins/local/things`. Include the files inside that folder directly, such as `plugin.json` and `.cursor-plugin/plugin.json`. Restart Cursor or run **Developer: Reload Window**, then check **Customize** for Things.

Cursor supports the portable package and its `.cursor-plugin/plugin.json` compatibility manifest. Local plugin imports must be allowed by your workspace. See [Cursor's local-plugin instructions](https://cursor.com/docs/plugins#test-plugins-locally).

## Any MCP host

The executable also works as a direct stdio server:

```bash
codex mcp add things -- things-cli serve
claude mcp add --transport stdio --scope user things -- things-cli serve
cursor --add-mcp '{"name":"things","command":"things-cli","args":["serve"]}'
```

Use the installed binary's absolute path if the host does not inherit your shell PATH. Choose either the plugin or a direct MCP registration for each host to avoid duplicate tools. The plugin launcher checks PATH, then `~/.local/bin/things-cli`, so GUI launches work after the default installation. No password belongs in these manifests.

Restart the host session after installing. MCP discovery works before login, while task actions ask you to connect through the terminal. Task commands synchronize automatically; cached CLI `status` remains available for diagnostics. Repeating task edits and desktop notifications are unsupported.

## Updates and removal

To update the CLI, download the new matching archive and run its installer. It replaces the executable and preserves the login and task cache. Update the host plugin through its marketplace, or copy the new packaged plugin into Cursor's local plugin directory and reload the host.

To disconnect, run `things-cli logout`. To remove the CLI, delete `~/.local/bin/things-cli` and `~/.local/bin/things` (or the copies in your custom installation directory). Uninstall the Things plugin in your host; for a local Cursor installation, remove `~/.cursor/plugins/local/things`. For a direct MCP registration, remove the `things` server from the host instead. None of these steps deletes your cloud tasks.

## Maintainer packaging

```bash
make package
```

This builds macOS/Linux binaries for x86-64 and ARM64, produces four installable archives and one portable plugin ZIP, and writes `dist/SHA256SUMS`. Packages contain an explicit file allowlist; credentials, cloud history, task caches, Git metadata, and local state are excluded.

Release tags use the `cloud-vVERSION` prefix. The CLI remains a Go module with its original import path; the prefix avoids implying an incompatible Go module major-version path.
