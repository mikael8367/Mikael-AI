import os
from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

def serializer():
    secret = os.getenv("APP_SECRET", "")
    if len(secret) < 24:
        raise RuntimeError("Configure APP_SECRET com pelo menos 24 caracteres.")
    return URLSafeTimedSerializer(secret, salt="mikael-ai-session")

def make_session():
    return serializer().dumps({"authenticated": True})

def require_auth(request: Request):
    token = request.cookies.get("mikael_session")
    if not token:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    try:
        data = serializer().loads(token, max_age=60 * 60 * 24 * 7)
        if data.get("authenticated") is not True:
            raise ValueError()
    except (BadSignature, SignatureExpired, ValueError):
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
