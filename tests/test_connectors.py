import os
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException

from app.connectors import encrypt_secret, decrypt_secret, validate_mcp_endpoint, _safe_schema, execute_connector_tool, connector_tools, normalize_mcp_name, ensure_connector_enabled, github_permission_report, _connector_permissions, _connector_tool_enabled, GITHUB_TOOL_SPECS
from app.models import PendingAction, Connector, UploadedFile


class _ContextResponse:
    def __init__(self, response):
        self.response = response
    def __enter__(self):
        return self.response
    def __exit__(self, exc_type, exc, traceback):
        return False


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

    def test_github_permission_report_reads_exact_oauth_scopes(self):
        response = SimpleNamespace(
            headers={"X-OAuth-Scopes": "read:user, repo, workflow"},
            read=lambda size: b'{"login":"mikael8367"}',
        )
        opener = SimpleNamespace(open=lambda request, timeout: _ContextResponse(response))
        with patch("app.connectors.urllib.request.build_opener", return_value=opener):
            report = github_permission_report("fake-token")
        self.assertEqual(report["account"], "mikael8367")
        self.assertEqual(report["oauth_scopes"], ["read:user", "repo", "workflow"])
        self.assertEqual(report["scope_status"], "confirmed")

    def test_github_permission_report_does_not_infer_missing_scope_header(self):
        response = SimpleNamespace(
            headers={},
            read=lambda size: b'{"login":"mikael8367"}',
        )
        opener = SimpleNamespace(open=lambda request, timeout: _ContextResponse(response))
        with patch("app.connectors.urllib.request.build_opener", return_value=opener):
            report = github_permission_report("fake-token")
        self.assertIsNone(report["oauth_scopes"])
        self.assertEqual(report["scope_status"], "unavailable")

    def test_empty_connector_permissions_preserve_legacy_all_tools_behavior(self):
        connector = SimpleNamespace(tool_permissions="")
        self.assertIsNone(_connector_permissions(connector))
        self.assertTrue(_connector_tool_enabled(connector, "github_read_file"))

    def test_explicit_empty_permissions_disable_every_connector_tool(self):
        connector = SimpleNamespace(tool_permissions="[]")
        self.assertEqual(_connector_permissions(connector), set())
        self.assertFalse(_connector_tool_enabled(connector, "github_read_file"))

    def test_malformed_permissions_fail_closed(self):
        connector = SimpleNamespace(tool_permissions='{"unexpected":"value"}')
        self.assertEqual(_connector_permissions(connector), set())
        self.assertFalse(_connector_tool_enabled(connector, "github_read_file"))

    def test_expanded_github_catalog_contains_code_search_and_branch_tools(self):
        names = {tool["name"] for tool in GITHUB_TOOL_SPECS}
        self.assertIn("github_search_code", names)
        self.assertIn("github_list_branches", names)
        self.assertIn("github_create_branch", names)
        self.assertIn("github_list_pull_requests", names)

    def test_workspace_create_file_saves_text_artifact(self):
        class FakeDB:
            def add(self, item):
                self.item = item
            def commit(self):
                pass
            def refresh(self, item):
                item.id = 456
        db = FakeDB()
        result = execute_connector_tool("workspace_create_file", {
            "filename": "Example.java", "content": "class Example {}"
        }, db)
        self.assertTrue(result["ok"])
        self.assertEqual(result["file_id"], 456)
        self.assertEqual(db.item.file_data, b"class Example {}")
        self.assertEqual(db.item.extracted_text, "class Example {}")

    def test_workspace_update_requires_matching_content_hash(self):
        import hashlib
        item = SimpleNamespace(id=9, filename="Main.java", extracted_text="class Main {}", file_data=b"class Main {}", mime_type="text/plain")
        class FakeDB:
            def get(self, model, file_id):
                self.asserted = (model, file_id)
                return item
            def commit(self):
                pass
        db = FakeDB()
        digest = hashlib.sha256(item.extracted_text.encode("utf-8")).hexdigest()
        result = execute_connector_tool("workspace_update_file", {
            "file_id": 9, "content": "class Main { int x; }", "expected_sha256": digest
        }, db)
        self.assertTrue(result["ok"])
        self.assertEqual(item.extracted_text, "class Main { int x; }")

    def test_workspace_update_rejects_stale_content_hash(self):
        item = SimpleNamespace(id=9, filename="Main.java", extracted_text="class Main {}", file_data=b"class Main {}", mime_type="text/plain")
        class FakeDB:
            def get(self, model, file_id):
                return item
            def commit(self):
                raise AssertionError("Não deve salvar conteúdo com hash antigo")
        result = execute_connector_tool("workspace_update_file", {
            "file_id": 9, "content": "class Main { int x; }", "expected_sha256": "stale"
        }, FakeDB())
        self.assertIn("alterado desde a leitura", result["error"])
        self.assertEqual(item.extracted_text, "class Main {}")

    def test_rejects_plain_http_mcp(self):
        with self.assertRaises(HTTPException):
            validate_mcp_endpoint("http://example.com/mcp")

    def test_rejects_local_mcp_host(self):
        with self.assertRaises(HTTPException):
            validate_mcp_endpoint("https://localhost/mcp")

    def test_mcp_name_is_trimmed_and_whitespace_is_rejected(self):
        self.assertEqual(normalize_mcp_name("  servidor MCP  "), "servidor MCP")
        with self.assertRaises(HTTPException):
            normalize_mcp_name("   ")

    def test_disabled_connector_cannot_be_tested(self):
        with self.assertRaises(HTTPException) as error:
            ensure_connector_enabled(SimpleNamespace(enabled=False))
        self.assertEqual(error.exception.status_code, 409)

    def test_legacy_connector_without_enabled_field_remains_enabled(self):
        ensure_connector_enabled(SimpleNamespace())

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

    def test_disabled_connector_does_not_expose_tools(self):
        disabled = SimpleNamespace(provider="github", enabled=False)
        class FakeQuery:
            def all(self):
                return [disabled]
        class FakeDB:
            def query(self, model):
                self.asserted_model = model
                return FakeQuery()
        self.assertEqual(connector_tools(FakeDB()), [])

    def test_connector_has_enabled_flag_defaulting_to_true(self):
        self.assertIn("enabled", Connector.__table__.columns)
        self.assertIn("avatar_url", Connector.__table__.columns)
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
