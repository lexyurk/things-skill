# Install Things Cloud on macOS or Linux

The CLI and all three plugin hosts use the same Go executable and the same persisted account. Python 3.9+ is required at runtime; no pip packages are needed. Go is required only to build from source.

## Binary package

Choose `darwin-arm64` for Apple Silicon, `darwin-amd64` for Intel Macs, `linux-amd64` for Intel/AMD Linux PCs, or `linux-arm64` for ARM Linux machines. Extract the matching `things-cli-VERSION-PLATFORM.tar.gz`, then run:

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
things-cli login
things-cli list today
```

The installer adds `things-cli` and the compatible `things` alias to `~/.local/bin`. Pass another directory to `./install.sh /your/bin`. `THINGS_CLI_BINARY` can select a custom executable for the plugin. The package includes a `plugin/` folder containing the plugin and all marketplace files.

## Source package

Until PR #3 is merged, install from the Cloud branch:

```bash
git clone --branch feat/cloud-mcp https://github.com/lexyurk/things-skill.git
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

For the published Git branch, you can instead add `lexyurk/things-skill --ref feat/cloud-mcp`. Older Codex clients can use the Plugins Directory after adding the marketplace, or register the MCP server directly. The repository contains a portable Agent Plugins manifest, Codex compatibility manifest, and `.agents/plugins/marketplace.json` catalog. See the [official packaging documentation](https://developers.openai.com/plugins/build/plugins).

## Claude Code plugin

From the same plugin root:

```bash
claude plugin marketplace add .
claude plugin install things@lexyurk-things
```

For development, `claude --plugin-dir /absolute/path/to/things-skill` loads the checkout. The repository includes `.claude-plugin/plugin.json`, its marketplace, and the shared MCP entry. See the [Claude manifest reference](https://code.claude.com/docs/en/plugins-reference).

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

## Maintainer packaging

```bash
make package
```

This builds macOS/Linux binaries for x86-64 and ARM64, produces four installable archives and one portable plugin ZIP, and writes `dist/SHA256SUMS`. Packages contain an explicit file allowlist; credentials, cloud history, task caches, Git metadata, and local state are excluded.
