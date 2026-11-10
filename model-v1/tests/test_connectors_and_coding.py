import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from connectors import Connector, ConnectorError, ConnectorRegistry
from coding_tools import check_code
from dataset_tools import load_jsonl, prepare

def test_registry_lists_and_calls_registered_connector():
    registry = ConnectorRegistry()
    registry.register(Connector("hello", "Teste", lambda name: {"hello": name}))
    assert registry.call("hello", {"name": "Mikael"}) == {"hello": "Mikael"}
    assert registry.describe()[0]["name"] == "hello"

def test_registry_rejects_duplicate_and_unknown_connector():
    registry = ConnectorRegistry()
    registry.register(Connector("hello", "Teste", lambda: "ok"))
    with pytest.raises(ConnectorError):
        registry.register(Connector("hello", "Duplicado", lambda: "x"))
    with pytest.raises(ConnectorError):
        registry.call("not_registered", {})

def test_registry_requires_internet_and_dict_arguments():
    registry = ConnectorRegistry()
    registry.register(Connector("online", "Teste", lambda: "ok", requires_internet=True))
    with pytest.raises(ConnectorError):
        registry.call("online", {}, internet_available=False)
    with pytest.raises(ConnectorError):
        registry.call("online", [], internet_available=True)

def test_python_static_syntax_checker():
    assert check_code("print('oi')").valid
    invalid = check_code("if True print('x')")
    assert not invalid.valid and "linha" in invalid.message

def test_other_language_is_not_claimed_as_verified():
    result = check_code("console.log('oi')", "javascript")
    assert not result.valid and "ainda não disponível" in result.message

def test_dataset_jsonl_validation_and_prepare(tmp_path):
    source = tmp_path / "examples.jsonl"
    source.write_text('{"instruction":"Oi","response":"Olá!"}\n', encoding="utf-8")
    examples, errors = load_jsonl(source)
    assert len(examples) == 1 and not errors
    output = tmp_path / "train.txt"
    assert prepare(source, output) == 1
    assert "Usuário: Oi" in output.read_text(encoding="utf-8")

def test_dataset_rejects_invalid_rows(tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text('{"instruction":"","response":"x"}\n', encoding="utf-8")
    examples, errors = load_jsonl(source)
    assert not examples and errors
