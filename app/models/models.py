from datetime import datetime
from app import db


def _parse_price(val):
    """'2.175.000 TL' → 2175000.0 — boş/geçersiz değerler None döner."""
    if not val:
        return None
    try:
        import re
        # Sadece rakam, nokta, virgül bırak
        cleaned = re.sub(r'[^0-9.,]', '', str(val))
        if not cleaned:
            return None
        if ',' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace('.', '')
        if not cleaned or cleaned == '.':
            return None
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


class Vehicle(db.Model):
    """Araç ilanları — tüm kolonlar DB'nin gerçek tipinde (çoğu varchar)."""
    __tablename__ = "araclar"

    # Tüm kolonlar String — DB'deki gerçek tipe uygun
    id              = db.Column(db.String(50), primary_key=True)
    no              = db.Column(db.String(50), unique=True, nullable=False, index=True)
    create_date     = db.Column(db.String(50))
    ilan_tarihi     = db.Column(db.String(50))
    marka           = db.Column(db.String(100), index=True)
    seri            = db.Column(db.String(100))
    model           = db.Column(db.String(100), index=True)
    model_year      = db.Column(db.String(10))
    fueloil         = db.Column(db.String(50))
    gear            = db.Column(db.String(50))
    car_status      = db.Column(db.String(50))
    km              = db.Column(db.String(50))
    car_type        = db.Column(db.String(50))
    engine_power    = db.Column(db.String(50))
    engine_size     = db.Column(db.String(50))
    drive           = db.Column(db.String(50))
    color           = db.Column(db.String(50))
    guarantee       = db.Column(db.String(10))
    damage_registered = db.Column(db.String(10))
    plate           = db.Column(db.String(20))
    whois           = db.Column(db.String(100))
    swap            = db.Column(db.String(10))
    price           = db.Column(db.String(50))
    description     = db.Column(db.Text)
    front_bumper    = db.Column(db.String(50))
    front_hood      = db.Column(db.String(50))
    roof            = db.Column(db.String(50))
    front_right_mudguard = db.Column(db.String(50))
    front_right_door     = db.Column(db.String(50))
    rear_right_door      = db.Column(db.String(50))
    rear_right_mudguard  = db.Column(db.String(50))
    front_left_mudguard  = db.Column(db.String(50))
    front_left_door      = db.Column(db.String(50))
    rear_left_door       = db.Column(db.String(50))
    rear_left_mudguard   = db.Column(db.String(50))
    rear_hood       = db.Column(db.String(50))
    rear_bumper     = db.Column(db.String(50))

    # İlişki
    price_history = db.relationship("PriceHistory", backref="vehicle",
                                    lazy="dynamic", foreign_keys="PriceHistory.no")

    @property
    def damage_count(self):
        parts = [self.front_bumper, self.front_hood, self.roof,
                 self.front_right_mudguard, self.front_right_door, self.rear_right_door,
                 self.rear_right_mudguard, self.front_left_mudguard, self.front_left_door,
                 self.rear_left_door, self.rear_left_mudguard, self.rear_hood, self.rear_bumper]
        return sum(1 for p in parts if p and p not in ('O', 'Orijinal', None, ''))

    def to_dict(self):
        return {
            "id": self.id,
            "no": self.no,
            "marka": self.marka,
            "seri": self.seri,
            "model": self.model,
            "model_year": _parse_int(self.model_year),
            "fueloil": self.fueloil,
            "gear": self.gear,
            "car_status": self.car_status,
            "km": _parse_int(self.km),
            "car_type": self.car_type,
            "engine_power": self.engine_power,
            "engine_size": self.engine_size,
            "drive": self.drive,
            "color": self.color,
            "guarantee": self.guarantee,
            "damage_registered": self.damage_registered,
            "damage_count": self.damage_count,
            "plate": self.plate,
            "whois": self.whois,
            "swap": self.swap,
            "price": _parse_price(self.price),
            "ilan_tarihi": self.ilan_tarihi,
            # Hasar parçaları
            "front_bumper": self.front_bumper,
            "front_hood": self.front_hood,
            "roof": self.roof,
            "front_right_mudguard": self.front_right_mudguard,
            "front_right_door": self.front_right_door,
            "rear_right_door": self.rear_right_door,
            "rear_right_mudguard": self.rear_right_mudguard,
            "front_left_mudguard": self.front_left_mudguard,
            "front_left_door": self.front_left_door,
            "rear_left_door": self.rear_left_door,
            "rear_left_mudguard": self.rear_left_mudguard,
            "rear_hood": self.rear_hood,
            "rear_bumper": self.rear_bumper,
        }

    def __repr__(self):
        return f"<Vehicle {self.marka} {self.model} {self.model_year}>"


class PriceHistory(db.Model):
    """Fiyat geçmişi tablosu."""
    __tablename__ = "price"

    id          = db.Column(db.Integer, primary_key=True)
    no          = db.Column(db.String(50), db.ForeignKey("araclar.no"),
                            nullable=False, index=True)
    create_date = db.Column(db.String(50))
    price       = db.Column(db.String(50))

    def to_dict(self):
        return {
            "id": self.id,
            "no": self.no,
            "create_date": self.create_date,
            "price": _parse_price(self.price),
        }


class QueryHistory(db.Model):
    """Kullanıcı sorgu geçmişi."""
    __tablename__ = "queries"

    id          = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    session_id  = db.Column(db.String(100), index=True)
    marka       = db.Column(db.String(100))
    seri        = db.Column(db.String(100))
    model       = db.Column(db.String(100))
    model_year  = db.Column(db.Integer)
    fueloil     = db.Column(db.String(50))
    gear        = db.Column(db.String(50))
    km          = db.Column(db.Integer)
    car_type    = db.Column(db.String(50))
    damage_registered = db.Column(db.Boolean)
    predicted_price   = db.Column(db.Numeric(12, 2))
    price_lower       = db.Column(db.Numeric(12, 2))
    price_upper       = db.Column(db.Numeric(12, 2))
    model_version     = db.Column(db.String(50))

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "marka": self.marka,
            "seri": self.seri,
            "model": self.model,
            "model_year": self.model_year,
            "fueloil": self.fueloil,
            "gear": self.gear,
            "km": self.km,
            "predicted_price": float(self.predicted_price) if self.predicted_price else None,
            "price_lower": float(self.price_lower) if self.price_lower else None,
            "price_upper": float(self.price_upper) if self.price_upper else None,
        }


class ModelMetadata(db.Model):
    """ML model versiyonlama."""
    __tablename__ = "model_metadata"

    id          = db.Column(db.Integer, primary_key=True)
    version     = db.Column(db.String(50), unique=True, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_active   = db.Column(db.Boolean, default=False)
    model_path  = db.Column(db.String(500))
    train_samples = db.Column(db.Integer)
    rmse        = db.Column(db.Float)
    mae         = db.Column(db.Float)
    r2_score    = db.Column(db.Float)
    feature_names    = db.Column(db.JSON)
    hyperparameters  = db.Column(db.JSON)
    notes       = db.Column(db.Text)


class DamageConfig(db.Model):
    """Hasar düşüş oranları config tablosu — admin panelinden yönetilir."""
    __tablename__ = "damage_config"

    id          = db.Column(db.Integer, primary_key=True)
    key         = db.Column(db.String(50), unique=True, nullable=False)
    value       = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Varsayılan config değerleri
    DEFAULTS = {
        # Parça durumu baz skorları (her 10 birim = %8 düşüş)
        "severity_localpainted":  2.0,   # Lokal Boyalı
        "severity_painted":       5.0,   # Boyalı
        "severity_changed":      10.0,   # Değişen

        # Kritik parça çarpanları
        "weight_front_hood":      2.0,   # Ön Kaput
        "weight_roof":            2.0,   # Tavan
        "weight_rear_hood":       1.5,   # Arka Kaput
        "weight_front_right_door":1.1,   # Sağ Ön Kapı
        "weight_front_left_door": 1.1,   # Sol Ön Kapı
        "weight_rear_right_door": 1.0,   # Sağ Arka Kapı
        "weight_rear_left_door":  1.0,   # Sol Arka Kapı
        "weight_default":         1.0,   # Diğer parçalar (tampon, çamurluk)

        # Her 10 skor birimi = kaç % düşüş
        "drop_per_10_score":      8.0,   # %8

        # Maksimum düşüş oranı
        "max_drop_pct":          45.0,   # %45

        # Ağır hasar kaydı (parça bilgisi olmadan işaretlenince)
        "heavy_damage_score":    10.0,   # 1 değişen parça eşdeğeri
        # Ağır hasarda parça detayı yoksay — sabit oran uygula
        "heavy_damage_override": 0,      # 0=hayır, 1=evet
        "heavy_damage_fixed_pct":16.0,   # override=1 ise sabit %16 düşüş
    }

    def to_dict(self):
        return {"key": self.key, "value": self.value, "description": self.description}

    @classmethod
    def get_all(cls):
        """Tüm config değerlerini dict olarak döndür, eksikler için default kullan."""
        rows = {r.key: r.value for r in cls.query.all()}
        result = dict(cls.DEFAULTS)
        result.update(rows)
        return result
