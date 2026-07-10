# Bedesten API Rate-Limit — Ölçüm Raporu

**Tarih:** 2026-07-10 · **Yöntem:** canlı `bedesten.adalet.gov.tr/mevzuat` üzerinde kontrollü deney
**Neden:** 4990 tebliğ × 2 istek çekilecek; kör backoff yerine ölçülmüş bir hız modeli gerekiyordu.

> **Özet:** Sunucu **sabit pencere** uyguluyor: **~10 istek / ~29-30 sn, IP başına.**
> İstek-arası gecikme **önemsiz**; pencere başına **sayı** önemli. En verimli sürdürülebilir
> strateji: **9 istek hızlıca at → 31 sn bekle** = **0.303 istek/sn**, sıfır 429.

---

## 1. Çürütülen varsayımlar

Kanun `fetch.py`'si "token-bucket, 10 istek, 17 sn cooldown" varsayıyordu. Ölçüm:

| Hipotez | Test | Sonuç |
|---|---|---|
| Sabit gecikme (0.5 sn) yeter | 0.5 sn arayla 30 istek | ❌ **11. istekte 429** (`Retry-After: 25`) |
| Yavaşlamak kurtarır (2.5 sn) | 2.5 sn arayla 16 istek | ❌ **Yine 11. istekte** 429 (`Retry-After: 5`) |
| Daha da yavaş (3.0 sn) | 3.0 sn arayla 40 istek | ❌ **12. istekte** 429 (34 sn'de) |
| Kova endpoint başına | tree kovasını doldur → html dene | ❌ **Global (IP)**: html de 429 |
| `Retry-After` abartılı | 429 sonrası 2 sn'de bir dene | ❌ **Dürüst**: 30 dedi → 30.3 sn'de açıldı |
| Kova kademeli dolar | 10 istek → T sn bekle → kaç geçer? | ❌ **Ya kapalı ya tam açık** |

**Kova doluş ölçümü** (10 istek attıktan sonra):

| Bekleme | Geçen istek |
|---|---|
| 5 sn | **0** |
| 10 sn | **10** (tam) |
| 20 sn | 10 (tavan) |

→ Token-bucket değil, **sabit pencere**. Aralığı 6× büyütmek (0.5 → 3.0 sn) hiçbir şeyi
değiştirmedi: her iki durumda da ~11-12. istekte duvar. Yani sunucu **ortalama hızı değil,
pencere içindeki istek sayısını** sayıyor.

---

## 2. Parti stratejisi — doğrulama

`N` istek hızlıca (0.15 sn arayla) → `T` sn bekle → tekrarla.

| N × T | Sonuç |
|---|---|
| 10 × 26 sn | ❌ 2. turda 429 (`Retry-After: 3` → 26 sn yetmedi, ~29 gerekiyordu) |
| **9 × 31 sn** | ✅ **54 istek boyunca sıfır 429** — 0.327 i/s |

> ⚠️ **Kısa testler yanıltır.** 3 turluk taramada `3 istek × 1 sn` (2.54 i/s) "kazanan"
> görünüyordu; 5 tura çıkarınca 4. turda çöktü. `2 × 0.5 sn` de 5 tur dayandı ama uzun koşuda
> (100 ardışık istek) **11. istekte** 429 yedi — çünkü test toplam istek sayısı bakımından adil
> değildi. **Her ayarı sabit sayıda istekle test edin.**

---

## 3. Temkinli vs agresif — adil kıyas

Her strateji **60 başarılı istek** atacak şekilde ölçüldü:

| Strateji | Süre | 429 | Hız | 9980 istek |
|---|---|---|---|---|
| **A — temkinli** (9 istek + 31 sn) | 198 sn | 0 | **0.303 i/s** | **9.1 saat** |
| B — agresif (durmadan at, 429'da `Retry-After` bekle) | 215 sn | 7 | 0.279 i/s | 9.9 saat |

**Temkinli %9 daha hızlı.** 429 "ucuz" değil: her ceza ~27-30 sn. Sunucunun kotayı kendi
söylemesine güvenmek (agresif) kazançlı değil.

---

## 4. Uygulama (`src/teblig/fetch.py`)

```python
_PARTI     = 9      # pencere başına istek (kota 10; 1 pay)
_PARTI_ICI = 0.15   # parti içinde istek-arası (nezaket)
_PENCERE   = 31.0   # parti sonrası bekleme (ölçülen pencere ~29-30 sn + pay)
```

`_HizSinirlayici` bu partiyi uygular. 429 görülürse `geri_cekil()` parti boyutunu 1 azaltır
(min 3) — aynı koşuda tekrar 429 yememek için. 429'da `Retry-After` okunur ve tam o kadar
beklenir (dürüst olduğu ölçüldü; erken deneme boşuna).

---

## 5. Ayrı bir tuzak: `pageSize` tavanı 20

`searchDocuments` isteğinde `pageSize > 20` verilirse sunucu **HTTP 200** döner ama gövdede:

```json
{"metadata": {"FMTY": "ERROR", "FMTE": "data.pageSize=Kayıt sayısı 20'den fazla olamaz"}}
```

`mevzuatList` boş gelir → **sessiz 0-sonuç.** Bu yüzden `fetch_teblig_ids` artık
`metadata.FMTY != "SUCCESS"` ise `RuntimeError` fırlatır. (Aynı kontrol `fetch_html` /
`fetch_tree`'de zaten vardı.)

Sonuç: 4990 tebliğ / 20 = **250 sayfa** → id listesi tek başına ~14 dk (bir kez, cache'lenir).

---

## 6. Maliyet (ölçülen 0.303 istek/sn ile)

| İş | İstek | Süre |
|---|---|---|
| id listesi (250 sayfa) | 250 | ~14 dk *(cache'lenir)* |
| 4990 tebliğ × (HTML + ağaç) | 9.980 | **~9.1 saat** |
| 4990 tebliğ × yalnız HTML | 4.990 | **~4.6 saat** |

Çekim **devam-güvenlidir**: cache'li dosyalar için istek atılmaz, kesinti sonrası kaldığı
yerden sürer.

---

## 7. Kanun tarafına etkisi

`src/kanun/fetch.py` **değiştirilmedi** (ADR-0014: türler arası sıfır kod paylaşımı). 916
kanunu sıfır kayıpla çekmişti; dokunmak regresyon riski. Bu ölçüm yalnız `src/teblig/fetch.py`'ye
uygulandı. Kanun cache'i yeniden çekilecekse aynı parti modeli oraya da kopyalanabilir
(~1832 istek → 52 dk yerine ~1.7 saat; ölçülen model daha yavaş ama 429'suz).
