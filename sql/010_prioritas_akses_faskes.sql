
CREATE OR REPLACE VIEW v_prioritas_akses_faskes_desa AS
WITH dasar AS (
    SELECT
        id_desa,
        desa,
        kecamatan,
        fasilitas_terdekat,
        jenis_fasilitas,
        jarak_meter,
        kategori_jarak,
        CASE
            WHEN jarak_meter IS NULL THEN NULL
            WHEN jarak_meter > 5000 THEN 1
            WHEN jarak_meter > 3000 THEN 2
            WHEN jarak_meter > 1000 THEN 3
            ELSE 4
        END AS tingkat_prioritas
    FROM v_akses_faskes_desa
),
peringkat AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            ORDER BY
                tingkat_prioritas ASC NULLS LAST,
                jarak_meter DESC NULLS LAST,
                kecamatan,
                desa,
                id_desa
        ) AS peringkat
    FROM dasar
)
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
    CASE tingkat_prioritas
        WHEN 1 THEN 'PRIORITAS PENELAAHAN 1'
        WHEN 2 THEN 'PRIORITAS PENELAAHAN 2'
        WHEN 3 THEN 'PRIORITAS PENELAAHAN 3'
        WHEN 4 THEN 'PRIORITAS PENELAAHAN 4'
        ELSE 'DATA BELUM LENGKAP'
    END AS label_prioritas
FROM peringkat;
