
import logging
import os

from contextlib import contextmanager
from pathlib import Path

import psycopg

from psycopg.rows import dict_row
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
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

app.include_router(monitoring_router)


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
# ==========================================

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
        logger.exception("Gagal membaca dashboard")

        raise HTTPException(
            status_code=503,
            detail="Database tidak dapat diakses",
        )


# ==========================================
# FACILITY GEOJSON
# ==========================================

@app.get("/api/fasilitas/geojson")
def fasilitas_geojson():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
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
                """
            ).fetchall()

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
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    except psycopg.Error:
        logger.exception("Gagal membaca fasilitas")

        raise HTTPException(
            status_code=503,
            detail="Gagal membaca fasilitas kesehatan",
        )


# ==========================================
# VILLAGE GEOJSON
# ==========================================

@app.get("/api/wilayah/desa")
def geojson_desa():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    "OBJECTID" AS id,
                    "WADMKD" AS desa,
                    "WADMKC" AS kecamatan,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM batas_desa_nias_barat
                WHERE geom IS NOT NULL
                ORDER BY "OBJECTID"
                """
            ).fetchall()

        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row["id"],
                    "geometry": row["geometry"],
                    "properties": {
                        "id_desa": row["id"],
                        "desa": row["desa"],
                        "kecamatan": row["kecamatan"],
                    },
                }
                for row in rows
            ],
        }

    except psycopg.Error:
        logger.exception("Gagal membaca desa")

        raise HTTPException(
            status_code=503,
            detail="Gagal membaca polygon desa",
        )


# ==========================================
# DISTRICT GEOJSON
# ==========================================

@app.get("/api/wilayah/kecamatan")
def geojson_kecamatan():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
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
                """
            ).fetchall()

        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row["id"],
                    "geometry": row["geometry"],
                    "properties": {
                        "kecamatan": row["kecamatan"],
                        "total_fasilitas": row["total_fasilitas"],
                        "puskesmas": row["puskesmas"],
                        "pustu": row["pustu"],
                        "poskesdes": row["poskesdes"],
                    },
                }
                for row in rows
            ],
        }

    except psycopg.Error:
        logger.exception("Gagal membaca kecamatan")

        raise HTTPException(
            status_code=503,
            detail="Gagal membaca polygon kecamatan",
        )


# ==========================================
# ACCESS ANALYSIS GEOJSON
# ==========================================

@app.get("/api/analisis/akses-desa")
def geojson_akses_faskes_desa():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    desa,
                    kecamatan,
                    fasilitas_terdekat,
                    jenis_fasilitas,
                    jarak_meter,
                    kategori_jarak,
                    warna_hex,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM v_peta_akses_faskes_desa
                WHERE geom IS NOT NULL
                ORDER BY kecamatan, desa, id
                """
            ).fetchall()

        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row["id"],
                    "geometry": row["geometry"],
                    "properties": {
                        "id_desa": row["id"],
                        "desa": row["desa"],
                        "kecamatan": row["kecamatan"],
                        "fasilitas_terdekat": (
                            row["fasilitas_terdekat"]
                        ),
                        "jenis_fasilitas": (
                            row["jenis_fasilitas"]
                        ),
                        "jarak_meter": (
                            float(row["jarak_meter"])
                            if row["jarak_meter"] is not None
                            else None
                        ),
                        "kategori_jarak": (
                            row["kategori_jarak"]
                        ),
                        "warna_hex": row["warna_hex"],
                    },
                }
                for row in rows
            ],
        }

    except psycopg.Error:
        logger.exception("Gagal membaca analisis akses")

        raise HTTPException(
            status_code=503,
            detail=(
                "Gagal membaca analisis akses "
                "fasilitas kesehatan"
            ),
        )


# ==========================================
# PRIORITY VILLAGES
# ==========================================

@app.get("/api/analisis/prioritas-desa")
def daftar_prioritas_desa(
    kecamatan: str | None = None,
    kategori: str | None = None,
    limit: int = 105,
):
    if not 1 <= limit <= 105:
        raise HTTPException(
            status_code=422,
            detail="Limit harus antara 1 dan 105",
        )

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    peringkat,
                    id_desa,
                    desa,
                    kecamatan,
                    fasilitas_terdekat,
                    jenis_fasilitas,
                    jarak_meter,
                    kategori_jarak,
                    tingkat_prioritas,
                    label_prioritas
                FROM v_prioritas_akses_faskes_desa
                WHERE
                    (
                        %s::text IS NULL
                        OR kecamatan = %s
                    )
                    AND
                    (
                        %s::text IS NULL
                        OR kategori_jarak = %s
                    )
                ORDER BY peringkat
                LIMIT %s
                """,
                (
                    kecamatan,
                    kecamatan,
                    kategori,
                    kategori,
                    limit,
                ),
            ).fetchall()

        data = []

        for row in rows:
            item = dict(row)

            if item["jarak_meter"] is not None:
                item["jarak_meter"] = float(
                    item["jarak_meter"]
                )

            data.append(item)

        return {
            "total_ditampilkan": len(data),
            "filter": {
                "kecamatan": kecamatan,
                "kategori": kategori,
            },
            "data": data,
        }

    except psycopg.Error:
        logger.exception("Gagal membaca prioritas desa")

        raise HTTPException(
            status_code=503,
            detail="Gagal membaca data prioritas desa",
        )


# ==========================================
# VILLAGE RECOMMENDATIONS
# NEW ENDPOINT — MODULE 4.4.55 FIX
# ==========================================

@app.get("/api/analisis/rekomendasi-desa")
def daftar_rekomendasi_desa(
    kecamatan: str | None = None,
    kategori: str | None = None,
    limit: int = 105,
):
    """
    Return preliminary recommendations for village
    healthcare accessibility.

    Recommendations are based on straight-line
    distances and require field verification.
    """

    if not 1 <= limit <= 105:
        raise HTTPException(
            status_code=422,
            detail="Limit harus antara 1 dan 105",
        )

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    peringkat,
                    id_desa,
                    desa,
                    kecamatan,
                    fasilitas_terdekat,
                    jenis_fasilitas,
                    jarak_meter,
                    kategori_jarak,
                    tingkat_prioritas,
                    label_prioritas,
                    kategori_rekomendasi,
                    alasan_rekomendasi,
                    tindak_lanjut,
                    opd_terkait,
                    status_rekomendasi
                FROM v_rekomendasi_akses_faskes_desa
                WHERE
                    (
                        %s::text IS NULL
                        OR kecamatan = %s
                    )
                    AND
                    (
                        %s::text IS NULL
                        OR kategori_jarak = %s
                    )
                ORDER BY peringkat
                LIMIT %s
                """,
                (
                    kecamatan,
                    kecamatan,
                    kategori,
                    kategori,
                    limit,
                ),
            ).fetchall()

        data = []

        for row in rows:
            item = dict(row)

            if item["jarak_meter"] is not None:
                item["jarak_meter"] = float(
                    item["jarak_meter"]
                )

            data.append(item)

        return {
            "status": "success",
            "total_ditampilkan": len(data),
            "filter": {
                "kecamatan": kecamatan,
                "kategori": kategori,
            },
            "catatan": (
                "Rekomendasi merupakan hasil analisis "
                "awal berbasis jarak garis lurus "
                "dan memerlukan validasi lebih lanjut."
            ),
            "data": data,
        }

    except psycopg.Error:
        logger.exception(
            "Gagal membaca rekomendasi desa"
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Gagal membaca data rekomendasi desa. "
                "Pastikan view "
                "v_rekomendasi_akses_faskes_desa "
                "sudah tersedia."
            ),
        )


from api.verifikasi_router import router as verifikasi_router
app.include_router(verifikasi_router)
