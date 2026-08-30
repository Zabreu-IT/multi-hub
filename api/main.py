from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from core.database import engine
from core.models import Base
from api.middleware import request_context
from api.routes import products,categories,availability,connectors,orders,dashboard,media,leads,auth
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 with engine.begin() as connection:
     connection.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb"))
     connection.execute(text("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'viewer'"))
 yield
app=FastAPI(title="Multi-Hub API",version="1.0.0",lifespan=lifespan)
app.middleware("http")(request_context)
for route in (products,categories,availability,connectors,orders,dashboard,media,leads,auth): app.include_router(route.router,prefix="/api/v1")
@app.get("/health")
def health(): return {"ok":True}
app.mount("/dashboard",StaticFiles(directory=Path("/app/dashboard"),html=True),name="dashboard")
app.mount("/apps/frontend",StaticFiles(directory=Path("/app/apps/frontend"),html=True),name="how-it-works")
app.mount("/",StaticFiles(directory=Path("/app/frontend"),html=True),name="frontend")
