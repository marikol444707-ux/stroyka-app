"""Offline MCP contract/security tests. Never contact a real worker."""
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from dev_control.jev_mcp_gateway import app

TOKEN = "t" * 48
ENV = {"JEV_MCP_ENABLED": "1", "JEV_MCP_ALLOWED_ORIGIN": "https://qa-mcp.example.test",
       "JEV_MCP_BEARER_TOKEN": TOKEN}
HEADERS = {"Authorization": "Bearer " + TOKEN}


class JevMCPTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def rpc(self, method, params=None, headers=None):
        data = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            data["params"] = params
        return self.client.post("/mcp", json=data, headers=headers or HEADERS)

    def test_disabled_and_wrong_token_or_origin(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.rpc("tools/list").status_code, 403)
        with patch.dict(os.environ, ENV, clear=True):
            self.assertEqual(self.rpc("tools/list", headers={"Authorization": "Bearer wrong"}).status_code, 403)
            self.assertEqual(self.rpc("tools/list", headers={**HEADERS, "Origin": "https://evil.test"}).status_code, 403)

    def test_initialize_and_tools_list(self):
        with patch.dict(os.environ, ENV, clear=True):
            self.assertEqual(self.rpc("initialize").json()["result"]["protocolVersion"], "2025-03-26")
            names = [x["name"] for x in self.rpc("tools/list").json()["result"]["tools"]]
            self.assertEqual(names, ["jev_qa_capabilities", "jev_qa_status", "jev_qa_start_smoke"])

    def test_unapproved_start_does_not_call_worker(self):
        with patch.dict(os.environ, ENV, clear=True), patch("dev_control.jev_mcp_gateway._worker") as worker:
            response = self.rpc("tools/call", {"name": "jev_qa_start_smoke", "arguments": {}})
            self.assertIn("QA_RELEASE_GATES_NOT_APPROVED", response.text)
            worker.assert_not_called()

    def test_status_reads_health_only_and_never_returns_raw_fields(self):
        with patch.dict(os.environ, ENV, clear=True), patch("dev_control.jev_mcp_gateway._worker") as worker:
            worker.return_value = {"ok": True, "environment": "qa",
                                   "watcher_target": "https://stroyka-qa-gateway/app",
                                   "secret": "sensitive"}
            response = self.rpc("tools/call", {"name": "jev_qa_status", "arguments": {}})
            self.assertIn("READY", response.text)
            self.assertNotIn("sensitive", response.text)
            worker.assert_called_once_with("GET", "/watcher/health")

    def test_unknown_tool_and_args_fail_closed(self):
        with patch.dict(os.environ, ENV, clear=True), patch("dev_control.jev_mcp_gateway._worker") as worker:
            self.assertIn("UNKNOWN_TOOL", self.rpc("tools/call", {"name": "shell", "arguments": {}}).text)
            self.assertIn("INVALID_ARGUMENTS", self.rpc("tools/call", {"name": "jev_qa_status", "arguments": {"url": "https://evil.test"}}).text)
            worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
