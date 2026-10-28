
import os
from pathlib import Path

import shapefile
import psycopg
from dotenv import load_dotenv
from shapely.geometry import shape, MultiPolygon
from shapely import wkb

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "batas_desa_nias_barat.shp"

load_dotenv(ROOT / ".env")

if not SOURCE.exists():
    raise FileNotFoundError(SOURCE)

password = os.environ["POSTGRES_PASSWORD"]

with shapefile.Reader(str(SOURCE), encoding="utf-8") as reader:
    # Simpan nama dan tipe kolom dari SHP
    fields = reader.fields[1:]
    names = [field[0] for field in fields]

    if "WADMKK" not in names:
        raise ValueError("Kolom WADMKK tidak ditemukan")

    if len(reader) != 105:
        raise ValueError(
            f"Jumlah polygon tidak sesuai: {len(reader)}"
        )

    # Pertahankan nilai atribut asli dalam kolom TEXT,
    # kecuali OBJECTID yang disimpan sebagai BIGINT.
    definitions = []
    for name in names:
        data_type = "BIGINT" if name == "OBJECTID" else "TEXT"
        definitions.append(f'"{name}" {data_type}')

    definitions_sql = ",\n".join(definitions)

    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname="geolake",
        user="geolake_user",
        password=password
    ) as conn:

        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")

            # Jangan menimpa tabel yang sudah ada
            cur.execute(
                f"""
                CREATE TABLE batas_desa_nias_barat (
                    {definitions_sql},
                    geom geometry(MultiPolygon, 4326)
                )
                """
            )

            columns = ", ".join(f'"{n}"' for n in names)
            placeholders = ", ".join(["%s"] * len(names))

            insert_sql = f"""
                INSERT INTO batas_desa_nias_barat
                ({columns}, geom)
                VALUES (
                    {placeholders},
                    ST_Multi(ST_GeomFromWKB(%s, 4326))
                )
            """

            count = 0

            for item in reader.iterShapeRecords():
                record = item.record.as_dict()

                if "NIAS BARAT" not in str(
                    record["WADMKK"]
                ).upper():
                    raise ValueError(
                        "Ditemukan record di luar Nias Barat"
                    )

                geom = shape(item.shape.__geo_interface__)

                if geom.is_empty:
                    raise ValueError("Geometri kosong ditemukan")

                if geom.geom_type == "Polygon":
                    geom = MultiPolygon([geom])

                if geom.geom_type != "MultiPolygon":
                    raise ValueError(
                        f"Geometri tidak didukung: {geom.geom_type}"
                    )

                values = [
                    record[name] if name == "OBJECTID"
                    else (
                        None if record[name] is None
                        else str(record[name])
                    )
                    for name in names
                ]

                cur.execute(
                    insert_sql,
                    values + [wkb.dumps(geom)]
                )

                count += 1

            cur.execute(
                """
                CREATE INDEX idx_batas_desa_nias_barat_geom
                ON batas_desa_nias_barat
                USING GIST (geom)
                """
            )

            cur.execute(
                """
                SELECT COUNT(*)
                FROM batas_desa_nias_barat
                """
            )
            total = cur.fetchone()[0]

            if total != 105:
                raise ValueError(
                    f"Validasi gagal: {total} polygon"
                )

        conn.commit()

print(f"Berhasil mengimpor {count} polygon desa")
print("Database: geolake")
print("Tabel: batas_desa_nias_barat")
print("SRID: EPSG:4326")
print("Indeks spasial: GiST")
