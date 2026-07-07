# Korpus ↔ madde_gen_prompted.jsonl — Tam Karşılaştırma & Kaynak-Doğrulamalı Hakemlik

> Tarih: 2026-07-07 · Mod: **salt analiz (fix yok, korpusa dokunulmadı)**
> Kaynaklar: `data/corpus/korpus.jsonl` (biz, 31.422 chunk) vs `altınset/madde_gen_prompted.jsonl` (GEN, 45.399 kayıt).
> Yöntem: madde-seviyesi normalize eşleştirme → içerik kovaları → 3 paralel hakem agent (Opus 4.8) mevzuat-mcp ile gerçek kanuna baktı → ham-veri ile halüsinasyon-eleme.

---

## 1. Sayısal Temel

| Ölçüt | GEN | KOR (biz) | Sonuç |
|---|---|---|---|
| Kayıt/satır | 45.399 (fıkra-bölünmüş) | 31.422 (madde-bazlı) | şema farkı, direkt kıyaslanamaz |
| Benzersiz kanun | 900 | 902 | **biz +2 (221, 2308), 0 eksik** |
| Benzersiz madde | 28.622 | 31.105 | — |
| Ortak madde | — | — | **27.763** |

## 2. Kapsam farkı (GEN-only "eksik" 859 madde)

Sınıflandırma (bizde yok görünüp GEN'de olan):
- **519 = redirect/değişiklik maddesi** ("Bu maddeler X sayılı Kanunun … değiştirilmesi ile ilgili olup işlenmiştir"). Bunları korpusa ayrı madde koymamak **DOĞRU** (RAG içeriksiz-aralık prensibi).
- **~270 = konsolide-yok hayalet / mülga** (GEN kendisi "Bu madde konsolide metinde yer almamaktadır" diyor, ya da mülga).
- **~10-15 = gerçek tekil eksik aday** (2954 Geç1-3, 2559 Geç1, 2983 Geç3, 1567 Geç2). KAYNAK-BELİRSİZ: bedesten madde-ağacı bu geçici/ek maddeleri hiç listelemiyor (mevzuat.gov.tr konsolide ile farklı konsolidasyon). Ayrı fetch-incelemesi gerek; FAZ 20 (213:93) ailesi.

**Kapsam hükmü: biz ≥ altınset. "Eksik" sanılanın ~%99'u ya redirect ya hayalet.**

## 3. İçerik farkı (27.763 ortak madde)

| Kova | Sayı | % |
|---|---|---|
| Birebir aynı (jac≥0.92) | 20.034 | 72.2 |
| kor_uzun (biz uzun) | 1.550 | 5.6 |
| gen_uzun (GEN uzun) | 662 | 2.4 |
| farkli (orta benzerlik) | 5.517 | 19.9 |

"farkli" kovasının 148'i tertip-çakışması artefaktı (aynı kanun_no farklı kanun).

## 4. Kaynak-doğrulamalı hakemlik (3 kategori, temsili örnekler)

### 4a. gen_uzun (12 örnek) — "bizde gövde-kaybı" hipotezi ÇÖKTÜ
- **9 GEN_KIRLI**: duplikasyon VEYA mevzuat.gov.tr'nin "ANA KANUNA İŞLENEMEYEN HÜKÜMLER" bloğundaki **başka mevzuatın geçici maddesini asıl kanuna yapıştırma** (2983 Geç2, 3238 Geç1, 2820 Geç1, 1479 Geç27, 3254 Geç1, 6102 m1131/m192, 2802 m17, 2575 m2).
- **1 GEN_HALÜSİNASYON**: 3213 Geç4'e başka kanunun (Jeotermal 5686) metni.
- **1 ÖNEMSIZ**, **1 hakem "BIZ_EKSIK" dedi → ham-doğrulama ÇÜRÜTTÜ**: 6493 m31 bizde temiz tam cümleyle bitiyor; GEN "fıkra 1/2/3" diye AYNI metni 3× kopyalamış (996 kar × 3). Biz doğru.
- **Gerçek BİZ_EKSIK: 0.**

### 4b. kor_uzun (12 örnek) — GERÇEK bleed burada
- **8 biz-iyi**: GEN maddeyi boş/kırpık bırakmış (5834, 5434, 4721, 1632) veya fark sadece başlık (6320, 5237, 4925, 6701).
- **4 gerçek BİZ_BLEED**:
  - **5809 m69, 5564 m9, 5747 m5** → "Yürütme" maddesine kanun-sonu **SAYILI CETVEL/LİSTE** sızmış (kor_len 4500-13000).
  - **213 Geç4** → sonraki geçici madde sızmış (VUK).

### 4c. farkli (12 örnek) — biçim farkı, içerik-kaybı yok
- **5 biz-haklı** (GEN duplike: 5393 m5, 2521 Geç2; GEN bozuk-fragman: 406 Geç6), **5 önemsiz** (mülga/başlık/fıkra-bölme), **2 hafif başlık-bleed** (5510 Geç19, 6362 Geç4).
- **Gerçek içerik-kaybı: 0. Tablo-kaybı yok, GEN-güncel/biz-eski yok.**

## 5. Yeni bulunan GERÇEK bug aileleri (bizde, ölçüldü)

| Aile | Boyut | Doğrulama | Not |
|---|---|---|---|
| **Yürütme + SAYILI CETVEL/LİSTE bleed** | ~20 madde | 488 m33 = 33.368 kar (Damga V. tüm tablo sızmış) doğrulandı | FAZ 15/17 anchor'ının cetvel-varyantı, YENİ |
| **Komşu-madde başlığı bleed** (kolonsuz) | ~35 madde (E-tuzağı elendi) | 5510 Geç19, 6362 Geç4 doğrulandı | FAZ 18a/18b'de "ertelendi" denen aile |

Not: kaba heuristik 257 aday buldu; E-tuzağı (TBK/TMK madde-içi kenar-başlık) + FP eleyince **~35 yüksek-güven**. Tam sayı için 0-FP'li ayrı tarama gerekir.

## 6. NİHAİ HÜKÜM

**Korpusumuz madde_gen_prompted'tan (altınset) belirgin şekilde daha temiz ve güvenilir.**

- GEN'in başlıca hataları: aynı fıkrayı 2-3× tekrar (duplikasyon), "işlenemeyen hükümler" bloğundaki başka mevzuatı asıl maddeye yapıştırma, masthead/değişiklik-tablosu ekleme, en az 1 net halüsinasyon.
- Bizim kalanan gerçek kusurlarımız yalnız **bleed** (çöp EKLEME), içerik-KAYBI değil: ~20 cetvel-sızması + ~35 komşu-başlık sızması. İkisi de zaten bilinen/ertelenen ailelerin devamı.
- Kaynak-doğrulanan 36 temsili vakada: **biz-haklı ~26, önemsiz ~6, bizde-bleed ~6, GEN-haklı/biz-eksik = 0.**

**Öğrenme:** "gen_uzun" (GEN daha uzun) sezgisel olarak "bizde eksik" gibi görünür ama kaynak-doğrulamada tam tersi çıktı — GEN'in uzunluğu neredeyse hep kirlilik. Hakem agent bile 6493 m31'de yanıldı; ham veri hakem oldu.

---

## Ek: Çözülürse öncelik sırası (fix YAPILMADI, öneri)

1. **488 m33** — 33K'lık tablo çöpü, Damga Vergisi (yüksek atıf). Tekil ama en zararlı.
2. **Yürütme+cetvel ailesi** (~20 madde) — FAZ 15/17 anchor'ına "yürütür + SAYILI CETVEL/LİSTE" dalı; 0-FP + regresyon gerekir.
3. **Komşu-başlık bleed** (~35) — FAZ 18 kolonsuz-başlık ailesi; 0-FP zor, E-tuzağı (TBK/TMK kenar-başlık) FP riski yüksek.
