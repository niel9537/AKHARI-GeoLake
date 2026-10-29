
-- AKHARI GeoLake
-- Modul 4.4.58 — Authentication & RBAC
-- Database: PostgreSQL
-- Tidak membuat akun atau password default.

BEGIN;

CREATE TABLE IF NOT EXISTS auth_roles (
    id BIGSERIAL PRIMARY KEY,
    kode VARCHAR(40) NOT NULL UNIQUE,
    nama VARCHAR(120) NOT NULL,
    deskripsi TEXT,
    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO auth_roles (kode, nama, deskripsi)
VALUES
    ('SUPER_ADMIN', 'Super Admin',
     'Mengelola pengguna dan seluruh sistem'),
    ('ADMIN_OPD', 'Admin OPD',
     'Mengelola monitoring OPD yang ditugaskan'),
    ('VERIFIKATOR', 'Verifikator',
     'Memeriksa dan memutuskan pengajuan'),
    ('PIMPINAN', 'Pimpinan',
     'Membaca dashboard dan laporan')
ON CONFLICT (kode) DO NOTHING;


CREATE TABLE IF NOT EXISTS auth_users (
    id BIGSERIAL PRIMARY KEY,

    username VARCHAR(80) NOT NULL UNIQUE,

    nama_lengkap VARCHAR(200) NOT NULL,

    password_hash TEXT NOT NULL,

    role_id BIGINT NOT NULL
        REFERENCES auth_roles(id),

    opd VARCHAR(250),

    aktif BOOLEAN NOT NULL DEFAULT TRUE,

    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    diperbarui_pada TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    login_terakhir TIMESTAMPTZ,

    CONSTRAINT chk_username
        CHECK (username ~ '^[a-z0-9_.-]{3,80}$'),

    CONSTRAINT chk_password_hash
        CHECK (length(password_hash) >= 30)
);


CREATE INDEX IF NOT EXISTS idx_auth_users_role
ON auth_users(role_id);

CREATE INDEX IF NOT EXISTS idx_auth_users_opd
ON auth_users(opd);


CREATE TABLE IF NOT EXISTS auth_sessions (
    id BIGSERIAL PRIMARY KEY,

    user_id BIGINT NOT NULL
        REFERENCES auth_users(id)
        ON DELETE CASCADE,

    token_hash CHAR(64) NOT NULL UNIQUE,

    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    kedaluwarsa_pada TIMESTAMPTZ NOT NULL,

    dicabut_pada TIMESTAMPTZ,

    CONSTRAINT chk_session_expiry
        CHECK (kedaluwarsa_pada > dibuat_pada)
);


CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
ON auth_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry
ON auth_sessions(kedaluwarsa_pada);


CREATE TABLE IF NOT EXISTS auth_audit_log (
    id BIGSERIAL PRIMARY KEY,

    user_id BIGINT REFERENCES auth_users(id)
        ON DELETE SET NULL,

    aksi VARCHAR(100) NOT NULL,

    objek VARCHAR(100),

    objek_id VARCHAR(120),

    keterangan TEXT,

    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_auth_audit_user
ON auth_audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_audit_time
ON auth_audit_log(dibuat_pada DESC);


CREATE OR REPLACE VIEW v_auth_users AS
SELECT
    u.id,
    u.username,
    u.nama_lengkap,
    r.kode AS role,
    r.nama AS nama_role,
    u.opd,
    u.aktif,
    u.dibuat_pada,
    u.login_terakhir
FROM auth_users u
JOIN auth_roles r
    ON r.id = u.role_id;

COMMIT;
