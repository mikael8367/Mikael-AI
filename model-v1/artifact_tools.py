"""Criação controlada de arquivos e imagens para entrega pelo aplicativo.

A camada de armazenamento não publica arquivos sozinha. O host deve configurar
uma URL de download autenticada ou transferir os bytes ao cliente.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import mimetypes
import os
import re
import uuid

TEXT_TYPES = {
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".py": "text/x-python; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".xml": "application/xml",
    ".yaml": "text/yaml; charset=utf-8",
    ".yml": "text/yaml; charset=utf-8",
    ".java": "text/x-java-source; charset=utf-8",
    ".kt": "text/plain; charset=utf-8",
    ".c": "text/x-c; charset=utf-8",
    ".cpp": "text/x-c++; charset=utf-8",
}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MAX_TEXT_BYTES = 2_000_000
MAX_IMAGE_BYTES = 15_000_000
MAX_PROMPT_CHARS = 4000

class ArtifactError(Exception):
    pass

@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    filename: str
    mime_type: str
    size: int
    download_url: Optional[str] = None

    def as_dict(self):
        result = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
        }
        if self.download_url:
            result["download_url"] = self.download_url
        return result

class ArtifactManager:
    def __init__(self, output_dir, url_builder: Optional[Callable[[str], str]] = None):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.url_builder = url_builder

    @staticmethod
    def _validate_filename(filename, allowed):
        if not isinstance(filename, str) or not filename.strip():
            raise ArtifactError("Informe um nome de arquivo.")
        if len(filename) > 120 or "/" in filename or "\\" in filename:
            raise ArtifactError("Nome de arquivo inválido.")
        name = Path(filename).name
        if name in ("", ".", "..") or name != filename:
            raise ArtifactError("Caminho não permitido.")
        if not re.fullmatch(r"[A-Za-z0-9À-ÿ _.-]+", name):
            raise ArtifactError("Use letras, números, espaços, ponto, hífen ou sublinhado no nome.")
        suffix = Path(name).suffix.lower()
        if suffix not in allowed:
            raise ArtifactError("Tipo de arquivo não permitido.")
        return name, suffix

    def _write(self, filename, suffix, data, mime):
        artifact_id = uuid.uuid4().hex
        safe_name = f"{Path(filename).stem[:80]}-{artifact_id[:10]}{suffix}"
        target = (self.output_dir / safe_name).resolve()
        if target.parent != self.output_dir or target.exists() or target.is_symlink():
            raise ArtifactError("Não foi possível reservar o arquivo de saída.")
        temp = self.output_dir / f".{artifact_id}.tmp"
        try:
            with temp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        except OSError as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise ArtifactError("Falha ao salvar o arquivo.") from exc
        url = self.url_builder(artifact_id) if self.url_builder else None
        return Artifact(artifact_id, safe_name, mime, len(data), url)

    def create_text_file(self, filename, content):
        name, suffix = self._validate_filename(filename, TEXT_TYPES)
        if not isinstance(content, str):
            raise ArtifactError("O conteúdo do arquivo precisa ser texto.")
        data = content.encode("utf-8")
        if not data or len(data) > MAX_TEXT_BYTES:
            raise ArtifactError("Arquivo vazio ou maior que o limite de 2 MB.")
        return self._write(name, suffix, data, TEXT_TYPES[suffix]).as_dict()

    def create_image_file(self, filename, prompt, image_generator):
        name, suffix = self._validate_filename(filename, IMAGE_TYPES)
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
            raise ArtifactError("Descrição da imagem vazia ou muito longa.")
        if not callable(image_generator):
            raise ArtifactError("Geração de imagens não está configurada.")
        try:
            data = image_generator(prompt.strip())
        except Exception as exc:
            raise ArtifactError("O serviço de geração de imagens falhou.") from exc
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ArtifactError("O serviço não retornou uma imagem válida.")
        data = bytes(data)
        if len(data) > MAX_IMAGE_BYTES:
            raise ArtifactError("A imagem excede o limite de 15 MB.")
        signatures = {
            ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": data.startswith(b"\xff\xd8\xff"),
            ".jpeg": data.startswith(b"\xff\xd8\xff"),
            ".webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        }
        if not signatures[suffix]:
            raise ArtifactError("Os bytes retornados não correspondem ao formato da imagem.")
        return self._write(name, suffix, data, IMAGE_TYPES[suffix]).as_dict()

def register_artifact_connectors(registry, manager, image_generator=None):
    """Registra somente ações de criação explicitamente autorizadas pelo host."""
    from connectors import Connector
    registry.register(Connector(
        "create_text_file",
        "Cria um arquivo de texto/código e retorna metadados para o host entregar ao usuário.",
        manager.create_text_file,
    ))
    if image_generator is not None:
        registry.register(Connector(
            "create_image",
            "Gera uma imagem por um provedor configurado e salva o resultado para entrega.",
            lambda filename, prompt: manager.create_image_file(filename, prompt, image_generator),
            requires_internet=True,
        ))
