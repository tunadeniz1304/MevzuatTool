# FAZ 8 — Sarkan kenar-numara (Z4) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (0 FP)**
> Dosya: `src/mevzuat_tool/enrich.py`. "Kalan Zehir" Z4.

## ✅ SONUÇ (commit `4dcb7de` — etkilenen 41, 0 FP)

- **Z4** ([enrich.py](../../src/mevzuat_tool/enrich.py) `_SARKAN_KENAR_NUMARA_RE` + `_strip_bleed`):
  kenar-numaralı kanunlarda sonraki maddenin kenar-numarası (`6.`) önceki maddenin gövde
  kuyruğuna tek başına sızıyordu. Cümle-sonu + tek `N.` + gövde-sonu → kırpılır.
- **Birim test:** +2 (sarkan-kesim 104458-35 deseni + madde-içi-numara koruma). **204 passed**.
- **916-kanun regresyon:** etkilenen **41 madde** (FSEK 5846: 16, Kooperatifler 1163: 22, KMK 634: 3),
  HEPSİ tam tek `N.` kesimi (0 şüpheli/FP); text korundu; E-tuzağı madde başlıkları
  (`1. Genel olarak`) dokunulmadı (desen yalnız gövde-SONU `$` hedefler); status-flip 0.

> 🔑 **DERS:** İlk proxy 9 madde dedi (yalnız bent-text sonu) ama gerçek etki **41** — sarkan `N.`
> madde.text/fıkra-sonu seviyesinde de var. Hepsi TP çünkü desen çok dar (cümle-sonu + tek `N.` +
> `$`). E-tuzağı endişesi tersine döndü: bu fix tam da kenar-numaralı kanunları (FSEK/TMK ailesi)
> temizledi, başlıklara dokunmadan.

## Kök neden
FSEK gibi kenar-numaralı kanunlarda madde başlığı kenar-numarayla başlar (`5. İktibas serbestisi`).
Madde split'i başlık metnini dahil etmeyince, sonraki maddenin numarası (`6.`) gövde kuyruğuna
yapışır (`104458-35`: `...belirtilir. 6.`). tree-marker (`6. Gazete münderecatı`) gövdede yalnız
`6.` görünür → mevcut bleed-marker eşleşmesi kaçırır.

## Çözüm + YP-riski
`_SARKAN_KENAR_NUMARA_RE = (?<=[.!?])\s+\d+\.\s*$` — cümle-sonu + tek `N.` + gövde sonu. Madde-İÇİ
`N.` (numaralı liste, kenar-başlık) DOKUNULMAZ çünkü `$` yalnız gövde sonunu hedefler. DÜŞÜK risk;
E-tuzağı koruma testi (`1. Ticari kazanç` madde-içi korunur) yeşil.

## Bilinen kalan (FAZ 10'da keşfedildi)
Roman kenar-numara kuyruğu (`...uygulanmaz. III.`) bu desenle yakalanmaz (`\d+` rakam, roman değil).
Korpusta ~19 madde. Z4-roman olarak ayrı değerlendirilebilir (düşük frekans, kozmetik).

## Çıktılar
- `fix(enrich): sarkan kenar-numara kuyruğunu madde sonundan kırp (Z4)`
- `docs(faz-8/10): Z4+Z3 tamamlandı, Z2 ertelendi`
