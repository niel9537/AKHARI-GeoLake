
"""Create the first AKHARI GeoLake administrator locally."""

import getpass
import re
import sys

import psycopg
from argon2 import PasswordHasher

from api.main import get_connection


def main():
    print("=== AKHARI GeoLake: Bootstrap Super Admin ===")

    username = input("Username: ").strip().lower()
    nama = input("Nama lengkap: ").strip()

    if not re.fullmatch(r"[a-z0-9_.-]{3,80}", username):
        sys.exit("Username tidak valid.")

    if len(nama) < 2 or len(nama) > 200:
        sys.exit("Nama lengkap tidak valid.")

    password = getpass.getpass("Password (minimal 12 karakter): ")
    confirmation = getpass.getpass("Ulangi password: ")

    if len(password) < 12 or password != confirmation:
        sys.exit("Password tidak sesuai atau terlalu pendek.")

    with get_connection() as conn:
        with conn.transaction():
            # Prevent concurrent bootstrap operations.
            conn.execute(
                "SELECT pg_advisory_xact_lock(458058)"
            )

            count = conn.execute(
                "SELECT COUNT(*) AS total FROM auth_users"
            ).fetchone()["total"]

            if count > 0:
                sys.exit(
                    "Bootstrap hanya untuk database tanpa akun. "
                    "Gunakan API admin untuk membuat akun tambahan."
                )

            hashed = PasswordHasher().hash(password)

            row = conn.execute(
                """
                INSERT INTO auth_users (
                    username,
                    nama_lengkap,
                    password_hash,
                    role_id
                )
                SELECT %s, %s, %s, id
                FROM auth_roles
                WHERE kode = 'SUPER_ADMIN'
                RETURNING id, username
                """,
                (username, nama, hashed),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Role SUPER_ADMIN belum tersedia."
                )

            conn.execute(
                """
                INSERT INTO auth_audit_log (
                    user_id, aksi
                )
                VALUES (%s, 'BOOTSTRAP_ADMIN')
                """,
                (row["id"],),
            )

    print("Akun Super Admin berhasil dibuat.")
    print("Username:", username)


if __name__ == "__main__":
    main()
