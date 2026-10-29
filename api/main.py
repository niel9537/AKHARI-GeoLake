import logging
import os

from contextlib import contextmanager
from pathlib import Path

import psycopg

from psycopg.rows import dict_row
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

# ==========================================
# CONFIGURATION
# ==========================================

load_dotenv()

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("akhari.geolake")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="AKHARI GeoLake API",
    description=(
        "API geospasial, analisis akses kesehatan, "
        "rekomendasi, dan monitoring pembangunan daerah"
    ),
    version="0.1.1",
)

from api.auth_router import current_user, router as auth_router

app.include_router(auth_router)
# ==========================================
# DATABASE CONNECTION
# ==========================================

@contextmanager
def get_connection():
    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "geolake"),
        user=os.getenv("POSTGRES_USER", "geolake_user"),
        password=os.environ["POSTGRES_PASSWORD"],
        row_factory=dict_row,
        connect_timeout=5,
    ) as conn:
        yield conn


# ==========================================
# MONITORING ROUTER
# ==========================================

from api.monitoring_router import router as monitoring_router

app.include_router(monitoring_router, dependencies=[Depends(current_user)])


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "AKHARI GeoLake",
    }


# ==========================================
# WEBGIS FRONTEND
# ==========================================

@app.get("/", include_in_schema=False)
def webgis_home():
    index_file = PROJECT_ROOT / "web" / "index.html"

    if not index_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="File web/index.html tidak ditemukan",
        )

    return FileResponse(index_file)


# ==========================================
# DASHBOARD