# FAZ 21 — CETVEL/LİSTE + Kolonsuz Komşu-Başlık Bleed ✅

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (0-FP, tam regresyon)**
> Tasarım: [../superpowers/specs/2026-07-07-faz-21-cetvel-ve-kolonsuz-baslik-bleed-design.md](../superpowers/specs/2026-07-07-faz-21-cetvel-ve-kolonsuz-baslik-bleed-design.md)
> Plan: [../superpowers/plans/2026-07-07-faz-21-cetvel-kolonsuz-baslik-bleed.md](../superpowers/plans/2026-07-07-faz-21-cetvel-kolonsuz-baslik-bleed.md)
> Branch: `faz-21/cetvel-kolonsuz-baslik-bleed`

## Kaynak: madde_gen (altınset) kıyas-hakemliği

`altınset/madde_gen_prompted.jsonl` ile korpusun 3-hakem (Opus, mevzuat-mcp kaynak-doğrulamalı) kıyası
(bkz. [../olcum-sonuclari/madde-gen-karsilastirma-raporu.md](../olcum-sonuclari/madde-gen-karsilastirma-raporu.md)):
korpus altınsetten belirgin daha temiz, madde_gen'e karşı gerçek gövde-kaybı = 0. Kalan iki gerçek bleed
ailesi bu fazda çözüldü.

---

## FAZ 21a — Yürütme + CETVEL/LİSTE sızması (parser) — commit `d9f0d1f`

**Sorun:** Kanunun son "Yürütme" maddesine (`Bu kanunu Bakanlar Kurulu yürütür.`) kanun-sonu ekli
`(1) SAYILI TABLO/CETVEL/LİSTE` yapışık. Mevcut `_strip_kanun_sonu_ek` anchor sonrası kuyruğu yalnız
**tümü-büyük (>0.85)** ise kesiyordu; Title-Case tablo başlıkları (`Damga Vergisine Tâbi Kâğıtlar`)
oranı 0.28'e düşürüp guard'ı kaçırıyordu. En çarpıcı: **488 m33 = 33.368 kar çöp**.

**Fix:** `chunker.py`'ye `_SAYILI_EK_BASI` regex + `_strip_kanun_sonu_ek`'e dal: yürütme-anchor sonrası
kuyruk `[IVX0-9] SAYILI TABLO/CETVEL/LİSTE` imzasıyla BAŞLIYORSA tümü-büyük şartına bakmadan kes.

**0-FP:** yürütme-anchor ZORUNLU (madde-içi 1214 meşru "...ekli (III) sayılı liste" atıfı — yürütmesiz —
etkilenmez); imza kuyruğun başında (`.match`). Mevcut tümü-büyük dalı bit-bit korundu.

**Etki:** 19 madde CETVEL/ek kesimi (12 FAZ 21-yeni imza-başlangıçlı incl. 488 m33 33K→40, 5747 m5
7693→57, 5564 m9 4536→57; 7 mevcut tümü-büyük dalının zaten kestiği = regresyon değil). 0-FP (kesilen
tüm kuyruklar kanun-sonu ek/tablo çöpü, ham-doğrulandı).

## FAZ 21b — Kolonsuz komşu-madde başlığı sızması (enrich) — commit `20d818f` + `157dc08`

**Sorun:** Madde sonuna sonraki maddenin **kolonsuz** başlığı yapışık (`"...uygulanır. Yürürlükten
kaldırılan hükümler"`). Mevcut C1 (`_KAPANIS_BASLIK` + `_KAPANIS_BASLIK_RE`) kesimi `esik` (gövdenin
son %15'i) şartına bağlı; kısa maddelerde (7330 m9, 6491 m26, 6428 m10 — 135-183 kar) başlık son %15'ten
ÖNCE başladığı için kaçıyordu.

**Fix (mimari kilit — ölçümle):** Mevcut C1/`esik` bloğuna DOKUNULMADI. `enrich.py`'ye AYRI, **esik-siz,
gövde-sonu (`$`) anchor'lı** FAZ 21 bloğu: `_FAZ21_KAPANIS_RE` (dar sabit-sözlük birleşik varyantları:
`Değiştirilen ve yürürlükten kaldırılan hükümler` vb.) + `_KAPANIS_ILISKIN_RE` (önek-değişken
`<özne> ilişkin geçiş hükümleri` / `<özne> ile ilgili hükümler`). `_strip_bleed`'e `kanun_no=None`
parametresi (geriye uyumlu) + **E-tuzağı guard** (`if kanun_no not in _ETUZAK`).

**0-FP (E-tuzağı guard kanıtı):** guard olmasaydı 4 FP eşleşecekti (6098 m47 "Saklı hükümler",
2709 m35/m48/m92 = maddenin KENDİ kenar-başlığı); guard bunları TAM eledi. FAZ 21 kesimleri gövde-sonu
`$` anchor'lı → cümle-ortası kesilmez.

**Etki:** 43 madde kesim. **E-tuzağı = 0.** 43/43 kesim gerçek cümle-sonu (`.!?`) sonrası başlık-bleed
(adversaryal ham-doğrulama: hiçbiri maddeyi ortadan bölmüyor).

---

## Toplam Regresyon Kapısı (5-katman)

- **Test:** 260 passed (247 baz + 13 yeni: CETVEL 4, Task3 geriye-uyum 1, kolonsuz 8).
- **Birleşik korpus regresyon:** text-değişen 62 madde (CETVEL 19 + kolonsuz 43, çakışma 0). Madde
  sayısı ±0 (kesim yalnız kuyruk kırpar). **STATUS-FLIP = 0** (hiçbir madde yürürlük durumu değişmedi).
- **Confusion matrix / 0-FP:** CETVEL 19/19 kanun-sonu ek çöpü; kolonsuz 43/43 cümle-sonu sonrası
  başlık-bleed. Beklenmedik kesim = 0.
- **E-tuzağı** (TMK/TBK/TTK/FSEK/Anayasa 4721/6098/6102/5846/2709): kolonsuz-başlık fix bu 5 kanunu HİÇ
  işlemez (guard). Kesim = 0, yapı korundu.
- **İki-stage review:** her task grubu spec ✅ + quality Approved (0 must-fix). Final whole-branch review.

## Etki

- ~62 madde bleed-çöpü (kanun-sonu tablo/cetvel + kolonsuz komşu-madde başlığı) text-kuyruğundan temizlendi.
- 488 m33 (Damga Vergisi, yüksek atıf): 33.368 → 40 karakter (%99.9 çöp temizlendi).
- **0-FP, yapı korundu, status-flip 0, madde sayısı ±0.** "Çalışan şeyleri bozma" tutturuldu.

## Ertelenenler (bilinen-sınır)

- **5510 Geç19** ve rakamla-başlayan kolonsuz başlıklar (`"506 sayılı Kanunun ... kapsamındaki ... hükümler"`):
  `_KAPANIS_ILISKIN_RE` bilinçli yalnız BÜYÜK-HARF-başlangıç kabul eder (0-FP kapısı); rakam-başlangıca
  izin madde-içi atıf FP riski açar. `kapsamındaki` dalı korpusta 0 temiz kesim verdiğinden çıkarıldı.
- CETVEL ailesinde yürütme-anchor'ı OLMAYAN olası sızmalar (anchor bu fazda zorunlu).
- Kapsam gri-alanı (2954/2559/2983/1567 geçici maddeleri): FAZ 20 fetch ailesi, bu faz dışı.
