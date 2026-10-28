CREATE OR REPLACE VIEW v_fasilitas_kesehatan_spasial AS
SELECT
    f.id,
    f.nama,
    f.jenis,
    f.koordinat,
    f.desa,
    f.kecamatan,
    f.geom,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM batas_desa_nias_barat b
            WHERE ST_Covers(b.geom, f.geom)
        ) THEN 'DALAM WILAYAH'

        WHEN EXISTS (
            SELECT 1
            FROM batas_desa_nias_barat b
            WHERE ST_DWithin(
                f.geom::geography,
                b.geom::geography,
                150
            )
        ) THEN 'PERLU VERIFIKASI'

        ELSE 'DI LUAR WILAYAH'
    END AS status_spasial
FROM fasilitas_publik f;