# FAZ 4 — Sızma / Bleed (C1 + C2) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (confusion matrix temiz)**
> ⚠️ **YÜKSEK over-truncation RİSKİ** (geçmiş: commit 2158ea7, KVKK M23 'Başkan' içerik kaybı).
> **Strateji (kullanıcı kararı): YAP → REGRESYON → CONFUSION MATRIX → kötü etkiliyorsa ERTELE.**
> Dosya: `src/mevzuat_tool/enrich.py`.

## ✅ SONUÇ (commit edildi — confusion matrix FP=0)
- **C1** ([enrich.py](../../src/mevzuat_tool/enrich.py) `_KAPANIS_BASLIK` + `_strip_bleed`): tree'de OLMAYAN yüksek-güven kapanış-başlığı (`Yürürlük`, `Yürütme`, `Geçiş hükümleri`...) cümle-sonu + gövde sonu + son %15'te kuyruktan kesilir.
- **C2:** kenar-numaralı başlık (`2. Kefalet hâlinde`) tree'de varsa mevcut `_strip_bleed` ZATEN kesiyor (test ile doğrulandı) — ayrı düzeltme gerekmedi.
- **Birim test:** +3 (C1 hedef, C1 over-trunc koruma, C2 hedef). Mevcut 4 over-truncation koruma testi (KVKK M23, 7315 M3, 7071 M1) YEŞİL. Tam paket **193 passed**.
- **🔬 CONFUSION MATRIX (916-kanun):**
  | | Sayı |
  |---|---|
  | Toplam kesim | **312** |
  | **TP (gerçek başlık sızması)** | **312** |
  | **FP (içerik kaybı / over-truncation)** | **0** |
  | Kesim uzunluğu | ort 9, maks 31 krk |
  | status-flip / fıkra değişimi | 0 / 0 |
  - 259/312 kesilen kuyruk aynı kanunda madde başlığıyla eşleşti; kalan 53 de gerçek sızma (kapanış maddeleri başlıksız chunk olduğu için eşleşmedi — spot-check ile doğrulandı: `...girer. Yürütme`, `...saklıdır. Geçiş hükümleri`).
  - E-tuzağı: TMK/TBK'da 2 kesim (`103249-Gecici1`, `103273-Gecici2`) — ikisi de gerçek `Yürürlük` sızması, içerik kaybı YOK (kapı "etkilenen=0" meşru kesimi yanlış işaretliyor; FAZ 2 dersi).

> 🔑 **KARAR:** Yap-ölç-karar ver stratejisi (kullanıcı) işe yaradı — riskli faz olmasına rağmen yüksek-güven sözlük + son-%15 + cümle-sonu kapıları over-truncation'ı 0'da tuttu. FP belirgin olsaydı ertelenecekti; FP=0 olduğu için commit.

> 📌 **Genişletme borcu:** Sözlük 8 başlıkla DAR tutuldu (en güvenli). `Tanımlar`, `Kapsam`, `Amaç` gibi 10+ frekanslı başlıklar da eklenebilir ama belirsiz olanlar (`Sorumluluk`, `Konusu`) over-truncation riski taşır — ileride frekans+tree-doğrulamayla genişletilebilir.

## Context

Sonraki maddenin başlığı gövde kuyruğuna sızıyor; mevcut `_strip_bleed` ([enrich.py:72-83](../../src/mevzuat_tool/enrich.py#L72-L83)) kesemiyor çünkü:
- **C1 kök neden (DERİN):** `_bleed_markers` tree'den sonraki başlığı alıyor, ama bazı kanunlarda **tree↔HTML uyuşmuyor** — `332571-16` için tree `BEŞİNCİ BÖLÜM > M17 (Başarı...)` derken HTML'de M16'dan sonra `Hizmet puanı` başlıklı madde var; `Hizmet puanı` bleed-marker listesinde YOK → kesilemez.
- **C2:** kenar-numaralı başlık (`2. Kefalet hâlinde`, TBK M139→M140) `_is_guvenilir_marker` ya da konum kapısından kaçıyor.

### Doğrulanmış gerçekler (bu oturumda)
- Kuyruk frekansı (son-fıkra `. Xxx` büyük-harf kısa kuyruk): **Yürürlük 260**, Geçiş hükümleri 26, Yürütme 13, Tanımlar 10, Yürürlükten kaldırılan hükümler 9, Kapsam 4... = standart kapanış-madde başlıkları.
- Kaba proxy: ~2683 madde şüpheli (ama bu çok geniş — `Sorumluluk`, `Konusu` gibi belirsizler dahil; meşru cümle sonu olabilir → over-truncation riski).

## Strateji — risk-kontrollü, ölçüm-temelli karar

**C1 — iki katmanlı güvenli kesim (tree'ye güvenmeden):**
1. **Yüksek-güven kapanış-başlık sözlüğü:** standart, neredeyse-asla-meşru-cümle-sonu-olmayan başlıklar — `Yürürlük`, `Yürütme`, `Geçiş hükümleri`, `Geçici hükümler`, `Yürürlükten kaldırılan hükümler`, `Değiştirilen hükümler`, `Çeşitli hükümler`, `Son hükümler`. Gövde kuyruğunda (son %15 + cümle-sonu sınırı) bu ifadeyle bitiyorsa kes.
2. **Tree-doğrulamalı kesim:** kuyruk ifadesi tree'deki HERHANGİ sonraki başlıkla eşleşiyorsa kes (mevcut `_bleed_markers`'ı son %15 + cümle-sonu şartıyla genişlet).

**C2 — kenar-numara kuyruğu:** `\. \d+\.\s[A-ZÇĞİÖŞÜ]` (cümle-sonu + kenar-numara + büyük harf) deseni, **yalnız** gövde son %15'inde + tree-doğrulaması varsa kes. E-tuzağıyla çakışmaz (gövde-kuyruk kesimi, bent-bölme değil).

**Hepsinde ortak güvenlik:** yalnız son %15 (`_MADDE_MARKER_SON_ORAN`), cümle-sonu sınırından sonra, kesilen kuyruk KISA (≤5 kelime). Mevcut over-truncation korumaları ([enrich.py:78-82](../../src/mevzuat_tool/enrich.py#L78-L82)) yeniden kullanılır.

## KARAR METRİĞİ — Confusion Matrix (yeni)

Her kesimi sınıflandır:
- **Doğru-pozitif (TP):** kesilen kuyruk gerçekten sonraki-madde başlığı (tree'de var VEYA yüksek-güven sözlükte).
- **Yanlış-pozitif (FP):** kesilen kuyruk meşru madde içeriği (over-truncation — KÖTÜ).
- Adversarial doğrulama: kesilen kuyrukların örneklemini ajan(lar)la "başlık mı içerik mi" diye sınıflandır.

**KARAR KURALI:**
- FP ≈ 0 (yüksek-güven sözlük + tree-doğrulama temiz) → **commit**.
- FP belirgin (over-truncation çok) → **ERTELE** (geri al, C1'i daha dar yap veya FAZ 4'ü sonraya bırak).

## Regresyon / Doğrulama
1. 🔴→🟢 TDD: C1/C2 hedef testleri (332571-16 `Hizmet puanı`, TBK `2. Kefalet`) + over-truncation koruma testleri (mevcut `test_enrich_does_not_truncate_*` YEŞİL kalmalı — KRİTİK).
2. ♻️ Tam `pytest`.
3. 📊 916-kanun compare: son-fıkra uzunluk dağılımı (kısalma beklenir); **etkilenen-madde** + status-flip.
4. 🔬 **Confusion matrix** (adversarial): kesilen kuyrukları TP/FP sınıflandır. Karar kuralını uygula.

> ⚠️ Smoke build korpusu ezer → baseline al/geri yükle.

## Çıktılar (commit'ler — YALNIZ confusion matrix temizse)
- `fix(enrich): kolonsuz sonraki-madde başlığı kuyruk sızması (C1)`
- `fix(enrich): kenar-numara kuyruk sızması (C2)`
- VEYA ertele: `docs(faz-4): sızma fazı ertelendi — over-truncation riski (FP=N)`
