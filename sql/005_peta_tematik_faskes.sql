CREATE OR REPLACE VIEW v_peta_faskes_kecamatan AS
WITH wilayah AS (
    SELECT
        "WADMKC" AS kecamatan,
        ST_Multi(
            ST_CollectionExtract(
                ST_Union(geom), 3
            )
        )::geometry(MultiPolygon, 4326) AS geom
    FROM batas_desa_nias_barat
    GROUP BY "WADMKC"
)
SELECT
    ROW_NUMBER() OVER (ORDER BY w.kecamatan)::integer AS id,
    w.kecamatan,
    a.total_fasilitas,
    a.puskesmas,
    a.pustu,
    a.poskesdes,
    w.geom
FROM wilayah w
JOIN v_analisis_faskes_kecamatan a
    ON a.kecamatan = w.kecamatan;