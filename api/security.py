import hashlib
import hmac
import os
from fastapi import Header, HTTPException, Request


def authorize(request: Request, x_api_key: str | None = Header(default=None), x_hub_signature: str | None = Header(default=None)):
    key, secret = os.getenv("API_KEY"), os.getenv("HMAC_SECRET")
    if key and not hmac.compare_digest(x_api_key or "", key): raise HTTPException(401, "Invalid API key")
    if secret:
        body = getattr(request.state, "raw_body", b"")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(x_hub_signature or "", expected): raise HTTPException(401, "Invalid HMAC signature")
