import json
import os
import re
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text


FILO_FILE = os.getenv("FILO_FILE", "/data/filo_takip_20260727_104533.xls")
HASAR_FILE = os.getenv("HASAR_FILE", "/data/Hasar Listesi.xls")
SOURCE_DATE = os.getenv("SOURCE_DATE", "2026-05-13")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL .env icinde bulunamadi")

FILO_HEADER_ROW = int(os.getenv("FILO_HEADER_ROW", "1"))
SCHEMA_FILE = os.getenv("SCHEMA_FILE", "/sql/01_create_filo_arac_master.sql")
RECREATE_TABLE_ON_IMPORT = os.getenv("RECREATE_TABLE_ON_IMPORT", "false").lower() in {
    "1", "true", "yes", "evet"
}


def normalize_plate(value):
    if pd.isna(value):
        return None
    value = str(value).strip().upper()
    value = re.sub(r"\s+", "", value)
    return value or None


def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value if value else None


def parse_int(value):
    if pd.isna(value) or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return int(float(value))
        except ValueError:
            return None

    text_value = str(value).strip()
    if not text_value:
        return None

    text_value = text_value.replace(".", "").replace(",", ".")
    try:
        return int(float(text_value))
    except ValueError:
        return None


def parse_smallint(value):
    parsed = parse_int(value)
    if parsed is None:
        return None
    if parsed < -32768 or parsed > 32767:
        return None
    return parsed


def parse_decimal(value):
    if pd.isna(value) or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text_value = str(value).strip()
    if not text_value:
        return None

    text_value = text_value.replace("TL", "").replace("₺", "").strip()
    text_value = text_value.replace(".", "").replace(",", ".")

    try:
        return float(text_value)
    except ValueError:
        return None


def parse_date(value):
    if pd.isna(value) or value == "":
        return None

    dt = pd.to_datetime(value, errors="coerce", dayfirst=True)

    if pd.isna(dt):
        return None

    return dt.date()


def parse_timestamp(value):
    if pd.isna(value) or value == "":
        return None

    dt = pd.to_datetime(value, errors="coerce", dayfirst=True)

    if pd.isna(dt):
        return None

    return dt.to_pydatetime()


def bool_from_tr(value):
    if pd.isna(value):
        return False

    text_value = str(value).strip().lower()

    return text_value in {
        "true",
        "1",
        "evet",
        "e",
        "var",
        "pert",
        "x",
        "yes",
    }


def get(row, column):
    return row[column] if column in row.index else None


def read_excel(path, header=0):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dosya bulunamadi: {path}")

    return pd.read_excel(path, header=header)


def load_hasar_summary(hasar_path):
    hasar_df = read_excel(hasar_path)

    hasar_df["plaka_norm"] = hasar_df["Plaka"].apply(normalize_plate)
    hasar_df["hasar_ts"] = hasar_df["Hasar Tarihi"].apply(parse_timestamp)

    hasar_df = hasar_df[hasar_df["plaka_norm"].notna()].copy()

    summaries = {}

    for plaka_norm, group in hasar_df.groupby("plaka_norm"):
        group_sorted = group.sort_values("hasar_ts", ascending=False)
        last = group_sorted.iloc[0]

        gider = (
            sum(parse_decimal(v) or 0 for v in group["Toplam Gider"])
            if "Toplam Gider" in group
            else 0
        )

        gelir = (
            sum(parse_decimal(v) or 0 for v in group["Toplam Gelir"])
            if "Toplam Gelir" in group
            else 0
        )

        sigorta = (
            sum(parse_decimal(v) or 0 for v in group["Sigorta Tahsilat"])
            if "Sigorta Tahsilat" in group
            else 0
        )

        pert_var = (
            any(bool_from_tr(v) for v in group["Pert"])
            if "Pert" in group
            else False
        )

        recent_records = []

        for _, r in group_sorted.head(10).iterrows():
            hasar_tarihi = parse_timestamp(get(r, "Hasar Tarihi"))

            recent_records.append(
                {
                    "hasar_no": parse_int(get(r, "Hasar No")),
                    "dosya_no": clean_text(get(r, "Dosya No")),
                    "durum": clean_text(get(r, "Durum")),
                    "hasar_tarihi": str(hasar_tarihi) if hasar_tarihi else None,
                    "hasar_sekli": clean_text(get(r, "Hasar Şekli")),
                    "hasar_durum": clean_text(get(r, "Hasar Durum")),
                    "pert": bool_from_tr(get(r, "Pert")),
                    "toplam_gider": parse_decimal(get(r, "Toplam Gider")),
                    "toplam_gelir": parse_decimal(get(r, "Toplam Gelir")),
                }
            )

        summaries[plaka_norm] = {
            "hasar_adedi": int(len(group)),
            "son_hasar_tarihi": parse_timestamp(get(last, "Hasar Tarihi")),
            "son_hasar_sekli": clean_text(get(last, "Hasar Şekli")),
            "son_hasar_durum": clean_text(get(last, "Hasar Durum")),
            "pert_var_mi": pert_var,
            "toplam_hasar_gider": gider,
            "toplam_hasar_gelir": gelir,
            "sigorta_tahsilat_toplam": sigorta,
            "hasar_ozeti": json.dumps(
                {"son_10_hasar": recent_records},
                ensure_ascii=False,
            ),
        }

    return summaries


def build_records(filo_path, hasar_map):
    filo_df = read_excel(filo_path, header=FILO_HEADER_ROW)

    records = []
    skipped = 0

    for _, row in filo_df.iterrows():
        plaka = clean_text(get(row, "Plaka"))
        plaka_norm = normalize_plate(plaka)

        if not plaka_norm:
            skipped += 1
            continue

        hasar_data = hasar_map.get(plaka_norm, {})

        fatura_tarihi = parse_date(get(row, "Fatura Tarihi"))
        siparis_tarihi = parse_date(get(row, "Sipariş Tarihi"))

        record = {
            "plaka": plaka_norm,
            "plaka_durum": clean_text(get(row, "Plaka Durum")),
            "marka": clean_text(get(row, "Marka")),
            "seri": clean_text(get(row, "Araç Tip")),
            "model": clean_text(get(row, "Versiyon")),
            "model_yili": parse_smallint(get(row, "Model")),
            "renk": clean_text(get(row, "Renk")),
            "yakit_tipi": clean_text(get(row, "Yakıt Tipi")),
            "vites_tipi": clean_text(get(row, "Vites Tipi")),
            "cekis_tipi": clean_text(get(row, "Çekiş Tipi")),

            # KM bilgisi artik sadece Filo Takip dosyasindan geliyor
            "son_km": parse_int(get(row, "Son Tespit Km")),
            "son_km_tarihi": parse_timestamp(get(row, "Km Tespit Tar")),

            # Alis fiyati ve alis tarihi
            "alis_fiyati": parse_decimal(get(row, "Revize Sip. Fiyatı")),
            "alis_tarihi": fatura_tarihi or siparis_tarihi,

            # Hasar bilgileri
            "hasar_adedi": hasar_data.get("hasar_adedi", 0),
            "son_hasar_tarihi": hasar_data.get("son_hasar_tarihi"),
            "son_hasar_sekli": hasar_data.get("son_hasar_sekli"),
            "son_hasar_durum": hasar_data.get("son_hasar_durum"),
            "pert_var_mi": hasar_data.get("pert_var_mi", False),
            "toplam_hasar_gider": hasar_data.get("toplam_hasar_gider", 0),
            "toplam_hasar_gelir": hasar_data.get("toplam_hasar_gelir", 0),
            "sigorta_tahsilat_toplam": hasar_data.get("sigorta_tahsilat_toplam", 0),
            "hasar_ozeti": hasar_data.get("hasar_ozeti"),

            "kaynak_dosya_tarihi": parse_date(SOURCE_DATE) or date.today(),
        }

        records.append(record)

    print(f"Filo takip okundu. Kayit: {len(records)}, plakasiz atlanan: {skipped}")

    return records


UPSERT_SQL = text(
    r"""
INSERT INTO public.filo_arac_master (
    plaka, plaka_durum, marka, seri, model, model_yili,
    renk, yakit_tipi, vites_tipi, cekis_tipi,
    son_km, son_km_tarihi,
    alis_fiyati, alis_tarihi,
    hasar_adedi, son_hasar_tarihi, son_hasar_sekli, son_hasar_durum, pert_var_mi,
    toplam_hasar_gider, toplam_hasar_gelir, sigorta_tahsilat_toplam, hasar_ozeti,
    kaynak_dosya_tarihi, updated_at
) VALUES (
    :plaka, :plaka_durum, :marka, :seri, :model, :model_yili,
    :renk, :yakit_tipi, :vites_tipi, :cekis_tipi,
    :son_km, :son_km_tarihi,
    :alis_fiyati, :alis_tarihi,
    :hasar_adedi, :son_hasar_tarihi, :son_hasar_sekli, :son_hasar_durum, :pert_var_mi,
    :toplam_hasar_gider, :toplam_hasar_gelir, :sigorta_tahsilat_toplam, CAST(:hasar_ozeti AS jsonb),
    :kaynak_dosya_tarihi, now()
)
ON CONFLICT (plaka) DO UPDATE SET
    plaka = EXCLUDED.plaka,
    plaka_durum = EXCLUDED.plaka_durum,
    marka = EXCLUDED.marka,
    seri = EXCLUDED.seri,
    model = EXCLUDED.model,
    model_yili = EXCLUDED.model_yili,
    renk = EXCLUDED.renk,
    yakit_tipi = EXCLUDED.yakit_tipi,
    vites_tipi = EXCLUDED.vites_tipi,
    cekis_tipi = EXCLUDED.cekis_tipi,
    son_km = EXCLUDED.son_km,
    son_km_tarihi = EXCLUDED.son_km_tarihi,
    alis_fiyati = EXCLUDED.alis_fiyati,
    alis_tarihi = EXCLUDED.alis_tarihi,
    hasar_adedi = EXCLUDED.hasar_adedi,
    son_hasar_tarihi = EXCLUDED.son_hasar_tarihi,
    son_hasar_sekli = EXCLUDED.son_hasar_sekli,
    son_hasar_durum = EXCLUDED.son_hasar_durum,
    pert_var_mi = EXCLUDED.pert_var_mi,
    toplam_hasar_gider = EXCLUDED.toplam_hasar_gider,
    toplam_hasar_gelir = EXCLUDED.toplam_hasar_gelir,
    sigorta_tahsilat_toplam = EXCLUDED.sigorta_tahsilat_toplam,
    hasar_ozeti = EXCLUDED.hasar_ozeti,
    kaynak_dosya_tarihi = EXCLUDED.kaynak_dosya_tarihi,
    updated_at = now()
"""
)


def recreate_schema_if_requested(engine):
    if not RECREATE_TABLE_ON_IMPORT:
        return

    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema SQL dosyasi bulunamadi: {SCHEMA_FILE}")

    print("Tablo semasi yeniden olusturuluyor...")

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    raw_conn = engine.raw_connection()

    try:
        cur = raw_conn.cursor()
        cur.execute(schema_sql)
        raw_conn.commit()
        cur.close()
    finally:
        raw_conn.close()


def main():
    print("Hasar listesi okunuyor...")
    hasar_map = load_hasar_summary(HASAR_FILE)
    print(f"Hasar plaka sayisi: {len(hasar_map)}")

    print("Filo takip listesi okunuyor ve master kayitlar olusturuluyor...")
    records = build_records(FILO_FILE, hasar_map)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    recreate_schema_if_requested(engine)

    if not records:
        print("Aktarilacak kayit bulunamadi.")
        return

    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, records)

        total = conn.execute(
            text("SELECT count(*) FROM public.filo_arac_master")
        ).scalar_one()

        hasarli = conn.execute(
            text("SELECT count(*) FROM public.filo_arac_master WHERE hasar_adedi > 0")
        ).scalar_one()

        km_dolu = conn.execute(
            text("SELECT count(*) FROM public.filo_arac_master WHERE son_km IS NOT NULL")
        ).scalar_one()

    print("Import tamamlandi.")
    print(f"Upsert edilen kayit: {len(records)}")
    print(f"Tablodaki toplam kayit: {total}")
    print(f"Son km dolu arac: {km_dolu}")
    print(f"Hasar bilgisi olan arac: {hasarli}")


if __name__ == "__main__":
    main()