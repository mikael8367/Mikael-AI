import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from artifact_tools import ArtifactManager, ArtifactError, register_artifact_connectors
from connectors import ConnectorRegistry

PNG = b"\\x89PNG\\r\\n\\x1a\\n" + b"test-image"

def test_create_text_file_returns_metadata_and_saves_utf8(tmp_path):
    manager = ArtifactManager(tmp_path, url_builder=lambda artifact_id: "/download/" + artifact_id)
    result = manager.create_text_file("olá.py", "print('Olá 🙂')")
    saved = tmp_path / result["filename"]
    assert saved.read_text(encoding="utf-8") == "print('Olá 🙂')"
    assert result["mime_type"].startswith("text/x-python")
    assert result["download_url"].startswith("/download/")

def test_rejects_path_traversal_and_disallowed_extension(tmp_path):
    manager = ArtifactManager(tmp_path)
    with pytest.raises(ArtifactError):
        manager.create_text_file("../secret.txt", "x")
    with pytest.raises(ArtifactError):
        manager.create_text_file("payload.exe", "x")

def test_rejects_empty_and_oversized_text(tmp_path):
    manager = ArtifactManager(tmp_path)
    with pytest.raises(ArtifactError):
        manager.create_text_file("empty.txt", "")
    with pytest.raises(ArtifactError):
        manager.create_text_file("large.txt", "a" * (2_000_001))

def test_image_generation_validates_real_format_and_saves(tmp_path):
    manager = ArtifactManager(tmp_path)
    result = manager.create_image_file("dragao.png", "Um dragão azul", lambda prompt: PNG)
    assert (tmp_path / result["filename"]).read_bytes() == PNG
    assert result["mime_type"] == "image/png"

def test_image_rejects_fake_format_and_missing_provider(tmp_path):
    manager = ArtifactManager(tmp_path)
    with pytest.raises(ArtifactError):
        manager.create_image_file("fake.png", "Uma imagem", lambda prompt: b"not png")
    with pytest.raises(ArtifactError):
        manager.create_image_file("x.png", "Uma imagem", None)

def test_registry_only_adds_image_connector_when_provider_exists(tmp_path):
    manager = ArtifactManager(tmp_path)
    registry = ConnectorRegistry()
    register_artifact_connectors(registry, manager)
    assert [item["name"] for item in registry.describe()] == ["create_text_file"]
    registry2 = ConnectorRegistry()
    register_artifact_connectors(registry2, manager, lambda prompt: PNG)
    assert {item["name"] for item in registry2.describe()} == {"create_text_file", "create_image"}
