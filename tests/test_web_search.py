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
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )
        openai_class.return_value = client

        result = llm.search_web("documentação Kotlin")

        self.assertEqual(result["summary"], "Resumo dos resultados.")
        self.assertEqual(result["provider"], "OpenRouter + exa")
        self.assertEqual(result["sources"], [{
            "title": "Documentação",
            "url": "https://docs.example.org/page",
        }])
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(len(request["messages"]), 2)
        self.assertEqual(request["messages"][-1], {
            "role": "user",
            "content": "documentação Kotlin",
        })
        self.assertEqual(request["tools"][0]["type"], "openrouter:web_search")

    @patch.dict(os.environ, {
        "LLM_API_KEY": "test-key",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_WEB_SEARCH_ENABLED": "true",
    }, clear=False)
    @patch("app.llm.OpenAI")
    def test_search_refuses_to_claim_results_without_citations(self, openai_class):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=FakeMessage("Resposta sem fontes.", []))]
        )
        openai_class.return_value = client

        with self.assertRaisesRegex(RuntimeError, "fontes verificáveis"):
            llm.search_web("consulta de teste")

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
