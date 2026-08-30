import os
import sys

import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select

from core.database import SessionLocal
from core.models import AdminUser

USERS = [
    ("demo_owner", os.getenv("DEMO_OWNER_PASS", "demo-owner-2026"), "owner"),
    ("demo_admin", os.getenv("DEMO_ADMIN_PASS", "demo-admin-2026"), "admin"),
    ("demo_viewer", os.getenv("DEMO_VIEWER_PASS", "demo-viewer-2026"), "viewer"),
]

db = SessionLocal()
try:
    for username, pw, role in USERS:
        u = db.scalar(select(AdminUser).where(AdminUser.username == username))
        h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        if u:
            u.password_hash, u.role, u.is_active = h, role, True
        else:
            db.add(AdminUser(username=username, password_hash=h, role=role, is_active=True))
    db.commit()
    print("seed ok: demo_owner/demo_admin/demo_viewer")
finally:
    db.close()
