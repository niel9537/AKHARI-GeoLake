
"""AKHARI GeoLake - Authentication API.

Database-backed session authentication.
Local development only until all existing routes
have been protected with authorization.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

logger = logging.getLogger("akhari.auth")

password_hasher = PasswordHasher()
SESSION_HOURS = 8


def get_db():
    from api.main import get_connection
    return get_connection()


def token_digest(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def unauthorized(message="Sesi tidak valid"):
    raise HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def database_error(error):
    logger.error("Authentication database error: %s", error)
    raise HTTPException(
        status_code=503,
        detail="Layanan autentikasi tidak tersedia",
    ) from error


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )
    password: str = Field(
        min_length=1,
        max_length=1024,
    )


class UserCreate(BaseModel):
    username: str = Field(
        pattern=r"^[a-z0-9_.-]{3,80}$",
    )
    nama_lengkap: str = Field(
        min_length=2,
        max_length=200,
    )
    password: str = Field(
        min_length=12,
        max_length=1024,
    )
    role: str
    opd: str | None = Field(
        default=None,
        max_length=250,
    )


def public_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "nama_lengkap": row["nama_lengkap"],
        "role": row["role"],
        "opd": row["opd"],
    }


def read_session(token: str):
    if not token or len(token) != 64:
        unauthorized()

    try:
        with get_db() as conn:
            user = conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.nama_lengkap,
                    u.opd,
                    r.kode AS role
                FROM auth_sessions s
                JOIN auth_users u
                    ON u.id = s.user_id
                JOIN auth_roles r
                    ON r.id = u.role_id
                WHERE s.token_hash = %s
                  AND s.dicabut_pada IS NULL
                  AND s.kedaluwarsa_pada > NOW()
                  AND u.aktif = TRUE
                """,
                (token_digest(token),),
            ).fetchone()

        if user is None:
            unauthorized()

        return dict(user)

    except psycopg.Error as error:
        database_error(error)


def current_user(
    authorization: Annotated[
        str | None,
        Header(),
    ] = None,
):
    if not authorization:
        unauthorized("Login diperlukan")

    scheme, separator, token = authorization.partition(" ")

    if separator != " " or scheme.lower() != "bearer":
        unauthorized("Gunakan Bearer token")

    return read_session(token.strip())


def require_roles(*roles):
    def dependency(
        user=Depends(current_user),
    ):
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail="Hak akses tidak mencukupi",
            )
        return user

    return dependency


@router.post("/login")
def login(payload: LoginRequest):
    try:
        with get_db() as conn:
            user = conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.nama_lengkap,
                    u.password_hash,
                    u.opd,
                    u.aktif,
                    r.kode AS role
                FROM auth_users u
                JOIN auth_roles r
                    ON r.id = u.role_id
                WHERE u.username = %s
                """,
                (payload.username,),
            ).fetchone()

            if user is None or not user["aktif"]:
                unauthorized("Username atau password salah")

            try:
                password_hasher.verify(
                    user["password_hash"],
                    payload.password,
                )
            except (
                VerifyMismatchError,
                VerificationError,
                InvalidHashError,
            ):
                unauthorized("Username atau password salah")

            token = secrets.token_hex(32)
            expires = (
                datetime.now(timezone.utc)
                + timedelta(hours=SESSION_HOURS)
            )

            conn.execute(
                """
                INSERT INTO auth_sessions (
                    user_id,
                    token_hash,
                    kedaluwarsa_pada
                )
                VALUES (%s, %s, %s)
                """,
                (
                    user["id"],
                    token_digest(token),
                    expires,
                ),
            )

            conn.execute(
                """
                UPDATE auth_users
                SET login_terakhir = NOW()
                WHERE id = %s
                """,
                (user["id"],),
            )

            conn.execute(
                """
                INSERT INTO auth_audit_log (
                    user_id,
                    aksi
                )
                VALUES (%s, 'LOGIN')
                """,
                (user["id"],),
            )

            conn.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires.isoformat(),
            "user": public_user(user),
        }

    except psycopg.Error as error:
        database_error(error)


@router.get("/me")
def me(user=Depends(current_user)):
    return {
        "authenticated": True,
        "user": user,
    }


@router.post("/logout")
def logout(
    authorization: Annotated[
        str | None,
        Header(),
    ] = None,
    user=Depends(current_user),
):
    token = authorization.partition(" ")[2].strip()

    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE auth_sessions
                SET dicabut_pada = NOW()
                WHERE token_hash = %s
                  AND dicabut_pada IS NULL
                """,
                (token_digest(token),),
            )

            conn.execute(
                """
                INSERT INTO auth_audit_log (
                    user_id,
                    aksi
                )
                VALUES (%s, 'LOGOUT')
                """,
                (user["id"],),
            )

            conn.commit()

        return {
            "message": "Logout berhasil",
        }

    except psycopg.Error as error:
        database_error(error)


@router.get("/users")
def list_users(
    user=Depends(
        require_roles("SUPER_ADMIN")
    ),
):
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM v_auth_users
                ORDER BY id
                """
            ).fetchall()

        return {
            "data": [dict(row) for row in rows],
            "total": len(rows),
        }

    except psycopg.Error as error:
        database_error(error)


@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    admin=Depends(
        require_roles("SUPER_ADMIN")
    ),
):
    valid_roles = {
        "SUPER_ADMIN",
        "ADMIN_OPD",
        "VERIFIKATOR",
        "PIMPINAN",
    }

    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=422,
            detail="Role tidak valid",
        )

    if payload.role == "ADMIN_OPD" and not payload.opd:
        raise HTTPException(
            status_code=422,
            detail="Admin OPD wajib memiliki OPD",
        )

    password_hash = password_hasher.hash(
        payload.password
    )

    try:
        with get_db() as conn:
            row = conn.execute(
                """
                INSERT INTO auth_users (
                    username,
                    nama_lengkap,
                    password_hash,
                    role_id,
                    opd
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    r.id,
                    %s
                FROM auth_roles r
                WHERE r.kode = %s
                RETURNING id, username, nama_lengkap, opd
                """,
                (
                    payload.username,
                    payload.nama_lengkap,
                    password_hash,
                    payload.opd,
                    payload.role,
                ),
            ).fetchone()

            if row is None:
                raise HTTPException(
                    status_code=422,
                    detail="Role tidak ditemukan",
                )

            conn.execute(
                """
                INSERT INTO auth_audit_log (
                    user_id,
                    aksi,
                    objek,
                    objek_id
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    admin["id"],
                    "CREATE_USER",
                    "auth_users",
                    str(row["id"]),
                ),
            )

            conn.commit()

        return {
            "message": "Pengguna berhasil dibuat",
            "user": {
                **dict(row),
                "role": payload.role,
            },
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Username sudah digunakan",
        )

    except psycopg.Error as error:
        database_error(error)
