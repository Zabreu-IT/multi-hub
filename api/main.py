from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.database import engine
from core.models import Base
from api.middleware import request_context
from api.routes import products,categories,availability,connectors,orders,dashboard,media
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine); yield
app=FastAPI(title="Multi-Hub API",version="1.0.0",lifespan=lifespan)
app.middleware("http")(request_context)
for route in (products,categories,connectors,orders,dashboard,media): app.include_router(route.router,prefix="/api/v1")
@app.get("/health")
def health(): return {"ok":True}
app.mount("/dashboard",StaticFiles(directory=Path("/app/dashboard"),html=True),name="dashboard")
app.mount("/",StaticFiles(directory=Path("/app/frontend"),html=True),name="frontend")
