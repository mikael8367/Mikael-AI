import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import llm


class FakeMessage:
    def __init__(self, content, annotations):
        self.content = content
        self._annotations = annotations

    def model_dump(self):
        return {"annotations": self._annotations}


class WebSearchTests(unittest.TestCase):
    @patch.dict(os.environ, {
        "LLM_API_KEY": "test-key",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_WEB_SEARCH_ENABLED": "true",
        "LLM_WEB_SEARCH_ENGINE": "exa",
    }, clear=False)
    @patch("app.llm.OpenAI")
    def test_search_sends_only_explicit_query_and_returns_verified_sources(self, openai_class):
        message = FakeMessage("Resumo dos resultados.", [
            {"url_citation": {"title": "Documentação", "url": "https://docs.example.org/page"}},
            {"url_citation": {"title": "Duplicada", "url": "https://docs.example.org/page"}},
            {"url_citation": {"title": "URL inválida", "url": "javascript:alert(1)"}},
        ])
        client = Mock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage("ALLOW", []))]),
            SimpleNamespace(choices=[SimpleNamespace(message=message)]),
        ]
        openai_class.return_value = client

        result = llm.search_web("documentação Kotlin")

        self.assertEqual(result["summary"], "Resumo dos resultados.")
        self.assertEqual(result["provider"], "OpenRouter + exa")
        self.assertEqual(result["sources"], [{
            "title": "Documentação",
            "url": "https://docs.example.org/page",
        }])
        self.assertEqual(client.chat.completions.create.call_count, 2)
        safety_request = client.chat.completions.create.call_args_list[0].kwargs
        search_request = client.chat.completions.create.call_args_list[1].kwargs
        self.assertEqual(safety_request["messages"][-1], {
            "role": "user",
            "content": "documentação Kotlin",
        })
        self.assertEqual(search_request["messages"][-1], {
            "role": "user",
            "content": "documentação Kotlin",
        })
        self.assertEqual(search_request["tools"][0]["type"], "openrouter:web_search")

    @patch.dict(os.environ, {
        "LLM_API_KEY": "test-key",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_WEB_SEARCH_ENABLED": "true",
    }, clear=False)
    @patch("app.llm.OpenAI")
    def test_search_refuses_to_claim_results_without_citations(self, openai_class):
        client = Mock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage("ALLOW", []))]),
            SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage("Resposta sem fontes.", []))]),
        ]
        openai_class.return_value = client

        with self.assertRaisesRegex(RuntimeError, "fontes verificáveis"):
            llm.search_web("consulta de teste")

    @patch.dict(os.environ, {
        "LLM_API_KEY": "test-key",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_WEB_SEARCH_ENABLED": "true",
    }, clear=False)
    @patch("app.llm.OpenAI")
    def test_blocked_query_never_reaches_web_search_tool(self, openai_class):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=FakeMessage("BLOCK", []))]
        )
        openai_class.return_value = client

        with self.assertRaises(PermissionError):
            llm.search_web("consulta não permitida")

        self.assertEqual(client.chat.completions.create.call_count, 1)
        request = client.chat.completions.create.call_args.kwargs
        self.assertNotIn("tools", request)

    def test_search_rejects_empty_or_oversized_queries(self):
        with self.assertRaises(ValueError):
            llm.search_web(" ")
        with self.assertRaises(ValueError):
            llm.search_web("x" * 501)

    @patch.dict(os.environ, {"LLM_WEB_SEARCH_ENABLED": "false"}, clear=False)
    @patch("app.llm.OpenAI")
    def test_disabled_search_does_not_call_provider(self, openai_class):
        with self.assertRaisesRegex(RuntimeError, "desativada"):
            llm.search_web("consulta")
        openai_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
