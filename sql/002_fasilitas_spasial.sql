
-- AKHARI GeoLake
-- Otomatisasi titik fasilitas kesehatan dan identifikasi desa

ALTER TABLE fasilitas_publik
ADD COLUMN IF NOT EXISTS kecamatan VARCHAR(100);

CREATE OR REPLACE FUNCTION update_lokasi_fasilitas()
RETURNS TRIGGER AS $$
DECLARE
    lat DOUBLE PRECISION;
    lon DOUBLE PRECISION;
    parts TEXT[];
BEGIN
    IF NEW.koordinat IS NULL OR btrim(NEW.koordinat) = '' THEN
        NEW.geom := NULL;
        NEW.desa := NULL;
        NEW.kecamatan := NULL;
        RETURN NEW;
    END IF;

    parts := string_to_array(NEW.koordinat, ',');

    IF array_length(parts, 1) <> 2 THEN
        RAISE EXCEPTION
            'Format koordinat harus latitude, longitude';
    END IF;

    lat := btrim(parts[1])::DOUBLE PRECISION;
    lon := btrim(parts[2])::DOUBLE PRECISION;

    IF NOT isfinite(lat) OR NOT isfinite(lon)
       OR lat NOT BETWEEN -90 AND 90
       OR lon NOT BETWEEN -180 AND 180 THEN
        RAISE EXCEPTION 'Koordinat tidak valid';
    END IF;

    NEW.geom := ST_SetSRID(
        ST_MakePoint(lon, lat), 4326
    );

    -- Cari desa berdasarkan posisi spasial
    SELECT b."WADMKD", b."WADMKC"
    INTO NEW.desa, NEW.kecamatan
    FROM batas_desa_nias_barat b
    WHERE ST_Covers(b.geom, NEW.geom)
    ORDER BY b."OBJECTID"
    LIMIT 1;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lokasi_fasilitas
ON fasilitas_publik;

CREATE TRIGGER trg_lokasi_fasilitas
BEFORE INSERT OR UPDATE OF koordinat
ON fasilitas_publik
FOR EACH ROW
EXECUTE FUNCTION update_lokasi_fasilitas();
