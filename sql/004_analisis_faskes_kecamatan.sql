CREATE OR REPLACE VIEW v_analisis_faskes_kecamatan AS
WITH wilayah AS (
    SELECT DISTINCT "WADMKC" AS kecamatan
    FROM batas_desa_nias_barat
),
rekap AS (
    SELECT
        kecamatan,
        COUNT(*) AS total_fasilitas,
        COUNT(*) FILTER (
            WHERE jenis IN (
                'Puskesmas',
                'Puskesmas Rawat Inap',
                'Puskesmas Rawat Jalan'
            )
        ) AS puskesmas,
        COUNT(*) FILTER (
            WHERE jenis IN (
                'Pustu',
                'Puskesmas Pembantu'
            )
        ) AS pustu,
        COUNT(*) FILTER (
            WHERE jenis = 'Poskesdes'
        ) AS poskesdes
    FROM v_fasilitas_kesehatan_spasial
    WHERE status_spasial = 'DALAM WILAYAH'
    GROUP BY kecamatan
)
SELECT
    w.kecamatan,
    COALESCE(r.total_fasilitas, 0) AS total_fasilitas,
    COALESCE(r.puskesmas, 0) AS puskesmas,
    COALESCE(r.pustu, 0) AS pustu,
    COALESCE(r.poskesdes, 0) AS poskesdes
FROM wilayah w
LEFT JOIN rekap r USING (kecamatan);