"""
Dışa açık tahmin API'si — /api/v1

Diğer uygulamaların (fleet paneli, mobil, 3. parti) çağırabileceği, STATELESS ve
API-key korumalı fiyat tahmini uç noktası. Hem yeni İngilizce `vehicles` alan
adlarını (brand, vehicle_type, version, last_odometer_km...) hem eski Türkçe
alanları (marka, seri, model, km...) kabul eder.

Auth: her istekte  X-API-Key: <PREDICT_API_KEY>  header'ı beklenir.
Session'a / QueryHistory'ye yazmaz (dahili /api/predict onu yapmaya devam eder).
"""

import os
from datetime import date, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify

from ml.predictor import get_predictor

from settings import B2B_FACTOR, BFL_MIN_HOLD_DAYS, map_fleet_naming   # merkezi config (settings.py)

predict_api_bp = Blueprint("predict_api", __name__)

# ── Auth ──────────────────────────────────────────────────────────────────────
def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("PREDICT_API_KEY", "")
        provided = request.headers.get("X-API-Key", "")
        if not expected:
            # Anahtar tanımlı değilse, yanlışlıkla korumasız açılmasın diye reddet.
            return jsonify({"error": "API anahtarı sunucuda yapılandırılmamış"}), 503
        if provided != expected:
            return jsonify({"error": "Geçersiz veya eksik API anahtarı"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ── Alan adı normalizasyonu ───────────────────────────────────────────────────
# İngilizce (vehicles şeması)  →  tahmin motorunun beklediği anahtar
FIELD_ALIASES = {
    "brand":            "marka",
    "vehicle_type":     "seri",
    "version":          "model",
    "model_year":       "model_year",
    "last_odometer_km": "km",
    "odometer_km":      "km",
    "fuel_type":        "fueloil",
    "transmission":     "gear",
    "body_type":        "car_type",
    "purchase_price":   "purchase_price",
    "purchase_invoice_date": "purchase_invoice_date",
    # Türkçe eşanlamlılar
    "model_yili":       "model_year",
    "yakit_tipi":       "fueloil",
    "vites_tipi":       "gear",
    "son_km":           "km",
    "alis_fiyati":      "purchase_price",
    "alis_tarihi":      "purchase_invoice_date",
}

_TITLE_CASE_FIELDS = {"marka", "seri", "fueloil", "gear"}


def _title(s):
    return str(s).strip().title() if s not in (None, "") else s


def _to_float(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) else float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v):
    f = _to_float(v)
    return int(f) if f is not None else None


def normalize_payload(raw: dict) -> dict:
    """
    Gelen JSON'u (İngilizce veya Türkçe alan adlarıyla) tahmin motorunun
    beklediği forma çevirir. Bilinmeyen alanlar aynen taşınır.
    """
    out = {}
    for k, v in raw.items():
        key = FIELD_ALIASES.get(k, k)
        out[key] = v

    # Tip düzeltmeleri
    if "model_year" in out:
        out["model_year"] = _to_int(out.get("model_year"))
    if "km" in out:
        out["km"] = _to_int(out.get("km")) or 0

    # Title-case (model motoru büyük/küçük harfe duyarlı)
    if out.get("marka"):
        out["marka"], out["seri"] = map_fleet_naming(out.get("marka"), out.get("seri"))

    # Title-case (model motoru büyük/küçük harfe duyarlı)
    for f in _TITLE_CASE_FIELDS:
        if out.get(f):
            out[f] = _title(out[f])

    # BFL mantığıyla tutarlı: dış tahminde hasar dikkate alınmaz
    out.setdefault("damage_registered", False)
    return out


# ── Valör hesabı (BFL ile birebir aynı mantık) ────────────────────────────────
def _calc_valor(tahmini_satis: float, annual_rate_pct: float, alis_tarihi_iso: str) -> dict:
    result = {
        "alis_tarihi":          alis_tarihi_iso,
        "min_hold_days":        BFL_MIN_HOLD_DAYS,
        "en_erken_satis":       None,
        "kalan_gun":            None,
        "satilabilir":          False,
        "valorlu":              False,
        "bugunku_fiyat":        round(tahmini_satis, -3),
        "hedef_satis_fiyati":   None,
        "valorlu_bugun_fiyati": None,
        "max_indirim_tl":       0,
        "max_indirim_pct":      0,
    }
    if not alis_tarihi_iso:
        result["satilabilir"] = True
        return result
    try:
        alis = date.fromisoformat(str(alis_tarihi_iso)[:10])
    except Exception:
        result["satilabilir"] = True
        return result

    bugun = date.today()
    en_erken = alis + timedelta(days=BFL_MIN_HOLD_DAYS)
    kalan_gun = (en_erken - bugun).days
    result["en_erken_satis"] = en_erken.isoformat()
    result["kalan_gun"] = kalan_gun

    if kalan_gun <= 0:
        result["satilabilir"] = True
        return result

    result["valorlu"] = True
    daily_rate = (annual_rate_pct / 100.0) / 365.0
    hedef = tahmini_satis * ((1 + daily_rate) ** kalan_gun)
    valorlu_bugun = tahmini_satis
    max_indirim = hedef - valorlu_bugun

    result["hedef_satis_fiyati"]   = round(hedef, -3)
    result["valorlu_bugun_fiyati"] = round(valorlu_bugun, -3)
    result["max_indirim_tl"]       = round(max_indirim, -3)
    result["max_indirim_pct"]      = round((max_indirim / hedef * 100) if hedef else 0, 2)
    return result


# ── Uç nokta ──────────────────────────────────────────────────────────────────
@predict_api_bp.route("/predict", methods=["POST"])
@require_api_key
def v1_predict():
    """
    Araç bilgileriyle fiyat tahmini (dışa açık, stateless).

    Body (İngilizce veya Türkçe alan adları):
      {
        "brand": "Renault", "vehicle_type": "Megane", "version": "1.5 dCi Touch",
        "model_year": 2021, "last_odometer_km": 78000,
        "fuel_type": "Dizel", "transmission": "Otomatik",
        "purchase_price": 850000,            # opsiyonel → kâr/valör açılır
        "purchase_invoice_date": "2025-03-15", # opsiyonel → valör için
        "annual_rate_pct": 45                 # opsiyonel → valör için
      }

    Dönüş: predicted_price, price_lower/upper, confidence_pct, model_group,
           (alış bilgisi verilirse) b2c/b2b fiyat + kâr, (faiz verilirse) valor.
    """
    raw = request.get_json(silent=True)
    if not raw:
        return jsonify({"error": "JSON body gerekli"}), 400

    predictor = get_predictor()
    if not predictor.is_loaded():
        return jsonify({"error": "Model henüz eğitilmemiş"}), 503

    data = normalize_payload(raw)

    # Zorunlu minimum alanlar
    if not data.get("marka"):
        return jsonify({"error": "En az marka (brand) gerekli"}), 400

    try:
        result = predictor.predict(data)
    except Exception as e:
        return jsonify({"error": f"Tahmin hatası: {str(e)}"}), 500

    b2c = result["predicted_price"]
    resp = {
        "success": True,
        "predicted_price": round(b2c, -3),
        "price_lower": result["price_lower"],
        "price_upper": result["price_upper"],
        "confidence_pct": result.get("confidence_pct"),
        "model_group": result.get("model_group", "genel"),
        "input": {
            "marka": data.get("marka"), "seri": data.get("seri"),
            "model": data.get("model"), "model_year": data.get("model_year"),
            "km": data.get("km"), "fueloil": data.get("fueloil"),
            "gear": data.get("gear"),
        },
    }

    # Alış fiyatı verildiyse B2C/B2B fiyat + kâr
    alis = _to_float(data.get("purchase_price"))
    if alis:
        b2b = b2c * B2B_FACTOR
        resp["b2c_fiyat"] = round(b2c, -3)
        resp["b2b_fiyat"] = round(b2b, -3)
        resp["alis_fiyati"] = alis
        resp["b2c_kar"] = round(b2c - alis, -3)
        resp["b2c_kar_pct"] = round((b2c - alis) / alis * 100, 1)
        resp["b2b_kar"] = round(b2b - alis, -3)
        resp["b2b_kar_pct"] = round((b2b - alis) / alis * 100, 1)

    # Faiz verildiyse valör
    annual_rate = _to_float(data.get("annual_rate_pct")) or 0
    if annual_rate > 0:
        resp["valor"] = _calc_valor(b2c, annual_rate, data.get("purchase_invoice_date"))
        resp["annual_rate_pct"] = annual_rate

    return jsonify(resp)


@predict_api_bp.route("/health", methods=["GET"])
def v1_health():
    """Basit sağlık kontrolü (auth gerektirmez)."""
    predictor = get_predictor()
    return jsonify({"status": "ok", "model_loaded": predictor.is_loaded()}), 200