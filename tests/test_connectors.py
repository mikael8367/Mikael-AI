import os
import unittest
from fastapi import HTTPException

from app.connectors import encrypt_secret, decrypt_secret, validate_mcp_endpoint, _safe_schema


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
