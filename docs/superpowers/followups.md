# Faz 3 Follow-up Adayları (AÇIK liste)

Bu liste **açık** tutulur — incelenebilir adaylar; henüz karara/plana bağlanmadı.
Kaynak: `kanun193.pdf` (resmî GVK, 159 sf, ground-truth) ↔ pipeline çıktısı karşılaştırması
(2026-06-22). PDF kapsam dışı (CLAUDE.md ilke 2) — yalnız analiz referansı, gitignored.

> Yöntem: `pdftotext` ile PDF metni çıkarıldı, `enrich()` çıktısıyla karşılaştırıldı.
> "Çoğu kısım düzgün; bazı kısımlarda eksik kalıyoruz" → eksik noktalar aşağıda.

---

## 🔴 1. Dipnot apendiksi son maddeye sızıyor (en kritik) — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** İçeriğin SONUNDA toplu **221 dipnot tanımı** (`[1]…[221]`, satır 8089–9022) var.
  Bunlar son `Madde N -` işaretinden sonra geldiği için **tamamı son maddenin gövdesine** düşüyor:
  `Geçici 5` gövdesi **83.418 karakter** (olması gerekenin ~100 katı; çöp).
- **Neden yakalanmıyor:** tree-otoriteli bleed-strip dipnotları bilmez (ağaçta düğümleri yok).
- **Etki:** 1 chunk tamamen bozuk + 221 dipnot yanlış yerde.
- **Fix yönü:** içerikteki dipnot bloğunu (`^\[\d+\]` ile başlayan kuyruk) madde gövdelerinden
  ayır; ayrı bir `dipnotlar` yapısına al.

## 🟠 2. Dipnotları yapısallaştır + `[n]` → madde bağı — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** Dipnotlar **zengin değişiklik metadata'sı** içerir: "X tarihli Y sayılı Kanunun Z md.
  ile değiştirilmiş / eklenmiş / **İptal: Anayasa Mahkemesi**…". Gövdelerdeki `[167]` gibi
  işaretler bunlara referans verir ama pipeline `[n] → dipnot` bağını **kurmuyor**.
- **Fix yönü:** `[n]` işaretlerini ayrıştır → ilgili dipnot metnini madde metadata'sına bağla
  (`degisiklik_gecmisi` ile birleşir).

## 🟠 3. `(Değişik/Ek/Mülga: tarih-kanun/md.)` inline künyeleri → değer — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** GVK'da ~**402** inline künye gövdede ham metin olarak duruyor (örn. Madde 70'te 7 adet).
- **İstenen (kullanıcı):** "madde değişik diye yazılıyorsa onu da text içinde değil, **bir değer
  atanmış** olarak tut."
- **Fix yönü:** `degisiklik_gecmisi: list[dict]` alanı → `{tip, tarih, kanun_no, madde, kapsam}`.
  Sağlam parser gerekir: `(Ek cümle: …)`, `(… İptal: Anayasa Mahkemesi …)`, kesik tarih, çoklu `md.`

## 🟠 4. Tablolar (vergi tarifesi) flat metinde bozuluyor
- **Bulgu:** Madde 103 (gelir vergisi tarifesi) 2B tablo (gelir dilimi × oran). Hem PDF-extract
  hem bizim gövde bunu **karışık sayı dizisine** çeviriyor (%15/%20/%27/%35 dilimlerden kopmuş;
  parantez içi güncel değerler `(190.000 TL)` iç içe).
- **Etki:** Tarife sorgusunda RAG çöp gövde döner.
- **Not:** Zor problem (kaynak metin zaten düz); özel tablo-tanıma gerekebilir → düşük öncelik / ayrı.

## 🟡 5. Fıkra/bent bölme (`1.` / `a)` stili) — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** `split_fikralar` yalnız `(1)` böler; eski GVK `1. 2.` ve `a) b)` kullanır → bölünmez.
  Madde 70'in 8 bendi tek gövde. Madde-seviyesi chunk OK ama fıkra/bent-seviyesi retrieval yok.
- **Fix yönü:** eski-stil fıkra/bent splitter (önceki sohbette tespit edildi).

## 🟡 6. Yürürlük kaba (madde-seviyesi) — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** `extract_status` bir maddede TEK `(Mülga` görse TÜM maddeyi mülga sayar; oysa çoğu
  zaman sadece **bir bent** mülgadır.
- **Fix yönü:** künye/fıkra konumlarıyla yürürlüğü **bent-seviyesine** indir (3 + 5 ile bağlantılı).

## 🟡 7. Çifte / sonek madde numaraları — ✅ KAPATILDI (phase-3/followup-amendments)
- **Bulgu:** İki ayrı `Geçici 1` (1092 + 492 krk) → aynı `no`, ID çakışması. Sonek maddeler
  (`123/A`) ağaçta yok → best-effort (maddeId None). Geçici maddelerin `hiyerarsi_yolu`'su donör
  maddeyi gösteriyor.
- **Fix yönü:** benzersiz id şeması (örn. değişiklik-epoğu/sıra ekiyle).

---

## Carry-forward (Faz 3 review'larından, DEFER edildi)
- tree.py `lstrip(" ")` tab girintisi; deepest-match (substring `in` + ilk-eşleşme) — gerçek veride etki yok.
- enrich.py `_strip_bleed` kısa marker (2-harfli başlık) teorik over-truncation — mevcut korpusta aktif defect yok.

---

**Durum:** #1, #2, #3, #5, #6, #7 phase-3/followup-amendments branch'inde KAPATILDI.
Açık kalan: #4 (tablolar — zor, ayrı) + Carry-forward maddeleri.
