
-- AKHARI GeoLake
-- Modul 4.4.52
-- Rekomendasi awal akses fasilitas kesehatan desa

CREATE OR REPLACE VIEW
v_rekomendasi_akses_faskes_desa AS

SELECT
    p.peringkat,
    p.id_desa,
    p.desa,
    p.kecamatan,
    p.fasilitas_terdekat,
    p.jenis_fasilitas,
    p.jarak_meter,
    p.kategori_jarak,
    p.tingkat_prioritas,
    p.label_prioritas,

    CASE
        WHEN p.jarak_meter IS NULL THEN
            'VERIFIKASI DATA'

        WHEN p.jarak_meter > 5000 THEN
            'KAJIAN AKSES MENDESAK'

        WHEN p.jarak_meter > 3000 THEN
            'PENGUATAN AKSES'

        WHEN p.jarak_meter > 1000 THEN
            'OPTIMALISASI LAYANAN'

        ELSE
            'PEMANTAUAN RUTIN'
    END AS kategori_rekomendasi,

    CASE
        WHEN p.jarak_meter IS NULL THEN
            'Belum tersedia informasi jarak yang dapat digunakan.'

        WHEN p.jarak_meter > 5000 THEN
            'Jarak garis lurus dari titik representatif desa '
            || 'ke fasilitas kesehatan terdekat melebihi 5 km.'

        WHEN p.jarak_meter > 3000 THEN
            'Jarak garis lurus ke fasilitas kesehatan '
            || 'terdekat berada di atas 3 km hingga 5 km.'

        WHEN p.jarak_meter > 1000 THEN
            'Jarak garis lurus ke fasilitas kesehatan '
            || 'terdekat berada di atas 1 km hingga 3 km.'

        ELSE
            'Jarak garis lurus ke fasilitas kesehatan '
            || 'terdekat tidak melebihi 1 km.'
    END AS alasan_rekomendasi,

    CASE
        WHEN p.jarak_meter IS NULL THEN
            'Lengkapi dan verifikasi data koordinat '
            || 'fasilitas kesehatan serta batas desa.'

        WHEN p.jarak_meter > 5000 THEN
            'Lakukan kajian kebutuhan layanan kesehatan, '
            || 'akses jalan, waktu tempuh, sebaran penduduk, '
            || 'dan kapasitas fasilitas sebelum menentukan '
            || 'intervensi pembangunan.'

        WHEN p.jarak_meter > 3000 THEN
            'Evaluasi konektivitas transportasi dan '
            || 'jangkauan layanan kesehatan keliling, '
            || 'serta identifikasi hambatan akses.'

        WHEN p.jarak_meter > 1000 THEN
            'Evaluasi pemerataan layanan, jadwal pelayanan, '
            || 'dan akses transportasi masyarakat.'

        ELSE
            'Pantau kualitas, kapasitas, dan keberlanjutan '
            || 'layanan kesehatan yang tersedia.'
    END AS tindak_lanjut,

    CASE
        WHEN p.jarak_meter IS NULL THEN
            'Dinas Kesehatan; Bappelitbangda'

        WHEN p.jarak_meter > 3000 THEN
            'Dinas Kesehatan; Dinas PUPR; Bappelitbangda'

        ELSE
            'Dinas Kesehatan; Bappelitbangda'
    END AS opd_terkait,

    'REKOMENDASI AWAL - PERLU VALIDASI'
        AS status_rekomendasi

FROM v_prioritas_akses_faskes_desa p;
