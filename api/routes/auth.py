from datetime import datetime, timezone, timedelta
from os import getenv
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import AdminUser, User
import bcrypt

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = getenv("JWT_SECRET", "multihub-jwt-secret-change-in-prod")
JWT_EXPIRE_HOURS = 72


def create_jwt(user_id: str, role: str | None = None) -> str:
    """Simple JWT-like token (base64 payload + signature)."""
    import base64, hashlib, hmac, json
    payload = {"sub": user_id, "role": role, "exp": (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)).isoformat()}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_jwt(token: str) -> dict:
    import base64, hashlib, hmac, json
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(401, "Invalid token")
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        if datetime.fromisoformat(payload["exp"]) < datetime.now(timezone.utc):
            raise HTTPException(401, "Token expired")
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


def get_current_user():
    """Dependency to extract user from Authorization header."""
    def _dep(request: Request, authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing authorization")
        payload = verify_jwt(authorization.split(" ", 1)[1])
        return payload["sub"]
    return _dep


class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token


@router.post("/google")
def google_login(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Verify Google ID token and create/update user. Returns JWT."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google OAuth not configured")

    # Verify the Google ID token
    user_info = verify_google_token(data.credential, GOOGLE_CLIENT_ID)
    if not user_info:
        raise HTTPException(401, "Invalid Google token")

    google_id = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", email.split("@")[0])
    avatar = user_info.get("picture")

    # Find or create user
    user = db.scalar(select(User).where(User.google_id == google_id))
    if user:
        user.email = email
        user.name = name
        user.avatar_url = avatar
        user.last_login = datetime.now(timezone.utc)
    else:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar,
            last_login=datetime.now(timezone.utc),
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    token = create_jwt(str(user.id))
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "avatar": user.avatar_url,
        },
    }


@router.get("/me")
def get_me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Get current user from JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    payload = verify_jwt(authorization.split(" ", 1)[1])
    admin = db.get(AdminUser, payload["sub"])
    if admin:
        return {"id": str(admin.id), "username": admin.username, "role": admin.role}
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "avatar": user.avatar_url,
    }


def verify_google_token(id_token: str, client_id: str) -> dict | None:
    """Verify Google ID token by decoding the JWT header and payload.
    For production, use google-auth library. This is a simplified version."""
    try:
        import base64, json
        # Google ID tokens are standard JWTs with 3 parts
        parts = id_token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (2nd part)
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))

        # Verify audience and issuer
        if data.get("aud") != client_id:
            return None
        if data.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            return None

        # Check expiry
        from datetime import timezone
        exp = datetime.fromtimestamp(data.get("exp", 0), tz=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None

        return data
    except Exception:
        return None

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login por usuario/contraseña para el panel admin. Devuelve JWT con role."""
    user = db.scalar(select(AdminUser).where(AdminUser.username == data.username))
    if not user or not user.is_active:
        raise HTTPException(401, "Credenciales inválidas")
    if not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "Credenciales inválidas")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_jwt(str(user.id), user.role)
    return {"token": token, "user": {"id": str(user.id), "username": user.username, "role": user.role}}
