
-- =====================================================
-- AKHARI GEOLAKE
-- MODUL 4.4.56 - VERIFIKASI TINDAK LANJUT
-- =====================================================

BEGIN;

-- 1. Permohonan verifikasi tindak lanjut
CREATE TABLE IF NOT EXISTS monitoring_verifikasi (
    id BIGSERIAL PRIMARY KEY,

    monitoring_id BIGINT NOT NULL
        REFERENCES monitoring_tindak_lanjut(id)
        ON DELETE RESTRICT,

    status_verifikasi VARCHAR(30) NOT NULL
        DEFAULT 'MENUNGGU'
        CHECK (
            status_verifikasi IN (
                'MENUNGGU',
                'DISETUJUI',
                'DITOLAK'
            )
        ),

    catatan_pengajuan TEXT,
    catatan_verifikator TEXT,

    -- Identitas sementara untuk pengembangan lokal.
    -- Pada tahap produksi harus berasal dari login.
    diajukan_oleh TEXT,
    diverifikasi_oleh TEXT,

    diajukan_pada TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    diverifikasi_pada TIMESTAMPTZ,

    CONSTRAINT chk_keputusan_verifikasi
    CHECK (
        (
            status_verifikasi = 'MENUNGGU'
            AND diverifikasi_pada IS NULL
        )
        OR
        (
            status_verifikasi IN ('DISETUJUI', 'DITOLAK')
            AND diverifikasi_pada IS NOT NULL
            AND NULLIF(TRIM(diverifikasi_oleh), '') IS NOT NULL
        )
    )
);

-- 2. Satu permohonan menunggu untuk setiap tindak lanjut
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_monitoring_verifikasi_menunggu
ON monitoring_verifikasi (monitoring_id)
WHERE status_verifikasi = 'MENUNGGU';

CREATE INDEX IF NOT EXISTS
    idx_monitoring_verifikasi_monitoring
ON monitoring_verifikasi (monitoring_id);

CREATE INDEX IF NOT EXISTS
    idx_monitoring_verifikasi_status
ON monitoring_verifikasi (status_verifikasi);

-- 3. Tampilan daftar verifikasi
CREATE OR REPLACE VIEW v_monitoring_verifikasi AS
SELECT
    v.id AS id_verifikasi,
    v.monitoring_id,

    m.id_desa,
    m.desa,
    m.kecamatan,
    m.opd_penanggung_jawab,
    m.penanggung_jawab,
    m.rekomendasi,
    m.status AS status_tindak_lanjut,
    m.progres,
    m.bukti_url,
    m.batas_waktu,

    v.status_verifikasi,
    v.catatan_pengajuan,
    v.catatan_verifikator,
    v.diajukan_oleh,
    v.diverifikasi_oleh,
    v.diajukan_pada,
    v.diverifikasi_pada

FROM monitoring_verifikasi v
JOIN monitoring_tindak_lanjut m
    ON m.id = v.monitoring_id;

-- 4. Ringkasan kinerja OPD
-- Catatan: indikator ini bersifat operasional,
-- bukan penilaian kinerja resmi pemerintah.

CREATE OR REPLACE VIEW v_kinerja_monitoring_opd AS
SELECT
    m.opd_penanggung_jawab AS opd,

    COUNT(*)::INTEGER AS total_tindak_lanjut,

    COUNT(*) FILTER (
        WHERE m.status = 'BELUM DITINDAKLANJUTI'
    )::INTEGER AS belum_ditindaklanjuti,

    COUNT(*) FILTER (
        WHERE m.status = 'DALAM PROSES'
    )::INTEGER AS dalam_proses,

    COUNT(*) FILTER (
        WHERE m.status = 'MENUNGGU VERIFIKASI'
    )::INTEGER AS menunggu_verifikasi,

    COUNT(*) FILTER (
        WHERE m.status = 'SELESAI'
    )::INTEGER AS dilaporkan_selesai,

    COUNT(*) FILTER (
        WHERE m.batas_waktu < CURRENT_DATE
        AND m.status <> 'SELESAI'
    )::INTEGER AS melewati_batas_waktu,

    ROUND(
        AVG(m.progres)::NUMERIC,
        2
    ) AS rata_rata_progres,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM monitoring_verifikasi v
            WHERE v.monitoring_id = m.id
              AND v.status_verifikasi = 'DISETUJUI'
        )
    )::INTEGER AS pernah_disetujui

FROM monitoring_tindak_lanjut m
GROUP BY m.opd_penanggung_jawab;

COMMIT;
