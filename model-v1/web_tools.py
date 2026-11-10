"""Ferramentas web opcionais da Mikael AI V1.

Pesquisa usa Brave Search API quando BRAVE_SEARCH_API_KEY está configurada.
Leitura aceita somente HTTP(S) público e bloqueia destinos locais/privados.
Não executa JavaScript, não faz login e não envia formulários.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "MikaelAI-V1-WebReader/0.1 (+public-page text extraction)"
MAX_PAGE_BYTES = 1_500_000
MAX_REDIRECTS = 4
TIMEOUT = (5, 12)


class WebToolError(Exception):
    """Erro seguro e legível de pesquisa ou leitura web."""


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise WebToolError("Use um endereço HTTP ou HTTPS válido.")
    if parsed.username or parsed.password:
        raise WebToolError("URLs com credenciais não são permitidas.")
    host = parsed.hostname.rstrip(".")
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise WebToolError("Endereços locais não são permitidos.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = {ipaddress.ip_address(item[4][0]) for item in infos}
        except OSError as exc:
            raise WebToolError("Não foi possível localizar o site.") from exc
    if not addresses or any(not ip.is_global for ip in addresses):
        raise WebToolError("Por segurança, só é permitido acessar sites públicos.")
    return url


def _safe_get(url: str) -> requests.Response:
    current = url
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"})
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_public_url(current)
            response = session.get(current, timeout=TIMEOUT, allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise WebToolError("Redirecionamento sem destino.")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_PAGE_BYTES:
                response.close()
                raise WebToolError("A página é grande demais para leitura.")
            body = bytearray()
            for chunk in response.iter_content(16384):
                body.extend(chunk)
                if len(body) > MAX_PAGE_BYTES:
                    response.close()
                    raise WebToolError("A página excede o limite de leitura.")
            response._content = bytes(body)
            response._content_consumed = True
            return response
        raise WebToolError("O site excedeu o limite de redirecionamentos.")
    except requests.RequestException as exc:
        raise WebToolError("Falha ao acessar o site. Verifique a conexão e o endereço.") from exc
    finally:
        session.close()


def search_web(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Pesquisa na web; requer BRAVE_SEARCH_API_KEY. Retorna título, URL e resumo."""
    query = (query or "").strip()
    if not query:
        raise WebToolError("Digite o que deseja pesquisar.")
    if len(query) > 400:
        raise WebToolError("A pesquisa é muito longa.")
    if not 1 <= limit <= 10:
        raise WebToolError("O limite deve ficar entre 1 e 10 resultados.")
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise WebToolError("Pesquisa online não configurada: adicione BRAVE_SEARCH_API_KEY nas variáveis de ambiente.")
    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise WebToolError("Não foi possível concluir a pesquisa online.") from exc
    results = []
    for item in payload.get("web", {}).get("results", [])[:limit]:
        url = item.get("url", "")
        try:
            _validate_public_url(url)
        except WebToolError:
            continue
        results.append({
            "title": str(item.get("title", ""))[:300],
            "url": url,
            "snippet": str(item.get("description", ""))[:1200],
        })
    return results


def read_website(url: str, max_chars: int = 12000) -> dict[str, str]:
    """Lê texto visível de uma página pública HTML/texto; não executa scripts."""
    if not 500 <= max_chars <= 20000:
        raise WebToolError("max_chars deve ficar entre 500 e 20000.")
    response = _safe_get(url)
    content_type = response.headers.get("Content-Type", "").lower()
    if not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml+xml")):
        raise WebToolError("Este tipo de arquivo não é compatível; envie uma página HTML ou texto.")
    encoding = response.encoding or "utf-8"
    raw = response.content.decode(encoding, errors="replace")
    if "html" in content_type or "xhtml" in content_type:
        soup = BeautifulSoup(raw, "html.parser")
        for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
            node.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else url
        text = soup.get_text(" ", strip=True)
    else:
        title, text = url, raw
    text = " ".join(text.split())
    return {"url": response.url, "title": title[:300], "text": text[:max_chars]}


def format_sources(results: list[dict[str, str]]) -> str:
    """Formata resultados como contexto com URLs para atribuição."""
    return "\n\n".join(
        f"Fonte: {item['title']}\nURL: {item['url']}\nResumo: {item['snippet']}"
        for item in results
    )
