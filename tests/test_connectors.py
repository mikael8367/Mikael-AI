import os
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException

from app.connectors import encrypt_secret, decrypt_secret, validate_mcp_endpoint, _safe_schema, execute_connector_tool
from app.models import PendingAction, Connector


class ConnectorSecurityTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.get("APP_SECRET")
        os.environ["APP_SECRET"] = "test-secret-long-enough-for-connector-encryption"

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("APP_SECRET", None)
        else:
            os.environ["APP_SECRET"] = self.previous

    def test_secret_round_trip(self):
        encrypted = encrypt_secret("private-token-value")
        self.assertNotEqual(encrypted, "private-token-value")
        self.assertEqual(decrypt_secret(encrypted), "private-token-value")

    def test_rejects_plain_http_mcp(self):
        with self.assertRaises(HTTPException):
            validate_mcp_endpoint("http://example.com/mcp")

    def test_rejects_local_mcp_host(self):
        with self.assertRaises(HTTPException):
            validate_mcp_endpoint("https://localhost/mcp")

    def test_github_delete_creates_pending_request_without_deleting(self):
        github = SimpleNamespace(secret=encrypt_secret("github-test-token"))

        class FakeQuery:
            def __init__(self, first=None, count=0):
                self.first_value = first
                self.count_value = count
            def filter_by(self, **kwargs):
                return self
            def filter(self, *args):
                return self
            def first(self):
                return self.first_value
            def count(self):
                return self.count_value

        class FakeDB:
            def __init__(self):
                self.action = None
            def query(self, model):
                if model is Connector:
                    return FakeQuery(first=github)
                if model is PendingAction:
                    return FakeQuery(count=0)
                raise AssertionError("Modelo inesperado")
            def add(self, action):
                self.action = action
            def commit(self):
                pass
            def refresh(self, action):
                action.id = 123

        db = FakeDB()
        with patch("app.connectors._http_json", return_value={
            "type": "file", "sha": "blob-sha-123", "path": "src/old.py"
        }) as request:
            result = execute_connector_tool("github_delete_file", {
                "owner": "mikael8367", "repo": "Mikael-AI",
                "path": "src/old.py", "message": "Remove obsolete file",
                "_conversation_id": 7
            }, db)

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["action_id"], 123)
        self.assertEqual(db.action.status, "pending")
        self.assertEqual(db.action.conversation_id, 7)
        self.assertGreater(db.action.expires_at, int(time.time()))
        self.assertEqual(json.loads(db.action.arguments)["sha"], "blob-sha-123")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs.get("method", "GET"), "GET")

    def test_connector_has_enabled_flag_defaulting_to_true(self):
        self.assertIn("enabled", Connector.__table__.columns)
        self.assertTrue(Connector.__table__.columns["enabled"].default.arg)

    def test_pending_action_model_has_expiration_and_single_use_status(self):
        self.assertEqual(PendingAction.__tablename__, "pending_actions")
        columns = PendingAction.__table__.columns
        self.assertIn("arguments", columns)
        self.assertIn("status", columns)
        self.assertIn("expires_at", columns)
        self.assertIn("conversation_id", columns)

    def test_schema_is_limited_to_supported_fields(self):
        schema = _safe_schema({
            "type": "object",
            "properties": {"path": {"type": "string"}, "bad": {"type": "nonsense"}},
            "required": ["path", "missing"],
            "additionalProperties": True,
        })
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"]["bad"]["type"], "object")
        self.assertEqual(schema["required"], ["path"])
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
