
"""AKHARI GeoLake — Monitoring Tindak Lanjut API.

Modul 4.4.56:
- Pencatatan tindak lanjut
- Pembaruan progres
- Pengajuan status MENUNGGU VERIFIKASI
- Pencegahan perubahan langsung ke SELESAI
- Riwayat perubahan
"""

import logging

from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

import psycopg

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger("akhari.monitoring")

router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring Tindak Lanjut"],
)

STATUSES = (
    "BELUM DITINDAKLANJUTI",
    "DALAM PROSES",
    "MENUNGGU VERIFIKASI",
    "SELESAI",
)


class MonitoringCreate(BaseModel):
    id_desa: str = Field(min_length=1, max_length=120)
    desa: str = Field(min_length=1, max_length=250)
    kecamatan: str = Field(min_length=1, max_length=250)
    rekomendasi: str = Field(min_length=1, max_length=10000)

    opd_penanggung_jawab: str = Field(
        min_length=1,
        max_length=250,
    )

    penanggung_jawab: Optional[str] = Field(
        default=None,
        max_length=250,
    )

    batas_waktu: Optional[date] = None

    catatan: Optional[str] = Field(
        default=None,
        max_length=5000,
    )


class MonitoringUpdate(BaseModel):
    opd_penanggung_jawab: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=250,
    )

    penanggung_jawab: Optional[str] = Field(
        default=None,
        max_length=250,
    )

    batas_waktu: Optional[date] = None

    status: Optional[str] = None

    progres: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
    )

    catatan: Optional[str] = Field(
        default=None,
        max_length=5000,
    )

    bukti_url: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is not None and value not in STATUSES:
            raise ValueError("Status tidak dikenal")
        return value

    @field_validator("bukti_url")
    @classmethod
    def validate_url(cls, value):
        if value:
            parsed = urlparse(value)

            if (
                parsed.scheme != "https"
                or not parsed.netloc
            ):
                raise ValueError(
                    "URL bukti harus menggunakan HTTPS"
                )

        return value


def serialize(row):
    if row is None:
        return None

    result = dict(row)

    for key, value in result.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()

    return result


def get_db():
    from api.main import get_connection
    return get_connection()


def database_error(message, error):
    logger.error(
        "%s: %s",
        message,
        error,
    )

    raise HTTPException(
        status_code=503,
        detail=message,
    ) from error


@router.get("")
def list_monitoring(
    status: Optional[str] = None,
    limit: int = 300,
):
    if status and status not in STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Status tidak dikenal",
        )

    if not 1 <= limit <= 1000:
        raise HTTPException(
            status_code=422,
            detail="Limit harus 1-1000",
        )

    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM monitoring_tindak_lanjut
                WHERE (
                    %s::text IS NULL
                    OR status = %s::text
                )
                ORDER BY diperbarui_pada DESC, id DESC
                LIMIT %s
                """,
                (status, status, limit),
            ).fetchall()

        return {
            "data": [serialize(row) for row in rows],
            "total": len(rows),
        }

    except psycopg.Error as error:
        database_error(
            "Gagal membaca monitoring",
            error,
        )


@router.get("/ringkasan")
def summary():
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)::int AS total,

                    COUNT(*) FILTER (
                        WHERE status =
                        'BELUM DITINDAKLANJUTI'
                    )::int AS belum,

                    COUNT(*) FILTER (
                        WHERE status = 'DALAM PROSES'
                    )::int AS proses,

                    COUNT(*) FILTER (
                        WHERE status =
                        'MENUNGGU VERIFIKASI'
                    )::int AS verifikasi,

                    COUNT(*) FILTER (
                        WHERE status = 'SELESAI'
                    )::int AS selesai

                FROM monitoring_tindak_lanjut
                """
            ).fetchone()

        return serialize(row)

    except psycopg.Error as error:
        database_error(
            "Gagal membaca ringkasan monitoring",
            error,
        )


@router.post("", status_code=201)
def create_monitoring(payload: MonitoringCreate):
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                INSERT INTO monitoring_tindak_lanjut (
                    id_desa,
                    desa,
                    kecamatan,
                    rekomendasi,
                    opd_penanggung_jawab,
                    penanggung_jawab,
                    batas_waktu,
                    catatan
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    payload.id_desa,
                    payload.desa,
                    payload.kecamatan,
                    payload.rekomendasi,
                    payload.opd_penanggung_jawab,
                    payload.penanggung_jawab,
                    payload.batas_waktu,
                    payload.catatan,
                ),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO monitoring_riwayat (
                    monitoring_id,
                    status_baru,
                    progres_baru,
                    catatan
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    row["id"],
                    row["status"],
                    row["progres"],
                    "Pencatatan awal",
                ),
            )

            conn.commit()

        return serialize(row)

    except psycopg.Error as error:
        database_error(
            "Gagal membuat tindak lanjut",
            error,
        )


@router.patch("/{monitoring_id}")
def update_monitoring(
    monitoring_id: int,
    payload: MonitoringUpdate,
):
    if monitoring_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="ID monitoring tidak valid",
        )

    fields = payload.model_dump(exclude_unset=True)

    if not fields:
        raise HTTPException(
            status_code=422,
            detail="Tidak ada perubahan",
        )

    # Hanya kolom yang ditentukan model yang boleh diperbarui.
    allowed_fields = {
        "opd_penanggung_jawab",
        "penanggung_jawab",
        "batas_waktu",
        "status",
        "progres",
        "catatan",
        "bukti_url",
    }

    if not set(fields).issubset(allowed_fields):
        raise HTTPException(
            status_code=422,
            detail="Kolom pembaruan tidak diizinkan",
        )

    try:
        with get_db() as conn:
            old = conn.execute(
                """
                SELECT *
                FROM monitoring_tindak_lanjut
                WHERE id = %s
                FOR UPDATE
                """,
                (monitoring_id,),
            ).fetchone()

            if old is None:
                raise HTTPException(
                    status_code=404,
                    detail="Monitoring tidak ditemukan",
                )

            old_status = old["status"]

            # Status SELESAI hanya boleh diubah
            # melalui proses keputusan verifikasi.
            if old_status == "SELESAI":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Tindak lanjut telah selesai. "
                        "Perubahan memerlukan mekanisme "
                        "pembukaan kembali yang terotorisasi."
                    ),
                )

            # Selama menunggu keputusan,
            # data monitoring tidak boleh diubah.
            if old_status == "MENUNGGU VERIFIKASI":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Tindak lanjut sedang menunggu "
                        "verifikasi dan tidak dapat diedit."
                    ),
                )

            new_status = fields.get(
                "status",
                old_status,
            )

            new_progress = fields.get(
                "progres",
                old["progres"],
            )

            new_evidence = fields.get(
                "bukti_url",
                old["bukti_url"],
            )

            if new_status is None:
                raise HTTPException(
                    status_code=422,
                    detail="Status tidak boleh kosong",
                )

            if new_progress is None:
                raise HTTPException(
                    status_code=422,
                    detail="Progres tidak boleh kosong",
                )

            if new_status == "SELESAI":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Status SELESAI hanya dapat "
                        "ditetapkan melalui keputusan "
                        "verifikasi."
                    ),
                )

            if new_status == "MENUNGGU VERIFIKASI":
                if new_progress != 100:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Pengajuan verifikasi "
                            "memerlukan progres 100%."
                        ),
                    )

                if not new_evidence:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Pengajuan verifikasi "
                            "memerlukan URL bukti."
                        ),
                    )

            elif new_progress == 100:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Progres 100% hanya diizinkan "
                        "untuk MENUNGGU VERIFIKASI "
                        "atau SELESAI."
                    ),
                )

            assignments = ", ".join(
                f"{key} = %s"
                for key in fields
            )

            params = list(fields.values()) + [
                monitoring_id,
            ]

            row = conn.execute(
                f"""
                UPDATE monitoring_tindak_lanjut
                SET
                    {assignments},
                    diperbarui_pada = NOW()
                WHERE id = %s
                RETURNING *
                """,
                params,
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
                    monitoring_id,
                    old["status"],
                    row["status"],
                    old["progres"],
                    row["progres"],
                    fields.get("catatan"),
                ),
            )

            conn.commit()

        return serialize(row)

    except psycopg.Error as error:
        database_error(
            "Gagal memperbarui monitoring",
            error,
        )


@router.get("/{monitoring_id}/riwayat")
def monitoring_history(monitoring_id: int):
    if monitoring_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="ID monitoring tidak valid",
        )

    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM monitoring_riwayat
                WHERE monitoring_id = %s
                ORDER BY dibuat_pada DESC, id DESC
                """,
                (monitoring_id,),
            ).fetchall()

        return {
            "data": [
                serialize(row)
                for row in rows
            ],
        }

    except psycopg.Error as error:
        database_error(
            "Gagal membaca riwayat monitoring",
            error,
        )
