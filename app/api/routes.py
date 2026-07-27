"""
Flask API Blueprint — tüm JSON endpoint'leri
"""

import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session
from sqlalchemy import func, desc, and_, cast, Numeric, Float, text
import numpy as np

from app import db
from app.models import Vehicle, PriceHistory, QueryHistory, ModelMetadata, FiloArac
from ml.predictor import get_predictor

api_bp = Blueprint("api", __name__)

@api_bp.route("/health", methods=["GET"])
def health():
    """Container healthcheck endpoint'i — DB'ye dokunmaz, hızlı yanıt verir."""
    return jsonify({"status": "ok"}), 200

def price_to_numeric(col):
    """
    "2.175.000 TL" → numeric. Boş/geçersiz değerler NULL olur (cast hatası vermez).
    1) Sadece rakam, nokta, virgül bırak (regexp ile harf/boşluk/TL temizle)
    2) Binlik noktayı sil, virgülü noktaya çevir
    3) Boş kalırsa NULL yap
    4) NUMERIC'e cast et
    """
    from sqlalchemy import func, cast, Numeric
    # Sadece rakam, nokta, virgül kalsın
    digits_only = func.regexp_replace(col, r'[^0-9.,]', '', 'g')
    # Binlik noktayı sil, virgülü noktaya çevir
    cleaned = func.replace(func.replace(digits_only, '.', ''), ',', '.')
    # Boş string → NULL (cast hatası önlenir)
    safe = func.nullif(cleaned, '')
    return cast(safe, Numeric)


def get_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def find_similar_sql(data: dict, predicted_price: float, top_n: int = 5) -> list:
    """
    Marka/seri/model öncelikli SQL tabanlı benzer ilan arama.
    """
    from app.models.models import _parse_price

    marka    = data.get("marka")
    seri     = data.get("seri")
    model    = data.get("model")
    car_type = data.get("car_type")
    fueloil  = data.get("fueloil")
    gear     = data.get("gear")
    model_year = data.get("model_year")

    if not marka:
        return []

    results = []
    seen_nos = set()
    price_low  = predicted_price * 0.60
    price_high = predicted_price * 1.40

    def run_query(q):
        try:
            vehicles = q.limit(top_n * 3).all()
        except Exception:
            db.session.rollback()
            return []
        out = []
        for v in vehicles:
            if v.no in seen_nos:
                continue
            parsed = _parse_price(v.price)
            if not parsed or parsed < price_low or parsed > price_high:
                continue
            price_diff_pct = abs(parsed - predicted_price) / max(predicted_price, 1)
            score = max(0.0, 1.0 - price_diff_pct)
            if model_year and str(v.model_year) == str(model_year): score += 0.05
            if fueloil and v.fueloil == fueloil:   score += 0.03
            if gear    and v.gear    == gear:       score += 0.02
            score = min(round(score, 4), 0.99)
            vd = v.to_dict()
            vd["similarity_score"] = score
            out.append(vd)
            seen_nos.add(v.no)
        out.sort(key=lambda x: x["similarity_score"], reverse=True)
        return out

    try:
        # 1. Aynı marka + seri + model + kasa tipi
        if len(results) < top_n and seri and model and car_type:
            q = Vehicle.query.filter(
                Vehicle.marka == marka, Vehicle.seri == seri,
                Vehicle.model == model, Vehicle.car_type == car_type,
                Vehicle.price.isnot(None), Vehicle.price != ''
            )
            results.extend(run_query(q))

        # 2. Aynı marka + seri + model
        if len(results) < top_n and seri and model:
            q = Vehicle.query.filter(
                Vehicle.marka == marka, Vehicle.seri == seri,
                Vehicle.model == model,
                Vehicle.price.isnot(None), Vehicle.price != ''
            )
            results.extend(run_query(q))

        # 3. Aynı marka + seri
        if len(results) < top_n and seri:
            q = Vehicle.query.filter(
                Vehicle.marka == marka, Vehicle.seri == seri,
                Vehicle.price.isnot(None), Vehicle.price != ''
            )
            results.extend(run_query(q))

        # 4. Aynı marka
        if len(results) < top_n:
            q = Vehicle.query.filter(
                Vehicle.marka == marka,
                Vehicle.price.isnot(None), Vehicle.price != ''
            )
            results.extend(run_query(q))

    except Exception as e:
        db.session.rollback()
        return []

    seen = set()
    unique = []
    for r in results:
        if r["no"] not in seen:
            seen.add(r["no"])
            unique.append(r)
    unique.sort(key=lambda x: x["similarity_score"], reverse=True)
    return unique[:top_n]


# ── /api/predict ──────────────────────────────────────────────────────────────

@api_bp.route("/predict", methods=["POST"])
def predict():
    """
    Araç fiyat tahmini.
    Body: {marka, seri, model, model_year, fueloil, gear, km, ...}
    Döndürür: {predicted_price, price_lower, price_upper, shap_values, similar_vehicles}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body gerekli"}), 400

    predictor = get_predictor()
    if not predictor.is_loaded():
        return jsonify({"error": "Model henüz eğitilmemiş. Lütfen önce modeli eğitin."}), 503

    try:
        # Tahmin
        result = predictor.predict(data)

        # Benzer araçlar — SQL tabanlı, marka/seri/model öncelikli
        similar_vehicles = find_similar_sql(data, result["predicted_price"], top_n=5)

        # Hasar etkisi — sadece damage_registered=True checkbox'ından gelince
        damage_effect = None
        dmg_raw = data.get("damage_registered", False)
        is_heavy = dmg_raw if isinstance(dmg_raw, bool) else str(dmg_raw).lower() in ("true","1")
        if is_heavy:
            damage_effect = predictor.damage_counterfactual(data)

        # Sorgu geçmişine kaydet
        active_meta = ModelMetadata.query.filter_by(is_active=True).first()
        query_record = QueryHistory(
            session_id=get_session_id(),
            marka=data.get("marka"),
            seri=data.get("seri"),
            model=data.get("model"),
            model_year=data.get("model_year"),
            fueloil=data.get("fueloil"),
            gear=data.get("gear"),
            km=data.get("km"),
            car_type=data.get("car_type"),
            damage_registered=data.get("damage_registered", False),
            predicted_price=result["predicted_price"],
            price_lower=result["price_lower"],
            price_upper=result["price_upper"],
            model_version=active_meta.version if active_meta else "unknown",
        )
        db.session.add(query_record)
        db.session.commit()

        return jsonify({
            "success": True,
            "query_id": query_record.id,
            "predicted_price": result["predicted_price"],
            "price_lower": result["price_lower"],
            "price_upper": result["price_upper"],
            "confidence_pct": result["confidence_pct"],
            "shap_values": result["shap_values"],
            "similar_vehicles": similar_vehicles,
            "damage_effect": damage_effect,
            "model_group": result.get("model_group", "genel"),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ── /api/similar ──────────────────────────────────────────────────────────────

@api_bp.route("/similar", methods=["POST"])
def similar():
    """Benzer araçları SQL ile getirir."""
    data = request.get_json()
    predicted_price = data.pop("predicted_price", None)
    if not predicted_price:
        predictor = get_predictor()
        if predictor.is_loaded():
            result = predictor.predict(data)
            predicted_price = result["predicted_price"]
        else:
            predicted_price = 1000000
    results = find_similar_sql(data, float(predicted_price), top_n=5)
    return jsonify({"vehicles": results})


# ── /api/history ──────────────────────────────────────────────────────────────

@api_bp.route("/history", methods=["GET"])
def history():
    """Kullanıcının geçmiş sorgularını döndürür."""
    session_id = get_session_id()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    queries = (
        QueryHistory.query
        .filter_by(session_id=session_id)
        .order_by(desc(QueryHistory.created_at))
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "queries": [q.to_dict() for q in queries.items],
        "total": queries.total,
        "page": page,
        "pages": queries.pages,
    })


# ── /api/search ───────────────────────────────────────────────────────────────

@api_bp.route("/search", methods=["GET"])
def search():
    """Araç filtreleme ve arama."""
    marka = request.args.get("marka")
    model = request.args.get("model")
    model_year_min = request.args.get("year_min", type=int)
    model_year_max = request.args.get("year_max", type=int)
    km_max = request.args.get("km_max", type=int)
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    fueloil = request.args.get("fueloil")
    page = request.args.get("page", 1, type=int)

    q = Vehicle.query
    if marka:
        q = q.filter(Vehicle.marka.ilike(f"%{marka}%"))
    if model:
        q = q.filter(Vehicle.model.ilike(f"%{model}%"))
    if model_year_min:
        q = q.filter(Vehicle.model_year >= model_year_min)
    if model_year_max:
        q = q.filter(Vehicle.model_year <= model_year_max)
    if km_max:
        q = q.filter(Vehicle.km <= km_max)
    if price_min:
        q = q.filter(price_to_numeric(Vehicle.price) >= price_min)
    if price_max:
        q = q.filter(price_to_numeric(Vehicle.price) <= price_max)
    if fueloil:
        q = q.filter(Vehicle.fueloil == fueloil)

    results = q.order_by(desc(Vehicle.ilan_tarihi)).paginate(page=page, per_page=20)
    return jsonify({
        "vehicles": [v.to_dict() for v in results.items],
        "total": results.total,
        "page": page,
        "pages": results.pages,
    })


# ── /api/compare ──────────────────────────────────────────────────────────────

@api_bp.route("/compare", methods=["POST"])
def compare():
    """İki araç karşılaştırması — hem DB ilanları hem de kullanıcı girişi."""
    data = request.get_json()
    vehicles_data = data.get("vehicles", [])
    if len(vehicles_data) != 2:
        return jsonify({"error": "Tam olarak 2 araç gerekli"}), 400

    predictor = get_predictor()
    results = []
    for v in vehicles_data:
        pred = predictor.predict(v)
        results.append({
            "input": v,
            "predicted_price": pred["predicted_price"],
            "price_lower": pred["price_lower"],
            "price_upper": pred["price_upper"],
            "shap_values": pred["shap_values"],
        })
    return jsonify({"comparison": results})


# ── /api/analytics ────────────────────────────────────────────────────────────

@api_bp.route("/analytics/price-trend", methods=["GET"])
def price_trend():
    """
    Belirli bir model için fiyat trendi.
    Params: marka, seri, model, model_year (opsiyonel)
    """
    marka = request.args.get("marka")
    seri  = request.args.get("seri")
    model_name = request.args.get("model")
    model_year = request.args.get("model_year", type=int)
    days = request.args.get("days", 90, type=int)

    cutoff = datetime.utcnow() - timedelta(days=days)

    # İlan no'larını bul
    q = Vehicle.query
    if marka:
        q = q.filter(Vehicle.marka == marka)
    if seri:
        q = q.filter(Vehicle.seri == seri)
    if model_name:
        q = q.filter(Vehicle.model == model_name)
    if model_year:
        q = q.filter(Vehicle.model_year == model_year)

    nos = [v.no for v in q.all()]
    if not nos:
        return jsonify({"trend": []})

    # Günlük ortalama fiyat
    trend = (
        db.session.query(
            func.date(PriceHistory.create_date).label("date"),
            func.avg(price_to_numeric(PriceHistory.price)).label("avg_price"),
            func.min(price_to_numeric(PriceHistory.price)).label("min_price"),
            func.max(price_to_numeric(PriceHistory.price)).label("max_price"),
            func.count(PriceHistory.id).label("count"),
        )
        .filter(
            PriceHistory.no.in_(nos),
            PriceHistory.create_date >= cutoff
        )
        .group_by(func.date(PriceHistory.create_date))
        .order_by(func.date(PriceHistory.create_date))
        .all()
    )

    return jsonify({
        "trend": [
            {
                "date": str(t.date),
                "avg_price": float(t.avg_price),
                "min_price": float(t.min_price),
                "max_price": float(t.max_price),
                "count": t.count,
            }
            for t in trend
        ]
    })


@api_bp.route("/analytics/market-heatmap", methods=["GET"])
def market_heatmap():
    """Marka × yıl medyan fiyat ısı haritası verisi."""
    rows = (
        db.session.query(
            Vehicle.marka,
            Vehicle.model_year,
            func.percentile_cont(0.5).within_group(
                price_to_numeric(Vehicle.price)
            ).label("median_price"),
            func.count(Vehicle.id).label("count"),
        )
        .filter(
            Vehicle.price.isnot(None),
            Vehicle.price != '',
            Vehicle.model_year >= 2015
        )
        .group_by(Vehicle.marka, Vehicle.model_year)
        .having(func.count(Vehicle.id) >= 5)
        .order_by(Vehicle.marka, Vehicle.model_year)
        .all()
    )
    return jsonify({
        "heatmap": [
            {"marka": r.marka, "year": r.model_year,
             "median_price": float(r.median_price), "count": r.count}
            for r in rows
        ]
    })


@api_bp.route("/analytics/stats", methods=["GET"])
def stats():
    """Genel veritabanı istatistikleri."""
    total = Vehicle.query.count()
    avg_price = db.session.query(
        func.avg(price_to_numeric(Vehicle.price))
    ).filter(
        Vehicle.price.isnot(None),
        Vehicle.price != ''
    ).scalar()
    brands = db.session.query(Vehicle.marka, func.count(Vehicle.id)).group_by(
        Vehicle.marka).order_by(desc(func.count(Vehicle.id))).limit(10).all()
    active_model = ModelMetadata.query.filter_by(is_active=True).first()

    return jsonify({
        "total_vehicles": total,
        "avg_price": float(avg_price) if avg_price else 0,
        "top_brands": [{"marka": b[0], "count": b[1]} for b in brands],
        "active_model": active_model.version if active_model else None,
        "model_r2": active_model.r2_score if active_model else None,
    })


# ── /api/vehicle/<no>/price-history ──────────────────────────────────────────

@api_bp.route("/vehicle/<string:no>/price-history", methods=["GET"])
def vehicle_price_history(no):
    """Belirli bir ilanın fiyat geçmişi."""
    from app.models.models import _parse_price
    history = (
        PriceHistory.query
        .filter_by(no=no)
        .order_by(PriceHistory.create_date)
        .all()
    )
    vehicle = Vehicle.query.filter_by(no=no).first()

    first_price = _parse_price(history[0].price) if history else None
    last_price  = _parse_price(history[-1].price) if history else None

    return jsonify({
        "vehicle": vehicle.to_dict() if vehicle else None,
        "history": [h.to_dict() for h in history],
        "changes": len(history) - 1,
        "first_price": first_price,
        "last_price": last_price,
        "price_change_pct": (
            (last_price - first_price) / first_price * 100
            if len(history) > 1 and first_price else 0
        ),
    })


# ── /api/options ──────────────────────────────────────────────────────────────

@api_bp.route("/options", methods=["GET"])
def options():
    """Form dropdown seçenekleri — DB'deki unique değerler."""
    markas = [r[0] for r in db.session.query(Vehicle.marka).distinct().filter(Vehicle.marka.isnot(None)).order_by(Vehicle.marka).all()]
    fueloils = [r[0] for r in db.session.query(Vehicle.fueloil).distinct().filter(Vehicle.fueloil.isnot(None)).all()]
    gears = [r[0] for r in db.session.query(Vehicle.gear).distinct().filter(Vehicle.gear.isnot(None)).all()]
    car_types = [r[0] for r in db.session.query(Vehicle.car_type).distinct().filter(Vehicle.car_type.isnot(None)).all()]
    years = sorted([r[0] for r in db.session.query(Vehicle.model_year).distinct().filter(Vehicle.model_year.isnot(None)).all()], reverse=True)
    return jsonify({
        "markas": markas,
        "fueloils": fueloils,
        "gears": gears,
        "car_types": car_types,
        "years": years,
    })


@api_bp.route("/options/models", methods=["GET"])
def model_options():
    """Markaya göre seri+model listesi."""
    marka = request.args.get("marka", "")
    models = (
        db.session.query(Vehicle.seri, Vehicle.model)
        .filter(Vehicle.marka == marka)
        .distinct()
        .order_by(Vehicle.seri, Vehicle.model)
        .all()
    )
    return jsonify({"models": [{"seri": r[0], "model": r[1]} for r in models]})


@api_bp.route("/vehicles/by-model", methods=["GET"])
def vehicles_by_model():
    """Marka/seri/model'e göre araç listesi — fiyat geçmişi seçimi için."""
    from app.models.models import _parse_price
    marka = request.args.get("marka")
    seri  = request.args.get("seri")
    model = request.args.get("model")

    q = Vehicle.query
    if marka: q = q.filter(Vehicle.marka == marka)
    if seri:  q = q.filter(Vehicle.seri == seri)
    if model: q = q.filter(Vehicle.model == model)

    vehicles = q.limit(100).all()
    result = []
    for v in vehicles:
        # Fiyat geçmişi kaç kayıt var?
        hist_count = PriceHistory.query.filter_by(no=v.no).count()
        result.append({
            "no":          v.no,
            "marka":       v.marka,
            "seri":        v.seri,
            "model":       v.model,
            "model_year":  v.model_year,
            "km":          v.km,
            "fueloil":     v.fueloil,
            "gear":        v.gear,
            "color":       v.color,
            "price":       _parse_price(v.price),
            "history_count": hist_count,
        })
    # Fiyat geçmişi olanları öne al
    result.sort(key=lambda x: x["history_count"], reverse=True)
    return jsonify({"vehicles": result})

# ── /api/config ───────────────────────────────────────────────────────────────

DAMAGE_CONFIG_PATH = "damage_config.json"
DAMAGE_CONFIG_DEFAULTS = {
    "part_max_pct": {
        "roof": 9.0, "front_hood": 7.0, "rear_hood": 6.0,
        "front_right_door": 4.5, "front_left_door": 4.5,
        "rear_right_door": 4.0, "rear_left_door": 4.0,
        "front_right_mudguard": 3.0, "front_left_mudguard": 3.0,
        "rear_right_mudguard": 2.5, "rear_left_mudguard": 2.5,
        "front_bumper": 2.0, "rear_bumper": 2.0,
    },
    "status_factor": {
        "changed-new": 1.0, "painted-new": 0.6,
        "localpainted-new": 0.35, "original-new": 0.0,
    },
    "top_n_parts": 3,
    "max_drop_pct": 18.0,
    "heavy_damage_pct": 15.0,
}


def _read_config_file():
    import json, os
    paths = [DAMAGE_CONFIG_PATH, os.path.join(os.getcwd(), DAMAGE_CONFIG_PATH)]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    return json.load(f)
            except Exception:
                pass
    return dict(DAMAGE_CONFIG_DEFAULTS)


def _write_config_file(cfg):
    import json
    with open(DAMAGE_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


@api_bp.route("/config/damage", methods=["GET"])
def get_damage_config():
    """Hasar config'ini damage_config.json'dan döndürür."""
    return jsonify(_read_config_file())


@api_bp.route("/config/damage", methods=["POST"])
def save_damage_config():
    """Hasar config'ini damage_config.json'a kaydeder."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "config gerekli"}), 400
    # Sadece bilinen anahtarları kaydet
    cfg = {
        "part_max_pct":  data.get("part_max_pct", {}),
        "status_factor": data.get("status_factor", DAMAGE_CONFIG_DEFAULTS["status_factor"]),
        "top_n_parts":   int(data.get("top_n_parts", 3)),
        "max_drop_pct":  float(data.get("max_drop_pct", 18.0)),
        "heavy_damage_pct": float(data.get("heavy_damage_pct", 15.0)),
    }
    try:
        _write_config_file(cfg)
        return jsonify({"success": True, "message": "Config kaydedildi"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/config/damage/reset", methods=["POST"])
def reset_damage_config():
    """Config'i varsayılanlara sıfırlar."""
    try:
        _write_config_file(dict(DAMAGE_CONFIG_DEFAULTS))
        return jsonify({"success": True, "message": "Varsayılanlara sıfırlandı"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── BFL Tahmin (Filo Araçları) ───────────────────────────────────────────────

# Tahmin yapılacak plaka durumları
BFL_ALLOWED_DURUMLAR = ["KSK", "USK", "Havuz", "Tahsis", "0 km Stok"]

# Araç minimum elde tutma süresi (gün)
BFL_MIN_HOLD_DAYS = 185

def _calc_valor_pricing(tahmini_satis: float, annual_rate_pct: float, alis_tarihi_iso: str) -> dict:
    """
    Valör bazlı fiyatlandırma.
    - Min. elde tutma: 185 gün → en erken satış = alış + 185 gün
    - Kalan gün > 0 ise araç valörlü satılabilir
    - Kalan gün sonunda araç günlük bileşik faizle HEDEF fiyata ulaşır
    - Valörlü satış bu hedef fiyat üzerinden hesaplanır
    """
    from datetime import date, timedelta

    result = {
        "alis_tarihi":          alis_tarihi_iso,
        "min_hold_days":        BFL_MIN_HOLD_DAYS,
        "en_erken_satis":       None,
        "elde_tutma_gun":       None,
        "kalan_gun":            None,
        "satilabilir":          False,   # bugün direkt satılabilir mi
        "valorlu":              False,   # valörlü mü satılmalı
        "bugunku_fiyat":        round(tahmini_satis, -3),
        "hedef_satis_fiyati":   None,    # kalan gün sonrası faizli hedef
        "valorlu_bugun_fiyati": None,    # bugün alıcıya sunulabilecek rasyonel fiyat
        "max_indirim_tl":       0,
        "max_indirim_pct":      0,
    }

    if not alis_tarihi_iso:
        result["satilabilir"] = True
        return result

    try:
        alis = date.fromisoformat(alis_tarihi_iso[:10])
    except Exception:
        result["satilabilir"] = True
        return result

    bugun = date.today()
    en_erken = alis + timedelta(days=BFL_MIN_HOLD_DAYS)
    result["en_erken_satis"] = en_erken.isoformat()
    result["elde_tutma_gun"] = (bugun - alis).days
    kalan_gun = (en_erken - bugun).days
    result["kalan_gun"] = kalan_gun

    # Kalan gün 0/negatif → bugün satılabilir, valör yok
    if kalan_gun <= 0:
        result["satilabilir"] = True
        return result

    result["valorlu"] = True

    # Yıllık faiz → günlük bileşik faiz
    daily_rate = (annual_rate_pct / 100.0) / 365.0

    # Kalan gün sonunda araç bu hedef fiyata ulaşır
    hedef = tahmini_satis * ((1 + daily_rate) ** kalan_gun)

    # Alıcı bugün peşin öderse, satıcı parayı faizde değerlendirip hedefe ulaşır.
    # Bu yüzden alıcıya bugün, hedef fiyatın bugünkü iskonto edilmiş değerini sunabilir.
    # = tahmini_satis (bugünkü fiyat) → rasyonel valörlü bugün fiyatı
    valorlu_bugun = tahmini_satis

    # Maksimum indirim: hedef fiyattan ne kadar düşülebilir
    max_indirim = hedef - valorlu_bugun
    max_indirim_pct = (max_indirim / hedef * 100) if hedef else 0

    result["hedef_satis_fiyati"]   = round(hedef, -3)
    result["valorlu_bugun_fiyati"] = round(valorlu_bugun, -3)
    result["max_indirim_tl"]       = round(max_indirim, -3)
    result["max_indirim_pct"]      = round(max_indirim_pct, 2)
    return result

@api_bp.route("/bfl/options", methods=["GET"])
def bfl_options():
    """BFL filtre seçenekleri — marka listesi (sadece uygun plaka durumları)."""
    markas = [
        r[0] for r in db.session.query(FiloArac.marka)
        .filter(
            FiloArac.plaka_durum.in_(BFL_ALLOWED_DURUMLAR),
            FiloArac.marka.isnot(None),
        )
        .distinct().order_by(FiloArac.marka).all()
    ]
    durumlar = [
        r[0] for r in db.session.query(FiloArac.plaka_durum)
        .filter(FiloArac.plaka_durum.in_(BFL_ALLOWED_DURUMLAR))
        .distinct().all()
    ]
    return jsonify({"markas": markas, "durumlar": durumlar})


@api_bp.route("/bfl/series", methods=["GET"])
def bfl_series():
    """Markaya göre seri listesi."""
    marka = request.args.get("marka", "")
    series = [
        r[0] for r in db.session.query(FiloArac.seri)
        .filter(
            FiloArac.marka == marka,
            FiloArac.plaka_durum.in_(BFL_ALLOWED_DURUMLAR),
            FiloArac.seri.isnot(None),
        )
        .distinct().order_by(FiloArac.seri).all()
    ]
    return jsonify({"series": series})


@api_bp.route("/bfl/vehicles", methods=["GET"])
def bfl_vehicles():
    """Marka/seri'ye göre araç (plaka) listesi."""
    marka = request.args.get("marka")
    seri  = request.args.get("seri")
    durum = request.args.get("durum")  # opsiyonel

    q = FiloArac.query.filter(FiloArac.plaka_durum.in_(BFL_ALLOWED_DURUMLAR))
    if marka: q = q.filter(FiloArac.marka == marka)
    if seri:  q = q.filter(FiloArac.seri == seri)
    if durum: q = q.filter(FiloArac.plaka_durum == durum)

    vehicles = q.order_by(FiloArac.plaka).all()
    return jsonify({"vehicles": [v.to_dict() for v in vehicles]})


def _normalize_for_prediction(filo_arac: dict) -> dict:
    """
    Filo aracını tahmin modeli formatına çevirir.
    filo_arac_master'daki değerler büyük harf olabilir (MEGANE),
    tahmin modeli farklı format bekleyebilir — normalize ediyoruz.
    """
    def title_case(s):
        if not s:
            return s
        return str(s).strip().title()

    return {
        "marka":      title_case(filo_arac.get("marka")),
        "seri":       title_case(filo_arac.get("seri")),
        "model":      filo_arac.get("model"),
        "model_year": filo_arac.get("model_yili"),
        "km":         filo_arac.get("son_km") or 0,
        "fueloil":    title_case(filo_arac.get("yakit_tipi")),
        "gear":       title_case(filo_arac.get("vites_tipi")),
        "damage_registered": False,   # BFL'de hasar dikkate alınmaz
    }


@api_bp.route("/bfl/predict/<int:filo_id>", methods=["POST"])
def bfl_predict(filo_id):
    """Tek bir filo aracı için tahmin + kâr + valör fiyatlandırma."""
    filo = FiloArac.query.get(filo_id)
    if not filo:
        return jsonify({"error": "Araç bulunamadı"}), 404

    predictor = get_predictor()
    if not predictor.is_loaded():
        return jsonify({"error": "Model henüz eğitilmemiş"}), 503

    # Faiz oranı kullanıcıdan
    body = request.get_json(silent=True) or {}
    annual_rate = float(body.get("annual_rate_pct", 0) or 0)

    filo_dict = filo.to_dict()
    pred_input = _normalize_for_prediction(filo_dict)

    try:
        result = predictor.predict(pred_input)
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Tahmin hatası: {str(e)}"}), 500

    b2c_fiyat = result["predicted_price"]
    b2b_fiyat = b2c_fiyat * 0.90
    alis_fiyati = filo_dict.get("alis_fiyati") or 0

    b2c_kar = b2c_fiyat - alis_fiyati if alis_fiyati else None
    b2c_kar_pct = (
        b2c_kar / alis_fiyati * 100
        if alis_fiyati and b2c_kar is not None
        else None
    )

    b2b_kar = b2b_fiyat - alis_fiyati if alis_fiyati else None
    b2b_kar_pct = (
        b2b_kar / alis_fiyati * 100
        if alis_fiyati and b2b_kar is not None
        else None
    )

    # Valör fiyatlandırma (faiz oranı verildiyse)
    valor = _calc_valor_pricing(b2c_fiyat, annual_rate, filo_dict.get("alis_tarihi")) if annual_rate > 0 else None

    return jsonify({
        "success": True,
        "arac": filo_dict,

        "tahmini_satis": round(b2c_fiyat, -3),
        "b2c_fiyat": round(b2c_fiyat, -3),
        "b2b_fiyat": round(b2b_fiyat, -3),

        "price_lower": result["price_lower"],
        "price_upper": result["price_upper"],
        "alis_fiyati": alis_fiyati,

        "kar": round(b2c_kar, -3) if b2c_kar is not None else None,
        "kar_pct": round(b2c_kar_pct, 1) if b2c_kar_pct is not None else None,

        "b2c_kar": round(b2c_kar, -3) if b2c_kar is not None else None,
        "b2c_kar_pct": round(b2c_kar_pct, 1) if b2c_kar_pct is not None else None,

        "b2b_kar": round(b2b_kar, -3) if b2b_kar is not None else None,
        "b2b_kar_pct": round(b2b_kar_pct, 1) if b2b_kar_pct is not None else None,

        "model_group": result.get("model_group", "genel"),
        "valor": valor,
        "annual_rate_pct": annual_rate,
    })


@api_bp.route("/bfl/predict-batch", methods=["POST"])
def bfl_predict_batch():
    """
    Marka/seri'ye göre tüm araçlar için toplu tahmin + kâr özeti.
    Body: {marka, seri, durum?}
    """
    data = request.get_json() or {}
    marka = data.get("marka")
    seri  = data.get("seri")
    durum = data.get("durum")
    annual_rate = float(data.get("annual_rate_pct", 0) or 0)

    predictor = get_predictor()
    if not predictor.is_loaded():
        return jsonify({"error": "Model henüz eğitilmemiş"}), 503

    q = FiloArac.query.filter(FiloArac.plaka_durum.in_(BFL_ALLOWED_DURUMLAR))
    if marka: q = q.filter(FiloArac.marka == marka)
    if seri:  q = q.filter(FiloArac.seri == seri)
    if durum: q = q.filter(FiloArac.plaka_durum == durum)

    vehicles = q.all()
    results = []
    toplam_alis = 0
    toplam_tahmin = 0
    karli = 0
    zararli = 0

    for v in vehicles:
        fd = v.to_dict()
        pred_input = _normalize_for_prediction(fd)
        try:
            r = predictor.predict(pred_input)
        except Exception:
            db.session.rollback()
            continue

        b2c_fiyat = r["predicted_price"]
        b2b_fiyat = b2c_fiyat * 0.90
        alis = fd.get("alis_fiyati") or 0

        b2c_kar = b2c_fiyat - alis if alis else None
        b2c_kar_pct = (
            b2c_kar / alis * 100
            if alis and b2c_kar is not None
            else None
        )

        b2b_kar = b2b_fiyat - alis if alis else None
        b2b_kar_pct = (
            b2b_kar / alis * 100
            if alis and b2b_kar is not None
            else None
        )

        if alis:
            toplam_alis   += alis
            toplam_tahmin += b2c_fiyat
            if b2c_kar and b2c_kar > 0: karli += 1
            elif b2c_kar and b2c_kar < 0: zararli += 1

        valor = _calc_valor_pricing(b2c_fiyat, annual_rate, fd.get("alis_tarihi")) if annual_rate > 0 else None

        results.append({
            "id":            fd["id"],
            "plaka":         fd["plaka"],
            "plaka_durum":   fd["plaka_durum"],
            "marka":         fd["marka"],
            "seri":          fd["seri"],
            "model":         fd["model"],
            "model_yili":    fd["model_yili"],
            "son_km":        fd["son_km"],
            "yakit_tipi":    fd["yakit_tipi"],
            "vites_tipi":    fd["vites_tipi"],
            "alis_fiyati": alis,

            "tahmini_satis": round(b2c_fiyat, -3),
            "b2c_fiyat": round(b2c_fiyat, -3),
            "b2b_fiyat": round(b2b_fiyat, -3),

            "price_lower": r["price_lower"],
            "price_upper": r["price_upper"],

            "kar": round(b2c_kar, -3) if b2c_kar is not None else None,
            "kar_pct": round(b2c_kar_pct, 1) if b2c_kar_pct is not None else None,

            "b2c_kar": round(b2c_kar, -3) if b2c_kar is not None else None,
            "b2c_kar_pct": round(b2c_kar_pct, 1) if b2c_kar_pct is not None else None,

            "b2b_kar": round(b2b_kar, -3) if b2b_kar is not None else None,
            "b2b_kar_pct": round(b2b_kar_pct, 1) if b2b_kar_pct is not None else None,

            "valor": valor,
        })

    toplam_kar = toplam_tahmin - toplam_alis
    ort_kar_pct = (toplam_kar / toplam_alis * 100) if toplam_alis else 0

    # Valör özeti — valörlü satılabilir araçların toplamı
    valor_ozet = None
    if annual_rate > 0 and results:
        valorlu_list = [r for r in results if r.get("valor") and r["valor"].get("valorlu")]
        satilabilir_count = sum(1 for r in results if r.get("valor") and r["valor"].get("satilabilir"))
        toplam_hedef   = sum(r["valor"]["hedef_satis_fiyati"] for r in valorlu_list)
        toplam_bugun   = sum(r["valor"]["valorlu_bugun_fiyati"] for r in valorlu_list)
        toplam_indirim = sum(r["valor"]["max_indirim_tl"] for r in valorlu_list)
        valor_ozet = {
            "valorlu_arac":      len(valorlu_list),
            "satilabilir_arac":  satilabilir_count,
            "toplam_hedef":      round(toplam_hedef, -3),
            "toplam_bugun":      round(toplam_bugun, -3),
            "toplam_max_indirim": round(toplam_indirim, -3),
            "ort_indirim_pct":   round(toplam_indirim / toplam_hedef * 100, 2) if toplam_hedef else 0,
        }

    return jsonify({
        "results": results,
        "annual_rate_pct": annual_rate,
        "valor_ozet": valor_ozet,
        "ozet": {
            "arac_sayisi":    len(results),
            "toplam_alis":    round(toplam_alis, -3),
            "toplam_tahmin":  round(toplam_tahmin, -3),
            "toplam_kar":     round(toplam_kar, -3),
            "ort_kar_pct":    round(ort_kar_pct, 1),
            "karli_arac":     karli,
            "zararli_arac":   zararli,
        }
    })
