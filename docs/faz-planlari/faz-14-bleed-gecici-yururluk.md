# FAZ 14 — SINIF 3 (bleed geçici-madde) + İKİNCİL B — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **E3 yürürlük tamam; bleed-text + İKİNCİL B kozmetik/fix-yok**
> Dosya: `src/mevzuat_tool/chunker.py`.

## ✅ E3 (dipnot künye-bloğu → mülga tespiti) — TAMAM (commit `abf2ef3`, 0 FP)

### Sorun (SINIF 3'ün KRİTİK kısmı — yürürlük)
`103912-Gecici14`: gövde `(Ek : ...)[13] (Mülga: KHK-703/99 md.) Yürürlük`. Açılış künye bloğunda
künyeler arası `[13]` dipnot işareti `_KUNYE_PAREN` dizisini kırıyordu → `(Mülga:)` açılış-bölgesinde
sayılmıyor → madde yanlış `yürürlükte`. **Mülga madde retrieval'da CANLI görünüyordu** (yürürlük
filtresi bozuk — MVP-kritik, CLAUDE.md ilke 5).

### Çözüm
`_KUNYE_PAREN`'de künyeden sonra opsiyonel `[n]` dipnot işaretine izin: `\)(?:\s*\[\d+\])?\s*`.
B1/D1 dipnot dersinin yürürlük versiyonu.

### Sonuç
**916-kanun:** etkilenen **2 madde** (status-flip yürürlükte→mülga: 103912-Gecici14,
103217-Ek1 'İptal birinci fıkra'), İKİSİ DE doğru mülga (Mülga/İptal künyesi var); **0 FP**.
Birim test +1. **217 passed**.

## ⏸️ SINIF 3 bleed-text + İKİNCİL B — kozmetik/fix-yok

### Bleed-text (`text='Yürürlük'`)
`103912-Gecici14` / `104863-Gecici1`: gövde TAMAMEN künye olduğundan, künyeler temizlenince
geriye yalnız bleed `Yürürlük` kalıyor → `text='Yürürlük'`. C1 `_strip_bleed` kesemiyor (gövde
çok kısa, son-%15 eşiği dışı). **Düşük getiri:** bu maddeler artık `yurutluk=mülga` (E3) → retrieval'da
mülga filtresiyle elenir; `text` bleed'i embedding gürültüsü ama mülga maddede düşük etki. 2 madde,
çok dar kenar vaka → ele alınmadı.

### İKİNCİL B (OCR `l)`→`1)`)
`103795-19`: kaynak HTML'de `l)` bendi OCR'da `1)` okunmuş, `k)` bendine yapışmış (l) kayıp).
Bu **kaynak/OCR kusuru**, bizim parser hatası değil. Düzeltmek riskli (`1)` gerçek alt-bent olabilir).
Plan gereği **fix yok** — kabul edilen kaynak kusuru olarak NOT edildi.

## Çıktılar
- `fix(chunker): dipnot '[n]' künye bloğunu kırmasın — mülga tespiti (E3)`
- (bleed-text + İKİNCİL B: fix yok)
