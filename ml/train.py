"""
Model eğitim scripti — grup bazlı.
Kullanım: docker compose exec web python ml/train.py
"""
import sys, os, logging, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def train_from_db():
    from app import create_app, db
    from app.models import Vehicle
    from app.models.models import ModelMetadata, _parse_price, _parse_int
    from ml.predictor import VehiclePricePredictor
    import pandas as pd

    app = create_app()
    with app.app_context():
        logger.info("Veritabanından araç verileri çekiliyor...")
        vehicles = db.session.query(Vehicle).filter(
            Vehicle.price.isnot(None),
            Vehicle.price != '',
            Vehicle.marka.isnot(None),
        ).all()
        logger.info(f"{len(vehicles)} araç bulundu.")

        if len(vehicles) < 50:
            logger.error("Yetersiz veri.")
            return

        records = []
        for v in vehicles:
            records.append({
                "no":           v.no,
                "marka":        v.marka,
                "seri":         v.seri,
                "model":        v.model,
                "model_year":   _parse_int(v.model_year),
                "fueloil":      v.fueloil,
                "gear":         v.gear,
                "car_status":   v.car_status,
                "km":           _parse_int(v.km),
                "car_type":     v.car_type,
                "drive":        v.drive,
                "color":        v.color,
                "plate":        v.plate,
                "whois":        v.whois,
                "damage_registered": v.damage_registered,
                "price":        _parse_price(v.price),  # float — sadece bir kez parse
                "front_bumper": v.front_bumper,
                "front_hood":   v.front_hood,
                "roof":         v.roof,
                "front_right_mudguard": v.front_right_mudguard,
                "front_right_door":     v.front_right_door,
                "rear_right_door":      v.rear_right_door,
                "rear_right_mudguard":  v.rear_right_mudguard,
                "front_left_mudguard":  v.front_left_mudguard,
                "front_left_door":      v.front_left_door,
                "rear_left_door":       v.rear_left_door,
                "rear_left_mudguard":   v.rear_left_mudguard,
                "rear_hood":    v.rear_hood,
                "rear_bumper":  v.rear_bumper,
            })

        df = pd.DataFrame(records)
        logger.info(f"DataFrame: {df.shape} — Fiyat örnekleri: {df['price'].dropna().head(3).tolist()}")

        predictor = VehiclePricePredictor()
        metrics = predictor.train(df)

        # Metadata kaydet
        version = datetime.datetime.now().strftime("v%Y%m%d_%H%M")
        db.session.query(ModelMetadata).filter_by(is_active=True).update({"is_active": False})
        meta = ModelMetadata(
            version=version,
            is_active=True,
            model_path="ml/models/",
            train_samples=metrics["train_samples"],
            rmse=metrics["rmse"],
            mae=metrics["mae"],
            r2_score=metrics["r2"],
            feature_names={"groups": list(metrics.get("group_metrics", {}).keys())},
            hyperparameters={"n_estimators": 1000, "learning_rate": 0.05,
                             "group_count": metrics.get("group_count", 0)},
            notes=f"{metrics.get('group_count',0)} grup modeli + genel model"
        )
        db.session.add(meta)
        db.session.commit()
        logger.info(f"✓ Model kaydedildi: {version}")
        logger.info(f"  Genel — RMSE:{metrics['rmse']:.4f}  R²:{metrics['r2']:.4f}")

        for gkey, gm in metrics.get("group_metrics", {}).items():
            if gkey != "__general__":
                logger.info(f"  [{gkey}] RMSE:{gm['rmse']:.4f}  R²:{gm['r2']:.4f}  n={gm['train_samples']}")
        return metrics


if __name__ == "__main__":
    train_from_db()
