# FAZ 10 — Bleed başlık kalanı (Z3) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (confusion matrix FP=0)**
> ⚠️ EN RİSKLİ faz (over-truncation geçmişi: 2158ea7 KVKK M23). Strateji: YAP→ÖLÇ→FP belirginse ERTELE.
> Dosya: `src/mevzuat_tool/enrich.py`. "Kalan Zehir" Z3.

## ✅ SONUÇ (commit `1a45936` — confusion matrix FP=0)

- **Z3** ([enrich.py](../../src/mevzuat_tool/enrich.py) `_KAPANIS_BASLIK` genişletme): C1 sözlüğüne
  7 GÜVENLİ başlık eklendi — `Tanımlar`, `Kapsam`, `Yönetmelik`, `Yönetmelikler`, `Atıflar`,
  `Ortak hükümler`, `Uygulanmayacak hükümler`. Regex uzun-önce sıralı.
- **Birim test:** +2 (genişletilmiş-güvenli kesim + belirsiz-başlık koruma). **206 passed**.
- **🔬 CONFUSION MATRIX (916-kanun):**
  | | Sayı |
  |---|---|
  | Toplam kesim | **30** |
  | **TP (gerçek başlık bleed)** | **30** |
  | **FP (over-truncation)** | **0** |
  | status-flip | 0 |
  - Her NEW gövde tam-cümle (`...düzenlemektir.`, `...kapsar.`, `...sayılır.`) ile bitiyor;
    kesilenler temiz başlık.

> 🔑 **KARAR:** Yap-ölç-karar (FAZ 4 deseni) işe yaradı — adversarial başlık-seçimi over-truncation'ı
> 0'da tuttu. FP belirgin olsaydı ertelenecekti; FP=0 → commit.

## Seçim mantığı (adversarial)
Aday başlıklar `madde_baslik` frekansı (gerçek başlık kanıtı) + kuyruk-örneği incelemesiyle elendi:
- **GÜVENLİ (eklendi):** fiilsiz, neredeyse-asla-cümle-sonu-değil, yüksek frekans (Tanımlar 211...).
- **EKLENMEDİ (over-truncation/E-tuzağı):**
  - `Sorumluluk`/`Konusu`/`Süre`/`Yetki`/`İzin` — meşru cümle sonu olabilir (belirsiz).
  - `Genel hükümler`/`Uygulanacak hükümler` — kenar-numaralı bağlamda (`1. Genel hükümler`,
    `5. Uygulanacak hükümler`) gelir → son-ek kesimi yarım keser (`1.`/`5.` kuyrukta kalır).
  - `Genel olarak` — 998-kenar-numara tuzağı (`1. Genel olarak`).

## Bilinen kalan
`103273-272`: `III. Ortak hükümler` kesildi → `Ortak hükümler` çıktı ama roman `III.` kuyrukta
kaldı (Z4-roman, ~19 madde korpus-geneli). Z3 FP'si DEĞİL (kesim doğru); ayrı kozmetik kalem.

## Çıktılar
- `fix(enrich): C1 kapanış-başlık sözlüğünü güvenli başlıklarla genişlet (Z3)`
