CREATE OR REPLACE VIEW v_klasifikasi_faskes_kecamatan AS
SELECT
    id,
    kecamatan,
    total_fasilitas,
    puskesmas,
    pustu,
    poskesdes,
    CASE
        WHEN total_fasilitas <= 2 THEN 'RENDAH'
        WHEN total_fasilitas <= 4 THEN 'SEDANG'
        ELSE 'TINGGI'
    END AS kelas_fasilitas,
    CASE
        WHEN total_fasilitas <= 2 THEN '#FDE68A'
        WHEN total_fasilitas <= 4 THEN '#F59E0B'
        ELSE '#B45309'
    END AS warna_hex,
    geom
FROM v_peta_faskes_kecamatan;