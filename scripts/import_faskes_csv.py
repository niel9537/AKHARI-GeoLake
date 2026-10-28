"""Import manually verified health facilities into AKHARI GeoLake PostGIS.
Run from repository root: python scripts/import_faskes_csv.py
Dependencies: pip install 'psycopg[binary]' python-dotenv
"""
import csv
import math
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CSV_FILE = ROOT / 'data' / 'input' / 'fasilitas_kesehatan.csv'
load_dotenv(ROOT / '.env')
ALLOWED_TYPES = {'Rumah Sakit', 'Puskesmas', 'Pustu', 'Poskesdes', 'Posyandu', 'Polindes', 'Klinik', 'Pos Kesehatan', 'Puskesmas Pembantu',
'Puskesmas Rawat Inap','Puskesmas Rawat Jalan'}


def parse_coordinates(raw: str):
    parts = raw.split(',')
    if len(parts) != 2:
        raise ValueError('koordinat harus satu sel berformat latitude, longitude')
    lat, lon = (float(part.strip()) for part in parts)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('latitude/longitude di luar rentang valid')
    return lat, lon


def main():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f'File CSV belum ada: {CSV_FILE}')

    records = []
    errors = []
    seen = set()
    with CSV_FILE.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not {'nama', 'jenis', 'koordinat'}.issubset(reader.fieldnames):
            raise ValueError('Header wajib: nama,jenis,koordinat')
        for line, row in enumerate(reader, start=2):
            if not any((v or '').strip() for v in row.values() if isinstance(v, str)):
                continue
            try:
                nama = (row['nama'] or '').strip()
                jenis = (row['jenis'] or '').strip()
                raw_coord = (row['koordinat'] or '').strip()
                if not nama or len(nama) > 150:
                    raise ValueError('nama wajib dan maksimal 150 karakter')
                if jenis not in ALLOWED_TYPES:
                    raise ValueError(f'jenis tidak dikenal: {jenis!r}; pilih salah satu {sorted(ALLOWED_TYPES)}')
                lat, lon = parse_coordinates(raw_coord)
                key = (nama.casefold(), jenis.casefold(), round(lat, 7), round(lon, 7))
                if key in seen:
                    raise ValueError('duplikat dalam CSV')
                seen.add(key)
                records.append((nama, jenis, f'{lat:.8f}, {lon:.8f}', lat, lon))
            except (ValueError, TypeError) as exc:
                errors.append(f'Baris {line}: {exc}')

    if errors:
        print('Impor dibatalkan: ada baris yang tidak valid. Tidak ada data disimpan.')
        print('\n'.join(errors[:30]))
        if len(errors) > 30:
            print(f'... dan {len(errors)-30} kesalahan lain')
        return
    if not records:
        print('CSV belum berisi fasilitas. Isi data riil terlebih dahulu; tidak ada perubahan database.')
        return

    password = os.getenv('POSTGRES_PASSWORD')
    if not password:
        raise RuntimeError('POSTGRES_PASSWORD tidak ditemukan di .env')

    inserted = skipped = unmatched = 0
    with psycopg.connect(host='127.0.0.1', port=5433, dbname='geolake', user='geolake_user', password=password) as conn:
        with conn.cursor() as cur:
            for nama, jenis, coord, lat, lon in records:
                cur.execute('''
                    SELECT 1 FROM fasilitas_publik
                    WHERE lower(btrim(nama)) = lower(%s)
                      AND lower(btrim(jenis)) = lower(%s)
                      AND geom IS NOT NULL
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 1)
                    LIMIT 1
                ''', (nama, jenis, lon, lat))
                if cur.fetchone():
                    skipped += 1
                    continue
                cur.execute('''
                    INSERT INTO fasilitas_publik (nama, jenis, koordinat)
                    VALUES (%s, %s, %s)
                    RETURNING desa, kecamatan
                ''', (nama, jenis, coord))
                desa, kecamatan = cur.fetchone()
                inserted += 1
                if not desa or not kecamatan:
                    unmatched += 1
                    print(f'PERIKSA: {nama} tidak cocok dengan polygon desa')
        # Context manager commits only when all operations succeed.
    print(f'Selesai: {inserted} ditambahkan, {skipped} dilewati (duplikat), {unmatched} perlu verifikasi lokasi.')
    print('Buka kembali layer fasilitas_publik di RustGIS untuk melihat titiknya.')


if __name__ == '__main__':
    main()
