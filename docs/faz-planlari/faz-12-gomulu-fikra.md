# FAZ 12 — Gömülü fıkra (E1) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (confusion matrix FP düzeltildi)**
> Adversarial denetimle (29+24 ajan, kaynak-HTML doğrulamalı) bulunan EN YÜKSEK DEĞERLİ bug.
> Dosya: `src/mevzuat_tool/fikra.py`.

## ✅ SONUÇ (commit `9ede923`)

- **E1** ([fikra.py](../../src/mevzuat_tool/fikra.py) `_FIKRA_BOL` yeni dal + `_ATIF_ONCUL` + `_CETVEL_BAS`
  genişletme): noktasız bent listesi sonrası `(N) BÜYÜK` fıkra-başı sayılır; atıf/ekli-belge öncülü
  (`Birinci..Onuncu`, `Bu/Aynı/Söz/Yukarıdaki`, `SAYILI/Sayılı/Numaralı`) negatif-lookahead'le elenir.
  `_CETVEL_BAS`'a `ÇİZELGE/KROKİ` eklendi.
- **Birim test:** +6 (gömülü-böl, çoklu-gömülü, atıf-koruma, ekli-belge-koruma, cetvel-çizelge). **215 passed**.
- **916-kanun:** etkilenen **75 madde**, ~73 TP (gömülü fıkra ayrıldı, hepsinde fıkra sayısı arttı,
  text korundu); status-flip 0; sahte-bent 14→13.
- **🔬 CONFUSION MATRIX (24 ajan, kaynak-HTML/PDF):** 98 yeni fıkra → **83 TP, 15 FP iddia → 13
  düzeltildi**. FP kök neden: `(N) SAYILI ÇİZELGE`, `(N) Numaralı Alt Bent` (tablo hücresi),
  `Ekli (N) Sayılı listede` → guard eklendi.
- **SERT KAPILAR:** E-tuzağı 5-kanun **0 etkilenen** ✓, çürütülen-9-meşru **0 etkilenen** ✓.

> 🔑 **DERS:** İki workflow olmadan körlemesine commit etseydim 15 FP sızacaktı. Adversarial
> confusion matrix (ajanlar kaynak HTML'e indi) `(N) SAYILI ÇİZELGE` / tablo-numarası FP'lerini
> yakaladı. B2 cetvel-guard'ı `ÇİZELGE/KROKİ` ile genişledi — gömülü-fıkra dalının cetvel karşılığı.

## Kök neden
Bent listesi noktasız bitiyor (`...Diğer gelirler`), ardından `(2) Başkanlığın giderleri şunlardır:`
yeni fıkra. `_FIKRA_BOL` cümle-sonu noktası/`]`/`)` lookbehind'ı beklediği için kelime sonrası `(N)`'yi
kaçırıyordu → fıkra (2)(5)(6)(7) fıkra (1)/(4)'ün bentler[]'ine gömülü. Gömülü `(Mülga)` → yürürlük
filtresi de bozuk. Gerçek veri: 102934-7 (gelir+gider), 103463-4 (TBMM (5)(6)(7)), 103045-5 (3 fıkra).

## YP-riski (YÜKSEK — yönetildi)
- **Atıf bölme:** `(2) Birinci fıkra...`, `(2) Bu Kanun...` → atıf kara-listesi.
- **Ekli-belge bölme:** `(N) SAYILI ÇİZELGE`, `(N) Numaralı Alt Bent` → confusion matrix yakaladı, guard.
- **B1/B2/B3 çakışma:** 215 test + 916-regresyon temiz.

## Bilinen kalan (kabul edildi)
2 FP — `104236-Gecici9` (`(1) Daire Başkanı, (1) Mühendis` kadro-listesi: `(N)`=adet),
`103212-37` (`A.` harf-başlığı altında `(1)(2)(3)` alt-numara restart). **text KORUNDU** (içerik kaybı
yok, yalnız fıkra-yapısı şüpheli). Daha agresif guard meşru enumerasyonları (`102957-20` yardım türleri
`(1) Emeklilik, (2) Malüliyet`) riske atardı → kabul edildi.
Ayrıca `103463-4` `(7) (Mülga)` ayrılmadı (öncesi `)` künye-kapanışı, künye-dalıyla çakışma) — 6 fıkra
ayrıldı, kısmi kalan.

## Regresyon stratejisi (uygulandı — 5 katman)
1. TDD RED→GREEN (hedef + atıf-FP + ekli-belge-FP koruma).
2. 215 test (B1/B2/B3/A2/E-tuzağı/over-trunc) yeşil.
3. 916-kanun: etkilenen/status-flip/fıkra-bent dağılımı + E-tuzağı + çürütülen-9 sert kapıları.
4. Confusion matrix (24 ajan adversarial): 98 yeni fıkra TP/FP → FP guard'la düzeltildi.
5. Spot-check: hedef bug'lar (102934-7, 103463-4) ayrıldı; kalan FP'ler text korundu.

## Çıktılar
- `fix(fikra): gömülü fıkrayı noktasız bent listesinden ayır (E1)`
