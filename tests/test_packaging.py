import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_each_plugin_mcp_entry_discovers_tools_with_shared_installed_cli(self):
        binary = os.environ.get("THINGS_PACKAGE_TEST_BINARY") or str(ROOT / "bin/things-cli")
        if not Path(binary).is_file():
            self.skipTest("Build the CLI or set THINGS_PACKAGE_TEST_BINARY before package integration tests.")
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "plugin-test", "version": "1"}},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "things_status", "arguments": {}}},
        ]
        for manifest in ("mcp.json", ".mcp.json"):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as directory:
                config = json.loads((ROOT / manifest).read_text())["mcpServers"]["things"]
                env = {
                    **os.environ,
                    "THINGS_CLI_BINARY": str(Path(binary).resolve()),
                    "THINGS_CLOUD_DATA_DIR": directory,
                    "THINGS_CLOUD_PYTHON": sys.executable,
                }
                result = subprocess.run(
                    [sys.executable] + config["args"],
                    input="\n".join(json.dumps(r) for r in requests) + "\n",
                    text=True,
                    capture_output=True,
                    env=env,
                    cwd=directory,
                    timeout=15,
                    check=True,
                )
                replies = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual([r["id"] for r in replies], [1, 2, 3])
                self.assertEqual(len(replies[1]["result"]["tools"]), 13)
                self.assertFalse(replies[2]["result"]["structuredContent"]["connected"])
                self.assertEqual(result.stderr, "")

    def test_missing_cli_is_actionable_and_stdout_remains_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            server = json.loads((ROOT / "mcp.json").read_text())["mcpServers"]["things"]
            result = subprocess.run(
                [sys.executable] + server["args"],
                capture_output=True,
                text=True,
                env={**os.environ, "THINGS_CLI_BINARY": str(Path(directory) / "missing")},
                timeout=5,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("Install the macOS/Linux package", result.stderr)


if __name__ == "__main__":
    unittest.main()
