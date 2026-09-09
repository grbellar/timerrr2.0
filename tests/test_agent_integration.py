"""Optional MCP and runner tests using a disposable HTTP server and database."""

import asyncio
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from werkzeug.serving import make_server

from app import create_app
from app.models import AgentToken, Client, User, db
from app.work_service import now

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    importlib.util.find_spec("mcp"), "Install requirements-mcp.txt for protocol tests"
)
class AgentIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        with patch.dict(
            os.environ, {"DATABASE_PATH": cls.directory.name + "/integration.db"}
        ):
            cls.app, _ = create_app()
        with cls.app.app_context():
            user = User(email="protocol@example.com", password_hash="unused")
            user.start_trial()
            db.session.add(user)
            db.session.flush()
            client = Client(user_id=user.id, name="Protocol client")
            db.session.add(client)
            db.session.add(
                AgentToken(
                    user_id=user.id,
                    name="Test token",
                    token_hash=hashlib.sha256(b"integration-test-token").hexdigest(),
                    scopes="work:read work:write draft:write",
                    expires_at=now() + timedelta(days=1),
                )
            )
            db.session.commit()
            cls.client_id = client.id
        cls.http = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.env = {
            **os.environ,
            "TIMERRR_URL": f"http://127.0.0.1:{cls.http.server_port}",
            "TIMERRR_TOKEN": "integration-test-token",
        }

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.thread.join(timeout=5)
        cls.http.server_close()
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.directory.cleanup()

    def test_stdio_protocol_and_ui_resource(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def check():
            params = StdioServerParameters(
                command=sys.executable, args=[str(ROOT / "mcp_server.py")], env=self.env
            )
            async with (
                stdio_client(params) as (read, write),
                ClientSession(read, write) as client,
            ):
                await client.initialize()
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 8)
                self.assertFalse(any(t.name == "approve_draft" for t in tools.tools))
                resources = await client.list_resources()
                ui = await client.read_resource(resources.resources[0].uri)
                self.assertEqual(ui.contents[0].mimeType, "text/html;profile=mcp-app")
                self.assertIn("ui/initialize", ui.contents[0].text)
                result = await client.call_tool("list_clients", {})
                self.assertFalse(result.isError)
                self.assertEqual(
                    result.structuredContent["clients"][0]["id"], self.client_id
                )
                arguments = {
                    "client_id": self.client_id,
                    "title": "MCP test",
                    "actor_id": "agent",
                    "actor_kind": "agent",
                    "budget_seconds": 60,
                    "request_id": str(uuid4()),
                }
                started = await client.call_tool("start_work", arguments)
                self.assertFalse(started.isError, started)
                replay = await client.call_tool("start_work", arguments)
                self.assertEqual(started.structuredContent, replay.structuredContent)
                wid = started.structuredContent["work"]["id"]
                finished = await client.call_tool(
                    "finish_work",
                    {
                        "work_id": wid,
                        "summary": "Protocol test passed",
                        "request_id": str(uuid4()),
                    },
                )
                self.assertFalse(finished.isError, finished)
                invalid = await client.call_tool("start_work", {})
                self.assertTrue(invalid.isError)

        asyncio.run(check())

    @unittest.skipUnless(os.name == "posix", "Runner requires POSIX process groups")
    def test_runner_cutoff_and_token_isolation(self):
        command = [
            sys.executable,
            "-m",
            "agent_tools.runner",
            "--client-id",
            str(self.client_id),
            "--title",
            "Budget test",
            "--budget",
            "2",
            "--",
            sys.executable,
            "-c",
            "import os,time; assert 'TIMERRR_TOKEN' not in os.environ; time.sleep(30)",
        ]
        started = time.monotonic()
        result = subprocess.run(
            command,
            env=self.env,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(time.monotonic() - started, 12)
        self.assertIn("budget or lease boundary", result.stderr)

    @unittest.skipUnless(os.name == "posix", "Runner requires POSIX process groups")
    def test_runner_preserves_exit_code(self):
        command = [
            sys.executable,
            "-m",
            "agent_tools.runner",
            "--client-id",
            str(self.client_id),
            "--title",
            "Exit test",
            "--budget",
            "30",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(7)",
        ]
        result = subprocess.run(
            command,
            env=self.env,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 7, result.stderr)


if __name__ == "__main__":
    unittest.main()
