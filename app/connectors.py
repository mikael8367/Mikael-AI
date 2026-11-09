import base64
import ipaddress
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from cryptography.fernet import Fernet
from fastapi import HTTPException


def _cipher():
    import hashlib
    secret = (os.getenv("APP_SECRET") or "").encode()
    if len(secret) < 24:
        raise RuntimeError("APP_SECRET precisa ter pelo menos 24 caracteres.")
    key = base64.urlsafe_b64encode(hashlib.sha256(b"mikael-connectors:" + secret).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _cipher().decrypt(value.encode()).decode()


def validate_mcp_endpoint(value: str) -> str:
    parsed = urllib.parse.urlsplit((value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(400, "O servidor MCP precisa usar uma URL HTTPS válida, sem usuário ou senha na URL.")
    if parsed.query or parsed.fragment:
        raise HTTPException(400, "Remova parâmetros e fragmentos da URL. Use o campo de token separado.")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise HTTPException(400, "Endereços locais não são permitidos.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        if not addresses:
            raise ValueError("DNS vazio")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("IP não público")
    except Exception:
        raise HTTPException(400, "O host do MCP precisa resolver para um endereço IP público.")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_json(url: str, token: str | None = None, method: str = "GET", payload=None, extra_headers=None):
    headers = {"Accept": "application/vnd.github+json, application/json", "User-Agent": "Mikael-AI/1.8"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    headers.update(extra_headers or {})
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=18) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise RuntimeError("Resposta do conector excedeu 2 MB.")
            content_type = response.headers.get("Content-Type", "")
            text = raw.decode("utf-8", errors="replace")
            if "text/event-stream" in content_type:
                events = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
                text = next((event for event in reversed(events) if event and event != "[DONE]"), "{}")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError("O serviço externo recusou a solicitação (HTTP %s)." % exc.code)
    except urllib.error.URLError:
        raise RuntimeError("Não foi possível alcançar o serviço externo.")
    except (TimeoutError, socket.timeout):
        raise RuntimeError("O serviço externo demorou demais para responder.")


def _mcp_call(endpoint: str, token: str | None, method: str, params=None):
    endpoint = validate_mcp_endpoint(endpoint)
    headers = {"MCP-Protocol-Version": "2025-03-26"}
    init = _http_json(endpoint, token, "POST", {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "Mikael AI", "version": "1.8.0"}}
    }, headers)
    # Stateless servers may omit a session ID; stateful servers return it in the response.
    session = init.get("_session_id") if isinstance(init, dict) else None
    initialized_headers = dict(headers)
    if session:
        initialized_headers["Mcp-Session-Id"] = session
    _http_json(endpoint, token, "POST", {"jsonrpc": "2.0", "method": "notifications/initialized"}, initialized_headers)
    result = _http_json(endpoint, token, "POST", {
        "jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}
    }, initialized_headers)
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError("O servidor MCP retornou um erro ao processar a solicitação.")
    return result.get("result", result) if isinstance(result, dict) else result


def _safe_schema(schema):
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    allowed_types = {"object", "array", "string", "number", "integer", "boolean"}
    kind = schema.get("type")
    result = {"type": kind if kind in allowed_types else "object"}
    if isinstance(schema.get("description"), str):
        result["description"] = schema["description"][:500]
    if result["type"] == "object":
        props = schema.get("properties") or {}
        result["properties"] = {
            str(key)[:64]: _safe_schema(value)
            for key, value in list(props.items())[:40]
            if isinstance(key, str) and isinstance(value, dict)
        }
        required = schema.get("required") or []
        result["required"] = [x for x in required if isinstance(x, str) and x in result["properties"]][:40]
        result["additionalProperties"] = False
    elif result["type"] == "array":
        result["items"] = _safe_schema(schema.get("items") or {})
    if "enum" in schema and isinstance(schema["enum"], list):
        result["enum"] = schema["enum"][:30]
    return result


def connector_tools(db):
    from .models import Connector
    tools = []
    rows = db.query(Connector).all()
    for connector in rows:
        if connector.provider == "github":
            tools.extend([
                {"type": "function", "function": {"name": "github_list_repositories", "description": "Lista repositórios da conta GitHub conectada. Use quando o usuário pedir para ver seus repositórios.", "parameters": {"type": "object", "properties": {"visibility": {"type": "string", "enum": ["all", "public", "private"]}}, "additionalProperties": False}}},
                {"type": "function", "function": {"name": "github_read_file", "description": "Lê um arquivo de um repositório GitHub autorizado. Informe owner, repo e path.", "parameters": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "ref": {"type": "string"}}, "required": ["owner", "repo", "path"], "additionalProperties": False}}},
                {"type": "function", "function": {"name": "github_list_issues", "description": "Lista issues abertas de um repositório GitHub autorizado.", "parameters": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}}, "required": ["owner", "repo"], "additionalProperties": False}}}
            ])
        elif connector.provider == "mcp":
            try:
                token = decrypt_secret(connector.secret) if connector.secret else None
                result = _mcp_call(connector.endpoint, token, "tools/list")
                for tool in (result.get("tools") or [])[:25]:
                    original = tool.get("name")
                    if not isinstance(original, str) or not original:
                        continue
                    safe = "".join(ch if ch.isalnum() else "_" for ch in original)[:50]
                    name = "mcp_%s_%s" % (connector.id, safe)
                    tools.append({"type": "function", "function": {
                        "name": name,
                        "description": ("Servidor MCP %s: " % connector.name) + str(tool.get("description") or original)[:700],
                        "parameters": _safe_schema(tool.get("inputSchema"))
                    }})
            except Exception:
                continue
    return tools[:60]


def execute_connector_tool(name: str, arguments: dict, db):
    from .models import Connector
    connector = db.query(Connector).filter_by(provider="github").first()
    if name.startswith("github_"):
        if not connector:
            return {"error": "GitHub não está conectado."}
        token = decrypt_secret(connector.secret)
        if name == "github_list_repositories":
            visibility = arguments.get("visibility", "all")
            if visibility not in {"all", "public", "private"}:
                visibility = "all"
            data = _http_json("https://api.github.com/user/repos?per_page=50&sort=updated&visibility=" + visibility, token)
            return [{"full_name": x.get("full_name"), "private": x.get("private"), "description": x.get("description"), "url": x.get("html_url")} for x in data[:50]]
        if name == "github_read_file":
            owner, repo, path = arguments.get("owner"), arguments.get("repo"), arguments.get("path")
            if not all(isinstance(x, str) and x and len(x) < 200 for x in (owner, repo, path)):
                return {"error": "Parâmetros owner, repo e path inválidos."}
            ref = arguments.get("ref")
            query = urllib.parse.urlencode({"ref": ref}) if isinstance(ref, str) and ref else ""
            url = "https://api.github.com/repos/%s/%s/contents/%s" % tuple(urllib.parse.quote(x, safe="") for x in (owner, repo, path))
            data = _http_json(url + (("?" + query) if query else ""), token)
            if data.get("encoding") != "base64" or not data.get("content"):
                return {"error": "O caminho não corresponde a um arquivo de texto simples."}
            raw = base64.b64decode(data["content"])
            return {"path": data.get("path"), "content": raw.decode("utf-8", errors="replace")[:24000]}
        if name == "github_list_issues":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            if not all(isinstance(x, str) and x and len(x) < 100 for x in (owner, repo)):
                return {"error": "Owner ou repositório inválido."}
            data = _http_json("https://api.github.com/repos/%s/%s/issues?state=open&per_page=30" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe="")), token)
            return [{"number": x.get("number"), "title": x.get("title"), "url": x.get("html_url"), "state": x.get("state")} for x in data if "pull_request" not in x]
        return {"error": "Ferramenta GitHub desconhecida."}
    if name.startswith("mcp_"):
        parts = name.split("_", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            return {"error": "Ferramenta MCP inválida."}
        item = db.query(Connector).filter_by(id=int(parts[1]), provider="mcp").first()
        if not item:
            return {"error": "Conector MCP não encontrado."}
        token = decrypt_secret(item.secret) if item.secret else None
        # Revalida endpoint a cada chamada para reduzir risco de SSRF.
        result = _mcp_call(item.endpoint, token, "tools/call", {"name": arguments.pop("__tool_name", parts[2]), "arguments": arguments})
        return result
    return {"error": "Ferramenta desconhecida."}
