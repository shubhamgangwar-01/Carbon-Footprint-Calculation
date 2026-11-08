"""FastAPI application entry point."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth_routes, conference_routes, factor_routes
from app.config import get_settings
from app.database.session import SessionLocal
from app.models import EmissionFactor
from app.services.auth import ensure_admin
from app.services.emissions_engine import ENGINE_VERSION
from app.services.factor_service import import_factors

log = logging.getLogger("carbon")


def run_migrations():
    from alembic import command
    from alembic.config import Config
    here = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("AUTO_MIGRATE", "true").lower() == "true":
        run_migrations()
    with SessionLocal() as db:
        if db.query(EmissionFactor).count() == 0:
            log.info("Seeding emission factors: %s", import_factors(db))
        ensure_admin(db)
    yield


app = FastAPI(title="Conference Carbon Footprint Calculator API", version=ENGINE_VERSION, lifespan=lifespan,
              description="Calculates conference GHG emissions (kg CO2e) from activity data and documented emission factors.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "engine_version": ENGINE_VERSION}


app.include_router(auth_routes.router)
app.include_router(conference_routes.router)
app.include_router(factor_routes.router)
