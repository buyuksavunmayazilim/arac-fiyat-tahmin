"""
ML Pipeline — Grup Bazlı XGBoost Araç Fiyat Tahmin Modeli

Her marka+seri+model kombinasyonu için ayrı XGBoost modeli eğitilir.
Az verili gruplar için genel (fallback) model kullanılır.
"""

import os
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import shap
from xgboost import XGBRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from settings import MIN_SAMPLES_FOR_GROUP_MODEL

logger = logging.getLogger(__name__)

# ── Sabitler ───────────────────────────────────────────────────────────────

CATEGORICAL_COLS = ["fueloil", "gear", "car_status", "car_type",
                    "drive", "color", "plate", "whois"]

# Grup modeli için marka/seri/model encode edilmez (zaten filtrelenmiş)
CATEGORICAL_COLS_GENERAL = ["marka", "seri", "model"] + CATEGORICAL_COLS

NUMERIC_COLS = ["model_year", "km"]

BOOLEAN_COLS = ["damage_registered"]

DAMAGE_PARTS = ["front_bumper", "front_hood", "roof", "front_right_mudguard",
                "front_right_door", "rear_right_door", "rear_right_mudguard",
                "front_left_mudguard", "front_left_door", "rear_left_door",
                "rear_left_mudguard", "rear_hood", "rear_bumper"]

# Kritik parçalar — daha ağır ağırlık
CRITICAL_PARTS = {"front_hood": 2.0, "roof": 2.0, "rear_hood": 1.5,
                  "front_right_door": 1.1, "front_left_door": 1.1,
                  "rear_right_door": 1.0, "rear_left_door": 1.0}

DAMAGE_SEVERITY = {
    "original-new":     0,    # Orijinal — etki yok
    "localpainted-new": 2,    # Lokal Boyalı — düşük etki
    "painted-new":      5,    # Boyalı — orta etki
    "changed-new":      10,   # Değişen — yüksek etki (ağır hasar)
    # form kısa kodları
    "o": 0, "lb": 2, "b": 5, "d": 10,
}

XGBOOST_PARAMS = {
    "n_estimators": 1000,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 3,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "early_stopping_rounds": 50,
}

XGBOOST_PARAMS_SMALL = {   # Az verili gruplar için daha basit model
    **XGBOOST_PARAMS,
    "max_depth": 4,
    "min_child_weight": 2,
    "n_estimators": 500,
    "early_stopping_rounds": 30,
}


"""def _group_key(marka, seri, model):
    "Grup anahtarı oluştur."
    parts = [str(x).strip().lower().replace(" ", "_")
             for x in [marka, seri, model] if x]
    return "__".join(parts)"""

def _group_key(marka, seri, model=None):
    parts = [str(x).strip().lower().replace(" ", "_")
             for x in [marka, seri] if x]
    return "__".join(parts)


def _load_damage_config() -> dict:
    """damage_config.json dosyasından config yükler."""
    config_paths = [
        Path("damage_config.json"),
        Path(__file__).parent.parent / "damage_config.json",
    ]
    for p in config_paths:
        if p.exists():
            try:
                with open(p) as f:
                    return json.load(f)
            except Exception:
                pass
    # Fallback — dosya bulunamazsa hardcoded default
    return {
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


def _select_top_parts(input_dict: dict, cfg: dict) -> list:
    """
    Hasarlı parçaları etki yüzdesine göre sıralar, en kötü top_n tanesini döndürür.
    Her parçanın etkisi = part_max_pct[parça] × status_factor[durum]
    """
    part_max  = cfg.get("part_max_pct", {})
    status_f  = cfg.get("status_factor", {})
    top_n     = int(cfg.get("top_n_parts", 3))

    parts_scored = []
    for part in DAMAGE_PARTS:
        val = input_dict.get(part, "original-new") or "original-new"
        val_lower = str(val).lower().strip()
        factor = status_f.get(val_lower, 0.0)
        if factor == 0.0:
            continue
        max_pct = part_max.get(part, 2.0)
        impact_pct = max_pct * factor   # bu parçanın % etkisi
        parts_scored.append({
            "part":       part,
            "value":      val,
            "max_pct":    max_pct,
            "factor":     factor,
            "impact_pct": impact_pct,
            "score":      impact_pct,   # geriye uyumluluk
        })

    # En çok etkileyen parçalar önce
    parts_scored.sort(key=lambda x: x["impact_pct"], reverse=True)
    return parts_scored[:top_n]


def _calc_damage_drop(input_dict: dict, base_price: float = None) -> float:
    """
    Hasar düşüş mantığı (yüzde tabanlı):
    - Her parçanın etkisi = part_max_pct × status_factor
    - En kötü top_n parçanın etkileri toplanır
    - damage_registered=True → heavy_damage_pct uygulanır (parçalardan bağımsız)
    - Final = max(parça_toplamı, ağır_hasar) ama max_drop_pct'i geçemez
    """
    cfg       = _load_damage_config()
    max_drop  = cfg.get("max_drop_pct", 18.0) / 100.0
    heavy_pct = cfg.get("heavy_damage_pct", 15.0) / 100.0

    dmg_raw  = input_dict.get("damage_registered", False)
    is_heavy = dmg_raw if isinstance(dmg_raw, bool) else str(dmg_raw).lower() in ("true", "1")

    # Parça etkilerini topla (top_n)
    top_parts  = _select_top_parts(input_dict, cfg)
    parts_drop = sum(p["impact_pct"] for p in top_parts) / 100.0

    # Ağır hasar işaretliyse sabit oran taban olur
    heavy_floor = heavy_pct if is_heavy else 0.0

    final_drop = max(parts_drop, heavy_floor)
    return min(final_drop, max_drop)


def _parse_damage_score(val, part_name=None):
    """Parça değerini şiddet skoruna çevir."""
    cfg  = _load_damage_config()
    sev  = cfg.get("severity", {})
    base = sev.get(str(val).lower().strip(), 0) if val else 0
    if part_name and base > 0:
        weight = cfg.get("part_weights", {}).get(part_name, 1.0)
        base   = base * weight
    return base


def _to_int_flag(series):
    def _conv(v):
        if isinstance(v, bool): return int(v)
        if isinstance(v, (int, float)): return int(bool(v))
        if isinstance(v, str): return 1 if v.lower() in ('true','1','evet','yes') else 0
        return 0
    return series.apply(_conv)


class GroupModel:
    """Tek bir marka+seri+model grubu için model."""

    def __init__(self, group_key: str):
        self.group_key  = group_key
        self.model      = None
        self.model_lower = None
        self.model_upper = None
        self.encoders   = {}
        self.feature_names = []
        self.explainer  = None

    def _build_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        df = df.copy()
        current_year = pd.Timestamp.now().year

        df["model_year"] = pd.to_numeric(df["model_year"], errors="coerce").fillna(current_year - 5)
        df["km"]         = pd.to_numeric(df["km"],         errors="coerce").fillna(0)
        df["vehicle_age"] = current_year - df["model_year"]
        df["km_per_year"] = df["km"] / df["vehicle_age"].clip(lower=1)
        df["log_km"]      = np.log1p(df["km"])

        # Hasar parçalarını etki yüzdesine çevir — dosya config kullan
        _dcfg     = _load_damage_config()
        _part_max = _dcfg.get("part_max_pct", {})
        _status_f = _dcfg.get("status_factor", {})

        total_score = pd.Series(0.0, index=df.index)
        for part in DAMAGE_PARTS:
            col = part + "_score"
            if part in df.columns:
                max_pct = _part_max.get(part, 2.0)
                df[col] = df[part].apply(
                    lambda v: max_pct * _status_f.get(str(v).lower().strip(), 0.0) if v else 0.0
                )
            else:
                df[col] = 0.0
            total_score += df[col]

        damage_score_cols = [p + "_score" for p in DAMAGE_PARTS]
        df["damage_total_score"]    = total_score
        df["damage_count"]          = (df[damage_score_cols] > 0).sum(axis=1)
        df["damage_ratio"]          = df["damage_count"] / len(DAMAGE_PARTS)
        df["has_changed"]           = (df[damage_score_cols] > 0).any(axis=1).astype(int)
        df["critical_damage_score"] = df[["front_hood_score","roof_score",
                                          "front_right_door_score","front_left_door_score"]].sum(axis=1)

        # damage_registered=True ama hiç parça seçilmemişse minimum skor ata
        # Parça seçildiyse parça skorları gerçek değeri taşır — dokunma
        dmg_flag = _to_int_flag(
            df["damage_registered"].fillna(False) if "damage_registered" in df.columns
            else pd.Series([False]*len(df), index=df.index)
        )
        no_parts = df["damage_total_score"] == 0
        df["damage_total_score"] = df.apply(
            lambda row: 10.0 if (dmg_flag[row.name] and no_parts[row.name])
                        else row["damage_total_score"],
            axis=1
        )

        # Grup modeli için marka/seri/model encode etme — zaten filtrelenmiş
        for col in CATEGORICAL_COLS:
            if col not in df.columns:
                df[col] = "unknown"
            df[col] = df[col].fillna("unknown").astype(str)
            if fit:
                enc = LabelEncoder()
                df[col + "_enc"] = enc.fit_transform(df[col])
                self.encoders[col] = enc
            else:
                enc = self.encoders.get(col)
                if enc:
                    df[col + "_enc"] = df[col].apply(
                        lambda x: enc.transform([x])[0] if x in enc.classes_ else -1
                    )
                else:
                    df[col + "_enc"] = -1

        for col in BOOLEAN_COLS:
            df[col + "_int"] = _to_int_flag(df[col].fillna(False)) if col in df.columns else 0

        for col in NUMERIC_COLS:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(
                df[col].median() if fit else 0
            )

        feature_cols = (
            [c + "_enc" for c in CATEGORICAL_COLS] +
            NUMERIC_COLS +
            ["vehicle_age", "km_per_year", "log_km",
             "damage_total_score", "damage_count", "damage_ratio",
             "has_changed", "critical_damage_score"] +
            damage_score_cols +
            [c + "_int" for c in BOOLEAN_COLS]
        )

        if fit:
            self.feature_names = feature_cols
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0

        return df[self.feature_names]

    def train(self, df: pd.DataFrame) -> dict:
        df = df[df["price"].notna() & (df["price"] > 0)].copy()
        if len(df) < 10:
            return None

        y = np.log1p(df["price"].astype(float).values)
        X = self._build_features(df, fit=True)

        # Az veri varsa test split yapma
        if len(df) < 60:
            X_train, X_test = X, X
            y_train, y_test = y, y
            params = {k: v for k, v in XGBOOST_PARAMS_SMALL.items()
                      if k != "early_stopping_rounds"}
            self.model = XGBRegressor(objective="reg:squarederror", **params)
            self.model.fit(X_train, y_train)
            self.model_lower = XGBRegressor(objective="reg:quantileerror",
                quantile_alpha=0.05, **{k:v for k,v in params.items() if k!="n_estimators"}, n_estimators=300)
            self.model_upper = XGBRegressor(objective="reg:quantileerror",
                quantile_alpha=0.95, **{k:v for k,v in params.items() if k!="n_estimators"}, n_estimators=300)
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
            self.model = XGBRegressor(objective="reg:squarederror", **XGBOOST_PARAMS)
            self.model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            params_q = {k: v for k, v in XGBOOST_PARAMS.items() if k != "early_stopping_rounds"}
            self.model_lower = XGBRegressor(objective="reg:quantileerror", quantile_alpha=0.05,
                **{k:v for k,v in params_q.items() if k!="n_estimators"}, n_estimators=500)
            self.model_upper = XGBRegressor(objective="reg:quantileerror", quantile_alpha=0.95,
                **{k:v for k,v in params_q.items() if k!="n_estimators"}, n_estimators=500)
            self.model_lower.fit(X_train, y_train)
            self.model_upper.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        return {
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "mae":  float(mean_absolute_error(y_test, y_pred)),
            "r2":   float(r2_score(y_test, y_pred)),
            "train_samples": len(df),
        }

    def predict(self, input_dict: dict) -> dict:
        X = self._build_features(pd.DataFrame([input_dict]), fit=False)
        log_pred  = self.model.predict(X)[0]
        log_lower = self.model_lower.predict(X)[0]
        log_upper = self.model_upper.predict(X)[0]

        predicted = float(np.expm1(log_pred))
        lower     = float(np.expm1(log_lower))
        upper     = float(np.expm1(log_upper))

        # ── Kural tabanlı hasar düzeltmesi ─────────────────────────────────
        damage_drop = _calc_damage_drop(input_dict, base_price=predicted)
        if damage_drop > 0:
            predicted = predicted * (1 - damage_drop)
            lower     = lower     * (1 - damage_drop * 1.2)
            upper     = upper     * (1 - damage_drop * 0.8)

        shap_result = self._explain(X, log_pred)
        return {
            "predicted_price": round(predicted, -3),
            "price_lower":     round(lower, -3),
            "price_upper":     round(upper, -3),
            "confidence_pct":  min(100, round((1 - (upper - lower) / max(predicted, 1)) * 100, 1)),
            "shap_values":     shap_result,
        }

    def _explain(self, X, log_pred):
        if self.explainer is None:
            self.explainer = shap.TreeExplainer(self.model)
        shap_vals    = self.explainer.shap_values(X)[0]
        predicted    = float(np.expm1(log_pred))
        impacts = []
        for fname, fval, sval in zip(self.feature_names, X.iloc[0], shap_vals):
            price_without = float(np.expm1(log_pred - sval))
            impact_tl     = predicted - price_without
            impacts.append({
                "feature":   fname,
                "value":     float(fval),
                "shap_value": float(sval),
                "impact_tl": round(impact_tl, -3),
                "direction": "positive" if sval > 0 else "negative",
            })
        impacts.sort(key=lambda x: abs(x["impact_tl"]), reverse=True)
        return impacts[:10]

    def damage_counterfactual(self, input_dict: dict) -> dict:
        with_dmg    = self.predict(input_dict)
        no_dmg_inp  = {**input_dict, "damage_registered": False}
        for part in DAMAGE_PARTS:
            no_dmg_inp[part] = "original-new"
        without_dmg = self.predict(no_dmg_inp)
        impact      = without_dmg["predicted_price"] - with_dmg["predicted_price"]
        impact_pct  = (impact / max(with_dmg["predicted_price"], 1)) * 100

        cfg       = _load_damage_config()
        top_parts = _select_top_parts(input_dict, cfg)

        PART_LABELS = {
            "front_bumper":"Ön Tampon","front_hood":"Ön Kaput","roof":"Tavan",
            "front_right_mudguard":"Sağ Ön Çamurluk","front_right_door":"Sağ Ön Kapı",
            "rear_right_door":"Sağ Arka Kapı","rear_right_mudguard":"Sağ Arka Çamurluk",
            "front_left_mudguard":"Sol Ön Çamurluk","front_left_door":"Sol Ön Kapı",
            "rear_left_door":"Sol Arka Kapı","rear_left_mudguard":"Sol Arka Çamurluk",
            "rear_hood":"Arka Kaput","rear_bumper":"Arka Tampon",
        }
        VAL_LABELS = {
            "changed-new":"Değişen","painted-new":"Boyalı",
            "localpainted-new":"Lokal Boyalı","original-new":"Orijinal",
        }
        top_parts_labeled = [
            {
                "part":  PART_LABELS.get(p["part"], p["part"]),
                "value": VAL_LABELS.get(p["value"], p["value"]),
                "score": round(p["score"], 2),
            }
            for p in top_parts
        ]

        dmg_raw  = input_dict.get("damage_registered", False)
        is_heavy = dmg_raw if isinstance(dmg_raw, bool) else str(dmg_raw).lower() in ("true","1")

        return {
            "with_damage":       with_dmg["predicted_price"],
            "without_damage":    without_dmg["predicted_price"],
            "price_impact_tl":   round(impact, -3),
            "price_impact_pct":  round(impact_pct, 1),
            "top_damaged_parts": top_parts_labeled,
            "is_heavy_damage":   is_heavy,
        }

    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model,       path / "model_main.joblib")
        joblib.dump(self.model_lower, path / "model_lower.joblib")
        joblib.dump(self.model_upper, path / "model_upper.joblib")
        joblib.dump(self.encoders,    path / "encoders.joblib")
        with open(path / "feature_names.json", "w") as f:
            json.dump(self.feature_names, f)

    def load(self, path: Path):
        self.model       = joblib.load(path / "model_main.joblib")
        self.model_lower = joblib.load(path / "model_lower.joblib")
        self.model_upper = joblib.load(path / "model_upper.joblib")
        self.encoders    = joblib.load(path / "encoders.joblib")
        with open(path / "feature_names.json") as f:
            self.feature_names = json.load(f)
        return self

    def is_loaded(self):
        return self.model is not None


class VehiclePricePredictor:
    """Ana koordinatör — grup modelleri + genel fallback."""

    def __init__(self, model_dir: str = "ml/models"):
        self.model_dir     = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.group_models: dict[str, GroupModel] = {}
        self.general_model: GroupModel | None    = None

    # ── Eğitim ────────────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame) -> dict:
        logger.info(f"Grup bazlı eğitim başlıyor — {len(df)} araç")
        df = df.copy()
        df = df[df["price"].notna() & (df["price"] > 0)]

        # Grup anahtarı ekle
        df["_group"] = df.apply(
            lambda r: _group_key(r.get("marka"), r.get("seri"), r.get("model")), axis=1
        )

        group_metrics = {}
        self.group_models = {}

        # Her grup için ayrı model
        for gkey, gdf in df.groupby("_group"):
            if len(gdf) < MIN_SAMPLES_FOR_GROUP_MODEL:
                logger.info(f"  [{gkey}] {len(gdf)} araç — yetersiz, genel modele bırakılır")
                continue
            logger.info(f"  [{gkey}] {len(gdf)} araç — eğitiliyor...")
            gm = GroupModel(gkey)
            metrics = gm.train(gdf)
            if metrics:
                self.group_models[gkey] = gm
                group_metrics[gkey] = metrics
                logger.info(f"    RMSE:{metrics['rmse']:.4f}  R²:{metrics['r2']:.4f}")

        # Genel fallback model (tüm veri)
        logger.info(f"Genel fallback modeli eğitiliyor ({len(df)} araç)...")
        self.general_model = GroupModel("__general__")
        # Genel modelde marka/seri/model de feature olarak kullan
        self.general_model.encoders = {}
        # CATEGORICAL_COLS_GENERAL kullanmak için _build_features'ı override et
        self.general_model._cat_cols = CATEGORICAL_COLS_GENERAL
        general_metrics = self._train_general(df)
        group_metrics["__general__"] = general_metrics

        # Kaydet
        self._save()

        total_samples = len(df)
        logger.info(f"✓ Eğitim tamamlandı: {len(self.group_models)} grup modeli + 1 genel model")
        return {
            "group_metrics": group_metrics,
            "total_samples": total_samples,
            "group_count": len(self.group_models),
            # Özet metrikler
            "rmse": general_metrics["rmse"],
            "mae":  general_metrics["mae"],
            "r2":   general_metrics["r2"],
            "train_samples": total_samples,
        }

    def _train_general(self, df: pd.DataFrame) -> dict:
        """Genel model — marka/seri/model de feature."""
        gm = self.general_model

        # Geçici olarak cat cols'u genişlet
        orig = CATEGORICAL_COLS.copy()
        import ml.predictor as _self_mod
        _self_mod.CATEGORICAL_COLS = CATEGORICAL_COLS_GENERAL

        metrics = gm.train(df)

        _self_mod.CATEGORICAL_COLS = orig
        return metrics or {"rmse": 0, "mae": 0, "r2": 0, "train_samples": len(df)}

    # ── Tahmin ────────────────────────────────────────────────────────────────

    def _get_model(self, input_dict: dict) -> tuple:
        """Gruba uygun modeli döndür. (model, grup_adı)"""
        gkey = _group_key(
            input_dict.get("marka"),
            input_dict.get("seri"),
            input_dict.get("model")
        )
        if gkey in self.group_models:
            return self.group_models[gkey], gkey
        return self.general_model, "__general__"

    def predict(self, input_dict: dict) -> dict:
        model, gkey = self._get_model(input_dict)
        if model is None or not model.is_loaded():
            raise RuntimeError("Model yüklü değil")
        result = model.predict(input_dict)
        result["model_group"] = gkey
        return result

    def damage_counterfactual(self, input_dict: dict) -> dict:
        model, _ = self._get_model(input_dict)
        return model.damage_counterfactual(input_dict)

    def is_loaded(self) -> bool:
        return self.general_model is not None and self.general_model.is_loaded()

    # ── Kaydet / Yükle ────────────────────────────────────────────────────────

    def _save(self):
        # Grup modellerini kaydet
        for gkey, gm in self.group_models.items():
            gm.save(self.model_dir / "groups" / gkey)

        # Genel modeli kaydet
        if self.general_model:
            self.general_model.save(self.model_dir / "general")

        # Index kaydet
        index = {
            "groups": list(self.group_models.keys()),
            "has_general": self.general_model is not None,
        }
        with open(self.model_dir / "index.json", "w") as f:
            json.dump(index, f)
        logger.info(f"Modeller kaydedildi: {len(self.group_models)} grup + genel")

    def load(self):
        index_path = self.model_dir / "index.json"
        if not index_path.exists():
            # Eski tek-model formatını dene
            old_path = self.model_dir / "model_main.joblib"
            if old_path.exists():
                logger.warning("Eski model formatı — lütfen yeniden eğitin")
            return self

        with open(index_path) as f:
            index = json.load(f)

        self.group_models = {}
        for gkey in index.get("groups", []):
            gm = GroupModel(gkey)
            gm.load(self.model_dir / "groups" / gkey)
            self.group_models[gkey] = gm
            logger.info(f"  Grup modeli yüklendi: {gkey}")

        if index.get("has_general"):
            self.general_model = GroupModel("__general__")
            self.general_model.load(self.model_dir / "general")
            logger.info("  Genel model yüklendi")

        return self


# ── Singleton ─────────────────────────────────────────────────────────────────
_predictor_instance = None

def get_predictor() -> VehiclePricePredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = VehiclePricePredictor()
        if (Path("ml/models/index.json")).exists():
            _predictor_instance.load()
    return _predictor_instance
