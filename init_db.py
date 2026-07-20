"""
Sadece EKSİK tabloları oluşturur.
vehicles ve price tablolarına dokunmaz.

Kullanım: docker compose exec web python init_db.py
"""
from app import create_app, db
from app.models.models import QueryHistory, ModelMetadata, DamageConfig

app = create_app()

with app.app_context():
    QueryHistory.__table__.create(db.engine, checkfirst=True)
    ModelMetadata.__table__.create(db.engine, checkfirst=True)
    DamageConfig.__table__.create(db.engine, checkfirst=True)

    # Varsayılan config değerlerini yükle (henüz yoksa)
    existing = {r.key for r in DamageConfig.query.all()}
    added = 0
    desc_map = {
        "severity_localpainted":   "Lokal Boyalı baz skoru",
        "severity_painted":        "Boyalı baz skoru",
        "severity_changed":        "Değişen baz skoru",
        "weight_front_hood":       "Ön Kaput ağırlık çarpanı",
        "weight_roof":             "Tavan ağırlık çarpanı",
        "weight_rear_hood":        "Arka Kaput ağırlık çarpanı",
        "weight_front_right_door": "Sağ Ön Kapı ağırlık çarpanı",
        "weight_front_left_door":  "Sol Ön Kapı ağırlık çarpanı",
        "weight_rear_right_door":  "Sağ Arka Kapı ağırlık çarpanı",
        "weight_rear_left_door":   "Sol Arka Kapı ağırlık çarpanı",
        "weight_default":          "Diğer parçalar (tampon, çamurluk) ağırlığı",
        "drop_per_10_score":       "Her 10 skor birimi için fiyat düşüşü (%)",
        "max_drop_pct":            "Maksimum toplam fiyat düşüşü (%)",
        "heavy_damage_score":      "Parça bilgisi olmadan hasar kaydı skoru",
        "heavy_damage_override":   "Ağır hasarda parça detayını yoksay (0=hayır, 1=evet)",
        "heavy_damage_fixed_pct":  "Ağır hasar sabit düşüş oranı (% — override=1 ise)",
    }
    for key, value in DamageConfig.DEFAULTS.items():
        if key not in existing:
            db.session.add(DamageConfig(
                key=key, value=value,
                description=desc_map.get(key, key)
            ))
            added += 1
    db.session.commit()

    print("✓ Tablolar hazır:")
    print("  - queries")
    print("  - model_metadata")
    print(f"  - damage_config ({added} varsayılan değer eklendi)")
    print()
    print("  Dokunulmayan tablolar:")
    print("  - araclar")
    print("  - price")
