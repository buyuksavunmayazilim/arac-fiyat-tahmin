"""
Ortak 3 katmanlı tahmin çözümleyici.

Katmanlar:
  trim > 0 (Mercedes/BMW gibi sayısal donanım kodlu araç):
    1) araclar'da tam-trim medyanı (önce aynı yıl, yoksa tüm yıllar) >= eşik  -> medyan
    2) grup ML modeli varsa                                                    -> ML
    3) hiçbiri yoksa                                                           -> veri yetersiz
  trim = 0 (Renault/Clio gibi donanımı isimle belirtilen "std" araç):
    1) grup ML modeli varsa                                                    -> ML
    2) tier segment medyanı >= eşik                                            -> medyan
    3) hiçbiri yoksa                                                           -> veri yetersiz

Genel (fallback) model bu çözümde KULLANILMAZ.
Dönen dict her zaman şu alanları içerir:
  predicted_price (None olabilir), price_lower, price_upper, confidence_pct,
  shap_values, model_group, prediction_source, benzer_ilan_sayisi,
  dusuk_guven, guven_sebebi, insufficient_data
prediction_source: "group_model" | "trim_median" | "segment_median" | "none"
"""

from statistics import median

from app import db
from app.models import Vehicle
from app.models.models import _parse_price
from ml.predictor import (
    get_predictor, _group_key, _tier, _extract_version_features,
)
from settings import MEDIAN_KM_MIN_LISTINGS, MEDIAN_MIN_LISTINGS, MEDIAN_CONFIDENT_LISTINGS


def _trim_of(model):
    _, trim, _, _, _ = _extract_version_features(model)
    return trim


# km bandları (alt, üst) — araç km'sine göre en dar uygun banttan başlanır
_KM_BANDS = [(0, 15000), (0, 30000), (0, 60000), (0, 10**9)]

def _parse_int_safe(v):
    try:
        return int(str(v).replace(".", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _in_band(kmv, lo, hi):
    """Aracın km'si bu bandın kapsadığı aralıkta mı (aracı kendi bandında değerlemek için)."""
    return lo <= kmv < hi

def _median_price(marka, seri, model, year=None, by_trim=True, km=None):
    """araclar'da eşleşen ilanların (medyan, adet, alt, üst).
    km verilirse, aracın km'sine yakın banttan (yeterli ilan varsa) medyan alınır."""
    if not marka:
        return None, 0, None, None
    try:
        q = Vehicle.query.filter(
            Vehicle.marka.ilike(marka),
            Vehicle.price.isnot(None), Vehicle.price != "",
        )
        if seri:
            q = q.filter(Vehicle.seri.ilike(seri))
        if year:
            q = q.filter(Vehicle.model_year == str(year))
        target_trim = _trim_of(model) if by_trim else None
        target_tier = _tier(model, marka)

        # (fiyat, km) çiftlerini topla
        pairs = []
        for v in q.all():
            if by_trim:
                if _trim_of(v.model) != target_trim:
                    continue
            else:
                if _tier(v.model, marka) != target_tier:
                    continue
            pr = _parse_price(v.price)
            if not pr:
                continue
            vk = _parse_int_safe(v.km)
            pairs.append((pr, vk))

        if not pairs:
            return None, 0, None, None

        # km bandı uygula (km biliniyorsa ve yeterli ilan varsa)
        chosen = [pr for pr, _ in pairs]   # varsayılan: tüm km
        if km is not None:
            try:
                kmv = int(km)
            except (TypeError, ValueError):
                kmv = None
            if kmv is not None:
                for lo, hi in _KM_BANDS:
                    band = [pr for pr, vk in pairs if vk is not None and lo <= vk < hi and _in_band(kmv, lo, hi)]
                    if len(band) >= MEDIAN_KM_MIN_LISTINGS:
                        chosen = band
                        break

        chosen.sort()
        n = len(chosen)
        med = round(median(chosen), -3)
        return med, n, round(chosen[0], -3), round(chosen[-1], -3)
    except Exception:
        db.session.rollback()
        return None, 0, None, None

def _median_result(gkey, price, n, lo, hi, source):
    dusuk = n < MEDIAN_CONFIDENT_LISTINGS
    return {
        "predicted_price":    price,
        "price_lower":        lo if lo is not None else round(price * 0.90, -3),
        "price_upper":        hi if hi is not None else round(price * 1.10, -3),
        "confidence_pct":     None,
        "shap_values":        [],
        "model_group":        gkey,
        "prediction_source":  source,
        "benzer_ilan_sayisi": n,
        "insufficient_data":  False,
        "dusuk_guven":        dusuk,
        "guven_sebebi":       (f"Segment ortalaması ({n} benzer ilan)"
                               + (" — az veri" if dusuk else "")),
    }


def _insufficient_result(gkey):
    return {
        "predicted_price":    None,
        "price_lower":        None,
        "price_upper":        None,
        "confidence_pct":     None,
        "shap_values":        [],
        "model_group":        gkey,
        "prediction_source":  "none",
        "benzer_ilan_sayisi": 0,
        "insufficient_data":  True,
        "dusuk_guven":        True,
        "guven_sebebi":       "Yeterli veri yok — tahmin üretilemedi",
    }


def resolve_prediction(input_dict: dict) -> dict:
    """3 katmanlı fiyat çözümü. input_dict, predictor'ın beklediği normalize girdi."""
    predictor = get_predictor()
    marka = input_dict.get("marka")
    seri  = input_dict.get("seri")
    model = input_dict.get("model")
    year  = input_dict.get("model_year")

    gkey = _group_key(marka, seri, model)
    has_group = gkey in getattr(predictor, "group_models", {})
    # trim mantığı sadece tier markalarında (Mercedes/BMW) geçerli
    trim = _trim_of(model) if _tier(model, marka) != "std" else 0

    def ml_result():
        # has_group True olduğundan predictor grup modelini kullanır (genel modele düşmez)
        r = predictor.predict(input_dict)
        r["prediction_source"]  = "group_model"
        r["insufficient_data"]  = False
        r["dusuk_guven"]        = False
        r["guven_sebebi"]       = None
        r["benzer_ilan_sayisi"] = None
        return r

    if trim > 0:
        _km = input_dict.get("km")
        # 1) Aynı yıl trim medyanı — 1 ilan bile olsa (aynı yıl en temsili sinyal)
        med, n, lo, hi = _median_price(marka, seri, model, year, by_trim=True, km=_km)
        if med is not None and n >= 1:
            return _median_result(gkey, med, n, lo, hi, "trim_median")
        # 2) Yıl yoksa tüm-yıl trim medyanı (>= eşik)
        med, n, lo, hi = _median_price(marka, seri, model, None, by_trim=True, km=_km)
        if med is not None and n >= MEDIAN_MIN_LISTINGS:
            return _median_result(gkey, med, n, lo, hi, "trim_median")
        # 3) Grup ML
        if has_group:
            return ml_result()
        # 4) Veri yetersiz
        return _insufficient_result(gkey)
    else:
        # 1) Grup ML
        if has_group:
            return ml_result()
        # 2) Tier segment medyanı
        med, n, lo, hi = _median_price(marka, seri, model, None, by_trim=False)
        if med is not None and n >= MEDIAN_MIN_LISTINGS:
            return _median_result(gkey, med, n, lo, hi, "segment_median")
        # 3) Veri yetersiz
        return _insufficient_result(gkey)