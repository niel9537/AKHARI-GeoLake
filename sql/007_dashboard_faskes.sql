CREATE OR REPLACE VIEW v_dashboard_faskes AS
SELECT
    COUNT(*) AS total_fasilitas,

    COUNT(*) FILTER (
        WHERE jenis IN (
            'Puskesmas',
            'Puskesmas Rawat Inap',
            'Puskesmas Rawat Jalan'
        )
    ) AS total_puskesmas,

    COUNT(*) FILTER (
        WHERE jenis IN (
            'Pustu',
            'Puskesmas Pembantu'
        )
    ) AS total_pustu,

    COUNT(*) FILTER (
        WHERE jenis = 'Poskesdes'
    ) AS total_poskesdes,

    COUNT(*) FILTER (
        WHERE status_spasial = 'DALAM WILAYAH'
    ) AS dalam_wilayah,

    COUNT(*) FILTER (
        WHERE status_spasial = 'PERLU VERIFIKASI'
    ) AS perlu_verifikasi,

    COUNT(*) FILTER (
        WHERE status_spasial = 'DI LUAR WILAYAH'
    ) AS di_luar_wilayah,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE status_spasial = 'DALAM WILAYAH'
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS persentase_terpetakan

FROM v_fasilitas_kesehatan_spasial;