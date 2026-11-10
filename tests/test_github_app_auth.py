import base64
import json
import os
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app import connectors


def _decode(segment):
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


class GitHubAppAuthTests(unittest.TestCase):
    def setUp(self):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        self.env = patch.dict(os.environ, {
            "GITHUB_APP_ID": "123456",
            "GITHUB_PRIVATE_KEY": pem,
            "APP_SECRET": "test-secret-with-at-least-24-characters",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_app_jwt_is_rs256_and_uses_app_id(self):
        token = connectors.github_app_jwt()
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_decode(header_part))
        payload = json.loads(_decode(payload_part))
        self.assertEqual(header["alg"], "RS256")
        self.assertEqual(payload["iss"], "123456")
        self.assertLessEqual(payload["exp"] - payload["iat"], 600)
        self.private_key.public_key().verify(
            _decode(signature_part),
            (header_part + "." + payload_part).encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_installation_token_uses_app_jwt(self):
        with patch.object(connectors, "github_app_jwt", return_value="signed-app-jwt"), patch.object(
            connectors, "_http_json", return_value={"token": "installation-token"}
        ) as request:
            token = connectors.github_installation_token("98765")
        self.assertEqual(token, "installation-token")
        request.assert_called_once_with(
            "https://api.github.com/app/installations/98765/access_tokens",
            "signed-app-jwt",
            method="POST",
            payload={},
        )

    def test_connector_metadata_and_legacy_oauth_token(self):
        class Connector:
            endpoint = '{"installation_id":"98765"}'
            secret = connectors.encrypt_secret("legacy-user-token")
        connector = Connector()
        self.assertEqual(connectors.github_connector_data(connector)["installation_id"], "98765")
        self.assertEqual(connectors.github_oauth_token(connector), "legacy-user-token")


if __name__ == "__main__":
    unittest.main()
