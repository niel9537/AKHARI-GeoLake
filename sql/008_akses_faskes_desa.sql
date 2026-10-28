
CREATE OR REPLACE VIEW v_akses_faskes_desa AS
WITH desa AS (
    SELECT
        "OBJECTID" AS id_desa,
        "WADMKD" AS desa,
        "WADMKC" AS kecamatan,
        ST_PointOnSurface(geom) AS titik_desa
    FROM batas_desa_nias_barat
)
SELECT
    d.id_desa,
    d.desa,
    d.kecamatan,
    f.id AS id_fasilitas_terdekat,
    f.nama AS fasilitas_terdekat,
    f.jenis AS jenis_fasilitas,
    ROUND(
        ST_Distance(
            d.titik_desa::geography,
            f.geom::geography
        )::numeric,
        2
    ) AS jarak_meter,
    CASE
        WHEN f.id IS NULL THEN 'BELUM ADA DATA'
        WHEN ST_Distance(
            d.titik_desa::geography,
            f.geom::geography
        ) <= 1000 THEN '0-1 KM'
        WHEN ST_Distance(
            d.titik_desa::geography,
            f.geom::geography
        ) <= 3000 THEN '1-3 KM'
        WHEN ST_Distance(
            d.titik_desa::geography,
            f.geom::geography
        ) <= 5000 THEN '3-5 KM'
        ELSE '>5 KM'
    END AS kategori_jarak,
    d.titik_desa AS geom
FROM desa d
LEFT JOIN LATERAL (
    SELECT id, nama, jenis, geom
    FROM fasilitas_publik
    WHERE geom IS NOT NULL
    ORDER BY geom <-> d.titik_desa, id
    LIMIT 1
) f ON TRUE;
