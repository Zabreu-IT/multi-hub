# Multi-Hub Admin — Sistema de Autenticación + Roles + Demo

> **Para Claude Code:** Implementa este plan tarea por tarea, en orden. Cada tarea lista archivos exactos, código completo y verificación. Commits frecuentes. NO toques: `frontend/`, `api/routes/media.py`, `worker/`, `connectors/`. Respeta el estilo existente (FastAPI, SQLAlchemy, JWT propio, JS vanilla).

**Objetivo:** Bloquear el panel admin (`/dashboard/`) con login por usuario/contraseña, proteger todos los endpoints admin con JWT, añadir roles (owner/admin/viewer), crear usuarios demo y verificar que "lo que dice, hace".

**Arquitectura:** Login password → bcrypt (tabla `admin_users` ya existe con `username`+`password_hash`) → JWT propio (ya existe `api/routes/auth.py:create_jwt`) → dependencia `require_admin` en `api/security.py` → cada endpoint admin la usa. Dashboard HTML obtiene token y envía `Authorization: Bearer` en cada fetch.

**Stack:** FastAPI, SQLAlchemy, bcrypt (a añadir), JWT propio HMAC, Postgres, JS vanilla.

**Estado actual (verificado):**
- `admin_users` existe: id/username/password_hash/totp_secret/is_active/created_at — VACÍA (0 filas)
- `auth.py` tiene `create_jwt(user_id)` que solo pone `sub` + `exp`, y `verify_jwt(token)` → payload
- `security.py` tiene `authorize()` (X-API-Key opcional) — los endpoints admin están ABIERTOS
- Endpoints a proteger (hoy con `dependencies=[Depends(authorize)]`): products POST/PUT/DELETE, categories POST/PUT/DELETE, connectors *, orders GET/PATCH, dashboard * , leads GET
- `main.py` lifespan hace `create_all` + ALTER para leads — patrón a reutilizar para añadir columna role
- `.env.prod` tiene API_KEY (quedará como respaldo, pero el gate pasa a ser JWT)
- Dashboard: index/products/orders/leads/connectors.html usan `fetch('/api/v1/...')` sin headers — hay que cambiarlas a authFetch

---

## Tarea 1: Añadir columna `role` a AdminUser

**Objetivo:** Soportar roles en la tabla admin_users.

**Archivos:**
- Modify: `core/models.py` (clase AdminUser, ~línea 108)
- Modify: `api/main.py` (lifespan, ALTER)

**En `core/models.py:AdminUser` añadir:**
```python
    role: Mapped[str] = mapped_column(String(16), default="viewer")
```

**En `api/main.py` lifespan, junto al ALTER de leads:**
```python
 with engine.begin() as connection:
     connection.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb"))
     connection.execute(text("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'viewer'"))
```

**Verificar:** `docker compose -f docker-compose.prod.yml build api` → `up -d api` → `docker exec multi-hub-db-1 psql -U hub -d multihub -c '\d admin_users'` muestra `role`.

**Commit:** `feat: add role column to admin_users`

---

## Tarea 2: Dependencia bcrypt

**Objetivo:** Hash seguro de contraseñas.

**Archivos:**
- Modify: `api/requirements.txt`

**Añadir:** `bcrypt>=4.1,<5`

**Verificar:** `docker compose -f docker-compose.prod.yml build api` compila.

**Commit:** `chore: add bcrypt dependency`

---

## Tarea 3: Hash + login por password en `auth.py`

**Objetivo:** Endpoint `POST /api/v1/auth/login` que devuelve JWT con `sub` y `role`. Endpoint `GET /api/v1/auth/me` extendido con role.

**Archivos:**
- Modify: `api/routes/auth.py`

**Añadir imports:** `import bcrypt` y `from core.models import AdminUser`

**Modificar `create_jwt` para aceptar role:**
```python
def create_jwt(user_id: str, role: str | None = None) -> str:
    payload = {"sub": user_id, "role": role, "exp": (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)).isoformat()}
```

**Añadir schema y endpoint (al final del archivo):**
```python
class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(AdminUser).where(AdminUser.username == data.username))
    if not user or not user.is_active:
        raise HTTPException(401, "Credenciales inválidas")
    if not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "Credenciales inválidas")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_jwt(str(user.id), user.role)
    return {"token": token, "user": {"id": str(user.id), "username": user.username, "role": user.role}}
```

**EXTENDER `get_me`** para devolver role y username cuando el usuario sea AdminUser:
```python
    user = db.get(AdminUser, payload["sub"])
    if user:
        return {"id": str(user.id), "username": user.username, "role": user.role}
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    return {"id": str(user.id), "name": user.name, "email": user.email, "avatar": user.avatar_url}
```

**Verificar con curl:**
```bash
curl -s -X POST http://localhost:8080/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"demo_owner","password":"demo-owner-2026"}'
# → {"token":"...","user":{...}} o 401 si no existe aún (seed viene en Tarea 4)
```

**Commit:** `feat: password login endpoint with roles`

---

## Tarea 4: Seed de usuarios admin (owner/admin/viewer)

**Objetivo:** Script que crea o actualiza 3 usuarios demo con bcrypt.

**Archivos:**
- Create: `scripts/seed_admin.py`

```python
import os, sys
import bcrypt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from core.database import SessionLocal
from core.models import AdminUser

USERS = [
    ("demo_owner",  os.getenv("DEMO_OWNER_PASS",  "demo-owner-2026"),  "owner"),
    ("demo_admin",  os.getenv("DEMO_ADMIN_PASS",  "demo-admin-2026"),  "admin"),
    ("demo_viewer", os.getenv("DEMO_VIEWER_PASS", "demo-viewer-2026"), "viewer"),
]
db = SessionLocal()
for username, pw, role in USERS:
    u = db.scalar(select(AdminUser).where(AdminUser.username == username))
    h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    if u:
        u.password_hash, u.role, u.is_active = h, role, True
    else:
        db.add(AdminUser(username=username, password_hash=h, role=role, is_active=True))
db.commit(); db.close()
print("seed ok")
```

**Nota:** Si `core/database.py` no tiene `SessionLocal`, usa la misma fábrica que usan los routes (get_db). Revisar y adaptar.

**Ejecutar:** `docker compose -f docker-compose.prod.yml up -d --build api && docker exec multi-hub-api-1 python scripts/seed_admin.py`

**Verificar:** login con los 3 usuarios devuelve token con su role (curl local contra :8080).

**Commit:** `feat: seed admin users (owner/admin/viewer)`

---

## Tarea 5: `require_admin` en `security.py`

**Objetivo:** Dependencia que exige Bearer JWT válido de un admin activo, con roles opcionales + modo solo-lectura.

**Archivos:**
- Modify: `api/security.py`

**Añadir:**
```python
from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import AdminUser
from api.routes.auth import verify_jwt

def require_admin(roles: list[str] | None = None):
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
```

**Verificar:** `/health` OK tras rebuild.

**Commit:** `feat: require_admin dependency for admin routes`

---

## Tarea 6: Proteger endpoints admin

**Objetivo:** Reemplazar `dependencies=[Depends(authorize)]` por `dependencies=[Depends(require_admin())]` en rutas mutables y sensibles. Lectura para viewer OK; mutaciones exigen `require_admin(["owner","admin"])`.

**Archivos:**
- Modify: `api/routes/products.py` — POST, PUT, DELETE → `require_admin(["owner","admin"])`. GET queda público.
- Modify: `api/routes/categories.py` — POST, PUT, DELETE → `require_admin(["owner","admin"])`.
- Modify: `api/routes/connectors.py` — todas → `require_admin()`.
- Modify: `api/routes/orders.py` — GET, GET/{id}, PATCH → `require_admin()`.
- Modify: `api/routes/leads.py` — GET → `require_admin()`.
- Modify: `api/routes/dashboard.py` — línea 7 `dependencies=[Depends(authorize)]` → `require_admin()`.

**Importante:** `POST /api/v1/orders` (checkout público) y GET products/categories públicos NO se tocan.

**Nota sobre connectors.py:** su `router=APIRouter(...)` NO declara dependencias a nivel router (a diferencia de dashboard.py). Añadir `Depends(require_admin())` en cada ruta o declarar en el router. Mismo criterio para orders.py y leads.py si el router no tiene dependency global.

**Verificar:**
```bash
# SIN token → 401
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/v1/dashboard/stats   # esperado 401
# CON token (de Tarea 4)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/dashboard/stats  # → 200
# viewer haciendo POST product → 403
```

**Commit:** `feat: protect admin endpoints with JWT`

---

## Tarea 7: Página `dashboard/login.html`

**Objetivo:** Login visual consistente con el admin (light premium, coral, Sora/Inter, logo hub SVG).

**Archivos:**
- Create: `dashboard/login.html`

**Contenido mínimo:**
- Logo hub SVG (mismo data-URI favicon coral del resto del dashboard), título "Multi-Hub Admin"
- Formulario: username, password, botón "Ingresar"
- En POST exitoso: `localStorage.setItem('mh_token', token)` + `localStorage.setItem('mh_user', JSON.stringify(user))` → `location.href = 'index.html'`
- En 401: mensaje "Credenciales inválidas"
- Error de conexión: mensaje claro
- CSS: reutilizar `styles.css` (misma hoja), centrar card, `--bg: #f5f5f7`

**Verificar:** `https://hub.zabreuit.com/dashboard/login.html` carga, login con demo_owner redirige a index.html.

**Commit:** `feat: admin login page`

---

## Tarea 8: Helper `dashboard/auth.js` + integración en las 5 páginas

**Objetivo:** Centralizar token/headers/redirección. Todas las páginas admin pasan de `fetch()` a `authFetch()`.

**Archivos:**
- Create: `dashboard/auth.js`
- Modify: `dashboard/index.html` (los fetch de stats/charts/orders/leads)
- Modify: `dashboard/products.html` (todos los fetch/api)
- Modify: `dashboard/orders.html`, `dashboard/leads.html`, `dashboard/connectors.html`

**Contenido de `auth.js`:**
```js
'use strict';
const TOKEN_KEY = 'mh_token';
const USER_KEY = 'mh_user';
function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (e) { return null; } }
function setAuth(token, user) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); }
function clearAuth() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }

function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  const t = getToken();
  if (t) h['Authorization'] = 'Bearer ' + t;
  return h;
}

async function authFetch(path, opts) {
  opts = opts || {};
  opts.headers = authHeaders(opts.headers);
  const r = await fetch(path, opts);
  if (r.status === 401) {
    clearAuth();
    if (!location.pathname.endsWith('login.html')) location.href = 'login.html';
    throw new Error('No autenticado');
  }
  return r;
}

function requireAuth() {
  if (!getToken()) { location.href = 'login.html'; return false; }
  return true;
}
function logout() { clearAuth(); location.href = 'login.html'; }

function renderUser() {
  const u = getUser();
  const el = document.getElementById('user-chip');
  if (el && u) el.innerHTML = '<span class="side-link" style="cursor:pointer"><svg class="icon"><use href="#i-lead"/></svg> ' + u.username + ' · ' + u.role + '</span>';
}
function isReadOnly() { const u = getUser(); return !u || u.role === 'viewer'; }
```

**En cada página:**
1. `<script src="auth.js"></script>` ANTES del script principal
2. `if (!requireAuth()) {}` al inicio del script principal
3. Reemplazar `fetch(API + ...)` por `authFetch(API + ...)`
4. Añadir en el sidebar un botón "Salir" que llama `logout()`
5. En `products.html` y `connectors.html`, si `isReadOnly()` ocultar botones de crear/editar/borrar y deshabilitar submit

**Verificar:** con demo_viewer → no ve botones de crear; con demo_owner → todo visible. Sin token → redirige a login.html.

**Commit:** `feat: auth integration in admin pages (authFetch, roles UI)`

---

## Tarea 9: Rebuild completo + despliegue + verificación E2E

**Objetivo:** Probar el sistema completo en producción, no solo en local.

**Pasos (en ash-micro-01):**
```bash
cd /home/ubuntu/multi-hub
docker compose -f docker-compose.prod.yml up -d --build api
docker exec multi-hub-api-1 python scripts/seed_admin.py
```

**E2E checklist:**
1. `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/v1/dashboard/stats` → **401**
2. Login demo_owner → token → `curl -H "Authorization: Bearer $T0" .../api/v1/dashboard/stats` → **200**
3. Login demo_viewer → `curl -X POST -H "Authorization: Bearer $TV" -H 'Content-Type: application/json' -d '{"name":"x","slug":"x","base_price":1,"product_type":"tour","category_id":"7a9d6132-..."}' .../api/v1/products` → **403**
4. demo_owner crea un producto de prueba → **200** → lo borra (DELETE) → **200**
5. `https://hub.zabreuit.com/dashboard/login.html` → login demo_owner → resumen carga
6. Sin token, abrir `https://hub.zabreuit.com/dashboard/index.html` → redirige a login
7. demo_viewer → verifica que no ve botones de crear
8. Checkout público sigue OK: `POST /api/v1/orders` sin token → **200** (no romper el sitio público)

**Commit:** `chore: deploy admin auth`

---

## Tarea 10: Documentación + limpieza

**Objetivo:** Dejar instrucciones claras para el humano.

**Archivos:**
- Modify: `CLAUDE.md` (añadir sección Admin Auth)

**Documentar:**
- URL: `https://hub.zabreuit.com/dashboard/login.html`
- Usuarios: demo_owner / demo_admin / demo_viewer (passwords demo marcados CAMBIAR)
- Para crear admin real: `docker exec multi-hub-api-1 python -c "..."` o reusar seed con env
- Nota de seguridad: **cambiar contraseñas demo ANTES de compartir el demo**

**Commit:** `docs: admin auth guide`

---

## Riesgos y notas
- **No romper checkout público:** `POST /orders` (sin auth) y GET products/categories públicos quedan iguales
- **bcrypt en python:3.12-slim** compila wheels — verificar build
- Los passwords demo son para demostración; **requisito de Vader: honestidad** — marcar clara y visualmente que son credenciales demo en el login si se comparte
- `verify_jwt` ya valida exp — no rehacer JWT
- Si `core/database.py` no expone `SessionLocal`, adaptar seed a lo que exista
- Verificar imports en `api/routes/connectors.py` (hoy importa authorize) y adaptar a require_admin sin duplicar
