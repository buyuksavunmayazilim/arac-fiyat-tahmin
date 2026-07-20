# BSY Araç Fiyat Tahmin Sistemi

## Proje Yapısı

```
arac-fiyat-tahmin/
├── run.py                  ← Flask + gunicorn giriş noktası
├── init_db.py              ← Tabloları oluşturur (migration gerekmez)
├── celery_worker.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── app/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── views.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── analytics.html
│   │   ├── compare.html
│   │   └── history.html
│   └── static/
│       ├── css/main.css
│       └── js/ (main, index, analytics, compare, history)
├── ml/
│   ├── __init__.py
│   ├── predictor.py
│   ├── train.py
│   └── models/            ← eğitilmiş .joblib dosyaları buraya gelir
└── migrations/
```

## Kurulum ve Başlatma

```bash
cd proje

# 2. Build ve başlat
sudo docker compose up --build -d

# 3. Web servisinin ayağa kalkmasını bekleyin (30-60 sn)
sudo docker compose ps

# 4. Tabloları oluştur  ← flask db upgrade KULLANMAYIN
sudo docker compose exec web python init_db.py

```

## Servis Durumu Kontrolü

```bash
sudo docker compose ps
sudo docker compose logs web       # web hataları
sudo docker compose logs worker    # celery hataları
sudo docker compose logs db        # postgres hataları
```

## Model Eğitimi

```bash
# Veriler DB'ye yüklendikten sonra
sudo docker compose exec web python ml/train.py
```

## API Endpoint'leri

| Endpoint | Method | Açıklama |
|---|---|---|
| `POST /api/predict` | POST | Fiyat tahmini + SHAP + benzer ilanlar |
| `POST /api/similar` | POST | Benzer araçlar |
| `POST /api/compare` | POST | İki araç karşılaştırma |
| `GET /api/history` | GET | Sorgu geçmişi |
| `GET /api/search` | GET | Araç arama/filtreleme |
| `GET /api/analytics/price-trend` | GET | Fiyat trendi |
| `GET /api/analytics/stats` | GET | Genel istatistikler |
| `GET /api/vehicle/<no>/price-history` | GET | İlan fiyat geçmişi |
| `GET /api/options` | GET | Form dropdown seçenekleri |
