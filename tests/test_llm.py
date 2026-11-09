import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import llm


class LocalInferenceTests(unittest.TestCase):
    def test_local_client_does_not_require_openrouter_key(self):
        env = {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "https://model.example/v1",
            "LLM_LOCAL_MODEL": "mikael-coder",
            "LLM_LOCAL_API_KEY": "private-test-token",
        }
        with patch.dict(os.environ, env, clear=True), patch("app.llm.OpenAI") as client:
            llm.get_client()
        kwargs = client.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "https://model.example/v1")
        self.assertEqual(kwargs["api_key"], "private-test-token")
        self.assertEqual(kwargs["timeout"], 300)

    def test_local_client_never_falls_back_to_openrouter_url_or_key(self):
        env = {
            "LLM_PROVIDER": "local",
            "LLM_API_KEY": "openrouter-secret-placeholder",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LLM_LOCAL_BASE_URL"):
                llm.get_client()

    def test_local_client_requires_server_authentication(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "https://model.example/v1",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LLM_LOCAL_API_KEY"):
                llm.get_client()

    def test_local_client_rejects_public_plain_http_endpoint(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "http://model.example/v1",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "deve usar HTTPS"):
                llm.get_client()

    def test_local_mode_disables_openrouter_web_search(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "https://model.example/v1",
        }, clear=True):
            self.assertEqual(llm._web_search_tools(), [])

    def test_local_chat_omits_openrouter_specific_reasoning_extension(self):
        message = SimpleNamespace(content="Resposta local", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        create = Mock(return_value=response)
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        env = {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "https://model.example/v1",
            "LLM_LOCAL_MODEL": "mikael-coder",
            "LLM_LOCAL_API_KEY": "private-test-token",
        }
        with patch.dict(os.environ, env, clear=True), patch("app.llm.OpenAI", return_value=fake_client):
            result = llm.answer([{"role": "user", "content": "Explique uma função Python"}])
        self.assertEqual(result, "Resposta local")
        self.assertEqual(create.call_args.kwargs["model"], "mikael-coder")
        self.assertNotIn("extra_body", create.call_args.kwargs)

    def test_local_mode_blocks_paid_model_presets(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "local",
            "LLM_LOCAL_BASE_URL": "https://model.example/v1",
            "LLM_LOCAL_MODEL": "mikael-coder",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Modelos externos pagos ficam bloqueados"):
                llm.answer([{"role": "user", "content": "Oi"}], model_id="deepseek")

    def test_local_mode_blocks_external_image_generation(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "local"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "bloqueada para impedir uso acidental"):
                llm.generate_image("Uma paisagem")


if __name__ == "__main__":
    unittest.main()
