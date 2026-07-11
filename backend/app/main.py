from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401  (register all tables on Base)
from app.api import public
from app.api.admin import articles as admin_articles
from app.api.admin import auth as admin_auth
from app.api.admin import config as admin_config
from app.api.admin import countries as admin_countries
from app.api.admin import crawl as admin_crawl
from app.api.admin import sites as admin_sites
from app.config import settings
from app.db import Base, engine
from app.scheduler import build_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="ZokoDaily API", lifespan=lifespan)

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(admin_auth.router, prefix="/api/admin/auth", tags=["admin-auth"])
app.include_router(admin_countries.router, prefix="/api/admin/countries", tags=["admin"])
app.include_router(admin_sites.router, prefix="/api/admin/sites", tags=["admin"])
app.include_router(admin_articles.router, prefix="/api/admin/articles", tags=["admin"])
app.include_router(admin_config.router, prefix="/api/admin/config", tags=["admin"])
app.include_router(admin_crawl.router, prefix="/api/admin", tags=["admin"])

from app.logistics.api import h5_auth, h5_driver, h5_uploads
from app.logistics.api.admin import staff as lg_admin_staff

app.include_router(h5_auth.router, prefix="/api/lg/auth", tags=["lg-h5"])
app.include_router(h5_uploads.router, prefix="/api/lg/uploads", tags=["lg-h5"])
app.include_router(h5_driver.router, prefix="/api/lg/driver", tags=["lg-h5"])
app.include_router(lg_admin_staff.router, prefix="/api/admin/lg/staff", tags=["lg-admin"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
