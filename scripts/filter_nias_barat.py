
from pathlib import Path
import shapefile
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "map" / "Batas_Wilayah_KelurahanDesa_10K_AR.shp"
OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = OUTPUT_DIR / "batas_desa_nias_barat"

count = 0
kecamatan = Counter()

with shapefile.Reader(str(SOURCE), encoding="utf-8") as reader:
    with shapefile.Writer(
        str(TARGET),
        shapeType=reader.shapeType,
        encoding="utf-8"
    ) as writer:

        # Pertahankan seluruh atribut dan tipe kolom asli
        writer.fields = reader.fields[1:]

        # Iterasi satu per satu, tidak memuat seluruh geometri
        for item in reader.iterShapeRecords():
            record = item.record

            if "NIAS BARAT" not in str(record["WADMKK"]).upper():
                continue

            writer.shape(item.shape)
            writer.record(*record)

            count += 1
            kecamatan[str(record["WADMKC"])] += 1

# Salin definisi sistem koordinat dan encoding
for ext in [".prj", ".cpg"]:
    source_file = SOURCE.with_suffix(ext)
    if source_file.exists():
        TARGET.with_suffix(ext).write_bytes(source_file.read_bytes())

print(f"Berhasil: {count} polygon desa")
print(f"Jumlah kecamatan: {len(kecamatan)}")

for nama, jumlah in sorted(kecamatan.items()):
    print(f"  {nama}: {jumlah} desa")

print(f"Output: {TARGET}.shp")
