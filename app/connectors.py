import base64
import ipaddress
import json
import os
import time
import socket
import urllib.error
import urllib.parse
import urllib.request
from cryptography.fernet import Fernet
from fastapi import HTTPException


def normalize_mcp_name(value: str) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if len(name) < 2 or len(name) > 120:
        raise HTTPException(422, "O nome do conector precisa ter entre 2 e 120 caracteres.")
    return name


def ensure_connector_enabled(connector) -> None:
    if not bool(getattr(connector, "enabled", True)):
        raise HTTPException(409, "Este conector está desabilitado. Habilite-o antes de testar.")


def github_permission_report(token: str) -> dict:
    """Consulta /user e lê X-OAuth-Scopes; nunca infere escopos ausentes."""
    request = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Mikael-AI/1.13",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=18) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise RuntimeError("Resposta do GitHub excedeu o limite esperado.")
            account_data = json.loads(raw.decode("utf-8")) if raw else {}
            header = response.headers.get("X-OAuth-Scopes")
            scopes = sorted({part.strip() for part in header.split(",") if part.strip()}) if header is not None else None
            return {
                "account": str(account_data.get("login") or ""),
                "scope_status": "confirmed" if header is not None else "unavailable",
                "oauth_scopes": scopes,
                "scope_header_available": header is not None,
                "checked_at": int(time.time()),
            }
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("O GitHub rejeitou o token. A autorização pode ter expirado ou sido revogada.")
        raise RuntimeError("O GitHub recusou a consulta de permissões (HTTP %s)." % exc.code)
    except urllib.error.URLError:
        raise RuntimeError("Não foi possível alcançar o GitHub para consultar as permissões.")
    except (TimeoutError, socket.timeout):
        raise RuntimeError("O GitHub demorou demais para responder.")


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
    # MCP Streamable HTTP sessions may require the session ID returned by initialize.
    init = _mcp_post(endpoint, token, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "Mikael AI", "version": "1.8.0"}}
    }, headers)
    session = init.get("_session_id") if isinstance(init, dict) else None
    if session:
        headers["Mcp-Session-Id"] = session
    _mcp_post(endpoint, token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers)
    result = _mcp_post(endpoint, token, {
        "jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}
    }, headers)
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError("O servidor MCP retornou um erro ao processar a solicitação.")
    return result.get("result", result) if isinstance(result, dict) else result


def _mcp_post(endpoint, token, payload, headers=None):
    import urllib.error
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "Mikael-AI/1.8",
        **(headers or {})
    }
    if token:
        request_headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers=request_headers, method="POST")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=18) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise RuntimeError("Resposta MCP excedeu 2 MB.")
            session_id = response.headers.get("Mcp-Session-Id")
            content_type = response.headers.get("Content-Type", "")
            text = raw.decode("utf-8", errors="replace")
            if "text/event-stream" in content_type:
                events = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
                text = next((event for event in reversed(events) if event and event != "[DONE]"), "{}")
            result = json.loads(text) if text else {}
            if isinstance(result, dict) and session_id:
                result["_session_id"] = session_id
            return result
    except urllib.error.HTTPError as exc:
        raise RuntimeError("O servidor MCP recusou a solicitação (HTTP %s)." % exc.code)
    except urllib.error.URLError:
        raise RuntimeError("Não foi possível alcançar o servidor MCP.")
    except (TimeoutError, socket.timeout):
        raise RuntimeError("O servidor MCP demorou demais para responder.")

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


GITHUB_TOOL_SPECS = [
    {"name":"github_list_repositories","label":"Listar repositórios","description":"Lista repositórios acessíveis pela conta GitHub conectada.","parameters":{"type":"object","properties":{"visibility":{"type":"string","enum":["all","public","private"]}},"additionalProperties":False}},
    {"name":"github_read_file","label":"Ler arquivos","description":"Lê um arquivo de texto de um repositório GitHub. Informe owner, repo e path.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"path":{"type":"string"},"ref":{"type":"string"}},"required":["owner","repo","path"],"additionalProperties":False}},
    {"name":"github_list_issues","label":"Listar issues","description":"Lista issues abertas de um repositório.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"state":{"type":"string","enum":["open","closed","all"]}},"required":["owner","repo"],"additionalProperties":False}},
    {"name":"github_search_code","label":"Pesquisar código","description":"Pesquisa arquivos e trechos de código nos repositórios que a conta pode acessar. Informe uma consulta GitHub Code Search.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"],"additionalProperties":False}},
    {"name":"github_list_branches","label":"Listar branches","description":"Lista branches de um repositório.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"}},"required":["owner","repo"],"additionalProperties":False}},
    {"name":"github_list_pull_requests","label":"Listar pull requests","description":"Lista pull requests de um repositório.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"state":{"type":"string","enum":["open","closed","all"]}},"required":["owner","repo"],"additionalProperties":False}},
    {"name":"github_create_branch","label":"Criar branch","description":"Cria uma nova branch a partir de uma branch existente. Não apaga nem altera a branch de origem.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"source_branch":{"type":"string"},"new_branch":{"type":"string"}},"required":["owner","repo","source_branch","new_branch"],"additionalProperties":False}},
    {"name":"github_write_file","label":"Criar ou modificar arquivos","description":"Cria ou atualiza um arquivo de texto em um repositório, gerando commit. Nunca use para apagar arquivos.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"path":{"type":"string"},"content":{"type":"string"},"message":{"type":"string"},"branch":{"type":"string"}},"required":["owner","repo","path","content","message"],"additionalProperties":False}},
    {"name":"github_create_issue","label":"Criar issue","description":"Cria uma issue em um repositório.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"title":{"type":"string"},"body":{"type":"string"}},"required":["owner","repo","title"],"additionalProperties":False}},
    {"name":"github_create_issue_comment","label":"Comentar em issue ou PR","description":"Publica um comentário em uma issue ou pull request. Use somente quando o usuário pedir explicitamente.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"number":{"type":"integer"},"body":{"type":"string"}},"required":["owner","repo","number","body"],"additionalProperties":False}},
    {"name":"github_create_pull_request","label":"Criar pull request","description":"Cria um pull request entre branches existentes.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"title":{"type":"string"},"head":{"type":"string"},"base":{"type":"string"},"body":{"type":"string"}},"required":["owner","repo","title","head","base"],"additionalProperties":False}},
    {"name":"github_delete_file","label":"Solicitar exclusão de arquivo","description":"Cria uma solicitação pendente. O arquivo só será apagado depois da aprovação explícita na interface.","parameters":{"type":"object","properties":{"owner":{"type":"string"},"repo":{"type":"string"},"path":{"type":"string"},"message":{"type":"string"},"branch":{"type":"string"}},"required":["owner","repo","path","message"],"additionalProperties":False}},
]

def _connector_permissions(connector):
    raw = getattr(connector, "tool_permissions", "") or ""
    if not raw.strip():
        return None
    try:
        value = json.loads(raw)
        return set(x for x in value if isinstance(x, str)) if isinstance(value, list) else None
    except Exception:
        return set()

def _connector_tool_enabled(connector, tool_id):
    allowed = _connector_permissions(connector)
    return allowed is None or tool_id in allowed

def _mcp_read_catalog(connector):
    token = decrypt_secret(connector.secret) if connector.secret else None
    result = _mcp_call(connector.endpoint, token, "tools/list")
    catalog = []
    for tool in (result.get("tools") or [])[:50]:
        original = tool.get("name")
        if not isinstance(original, str) or not original:
            continue
        lowered = original.lower()
        if not lowered.startswith(("get_", "list_", "read_", "search_", "find_", "fetch_", "query_", "describe_", "inspect_", "show_", "status_", "whoami")):
            continue
        description = str(tool.get("description") or "").lower()
        if any(word in description for word in ("delete", "remove", "write", "update", "create", "execute", "run command", "send ", "deploy", "purchase", "modify", "transfer", "payment")):
            continue
        import hashlib
        safe = hashlib.sha256(original.encode()).hexdigest()[:12]
        catalog.append({
            "id": "mcp_%s_%s" % (connector.id, safe),
            "original": original,
            "label": original[:100],
            "description": str(tool.get("description") or original)[:700],
            "parameters": _safe_schema(tool.get("inputSchema")),
        })
    return catalog

def connector_tool_catalog(connector):
    if connector.provider == "github":
        return [{"id": item["name"], "label": item["label"], "description": item["description"]} for item in GITHUB_TOOL_SPECS]
    if connector.provider == "mcp":
        try:
            return [{"id": item["id"], "label": item["label"], "description": item["description"]} for item in _mcp_read_catalog(connector)]
        except Exception:
            return []
    return []

def connector_tools(db):
    from .models import Connector
    tools = []
    for connector in db.query(Connector).all():
        if not bool(getattr(connector, "enabled", True)):
            continue
        if connector.provider == "github":
            for spec in GITHUB_TOOL_SPECS:
                if not _connector_tool_enabled(connector, spec["name"]):
                    continue
                tools.append({"type":"function","function":{
                    "name":spec["name"],"description":spec["description"],
                    "parameters":spec["parameters"]
                }})
        elif connector.provider == "mcp":
            try:
                for spec in _mcp_read_catalog(connector):
                    if not _connector_tool_enabled(connector, spec["id"]):
                        continue
                    tools.append({"type":"function","function":{
                        "name":spec["id"],
                        "description":"Conector %s: %s" % (connector.name, spec["description"]),
                        "parameters":spec["parameters"]
                    }})
            except Exception:
                continue
    # Ferramentas locais da área de arquivos da Mikael AI.
    tools.extend([
        {"type":"function","function":{"name":"workspace_list_files","description":"Lista arquivos enviados ou criados na área Arquivos da Mikael AI.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
        {"type":"function","function":{"name":"workspace_create_file","description":"Cria um arquivo de texto na área Arquivos da Mikael AI para baixar. Informe filename e content.","parameters":{"type":"object","properties":{"filename":{"type":"string"},"content":{"type":"string"}},"required":["filename","content"],"additionalProperties":False}}},
        {"type":"function","function":{"name":"workspace_read_file","description":"Lê o conteúdo textual de um arquivo salvo na área Arquivos. Informe file_id.","parameters":{"type":"object","properties":{"file_id":{"type":"integer"}},"required":["file_id"],"additionalProperties":False}}},
        {"type":"function","function":{"name":"workspace_update_file","description":"Modifica o conteúdo de um arquivo de texto salvo na área Arquivos. Informe file_id e o conteúdo completo atualizado. Não apaga arquivos.","parameters":{"type":"object","properties":{"file_id":{"type":"integer"},"content":{"type":"string"}},"required":["file_id","content"],"additionalProperties":False}}},
    ])
    return tools[:80]

def execute_connector_tool(name: str, arguments: dict, db):
    from .models import Connector
    if name.startswith("github_"):
        connector = db.query(Connector).filter_by(provider="github").first()
        if not connector:
            return {"error": "GitHub não está conectado."}
        if not bool(getattr(connector, "enabled", True)):
            return {"error": "O conector GitHub está desativado. Ative-o em Configurações para usar suas ferramentas."}
        if not _connector_tool_enabled(connector, name):
            return {"error": "Esta ferramenta está desabilitada nas permissões do conector GitHub."}
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
            url = "https://api.github.com/repos/%s/%s/contents/%s" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe=""), urllib.parse.quote(path, safe="/"))
            data = _http_json(url + (("?" + query) if query else ""), token)
            if data.get("encoding") != "base64" or not data.get("content"):
                return {"error": "O caminho não corresponde a um arquivo de texto simples."}
            raw = base64.b64decode(data["content"])
            return {"path": data.get("path"), "content": raw.decode("utf-8", errors="replace")[:24000]}
        if name == "github_search_code":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 300:
                return {"error": "Informe uma consulta de código válida."}
            data = _http_json("https://api.github.com/search/code?" + urllib.parse.urlencode({"q":query,"per_page":20}), token)
            return [{"repository":(x.get("repository") or {}).get("full_name"),"path":x.get("path"),"url":x.get("html_url")} for x in (data.get("items") or [])[:20]]
        if name == "github_list_branches":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            if not all(isinstance(x,str) and x.strip() and len(x)<100 for x in (owner,repo)):
                return {"error":"Owner ou repositório inválido."}
            data = _http_json("https://api.github.com/repos/%s/%s/branches?per_page=100" % (urllib.parse.quote(owner,safe=""),urllib.parse.quote(repo,safe="")),token)
            return [{"name":x.get("name"),"sha":(x.get("commit") or {}).get("sha")} for x in data[:100]]
        if name == "github_list_pull_requests":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            state = arguments.get("state","open")
            if state not in {"open","closed","all"}: state="open"
            if not all(isinstance(x,str) and x.strip() and len(x)<100 for x in (owner,repo)):
                return {"error":"Owner ou repositório inválido."}
            data = _http_json("https://api.github.com/repos/%s/%s/pulls?state=%s&per_page=30" % (urllib.parse.quote(owner,safe=""),urllib.parse.quote(repo,safe=""),state),token)
            return [{"number":x.get("number"),"title":x.get("title"),"state":x.get("state"),"head":(x.get("head") or {}).get("ref"),"base":(x.get("base") or {}).get("ref"),"url":x.get("html_url")} for x in data[:30]]
        if name == "github_create_branch":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            source, new = arguments.get("source_branch"), arguments.get("new_branch")
            if not all(isinstance(x,str) and x.strip() and len(x)<200 for x in (owner,repo,source,new)) or new == source:
                return {"error":"Informe owner, repo e nomes de branches válidos e diferentes."}
            base_url="https://api.github.com/repos/%s/%s/git/ref/heads/%s" % (urllib.parse.quote(owner,safe=""),urllib.parse.quote(repo,safe=""),urllib.parse.quote(source,safe="/"))
            source_ref=_http_json(base_url,token)
            sha=(source_ref.get("object") or {}).get("sha")
            if not isinstance(sha,str) or len(sha)!=40:
                return {"error":"Não foi possível obter o commit da branch de origem."}
            result=_http_json("https://api.github.com/repos/%s/%s/git/refs" % (urllib.parse.quote(owner,safe=""),urllib.parse.quote(repo,safe="")),token,method="POST",payload={"ref":"refs/heads/"+new,"sha":sha})
            return {"ok":True,"branch":(result.get("ref") or "").replace("refs/heads/",""),"sha":(result.get("object") or {}).get("sha")}
        if name == "github_create_issue_comment":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            number, body = arguments.get("number"), arguments.get("body")
            if not all(isinstance(x,str) and x.strip() and len(x)<100 for x in (owner,repo)) or not isinstance(number,int) or number<1 or not isinstance(body,str) or not body.strip() or len(body)>60000:
                return {"error":"Parâmetros do comentário inválidos."}
            result=_http_json("https://api.github.com/repos/%s/%s/issues/%s/comments" % (urllib.parse.quote(owner,safe=""),urllib.parse.quote(repo,safe=""),number),token,method="POST",payload={"body":body})
            return {"ok":True,"url":result.get("html_url"),"id":result.get("id")}
        if name == "github_list_issues":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            if not all(isinstance(x, str) and x and len(x) < 100 for x in (owner, repo)):
                return {"error": "Owner ou repositório inválido."}
            state = arguments.get("state", "open")
            if state not in {"open", "closed", "all"}: state = "open"
            data = _http_json("https://api.github.com/repos/%s/%s/issues?state=%s&per_page=30" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe=""), state), token)
            return [{"number": x.get("number"), "title": x.get("title"), "url": x.get("html_url"), "state": x.get("state")} for x in data if "pull_request" not in x]
        if name == "github_write_file":
            owner, repo, path = arguments.get("owner"), arguments.get("repo"), arguments.get("path")
            content, message = arguments.get("content"), arguments.get("message")
            if not all(isinstance(x, str) and x and len(x) < 200 for x in (owner, repo, path)) or not isinstance(content, str) or not isinstance(message, str) or not message.strip():
                return {"error": "Parâmetros de arquivo ou mensagem de commit inválidos."}
            if len(content.encode("utf-8")) > 800000:
                return {"error": "Arquivo excede o limite de 800 KB."}
            branch = arguments.get("branch")
            query = urllib.parse.urlencode({"ref": branch}) if isinstance(branch, str) and branch else ""
            base = "https://api.github.com/repos/%s/%s/contents/%s" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe=""), urllib.parse.quote(path, safe="/"))
            current = None
            try:
                current = _http_json(base + (("?" + query) if query else ""), token).get("sha")
            except RuntimeError as exc:
                if "HTTP 404" not in str(exc):
                    raise
            payload = {"message": message[:200], "content": base64.b64encode(content.encode("utf-8")).decode("ascii")}
            if current:
                payload["sha"] = current
            if isinstance(branch, str) and branch:
                payload["branch"] = branch
            result = _http_json(base, token, method="PUT", payload=payload)
            return {"ok": True, "path": result.get("content", {}).get("path", path), "commit": result.get("commit", {}).get("html_url")}
        if name == "github_create_issue":
            owner, repo, title = arguments.get("owner"), arguments.get("repo"), arguments.get("title")
            if not all(isinstance(x, str) and x.strip() and len(x) < 200 for x in (owner, repo, title)):
                return {"error": "Owner, repositório ou título inválido."}
            payload = {"title": title[:200], "body": str(arguments.get("body") or "")[:60000]}
            result = _http_json("https://api.github.com/repos/%s/%s/issues" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe="")), token, method="POST", payload=payload)
            return {"ok": True, "number": result.get("number"), "url": result.get("html_url")}
        if name == "github_create_pull_request":
            owner, repo = arguments.get("owner"), arguments.get("repo")
            title, head, base = arguments.get("title"), arguments.get("head"), arguments.get("base")
            if not all(isinstance(x, str) and x.strip() and len(x) < 200 for x in (owner, repo, title, head, base)):
                return {"error": "Parâmetros do pull request inválidos."}
            payload = {"title": title[:200], "head": head[:200], "base": base[:200], "body": str(arguments.get("body") or "")[:60000]}
            result = _http_json("https://api.github.com/repos/%s/%s/pulls" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe="")), token, method="POST", payload=payload)
            return {"ok": True, "number": result.get("number"), "url": result.get("html_url")}
        if name == "github_delete_file":
            from .models import PendingAction
            owner, repo, path = arguments.get("owner"), arguments.get("repo"), arguments.get("path")
            message = arguments.get("message")
            if not all(isinstance(x, str) and x.strip() and len(x) < 200 for x in (owner, repo, path)) or not isinstance(message, str) or not message.strip():
                return {"error": "Parâmetros de exclusão inválidos."}
            branch = arguments.get("branch")
            if branch is not None and (not isinstance(branch, str) or len(branch) > 200):
                return {"error": "Nome da branch inválido."}
            base = "https://api.github.com/repos/%s/%s/contents/%s" % (urllib.parse.quote(owner, safe=""), urllib.parse.quote(repo, safe=""), urllib.parse.quote(path, safe="/"))
            query = urllib.parse.urlencode({"ref": branch}) if isinstance(branch, str) and branch else ""
            current = _http_json(base + (("?" + query) if query else ""), token)
            if not isinstance(current, dict) or current.get("type") != "file" or not isinstance(current.get("sha"), str):
                return {"error": "O caminho informado não corresponde a um arquivo único que possa ser confirmado."}
            safe_args = {"owner": owner, "repo": repo, "path": current.get("path") or path, "message": message[:180], "branch": branch if isinstance(branch, str) else "", "sha": current["sha"]}
            pending = db.query(PendingAction).filter(
                PendingAction.status == "pending",
                PendingAction.expires_at > int(time.time())
            ).count()
            if pending >= 10:
                return {"error": "Há muitas exclusões aguardando aprovação. Aprove ou negue as solicitações existentes primeiro."}
            action = PendingAction(
                conversation_id=arguments.get("_conversation_id"),
                tool_name="github_delete_file",
                arguments=json.dumps(safe_args, ensure_ascii=False),
                title="Excluir arquivo do GitHub",
                description="%s/%s · %s · branch %s" % (owner, repo, safe_args["path"], safe_args["branch"] or "padrão"),
                status="pending",
                expires_at=int(time.time()) + 900,
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            return {"approval_required": True, "action_id": action.id, "message": "Aguardando aprovação explícita do usuário. Não tente executar a exclusão por outro caminho."}
        return {"error": "Ferramenta GitHub desconhecida."}
    if name.startswith("mcp_"):
        parts = name.split("_", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            return {"error": "Ferramenta MCP inválida."}
        item = db.query(Connector).filter_by(id=int(parts[1]), provider="mcp").first()
        if not item:
            return {"error": "Conector MCP não encontrado."}
        if not bool(getattr(item, "enabled", True)):
            return {"error": "Este conector MCP está desativado. Ative-o em Configurações para usar suas ferramentas."}
        if not _connector_tool_enabled(item, name):
            return {"error": "Esta ferramenta está desabilitada nas permissões deste conector MCP."}
        token = decrypt_secret(item.secret) if item.secret else None
        # Resolve o nome original consultando novamente o servidor, sem confiar no modelo.
        listed = _mcp_call(item.endpoint, token, "tools/list")
        import hashlib
        original = next((tool.get("name") for tool in (listed.get("tools") or []) if isinstance(tool, dict) and hashlib.sha256(str(tool.get("name", "")).encode()).hexdigest()[:12] == parts[2]), None)
        if not original:
            return {"error": "A ferramenta não existe mais no servidor MCP."}
        result = _mcp_call(item.endpoint, token, "tools/call", {"name": original, "arguments": arguments})
        return result
    if name.startswith("workspace_"):
        from .models import UploadedFile
        if name == "workspace_list_files":
            rows=db.query(UploadedFile).order_by(UploadedFile.id.desc()).limit(50).all()
            return [{"file_id":x.id,"filename":x.filename,"characters":len(x.extracted_text or "")} for x in rows]
        if name == "workspace_create_file":
            filename=arguments.get("filename")
            content=arguments.get("content")
            if not isinstance(filename,str) or not filename.strip() or len(filename)>120 or "/" in filename or "\\" in filename or not isinstance(content,str):
                return {"error":"Nome ou conteúdo do arquivo inválido."}
            if len(content.encode("utf-8"))>800000:
                return {"error":"O arquivo excede 800 KB."}
            item=UploadedFile(filename=filename.strip(),extracted_text=content,file_data=content.encode("utf-8"),mime_type="text/plain")
            db.add(item);db.commit();db.refresh(item)
            return {"ok":True,"file_id":item.id,"filename":item.filename,"characters":len(content),"download":"/api/files/%s/download"%item.id}
        if name == "workspace_read_file":
            file_id=arguments.get("file_id")
            if not isinstance(file_id,int) or file_id<1:return {"error":"file_id inválido."}
            item=db.get(UploadedFile,file_id)
            if not item:return {"error":"Arquivo não encontrado."}
            return {"file_id":item.id,"filename":item.filename,"content":(item.extracted_text or "")[:30000]}
        if name == "workspace_update_file":
            file_id=arguments.get("file_id")
            content=arguments.get("content")
            if not isinstance(file_id,int) or file_id<1 or not isinstance(content,str):return {"error":"Parâmetros inválidos."}
            if len(content.encode("utf-8"))>800000:return {"error":"O arquivo excede 800 KB."}
            item=db.get(UploadedFile,file_id)
            if not item:return {"error":"Arquivo não encontrado."}
            item.extracted_text=content
            item.file_data=content.encode("utf-8")
            item.mime_type="text/plain"
            db.commit()
            return {"ok":True,"file_id":item.id,"filename":item.filename,"characters":len(content)}
    return {"error": "Ferramenta desconhecida."}


def github_exchange_code(code: str, redirect_uri: str):
    client_id = (os.getenv("GITHUB_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GITHUB_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Configure GITHUB_CLIENT_ID e GITHUB_CLIENT_SECRET no Render.")
    payload = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "code": code, "redirect_uri": redirect_uri
    }).encode()
    request = urllib.request.Request(
        "https://github.com/login/oauth/access_token", data=payload,
        headers={"Accept": "application/json", "User-Agent": "Mikael-AI/1.8"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            data = json.loads(response.read(65536).decode("utf-8"))
    except Exception:
        raise RuntimeError("Não foi possível concluir a autorização do GitHub.")
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("O GitHub não retornou um token válido.")
    account = _http_json("https://api.github.com/user", token)
    return token, account


def mcp_test(endpoint: str, token: str | None):
    result = _mcp_call(endpoint, token, "tools/list")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise RuntimeError("O servidor respondeu, mas não retornou uma lista MCP de ferramentas.")
    return [{"name": str(x.get("name", ""))[:100], "description": str(x.get("description", ""))[:240]} for x in tools[:50] if isinstance(x, dict) and x.get("name")]
