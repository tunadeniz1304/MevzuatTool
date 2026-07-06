# FAZ 15 — Son-madde kanun-sonu ek bleed (BUG 9) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (confusion matrix FP=0)**
> Altınset (dış gold set) karşılaştırması + 3 fizibilite agent'ıyla bulunan EN YAYGIN bleed bug'ı.
> Dosya: `src/mevzuat_tool/chunker.py`. Spec: [../superpowers/specs/2026-07-06-faz-15-16-kanun-sonu-bleed-madde-bleed-design.md](../superpowers/specs/2026-07-06-faz-15-16-kanun-sonu-bleed-madde-bleed-design.md)

## ✅ SONUÇ (commit `19aea25` + `ddc269d`)

- **`_KANUN_SONU_ANCHOR` + `_strip_kanun_sonu_ek`** ([chunker.py](../../src/mevzuat_tool/chunker.py)): kanunun SON
  maddesi "yürütme"dir ("...Bakanlar Kurulu/Cumhurbaşkanı yürütür"). `split_articles` son maddede
  `end=len(text)` olduğu için ardından gelen kanun-sonu ekleri (değişiklik-listesi tablosu "X SAYILI
  KANUNA EK VE DEĞİŞİKLİK GETİREN...", kadro/tarife cetvelleri "N SAYILI LİSTE/CETVEL", "EK GÖSTERGE
  CETVELİ", madde-no-eşleştirme tabloları) gövdeye giriyordu (5996:50=5791 kar). ANCHOR = "yürütür"
  cümlesi; kuyruk (anchor sonrası, ilk 80 kar) TÜMÜ-BÜYÜK belge başlığıyla başlıyorsa (büyük-harf oranı
  >0.85) oradan madde sonuna kes.
- **0-FP KAPILARI (3):** (1) anchor ŞART — anchorsuz salt-sınır ölçümde 299 tüm-madde-kaybı (felaket);
  (2) kuyruk tümü-büyük OLMALI — küçük-harf başlarsa (meşru hüküm/düz-metin çöp: 7326:18 CB Kararı) KESME
  → ertelenen semantik vaka; (3) meşru "Yürürlük" maddeleri "yürütür" içermez → anchor dokunmaz.
- **Birim test:** +4 (kesim + 3 FP-koruma: temiz-yürütme / küçük-harf-kuyruk / yürürlük-anchor-yok).
  **221 passed** (mevcut hiçbir test kırılmadı).
- **916-kanun compare:** etkilenen **413 madde** (text-kesim; hepsinde "yürütür" korundu 413/413),
  eklenen/silinen 0/0, fıkra/bent dağılımı DEĞİŞMEDİ (ort 1.48, maks 42, sahte-bent 14→14 — yapısal
  sadakat korundu). Build deterministik (2 build birebir aynı).
- **🎁 BONUS — 5 yürürlük DÜZELTMESİ:** çöpteki "İPTAL EDİLEN HÜKÜMLERİN" ifadesi yüzünden yanlış-mülga
  işaretlenen yürütme maddeleri (6458-126, 5902-28, 5544-33, 6093-16, 6569-47) çöp kesilince DOĞRU
  yürürlükte oldu → CLAUDE.md ilke 5 (yürürlük birinci sınıf) açısından iyileşme. status-flip →mülga: 0.
- **🔬 CONFUSION MATRIX (adversarial agent, kaynak-mcp doğrulamalı):** 413 kesim → **413 TP, 0 FP**.
  64+ blok elle incelendi, 3 kanun (3520, 3234, 4737) mevzuat-mcp kaynağıyla çapraz doğrulandı, 3 FP-şüphesi
  (104702-6, 104777-41, 103220-Gecici5) çürütüldü (ilk ikisi gerçek çöp; üçüncüsü log-görüntüleme artefaktı,
  kod dokunmuyor). 61/413 kesimde atılan tablo `tablolar` metadata'sında zaten korunuyor (tam kayıp değil).
- **🔧 FOLLOW-UP FIX (commit `bc9e3e7`) — künye-pencere kaçağı:** oran ölçümü 80-kar penceresinde
  değişiklik künyesi (`(Ek:...)`, `(Mülga:...)` — küçük-harf) içerince oran 0.85 altına düşüp kesimi
  ATLATIYORDU (102924-239: 16.6k çöp hem `text` hem `fikralar[0].text`'te kalmış — fıkra ağacı aynı
  `art.body`'den kurulduğu için tek kök). FIX: oranı ölçmeden önce künye-parantezlerini SABİT pencerede
  çıkar (genişletme YOK — genişletme 102952-23'te regresyon yaratmıştı, yakalandı+düzeltildi). Ayırt edici:
  künye-anahtar + `:` (meşru `(1)`/`(2018 yılı için)` eşleşmez). **+11 kesim (413→424), 0 yeni-FP**
  (Opus reviewer: 916 ham HTML FP taraması, 0 regresyon). +3 test (2 kesim RED→GREEN + 1 regresyon-guard).
  **224 passed.** Fıkra ağacına propagasyon: `enrich.py:220 parse_fikralar` kesilmiş `art.body`'den kurar →
  tek fix hem text hem fikralar'ı kapsar.
- **⏸️ ERTELENEN GENİŞ EVREN (~97 kayıt, 0-FP imkansız):** anchor+kuyruk≥30 ama kesilmeyen ~97 madde var.
  Bunların çoğu Title-Case tablo başlığı ("GELİR İDARESİ BAŞKANLIĞI Başkan..." @0.76, "EK-1 SAYILI EK
  GÖSTERGE CETVELİ ... UNVANI Derece" @0.77). Kontrol kaydı 103532-12 (@0.746, MEŞRU küçük-harf devamı —
  kesilmemeli) bu bandda iç içe → güvenli eşik YOK, regex 0-FP veremez. 3'ü (104891-10, 102979-12,
  104030-5 @~0.84) eşiğin hemen altında gerçek çöp ama bunları yakalamak için eşik indirmek meşru-belirsiz
  bandı riske atar. Bu EKSİK-TEMİZLİK (kaçırılan TP), yeni FP DEĞİL. Çözüm: HTML-tablo temelli sınır
  tespiti (`html_table.py` genişletmesi, future) — Z2/SINIF2 gibi "semantik/HTML gerekir" ertelemesi.
- **SERT KAPILAR:** E-tuzağı 5-kanundan 2'si (FSEK 5846:91, TTK 6102:1535) kesime dahil AMA fıkra-yapısı
  1→1 KORUNDU, meşru içerik ("yürütür") kaybı 0 → yapısal-sadakat ihlali YOK (kullanıcı kararı: E-tuzağı
  sert kapısı = bent/fıkra yapısı, salt text-eşitlik değil). 104458-1B dipnot farkı FAZ 15'ten DEĞİL
  (text ESIT, chunker dipnota dokunmuyor, baseline stale).

> 🔑 **DERS:** Fizibilite analizi (kod öncesi) 9 aday bug'dan 7'sini FAZ-DIŞI bıraktı — körlemesine
> düzeltseydik regresyon (BUG 1 bent→fıkra) + boşa iş (BUG 3/6/7 parser-dışı) olurdu. ANCHOR şartı
> (ölçümle 299 felaket vs 0 FP) 0-FP'nin anahtarı. Confusion matrix kaynak-HTML'e inip 300-karakter-ötesi
> çöpü de doğruladı.

## Kök neden

`split_articles` son maddede gövde kuyruğunu `end=len(text)`'e kadar alır. Madde ağacı DOĞRU (son madde
sınırı doğru) ama kanun-sonu ekleri (cetvel/liste/tablo) ayrı bir yapısal birim olarak ağaçta yok →
son maddenin gövdesine yapışıyor. Çözüm: gövde-kuyruğu kırpma (`_SEVIYE_BASLIK_BLEED` / `_ISLENEMEYEN_EKI`
ailesine paralel), ağaç değişmez.

## Ertelenen (bu fazın DIŞI — semantik)

"yürütür" sonrası KÜÇÜK-harf düz cümleyle akan çöp (tümü-büyük başlık YOK): 7326:18 (CB Kararı düz metin),
6552:146, 3986:21 (AYM şerhi). Regex meşru hüküm cümlesinden ayıramaz (Z2/SINIF2 kategorisi). ~85 aday,
FP-koruma testi `test_yurutme_with_lowercase_tail_not_cut` ile bilinçli korunuyor (kesilmiyor).
