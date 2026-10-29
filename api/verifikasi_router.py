
from datetime import datetime
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/verifikasi",
    tags=["Verifikasi Tindak Lanjut"],
)


def get_db():
    from api.main import get_connection
    return get_connection()


class PengajuanVerifikasi(BaseModel):
    monitoring_id: int = Field(gt=0)
    diajukan_oleh: str = Field(min_length=2, max_length=150)
    catatan_pengajuan: str | None = None


class KeputusanVerifikasi(BaseModel):
    keputusan: Literal["DISETUJUI", "DITOLAK"]
    diverifikasi_oleh: str = Field(min_length=2, max_length=150)
    catatan_verifikator: str = Field(min_length=3)


@router.get("")
def daftar_verifikasi(
    status: str | None = None,
    limit: int = 100,
):
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=422,
            detail="Limit harus antara 1 dan 500",
        )

    if status and status not in (
        "MENUNGGU",
        "DISETUJUI",
        "DITOLAK",
    ):
        raise HTTPException(
            status_code=422,
            detail="Status verifikasi tidak valid",
        )

    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM v_monitoring_verifikasi
                WHERE (%s::text IS NULL
                    OR status_verifikasi = %s)
                ORDER BY diajukan_pada DESC, id_verifikasi DESC
                LIMIT %s
                """,
                (status, status, limit),
            ).fetchall()

        return {
            "total": len(rows),
            "data": rows,
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal membaca daftar verifikasi",
        )


@router.get("/kinerja-opd")
def kinerja_opd():
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM v_kinerja_monitoring_opd
                ORDER BY total_tindak_lanjut DESC, opd
                """
            ).fetchall()

        return {
            "total_opd": len(rows),
            "data": rows,
            "catatan": (
                "Indikator operasional monitoring, "
                "bukan penilaian kinerja resmi OPD."
            ),
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal membaca kinerja OPD",
        )


@router.post("", status_code=201)
def ajukan_verifikasi(payload: PengajuanVerifikasi):
    try:
        with get_db() as conn:
            with conn.transaction():
                monitoring = conn.execute(
                    """
                    SELECT id, status, progres, bukti_url
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

                if monitoring["status"] != "MENUNGGU VERIFIKASI":
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Status tindak lanjut harus "
                            "MENUNGGU VERIFIKASI"
                        ),
                    )

                if monitoring["progres"] != 100:
                    raise HTTPException(
                        status_code=409,
                        detail="Progres harus 100%",
                    )

                if not monitoring["bukti_url"]:
                    raise HTTPException(
                        status_code=409,
                        detail="Bukti tindak lanjut wajib tersedia",
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
                        payload.diajukan_oleh,
                        payload.catatan_pengajuan,
                    ),
                ).fetchone()

            return {
                "status": "success",
                "message": "Verifikasi berhasil diajukan",
                "data": row,
            }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Masih ada pengajuan verifikasi yang menunggu",
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal mengajukan verifikasi",
        )


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
                verifikasi = conn.execute(
                    """
                    SELECT *
                    FROM monitoring_verifikasi
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (verifikasi_id,),
                ).fetchone()

                if verifikasi is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Pengajuan verifikasi tidak ditemukan",
                    )

                if verifikasi["status_verifikasi"] != "MENUNGGU":
                    raise HTTPException(
                        status_code=409,
                        detail="Pengajuan sudah diputuskan",
                    )

                monitoring = conn.execute(
                    """
                    SELECT id, status, progres, bukti_url
                    FROM monitoring_tindak_lanjut
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (verifikasi["monitoring_id"],),
                ).fetchone()

                if monitoring is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Tindak lanjut tidak ditemukan",
                    )

                if monitoring["status"] != "MENUNGGU VERIFIKASI":
                    raise HTTPException(
                        status_code=409,
                        detail="Status tindak lanjut sudah berubah",
                    )

                if payload.keputusan == "DISETUJUI":
                    if monitoring["progres"] != 100:
                        raise HTTPException(
                            status_code=409,
                            detail="Progres belum 100%",
                        )

                    if not monitoring["bukti_url"]:
                        raise HTTPException(
                            status_code=409,
                            detail="Bukti tindak lanjut tidak tersedia",
                        )

                    status_baru = "SELESAI"
                    progres_baru = 100
                else:
                    status_baru = "DALAM PROSES"
                    progres_baru = min(monitoring["progres"], 99)

                conn.execute(
                    """
                    UPDATE monitoring_tindak_lanjut
                    SET
                        status = %s,
                        progres = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        status_baru,
                        progres_baru,
                        monitoring["id"],
                    ),
                )

                result = conn.execute(
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
                        payload.diverifikasi_oleh,
                        payload.catatan_verifikator,
                        verifikasi_id,
                    ),
                ).fetchone()

            return {
                "status": "success",
                "message": "Keputusan verifikasi tersimpan",
                "data": result,
            }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Gagal menyimpan keputusan verifikasi",
        )
