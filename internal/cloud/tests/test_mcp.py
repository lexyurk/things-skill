import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from things_cloud.mcp import handle
from things_cloud.service import Service
from test_service import FakeCloud
from test_model import TASK, ordinary

ROOT = Path(__file__).resolve().parents[1] / "runtime"


class MCPTests(unittest.TestCase):
    def test_subprocess_handshake_tools_and_error_are_clean_newline_json(self):
        with tempfile.TemporaryDirectory() as directory:
            messages = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "things_status", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "things_list_tasks", "arguments": {}}},
            ]
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/things-cloud.py"), "--data-dir", directory, "serve"],
                input="\n".join(json.dumps(item) for item in messages) + "\n",
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            responses = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([item["id"] for item in responses], [1, 2, 3, 4])
            self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-11-25")
            self.assertEqual(len(responses[1]["result"]["tools"]), 13)
            self.assertFalse(responses[2]["result"]["structuredContent"]["connected"])
            self.assertTrue(responses[3]["result"]["isError"])
            self.assertEqual(result.stderr, "")

    def test_tool_validation_blocks_unknown_arguments_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            cloud = FakeCloud()
            service = Service(directory, cloud_factory=lambda **kwargs: cloud)
            service.connect("test@example.com", "hidden")
            result = handle(
                service,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "things_create_task", "arguments": {"title": "x", "raw_payload": {}}},
                },
            )
            self.assertTrue(result["result"]["isError"])
            self.assertFalse(cloud.commits)

    def test_actual_mcp_tool_mutation_uses_same_sync_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            cloud = FakeCloud()
            service = Service(directory, cloud_factory=lambda **kwargs: cloud)
            service.connect("test@example.com", "hidden")
            cloud.events = [{TASK: {"e": "Task7", "t": 0, "p": ordinary()["p"]}}]
            response = handle(
                service,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "things_complete_task", "arguments": {"task_id": TASK, "request_id": "mcp-complete-1"}},
                },
            )
            self.assertFalse(response["result"]["isError"])
            self.assertTrue(response["result"]["structuredContent"]["synced"])
            self.assertEqual(service.get_task(TASK)["task"]["status"], "completed")

    def test_jsonrpc_bad_params_and_unknown_method(self):
        self.assertEqual(handle(None, {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []})["error"]["code"], -32602)
        self.assertEqual(handle(None, {"jsonrpc": "2.0", "id": 1, "method": "unknown"})["error"]["code"], -32601)
        self.assertIsNone(handle(None, {"jsonrpc": "2.0", "method": "notifications/initialized"}))


if __name__ == "__main__":
    unittest.main()
