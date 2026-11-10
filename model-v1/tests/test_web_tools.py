import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from web_tools import WebToolError, _validate_public_url
from response_policy import build_conversation_prompt

def test_rejects_non_http_and_local_urls():
    with pytest.raises(WebToolError):
        _validate_public_url("file:///etc/passwd")
    with pytest.raises(WebToolError):
        _validate_public_url("http://127.0.0.1/")
    with pytest.raises(WebToolError):
        _validate_public_url("http://localhost/")

def test_rejects_credentials_in_url():
    with pytest.raises(WebToolError):
        _validate_public_url("https://user:pass@example.com/")

def test_simple_answer_policy_is_portuguese_and_concise():
    prompt = build_conversation_prompt("Quanto é 2 + 2?")
    assert "português brasileiro" in prompt
    assert "curta, direta e clara" in prompt
    assert prompt.endswith("Mikael AI:")

def test_web_context_is_marked_untrusted_and_requires_sources():
    prompt = build_conversation_prompt("Resuma", "Fonte: Exemplo\nURL: https://example.com")
    assert "dado não confiável" in prompt
    assert "https://example.com" in prompt

def test_empty_user_message_rejected():
    with pytest.raises(ValueError):
        build_conversation_prompt("   ")
