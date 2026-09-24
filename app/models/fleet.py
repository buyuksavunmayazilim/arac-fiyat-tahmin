"""
Filo araçları — uzak/prod `vehicles` tablosu (salt okunur).

Bu model, eski `filo_arac_master` (FiloArac) ile *drop-in uyumlu* olacak şekilde
yazılmıştır: ORM attribute adları Türkçe (marka, seri, alis_fiyati...), ama her biri
`vehicles` tablosundaki gerçek İngilizce kolona map'lenir. Böylece BFL route'larındaki
mevcut sorgu/filtre/valör kodu neredeyse hiç değişmeden çalışır.

Bağlantı: ayrı bir SQLAlchemy "fleet" bind'i kullanır. Aynı DB ise FLEET_DATABASE_URL
= DATABASE_URL verilir; ayrı DB ise farklı verilir (bkz. app/__init__.py).
"""

from app import db


class FleetVehicle(db.Model):
    """Güncel filo araçları — `vehicles` tablosu (fleet bind, salt okunur)."""

    __tablename__ = "vehicles"
    __bind_key__ = "fleet"

    # ── Kimlik ───────────────────────────────────────────────────────────────
    id          = db.Column("id", db.BigInteger, primary_key=True)
    plaka       = db.Column("plate", db.String(20), index=True)
    plaka_durum = db.Column("plate_status", db.String(50), index=True)
    is_active   = db.Column("is_active", db.Boolean)

    # ── Araç bilgileri (tahmin motoru bunları kullanır) ──────────────────────
    marka       = db.Column("brand", db.String(100), index=True)
    seri        = db.Column("vehicle_type", db.String(100), index=True)   # eski "Araç Tip" = seri
    model       = db.Column("version", db.Text)
    model_yili  = db.Column("model", db.String) 
    renk        = db.Column("color", db.String(50))
    yakit_tipi  = db.Column("fuel_type", db.String(50))
    vites_tipi  = db.Column("transmission", db.String(50))

    # ── Kilometre ────────────────────────────────────────────────────────────
    son_km        = db.Column("last_odometer_km", db.Integer)
    son_km_tarihi = db.Column("last_odometer_date", db.Date)

    # ── Alış (kâr + valör için) ──────────────────────────────────────────────
    alis_fiyati = db.Column("purchase_price", db.Numeric)
    alis_tarihi = db.Column("purchase_invoice_date", db.Date)

    # ── İsteğe bağlı ek alanlar (filtre/segment için işine yarayabilir) ───────
    vehicle_segment = db.Column("vehicle_segment", db.String(50))
    source_type     = db.Column("source_type", db.String(50))

    # NOT: `vehicles` tablosunda cekis_tipi ve hasar_adedi karşılığı yok.
    # BFL zaten hasarı dikkate almıyor (damage_registered=False), sorun değil.

    def to_dict(self):
        """FiloArac.to_dict() ile aynı anahtarları döndürür → BFL route'ları aynen çalışır."""
        return {
            "id":          self.id,
            "plaka":       self.plaka,
            "plaka_durum": self.plaka_durum,
            "marka":       self.marka,
            "seri":        self.seri,
            "model":       self.model,
            "model_yili":  int(self.model_yili) if (self.model_yili and str(self.model_yili).strip().isdigit()) else None,
            "renk":        self.renk,
            "yakit_tipi":  self.yakit_tipi,
            "vites_tipi":  self.vites_tipi,
            "cekis_tipi":  None,   # vehicles tablosunda yok
            "son_km":      self.son_km,
            "alis_fiyati": float(self.alis_fiyati) if self.alis_fiyati is not None else None,
            "alis_tarihi": self.alis_tarihi.isoformat() if self.alis_tarihi else None,
            "hasar_adedi": 0,      # vehicles tablosunda tutulmuyor
            "vehicle_segment": self.vehicle_segment,
        }

    def __repr__(self):
        return f"<FleetVehicle {self.plaka} {self.marka} {self.model} {self.model_yili}>"