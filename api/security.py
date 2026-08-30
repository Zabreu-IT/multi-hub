import hashlib
import hmac
import os
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from api.routes.auth import verify_jwt
from core.database import get_db
from core.models import AdminUser


def authorize(request: Request, x_api_key: str | None = Header(default=None), x_hub_signature: str | None = Header(default=None)):
    key, secret = os.getenv("API_KEY"), os.getenv("HMAC_SECRET")
    if key and not hmac.compare_digest(x_api_key or "", key): raise HTTPException(401, "Invalid API key")
    if secret:
        body = getattr(request.state, "raw_body", b"")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(x_hub_signature or "", expected): raise HTTPException(401, "Invalid HMAC signature")


def require_admin(roles: list[str] | None = None):
    """Exige Bearer JWT de un admin activo. roles opcional: si se pasa, el role debe estar en la lista."""
    def _dep(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "No autenticado")
        payload = verify_jwt(authorization.split(" ", 1)[1])
        user = db.get(AdminUser, payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(401, "Usuario no válido")
        if roles and user.role not in roles:
            raise HTTPException(403, "No tienes permiso para esta acción")
        request.state.admin = user
        return user
    return _dep
