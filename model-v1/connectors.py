"""Registro de conectores controlados para Mikael AI V1.

O modelo apenas solicita uma ferramenta por nome e argumentos. O host decide
se permite a chamada, executa a função registrada e devolve dados estruturados.
Não existe execução de código arbitrário nem acesso implícito a credenciais.
"""
from dataclasses import dataclass
from typing import Any, Callable
import json

class ConnectorError(Exception):
    pass

@dataclass(frozen=True)
class Connector:
    name: str
    description: str
    handler: Callable[..., Any]
    requires_internet: bool = False

class ConnectorRegistry:
    def __init__(self):
        self._items: dict[str, Connector] = {}

    def register(self, connector: Connector):
        if not connector.name or not connector.name.replace("_", "").isalnum():
            raise ConnectorError("Nome de conector inválido.")
        if connector.name in self._items:
            raise ConnectorError(f"Conector já registrado: {connector.name}")
        self._items[connector.name] = connector

    def describe(self) -> list[dict[str, str | bool]]:
        return [
            {"name": c.name, "description": c.description, "requires_internet": c.requires_internet}
            for c in self._items.values()
        ]

    def call(self, name: str, arguments: dict[str, Any], *, internet_available: bool = False):
        connector = self._items.get(name)
        if connector is None:
            raise ConnectorError("Ferramenta não disponível.")
        if connector.requires_internet and not internet_available:
            raise ConnectorError("Este conector precisa de internet.")
        if not isinstance(arguments, dict):
            raise ConnectorError("Argumentos devem ser um objeto.")
        try:
            result = connector.handler(**arguments)
            # Limita o volume que volta para o modelo e garante serialização.
            encoded = json.dumps(result, ensure_ascii=False, default=str)
            if len(encoded) > 24000:
                raise ConnectorError("Resultado muito grande; reduza a consulta.")
            return result
        except TypeError as exc:
            raise ConnectorError("Argumentos incompatíveis com a ferramenta.") from exc

def build_default_registry():
    from web_tools import search_web, read_website
    registry = ConnectorRegistry()
    registry.register(Connector(
        "web_search", "Pesquisa na internet e retorna títulos, resumos e URLs.",
        search_web, requires_internet=True
    ))
    registry.register(Connector(
        "open_website", "Lê o texto de uma página pública HTTP ou HTTPS.",
        read_website, requires_internet=True
    ))
    return registry
