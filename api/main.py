
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

app = FastAPI(
    title="AKHARI GeoLake API",
    description="API geospasial dan analisis pembangunan daerah",
    version="0.1.0",
)


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


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AKHARI GeoLake"}


@app.get("/api/dashboard")
def dashboard():
    try:
        with get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM v_dashboard_faskes"
            ).fetchone()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Data dashboard belum tersedia",
            )

        return result

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database tidak dapat diakses",
        )
