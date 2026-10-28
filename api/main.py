
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


@app.get("/api/fasilitas/geojson")
def fasilitas_geojson():
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    nama,
                    jenis,
                    koordinat,
                    desa,
                    kecamatan,
                    status_spasial,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM v_fasilitas_kesehatan_spasial
                WHERE geom IS NOT NULL
                ORDER BY id
            """).fetchall()

        features = []

        for row in rows:
            features.append({
                "type": "Feature",
                "id": row["id"],
                "geometry": row["geometry"],
                "properties": {
                    "nama": row["nama"],
                    "jenis": row["jenis"],
                    "koordinat": row["koordinat"],
                    "desa": row["desa"],
                    "kecamatan": row["kecamatan"],
                    "status_spasial": row["status_spasial"],
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database tidak dapat diakses",
        )


from pathlib import Path
from fastapi.responses import FileResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent

@app.get("/", include_in_schema=False)
def webgis_home():
    return FileResponse(PROJECT_ROOT / "web" / "index.html")


@app.get("/api/wilayah/desa")
def geojson_desa():
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    "OBJECTID" AS id,
                    "WADMKD" AS desa,
                    "WADMKC" AS kecamatan,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM batas_desa_nias_barat
                WHERE geom IS NOT NULL
                ORDER BY "OBJECTID"
            """).fetchall()

        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": r["id"],
                    "geometry": r["geometry"],
                    "properties": {
                        "desa": r["desa"],
                        "kecamatan": r["kecamatan"]
                    }
                }
                for r in rows
            ]
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal membaca polygon desa"
        )


@app.get("/api/wilayah/kecamatan")
def geojson_kecamatan():
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    kecamatan,
                    total_fasilitas,
                    puskesmas,
                    pustu,
                    poskesdes,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM v_peta_faskes_kecamatan
                ORDER BY kecamatan
            """).fetchall()

        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": r["id"],
                    "geometry": r["geometry"],
                    "properties": {
                        "kecamatan": r["kecamatan"],
                        "total_fasilitas": r["total_fasilitas"],
                        "puskesmas": r["puskesmas"],
                        "pustu": r["pustu"],
                        "poskesdes": r["poskesdes"]
                    }
                }
                for r in rows
            ]
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal membaca polygon kecamatan"
        )
