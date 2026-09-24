"""
Merkezi yapılandırma — tüm iş kuralı ve model eşikleri tek yerde.

Buradaki her değer bir ortam değişkeniyle (.env) override edilebilir; verilmezse
aşağıdaki varsayılan kullanılır. Böylece kodu değiştirmeden .env'den ayar yapılabilir.

NEREDE NE VAR:
  - Sırlar (DB parolası, API anahtarı)     -> .env               (koda GİRMEZ)
  - Hasar düşüş oranları (parça/durum)      -> damage_config.json  (admin panelinden)
  - İş kuralı / model eşikleri (bu dosya)   -> settings.py
"""
import os


def _int(key, default):
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _float(key, default):
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _list(key, default):
    raw = os.getenv(key)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


# ── Model eğitimi ─────────────────────────────────────────────────────────────
# Bir marka+seri grubuna ÖZEL model eğitmek için gereken minimum araç sayısı.
# Altındaki gruplar genel (fallback) modele bırakılır.
# (Değiştirince modeli yeniden eğitmek gerekir: python ml/train.py)
MIN_SAMPLES_FOR_GROUP_MODEL = _int("MIN_SAMPLES_FOR_GROUP_MODEL", 10)


# ── BFL / Filo ────────────────────────────────────────────────────────────────
# Tahmin listesine dahil edilecek plaka durumları.
# Env override virgülle: BFL_ALLOWED_DURUMLAR="KSK,USK,Havuz"
BFL_ALLOWED_DURUMLAR = _list(
    "BFL_ALLOWED_DURUMLAR",
    ["KSK", "USK", "Havuz", "Tahsis", "0 km Stok"],
)

# Araç, alış tarihinden bu kadar gün sonra "satışa hazır" sayılır (valör kuralı).
BFL_MIN_HOLD_DAYS = _int("BFL_MIN_HOLD_DAYS", 185)

# araclar (ilan) tablosunda marka+seri+yıl için bu sayıdan AZ ilan varsa,
# tahmin "düşük güven" olarak işaretlenir.
BFL_MIN_COMPARABLE_LISTINGS = _int("BFL_MIN_COMPARABLE_LISTINGS", 5)


# ── Fiyatlandırma ─────────────────────────────────────────────────────────────
# B2B fiyatı = B2C (tahmini piyasa) fiyatı x bu çarpan.
B2B_FACTOR = _float("B2B_FACTOR", 0.90)



# ── Filo → araclar isim eşlemesi ──────────────────────────────────────────────
# vehicles (filo) tablosu ile araclar (eğitim) tablosu bazı marka/serileri farklı
# yazıyor. Bu yüzden bol veriyle eğitilmiş araçlar grup modelini kaçırıp genel
# modele düşüyordu. Aşağıdaki eşleme filo yazımını araclar yazımına çevirir.
# NOT: Dacia Duster ≠ Renault Duster (farklı araç) — bilerek eşlenMEDİ.

# Marka yeniden adlandırma (filo -> araclar)
FLEET_BRAND_ALIASES = {
    "mercedes": "mercedes-benz",
}

# (marka, seri) tam eşleme — marka alias UYGULANDIKTAN sonra bakılır
FLEET_MODEL_ALIASES = {
    ("bmw", "320"):            ("bmw", "3 serisi"),
    ("bmw", "520"):            ("bmw", "5 serisi"),
    ("mercedes-benz", "c"):    ("mercedes-benz", "c serisi"),
    ("mercedes-benz", "e"):    ("mercedes-benz", "e serisi"),
    ("audi", "a5"):            ("audi", "a5 a5 sedan"),
}


def _norm_name(s):
    return " ".join(str(s).strip().lower().split()) if s else s


def map_fleet_naming(marka, seri):
    """Filo (vehicles) marka/seri yazımını araclar (eğitim) yazımına çevirir.
    Eşleşme yoksa değeri (küçük harf normalize edilmiş haliyle) aynen döndürür."""
    m = _norm_name(marka)
    s = _norm_name(seri)
    if m in FLEET_BRAND_ALIASES:
        m = FLEET_BRAND_ALIASES[m]
    if (m, s) in FLEET_MODEL_ALIASES:
        m, s = FLEET_MODEL_ALIASES[(m, s)]
    return m, s