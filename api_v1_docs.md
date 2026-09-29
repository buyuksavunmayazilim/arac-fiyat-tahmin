# Araç Fiyat Tahmin API'si — v1

Araç bilgilerini gönderip tahmini piyasa değeri (ve istenirse kâr/valör) alan
HTTP JSON servisi. Kimlik doğrulamalı, durumsuz (stateless).

- **Temel URL:** `https://SUNUCU_ADRESI` (örn. dahili: `http://SUNUCU_IP:5007`)
- **Format:** JSON (istek ve yanıt)
- **Kimlik:** her istekte `X-API-Key` başlığı zorunlu

---

## 1. Kimlik doğrulama

Her isteğe API anahtarını başlık olarak ekleyin:

```
X-API-Key: <SİZE_VERİLEN_ANAHTAR>
```

Anahtar eksik/yanlışsa `401` döner. Anahtarı istemci koduna (özellikle tarayıcı/JS)
gömmeyin; çağrıyı mümkünse kendi sunucunuz üzerinden yapın.

---

## 2. Uç noktalar

| Method | Yol | Açıklama | Kimlik |
|---|---|---|---|
| `POST` | `/api/v1/predict` | Araç fiyat tahmini | Gerekli |
| `GET`  | `/api/v1/options` | Desteklenen marka listesi | Gerekli |
| `GET`  | `/api/v1/options/series` | Markaya göre seri listesi | Gerekli |
| `GET`  | `/api/v1/options/models` | Marka+seri'ye göre model listesi | Gerekli |
| `GET`  | `/api/v1/options/attributes` | Seçilen araca göre yakıt/vites/yıl/kasa | Gerekli |
| `GET`  | `/api/v1/health`  | Servis/model durumu | Gerekmez |

> Seçenek (options) uçları yalnızca **desteklenen/güvenilir** araçları döndürür — §6.

---

## 3. `POST /api/v1/predict`

### İstek

- **Method:** `POST`
- **URL:** `https://SUNUCU/api/v1/predict`
- **Başlıklar:** `Content-Type: application/json` ve `X-API-Key: <ANAHTAR>`
- **Gövde:** JSON (aşağıdaki alanlar)

Alan adlarını **İngilizce** veya **Türkçe** gönderebilirsiniz; ikisi de kabul edilir.

**Zorunlu alanlar:** `brand`, `vehicle_type`, `version`, `model_year`,
`last_odometer_km`, `fuel_type`, `transmission`. Biri bile eksikse istek `400`
döner ve hangi alan(lar)ın eksik olduğunu bildirir.

| İngilizce alan | Türkçe karşılığı | Zorunlu | Tip | Açıklama |
|---|---|---|---|---|
| `brand` | `marka` | **Evet** | string | Marka. Örn: `Renault`, `Mercedes`, `BMW` |
| `vehicle_type` | `seri` | **Evet** | string | Seri. Örn: `Clio`, `GLC`, `320` |
| `version` | `model` | **Evet** | string | Donanım/versiyon. Örn: `1.5 dCi Touch` |
| `model_year` | `model_yili` | **Evet** | integer | Model yılı. Örn: `2021` |
| `last_odometer_km` | `son_km` | **Evet** | integer | Kilometre. Örn: `78000` (0 km geçerli) |
| `fuel_type` | `yakit_tipi` | **Evet** | string | Bkz. geçerli değerler |
| `transmission` | `vites_tipi` | **Evet** | string | Bkz. geçerli değerler |
| `body_type` | — | Hayır | string | Kasa tipi (opsiyonel) |
| `purchase_price` | `alis_fiyati` | Hayır | number | Verilirse yanıta **kâr + B2B** eklenir |
| `purchase_invoice_date` | `alis_tarihi` | Hayır | string (`YYYY-MM-DD`) | Valör için alış tarihi |
| `annual_rate_pct` | — | Hayır | number | Verilirse yanıta **valör** eklenir (yıllık faiz %) |
| `damage_registered` | — | Hayır | bool | Ağır hasar kaydı var mı (bkz. Hasar durumları) |
| *(13 parça alanı)* | — | Hayır | string | Parça hasar durumları (bkz. Hasar durumları) |

> `last_odometer_km` yerine `odometer_km` de kabul edilir. Zorunlu alanların geçerli
> değerlerini `/api/v1/options*` uçlarından çekip formu doldurmanız önerilir (§6).

### Geçerli değerler

`fuel_type` ve `transmission` için **kaynak `/api/v1/options/attributes` ucudur** (§6) —
o uç seçilen araçta gerçekten var olan değerleri döndürür. Sık görülen değerler:

- **fuel_type / yakit_tipi:** `Benzinli`, `Dizel`, `Hibrit`, `Elektrikli`, `Benzin & LPG`
- **transmission / vites_tipi:** `Otomatik`, `Manuel`

Büyük/küçük harf önemli değildir (sistem normalize eder). Marka/seri yazımında bazı
yaygın farklar otomatik düzeltilir (örn. `MERCEDES` → `Mercedes-Benz`, BMW `320` →
`3 Serisi`), böylece doğru modele yönlenir.

### Hasar durumları (opsiyonel)

Hasar bilgisi göndermezseniz araç **hasarsız** kabul edilir. Göndermek isterseniz iki
tür alan var:

**1) `damage_registered`** (bool) — ağır/kayıtlı hasar var mı. `true` ise, parça
detayından bağımsız olarak sabit bir düşüş uygulanır.

**2) Parça durumları** — aşağıdaki 13 parçanın her biri için durum. Göndermediğiniz
parça `orijinal` sayılır. Her parça için geçerli değerler:
`orijinal` (varsayılan), `lokal boyalı`, `boyalı`, `değişen`.
(İngilizce/kodlu karşılıkları da kabul edilir: `original` / `localpainted` / `painted`
/ `changed`.)

| Alan (gönderilecek anahtar) | Parça |
|---|---|
| `front_bumper` | Ön Tampon |
| `front_hood` | Ön Kaput |
| `roof` | Tavan |
| `front_right_mudguard` | Sağ Ön Çamurluk |
| `front_right_door` | Sağ Ön Kapı |
| `rear_right_door` | Sağ Arka Kapı |
| `rear_right_mudguard` | Sağ Arka Çamurluk |
| `front_left_mudguard` | Sol Ön Çamurluk |
| `front_left_door` | Sol Ön Kapı |
| `rear_left_door` | Sol Arka Kapı |
| `rear_left_mudguard` | Sol Arka Çamurluk |
| `rear_hood` | Arka Kaput |
| `rear_bumper` | Arka Tampon |

Hasar bilgisi verilirse `predicted_price` zaten düşülmüş fiyattır **ve** yanıta ayrıca
`damage_effect` nesnesi eklenir (hasarlı/hasarsız fiyat farkı + en etkili parçalar).

### İstek örneği — hasarlı araç

```bash
curl -X POST https://SUNUCU/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <ANAHTAR>" \
  -d '{
    "brand": "Renault",
    "vehicle_type": "Clio",
    "version": "1.0 TCe Evolution",
    "model_year": 2022,
    "last_odometer_km": 45000,
    "fuel_type": "Benzinli",
    "transmission": "Otomatik",
    "roof": "değişen",
    "front_hood": "boyalı",
    "front_right_door": "lokal boyalı"
  }'
```

### İstek örneği — zorunlu alanlar (curl)

```bash
curl -X POST https://SUNUCU/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <ANAHTAR>" \
  -d '{
    "brand": "Renault",
    "vehicle_type": "Clio",
    "version": "1.0 TCe Evolution",
    "model_year": 2022,
    "last_odometer_km": 45000,
    "fuel_type": "Benzinli",
    "transmission": "Otomatik"
  }'
```

### İstek örneği — tam (kâr + valör dahil)

```bash
curl -X POST https://SUNUCU/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <ANAHTAR>" \
  -d '{
    "brand": "Mercedes",
    "vehicle_type": "GLC",
    "version": "GLC 300",
    "model_year": 2025,
    "last_odometer_km": 9000,
    "fuel_type": "Benzinli",
    "transmission": "Otomatik",
    "purchase_price": 4200000,
    "purchase_invoice_date": "2025-03-15",
    "annual_rate_pct": 45
  }'
```

### İstek örneği — JavaScript (fetch)

```javascript
const res = await fetch("https://SUNUCU/api/v1/predict", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "<ANAHTAR>",
  },
  body: JSON.stringify({
    brand: "Renault",
    vehicle_type: "Clio",
    version: "1.0 TCe Evolution",
    model_year: 2022,
    last_odometer_km: 45000,
    fuel_type: "Benzinli",
    transmission: "Otomatik",
    // opsiyonel:
    // purchase_price: 850000, annual_rate_pct: 45,
  }),
});
const data = await res.json();
if (!res.ok) throw new Error(data.error);
if (data.insufficient_data) {
  console.log("Bu araç için yeterli veri yok — tahmin üretilemedi");
} else {
  console.log(data.predicted_price, data.dusuk_guven, data.prediction_source);
}
```

### İstek örneği — Python (requests)

```python
import requests

r = requests.post(
    "https://SUNUCU/api/v1/predict",
    headers={"X-API-Key": "<ANAHTAR>"},
    json={
        "brand": "Renault",
        "vehicle_type": "Clio",
        "version": "1.0 TCe Evolution",
        "model_year": 2022,
        "last_odometer_km": 45000,
        "fuel_type": "Benzinli",
        "transmission": "Otomatik",
    },
)
r.raise_for_status()
data = r.json()
if data["insufficient_data"]:
    print("Bu araç için yeterli veri yok — tahmin üretilemedi")
else:
    print(data["predicted_price"], data["prediction_source"])
```

---

## 4. Yanıt

### Her zaman dönen alanlar

| Alan | Tip | Açıklama |
|---|---|---|
| `success` | bool | `true` |
| `predicted_price` | number \| **null** | Tahmini piyasa (B2C) değeri, TL — en yakın 1.000'e yuvarlı. **Yeterli veri yoksa `null` döner** (bkz. `insufficient_data`, §5) |
| `insufficient_data` | bool | `true` ise sistem bu araç için güvenilir bir fiyat **üretemedi** → `predicted_price` `null`'dır (bkz. §5) |
| `prediction_source` | string | Tahminin hangi katmandan geldiği: `group_model`, `trim_median`, `segment_median` veya `none` (bkz. §5) |
| `price_lower` | number \| null | Tahmin aralığı alt sınır (fiyat üretilemezse `null`) |
| `price_upper` | number \| null | Tahmin aralığı üst sınır (fiyat üretilemezse `null`) |
| `confidence_pct` | number | Model güven yüzdesi (0–100) |
| `model_group` | string | Kullanılan model grubu (örn. `mercedes-benz__glc__ust`). Bkz. §5 |
| `dusuk_guven` | bool | `true` ise tahmine temkinli yaklaşın (bkz. §5) |
| `guven_sebebi` | string \| null | Düşük güvenin / veri yetersizliğinin sebebi (yoksa `null`) |
| `benzer_ilan_sayisi` | number | Bu araç için eğitim verisindeki benzer ilan sayısı |
| `input` | object | Sistemin yorumladığı normalize girdi (kontrol için) |

> **Önemli:** `insufficient_data: true` bir **hata değildir** — HTTP `200` ile döner ve
> `success: true`'dur, sadece `predicted_price` `null`'dır. Yani "araç tanındı ama
> elimizde güvenilir fiyat üretecek kadar benzer ilan yok" demektir. İstemci tarafında
> önce `insufficient_data`'yı kontrol edip, `true` ise kullanıcıya fiyat yerine
> "bu araç için yeterli veri yok" mesajı gösterin. `purchase_price`/`annual_rate_pct`
> gönderilmiş olsa bile fiyat `null` olduğunda kâr/valör blokları **hesaplanmaz**.

### `purchase_price` gönderilirse ek olarak

| Alan | Açıklama |
|---|---|
| `b2c_fiyat` | B2C tahmini satış (= `predicted_price`) |
| `b2b_fiyat` | B2B tahmini satış (B2C × 0.90) |
| `alis_fiyati` | Gönderdiğiniz alış fiyatı |
| `b2c_kar` / `b2c_kar_pct` | B2C kâr (TL) ve yüzdesi |
| `b2b_kar` / `b2b_kar_pct` | B2B kâr (TL) ve yüzdesi |

### `annual_rate_pct` gönderilirse ek olarak

`valor` nesnesi ve `annual_rate_pct`. `valor` içeriği:

| Alan | Açıklama |
|---|---|
| `min_hold_days` | Minimum elde tutma süresi (gün, sabit 185) |
| `alis_tarihi` | Alış tarihi (gönderdiyseniz) |
| `en_erken_satis` | Alış + 185 gün |
| `kalan_gun` | Satışa kalan gün |
| `satilabilir` | Bugün satılabilir mi (bool) |
| `valorlu` | İleri tarihli (valörlü) satış gerekir mi (bool) |
| `bugunku_fiyat` | Bugünkü değer |
| `hedef_satis_fiyati` | Kalan gün sonrası faizli hedef fiyat |
| `valorlu_bugun_fiyati` | Bugün sunulabilecek rasyonel fiyat |
| `max_indirim_tl` / `max_indirim_pct` | Hedeften uygulanabilecek maksimum indirim |

### `damage_registered` veya parça durumu gönderilirse ek olarak

`damage_effect` nesnesi döner:

| Alan | Açıklama |
|---|---|
| `with_damage` | Hasar dikkate alınmış fiyat (= `predicted_price`) |
| `without_damage` | Hasarsız olsaydı fiyat |
| `price_impact_tl` / `price_impact_pct` | Hasarın fiyat etkisi (TL / %) |
| `top_damaged_parts` | Fiyatı en çok etkileyen parçalar (etiketli) |
| `is_heavy_damage` | Ağır hasar kaydı mı |

### Örnek yanıt

```json
{
  "success": true,
  "predicted_price": 5641000,
  "insufficient_data": false,
  "prediction_source": "group_model",
  "price_lower": 5379000,
  "price_upper": 6239000,
  "confidence_pct": 84.8,
  "model_group": "mercedes-benz__glc__ust",
  "dusuk_guven": false,
  "guven_sebebi": null,
  "benzer_ilan_sayisi": 328,
  "input": {
    "marka": "Mercedes-Benz", "seri": "Glc", "model": "GLC 300",
    "model_year": 2025, "km": 9000, "fueloil": "Benzin", "gear": "Otomatik"
  },
  "b2c_fiyat": 5641000,
  "b2b_fiyat": 5077000,
  "alis_fiyati": 4200000,
  "b2c_kar": 1441000,
  "b2c_kar_pct": 34.3,
  "b2b_kar": 877000,
  "b2b_kar_pct": 20.9,
  "valor": {
    "min_hold_days": 185,
    "alis_tarihi": "2025-03-15",
    "en_erken_satis": "2025-09-16",
    "kalan_gun": 0,
    "satilabilir": true,
    "valorlu": false,
    "bugunku_fiyat": 5641000,
    "hedef_satis_fiyati": null,
    "valorlu_bugun_fiyati": null,
    "max_indirim_tl": 0,
    "max_indirim_pct": 0
  },
  "annual_rate_pct": 45
}
```

### Örnek yanıt — fiyat üretilemedi (yeterli veri yok)

Araç tanınır ama elde güvenilir fiyat üretecek kadar benzer ilan yoksa (örn. çok yeni
veya kapsam dışı bir model), HTTP `200` ile şu döner:

```json
{
  "success": true,
  "predicted_price": null,
  "insufficient_data": true,
  "prediction_source": "none",
  "price_lower": null,
  "price_upper": null,
  "confidence_pct": null,
  "model_group": "citroen__c3",
  "dusuk_guven": true,
  "guven_sebebi": "Yeterli veri yok — tahmin üretilemedi",
  "benzer_ilan_sayisi": 0,
  "input": {
    "marka": "Citroen", "seri": "C3", "model": "E Max",
    "model_year": 2025, "km": 1000, "fueloil": "Elektrikli", "gear": "Otomatik"
  }
}
```

> `purchase_price` / `annual_rate_pct` gönderilmiş olsa bile, fiyat `null` olduğunda
> `b2c_kar`, `b2b_fiyat`, `valor` gibi bloklar **eklenmez** (hesaplanacak fiyat yok).

---

## 5. Güvenilirlik — "hangi araçlar" iyi tahmin alır?

Servis, elindeki veri güvenilir bir fiyat üretmeye **yetiyorsa** tahmin döndürür;
yetmiyorsa uydurma bir sayı üretmek yerine `predicted_price: null` +
`insufficient_data: true` döner. Yani iki durumu ayırt edersiniz:

- **Fiyat üretildi** (`insufficient_data: false`, `predicted_price` bir sayı) —
  `dusuk_guven` ile ince ayarı yaparsınız:
  - `dusuk_guven: false` → tahmin güvenilir.
  - `dusuk_guven: true` → fiyat üretildi ama temkinli yaklaşın (az sayıda benzer ilan,
    dolaylı katmandan gelen medyan vb.). `guven_sebebi` sebebi, `benzer_ilan_sayisi`
    kaç benzer ilan bulunduğunu verir. Kullanıcıya "tahmini değer, düşük güven" olarak gösterin.
- **Fiyat üretilemedi** (`insufficient_data: true`, `predicted_price: null`) — araç
  tanındı ama elde güvenilir fiyat üretecek kadar veri yok. `prediction_source: "none"`
  gelir. Kullanıcıya fiyat yerine "yeterli veri yok" mesajı gösterin.

### `prediction_source` — tahmin hangi katmandan geldi?

Sistem, aracın donanımına/verisine göre 3 katmanlı bir çözümleyici kullanır ve
tahminin hangi katmandan çıktığını `prediction_source` ile bildirir:

| Değer | Anlamı | Güven |
|---|---|---|
| `group_model` | O marka+seri (+donanım segmenti) için eğitilmiş özel XGBoost modeli kullanıldı | En yüksek |
| `trim_median` | Model bazlı yeterli veri yok; aynı donanım/yıl grubunun (km bandına göre daraltılmış) gerçek ilan **medyanı** kullanıldı | Orta |
| `segment_median` | Donanım segmentinin (baz/üst) medyanı kullanıldı | Orta-düşük |
| `none` | Hiçbir katman güvenilir sonuç veremedi → `insufficient_data: true`, `predicted_price: null` | — |

> `model_group` alanı kullanılan grup anahtarını teknik düzeyde verir
> (örn. `mercedes-benz__glc__ust`); asıl güven sinyali `prediction_source` + `dusuk_guven`'dir.

> **Not:** `/api/v1/options*` uçlarından seçilen araçlar zaten güvenilirdir
> (`dusuk_guven` her zaman `false` gelir). `dusuk_guven` asıl olarak kullanıcı
> marka/seri'yi **elle/serbest** girdiğinde işe yarar.

### Desteklenen marka+seri listesi

Liste zamanla (model yeniden eğitildikçe) değişir, o yüzden **sabit gömmeyin** —
canlı listeyi §6'daki seçenek uçlarından (`/api/v1/options`) alın. O uçlar zaten
**yalnızca desteklenen (güvenilir) araçları** döndürür; formunuzu bu listelerle
doldurursanız kullanıcı hep güvenilir tahmin alır.

Yaklaşık kapsam: Renault (Clio, Megane, Duster, Austral…), BMW (3/5 Serisi, X1, X3,
iX1…), Mercedes-Benz (GLC, GLA, GLB, EQB, C Serisi…), Audi (A3, Q3, A5…), Peugeot
(2008, 3008…), Toyota Corolla, VW (Golf, Polo), Skoda, Dacia Sandero, Volvo XC90 vb.
Yaygın binek/SUV modellerinin çoğu kapsamdadır; çok yeni, çok lüks veya ticari
araçlar (ör. bazı Citroen, Ferrari, Maserati, ticari van) kapsam dışıdır.

---

## 6. Form seçenekleri (dropdown uçları)

Tahmin formunu (marka → seri → model kaskadı + yıl/yakıt/vites) doldurmak için
seçenek uçları. **Hepsi yalnızca desteklenen (güvenilir) araçları döndürür** — yani
bu listelerden seçilen her araç güvenilir tahmin alır. Hepsi `X-API-Key` gerektirir.

### `GET /api/v1/options`
Desteklenen marka listesi (formun ilk dropdown'ı).
```bash
curl -H "X-API-Key: <ANAHTAR>" https://SUNUCU/api/v1/options
```
```json
{ "markas": ["Audi", "BMW", "Dacia", "Mercedes-Benz", "Renault", "Toyota", "..."] }
```

### `GET /api/v1/options/series?marka=<marka>`
Seçilen markanın desteklenen serileri.
```bash
curl -H "X-API-Key: <ANAHTAR>" "https://SUNUCU/api/v1/options/series?marka=Mercedes-Benz"
```
```json
{ "marka": "Mercedes-Benz", "series": ["C Serisi", "EQB", "GLA", "GLB", "GLC"] }
```

### `GET /api/v1/options/models?marka=<marka>&seri=<seri>`
Seçilen marka+seri için model/versiyon listesi.
```bash
curl -H "X-API-Key: <ANAHTAR>" "https://SUNUCU/api/v1/options/models?marka=Mercedes-Benz&seri=GLC"
```
```json
{ "marka": "Mercedes-Benz", "seri": "GLC", "models": ["GLC 220 d", "GLC 300", "..."] }
```

### `GET /api/v1/options/attributes?marka=<marka>&seri=<seri>[&model=<model>]`
Seçilen araçta **gerçekten var olan** yakıt/vites/yıl/kasa değerleri. Yakıt ve vites
**global değildir** — bu uçtan gelir. Böylece örneğin elektrikli bir modelde yakıt
listesinde LPG/benzin çıkmaz, sadece geçerli değerler görünür.
`marka`+`seri` zorunlu; `model` verilirse liste o versiyona göre daha da daralır.
```bash
curl -H "X-API-Key: <ANAHTAR>" "https://SUNUCU/api/v1/options/attributes?marka=Mercedes-Benz&seri=EQB"
```
```json
{
  "marka": "Mercedes-Benz", "seri": "EQB", "model": null,
  "fuel_types": ["Elektrikli"],
  "transmissions": ["Otomatik"],
  "body_types": ["SUV"],
  "years": [2026, 2025, 2024]
}
```

**Form akışı (önerilen):**
1. Sayfa açılışında `GET /api/v1/options` → **marka** dropdown'unu doldur.
2. Marka seçilince `GET /api/v1/options/series?marka=...` → **seri** dropdown'u.
3. Seri seçilince `GET /api/v1/options/models?marka=...&seri=...` → **model** dropdown'u.
4. Model seçilince `GET /api/v1/options/attributes?marka=...&seri=...&model=...`
   → **yakıt, vites, model yılı, kasa** dropdown'larını doldur.
   (Model henüz seçilmediyse `model` parametresini atlayıp marka+seri düzeyinde de çağırabilirsiniz.)
5. Kullanıcı formu tamamlayıp `POST /api/v1/predict` çağırır.

> Bu uçlardan gelen değerleri `predict`'e aynen gönderin. Yakıt/vites'i attributes
> ucundan doldurmak, elektrikli araca LPG gibi geçersiz kombinasyonları en baştan engeller.

---

## 7. Hata kodları

| HTTP | Örnek gövde | Anlamı |
|---|---|---|
| `400` | `{"error":"JSON body gerekli"}` | Gövde boş veya JSON değil |
| `400` | `{"error":"Zorunlu alan(lar) eksik: version (model), model_year (model_yili)"}` | Zorunlu alan eksik (hangileri listelenir) |
| `401` | `{"error":"Geçersiz veya eksik API anahtarı"}` | `X-API-Key` yok/yanlış |
| `503` | `{"error":"API anahtarı sunucuda yapılandırılmamış"}` | Sunucuda anahtar tanımlı değil |
| `503` | `{"error":"Model henüz eğitilmemiş"}` | Model yüklü değil |
| `500` | `{"error":"Tahmin hatası: ..."}` | Beklenmeyen hata |

Başarılı yanıtlarda `success: true` bulunur; hata yanıtlarında `error` alanı olur.

---

## 8. Sağlık kontrolü

```bash
curl https://SUNUCU/api/v1/health
# -> {"status":"ok","model_loaded":true}
```

Kimlik gerektirmez. İzleme (monitoring) için kullanılabilir.

---

## 9. Notlar

- Tüm fiyatlar TL ve en yakın **1.000**'e yuvarlanır.
- B2B fiyatı = B2C × **0.90** (yapılandırılabilir).
- Valör kuralı: araç alış tarihinden **185 gün** sonra "satışa hazır" sayılır.
- Servis durumsuzdur; her istek bağımsızdır, oturum/çerez yoktur.
- `input` alanını her zaman kontrol edin — sistemin marka/seri/yılı nasıl
  yorumladığını gösterir; beklenmedik bir tahminde ilk buraya bakın.
- **"Fiyat gelmedi" bir hata değildir:** `insufficient_data: true` + `predicted_price: null`
  HTTP `200`/`success: true` ile döner. İstemcide bunu `4xx`/`5xx` gibi ele almayın;
  önce `insufficient_data`'yı kontrol edip fiyat yerine "yeterli veri yok" gösterin.
- Fiyat, dahili tahminle aynı 3 katmanlı çözümleyiciden gelir
  (`group_model` → `trim_median` → `segment_median`), böylece dışa açık API ile
  panel içi tahmin **birebir aynı** sonucu üretir.