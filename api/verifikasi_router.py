
"""AKHARI GeoLake — API Verifikasi Tindak Lanjut.

Versi pengembangan lokal:
- Daftar pengajuan verifikasi
- Pengajuan verifikasi monitoring
- Persetujuan atau penolakan
- Sinkronisasi status monitoring
- Pencatatan riwayat monitoring
- Ringkasan kinerja OPD

PENTING:
Belum memiliki autentikasi/otorisasi.
Jangan digunakan sebagai persetujuan resmi.
"""

import logging

from datetime import date, datetime
from typing import Literal

import psycopg

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


logger = logging.getLogger("akhari.verifikasi")

router = APIRouter(
    prefix="/api/verifikasi",
    tags=["Verifikasi Tindak Lanjut"],
)


def get_db():
    # Import tertunda untuk menghindari circular import.
    from api.main import get_connection
    return get_connection()


def serialize(row):
    if row is None:
        return None

    result = dict(row)

    for key, value in result.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()

    return result


def db_error(message, error):
    logger.exception("%s: %s", message, error)

    raise HTTPException(
        status_code=503,
        detail=message,
    ) from error


class PengajuanVerifikasi(BaseModel):
    monitoring_id: int = Field(gt=0)

    diajukan_oleh: str = Field(
        min_length=2,
        max_length=150,
    )

    catatan_pengajuan: str | None = Field(
        default=None,
        max_length=5000,
    )


class KeputusanVerifikasi(BaseModel):
    keputusan: Literal[
        "DISETUJUI",
        "DITOLAK",
    ]

    diverifikasi_oleh: str = Field(
        min_length=2,
        max_length=150,
    )

    catatan_verifikator: str = Field(
        min_length=3,
        max_length=5000,
    )


# ==========================================
# DAFTAR VERIFIKASI
# ==========================================

@router.get("")
def daftar_verifikasi(
    status: Literal[
        "MENUNGGU",
        "DISETUJUI",
        "DITOLAK",
    ] | None = None,
    limit: int = 100,
):
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=422,
            detail="Limit harus antara 1 dan 500",
        )

    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM v_monitoring_verifikasi
                WHERE (
                    %s::text IS NULL
                    OR status_verifikasi = %s
                )
                ORDER BY
                    diajukan_pada DESC,
                    id_verifikasi DESC
                LIMIT %s
                """,
                (status, status, limit),
            ).fetchall()

        return {
            "status": "success",
            "total": len(rows),
            "data": [
                serialize(row)
                for row in rows
            ],
        }

    except psycopg.Error as error:
        db_error(
            "Gagal membaca daftar verifikasi",
            error,
        )


# ==========================================
# KINERJA OPD
# ==========================================

@router.get("/kinerja-opd")
def kinerja_opd():
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM v_kinerja_monitoring_opd
                ORDER BY
                    total_tindak_lanjut DESC,
                    opd
                """
            ).fetchall()

        return {
            "status": "success",
            "total_opd": len(rows),
            "data": [
                serialize(row)
                for row in rows
            ],
            "catatan": (
                "Indikator operasional monitoring. "
                "Bukan penilaian kinerja resmi OPD."
            ),
        }

    except psycopg.Error as error:
        db_error(
            "Gagal membaca kinerja OPD",
            error,
        )


# ==========================================
# PENGAJUAN VERIFIKASI
# ==========================================

@router.post("", status_code=201)
def ajukan_verifikasi(
    payload: PengajuanVerifikasi,
):
    try:
        with get_db() as conn:
            with conn.transaction():
                monitoring = conn.execute(
                    """
                    SELECT
                        id,
                        status,
                        progres,
                        bukti_url
                    FROM monitoring_tindak_lanjut
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (payload.monitoring_id,),
                ).fetchone()

                if monitoring is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Tindak lanjut tidak ditemukan",
                    )

                if (
                    monitoring["status"]
                    != "MENUNGGU VERIFIKASI"
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Ubah status monitoring menjadi "
                            "MENUNGGU VERIFIKASI terlebih dahulu."
                        ),
                    )

                if monitoring["progres"] != 100:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Pengajuan membutuhkan progres 100%."
                        ),
                    )

                if not monitoring["bukti_url"]:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "URL bukti tindak lanjut wajib tersedia."
                        ),
                    )

                existing = conn.execute(
                    """
                    SELECT id
                    FROM monitoring_verifikasi
                    WHERE monitoring_id = %s
                      AND status_verifikasi = 'MENUNGGU'
                    """,
                    (payload.monitoring_id,),
                ).fetchone()

                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Masih ada pengajuan verifikasi "
                            "yang belum diputuskan."
                        ),
                    )

                row = conn.execute(
                    """
                    INSERT INTO monitoring_verifikasi (
                        monitoring_id,
                        diajukan_oleh,
                        catatan_pengajuan
                    )
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (
                        payload.monitoring_id,
                        payload.diajukan_oleh.strip(),
                        payload.catatan_pengajuan,
                    ),
                ).fetchone()

                conn.execute(
                    """
                    INSERT INTO monitoring_riwayat (
                        monitoring_id,
                        status_lama,
                        status_baru,
                        progres_lama,
                        progres_baru,
                        catatan
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload.monitoring_id,
                        monitoring["status"],
                        monitoring["status"],
                        monitoring["progres"],
                        monitoring["progres"],
                        (
                            "Pengajuan verifikasi lokal "
                            f"#{row['id']} oleh "
                            f"{payload.diajukan_oleh.strip()}"
                        ),
                    ),
                )

        return {
            "status": "success",
            "message": "Pengajuan verifikasi berhasil dicatat",
            "data": serialize(row),
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail=(
                "Pengajuan verifikasi yang menunggu "
                "sudah tersedia."
            ),
        )

    except psycopg.Error as error:
        db_error(
            "Gagal mengajukan verifikasi",
            error,
        )


# ==========================================
# KEPUTUSAN VERIFIKASI
# ==========================================

@router.patch("/{verifikasi_id}/keputusan")
def putuskan_verifikasi(
    verifikasi_id: int,
    payload: KeputusanVerifikasi,
):
    if verifikasi_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="ID verifikasi tidak valid",
        )

    try:
        with get_db() as conn:
            with conn.transaction():
                # Baca ID monitoring terlebih dahulu.
                initial = conn.execute(
                    """
                    SELECT monitoring_id
                    FROM monitoring_verifikasi
                    WHERE id = %s
                    """,
                    (verifikasi_id,),
                ).fetchone()

                if initial is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Pengajuan verifikasi tidak ditemukan",
                    )

                # Urutan penguncian konsisten:
                # monitoring terlebih dahulu, lalu verifikasi.
                monitoring = conn.execute(
                    """
                    SELECT
                        id,
                        status,
                        progres,
                        bukti_url
                    FROM monitoring_tindak_lanjut
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (initial["monitoring_id"],),
                ).fetchone()

                if monitoring is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Monitoring tidak ditemukan",
                    )

                verifikasi = conn.execute(
                    """
                    SELECT *
                    FROM monitoring_verifikasi
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (verifikasi_id,),
                ).fetchone()

                if verifikasi["status_verifikasi"] != "MENUNGGU":
                    raise HTTPException(
                        status_code=409,
                        detail="Pengajuan sudah diputuskan",
                    )

                if (
                    monitoring["status"]
                    != "MENUNGGU VERIFIKASI"
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Status monitoring tidak lagi "
                            "menunggu verifikasi."
                        ),
                    )

                if payload.keputusan == "DISETUJUI":
                    if monitoring["progres"] != 100:
                        raise HTTPException(
                            status_code=409,
                            detail="Progres monitoring belum 100%",
                        )

                    if not monitoring["bukti_url"]:
                        raise HTTPException(
                            status_code=409,
                            detail="Bukti monitoring belum tersedia",
                        )

                    status_baru = "SELESAI"
                    progres_baru = 100

                else:
                    status_baru = "DALAM PROSES"
                    progres_baru = min(
                        monitoring["progres"],
                        99,
                    )

                updated_monitoring = conn.execute(
                    """
                    UPDATE monitoring_tindak_lanjut
                    SET
                        status = %s,
                        progres = %s,
                        diperbarui_pada = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        status_baru,
                        progres_baru,
                        monitoring["id"],
                    ),
                ).fetchone()

                updated_verifikasi = conn.execute(
                    """
                    UPDATE monitoring_verifikasi
                    SET
                        status_verifikasi = %s,
                        diverifikasi_oleh = %s,
                        catatan_verifikator = %s,
                        diverifikasi_pada = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        payload.keputusan,
                        payload.diverifikasi_oleh.strip(),
                        payload.catatan_verifikator.strip(),
                        verifikasi_id,
                    ),
                ).fetchone()

                conn.execute(
                    """
                    INSERT INTO monitoring_riwayat (
                        monitoring_id,
                        status_lama,
                        status_baru,
                        progres_lama,
                        progres_baru,
                        catatan
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        monitoring["id"],
                        monitoring["status"],
                        updated_monitoring["status"],
                        monitoring["progres"],
                        updated_monitoring["progres"],
                        (
                            f"Verifikasi lokal #{verifikasi_id}: "
                            f"{payload.keputusan}. "
                            f"Catatan: "
                            f"{payload.catatan_verifikator.strip()}"
                        ),
                    ),
                )

        return {
            "status": "success",
            "message": (
                "Keputusan verifikasi berhasil dicatat"
            ),
            "data": serialize(updated_verifikasi),
            "monitoring": serialize(updated_monitoring),
        }

    except psycopg.Error as error:
        db_error(
            "Gagal menyimpan keputusan verifikasi",
            error,
        )
