# Gold-Set Denetimi (unique_mevzuat.json, 2026-06-25)

Bağımsız gold-set (6055 mevzuat atfı: kanun-madde-fıkra-bent) ile korpus karşılaştırıldı.
Gold = içeriksiz adres listesi (vergi/mali hukuk ağırlıklı, %54); korpus = tam içerik (31.5K madde).

## Sonuç: korpus sağlam
- **Madde coverage:** gold-işaretli 2679 maddenin %80'i dolu içerikli; %16 kapsam-dışı/filtre (doğru);
  %1.2 (32) boş-aday → adversarial denetimde (workflow) 13 mülga + 1 yanlış-alarm + **1 gerçek bug**.
- **Madde sayısı:** bedesten ground-truth 30.022 ↔ korpus 31.515 (+%5 = Ek/Geçici fazlası, doğru).
- **Şişme yok:** (kanun,madde) gerçek-kopya 0; 1.371 boilerplate (Yürürlük/Yürütme) meşru (her kanunun
  kendi maddesi) — bırakıldı (kullanıcı kararı, atıf-modunda değerli).

## ✅ DÜZELTİLEN: dipnot over-truncation (commit 7754591)
- **Bulgu:** `split_dipnot_apendiksi` gövde-BAŞINDAki yoğun `[1][2]..` referanslarını kuyruk dipnot
  apendiksi sanıp gövdeyi kesiyordu (5335 M30: 3998ch→28ch). İlk 300 kanunda ~16 şüpheli vaka.
- **Adversarial doğrulama (2 workflow, 24 ajan):** şüphelilerin çoğu mülga/meşru-apendiks; sadece
  5335 M30 gerçek içerik-kaybıydı. Kalan 9 "over-truncation" → 9/9 meşru apendiks (büyük kanunların
  değişiklik-listesi kuyruğu, doğru kesim). Tek gerçek bug düzeltildi.
- **Fix:** son-[n]-kuyruğu uzunsa + uzun gövdede [1] öncesi metin kısaysa → gövde-içi referans,
  apendiks değil. 106 meşru apendiks korundu (false-positive yok). 5335 M30: 28→3796ch kurtarıldı.

## Açık (düşük öncelik): bent işaret-tipi uyuşmazlığı
- Gold "bent 2" der, parser `a,b,c` etiketler (1319 M33: metinde `1. 2. 3.` var ama harf-bent
  parse edilmiş). İÇERİK text'te TAM (kayıp değil), sadece bent ağacındaki `isaret` yanlış tip.
- Etki: fıkra/bent-seviyesi metadata filtrelemesi; retrieval'ı (madde-seviyesi) etkilemez. Ertelendi.

---

# Faz 5 (Embedding) Açık İşler

## 🟠 Dev maddeler (>20K char) — embedding'i aşar (Faz 5'te çöz)
- **Bulgu (2026-06-24, korpus sadakat denetimi):** 31.514 chunk'ın **26'sı (>20K char)** embedding
  context'ini aşar. İki olgu: (1) **düz-metin ek-listeler** — `102979-12` "Yürütme" maddesine
  binlerce kapatılan kurum/vakıf adı düz metin olarak yapışmış (160K char; markdown tablolar
  zaten `metadata.tablolar`'a çıkarıldı ama bu listeler `strip_html` ile DÜZ metin de geldi);
  `103011-Gecici1-*` Harçlar tarifesi. (2) **gerçek uzun maddeler** — vergi yapılandırma
  kanunlarının "Matrah ve vergi artırımı / Diğer hükümler" upuzun ama meşru hükümleri.
- **Karar (kullanıcı, 2026-06-24):** Faz 5'e ertelendi — çözüm embedding modeline bağlı.
  BGE-M3 8192 token (~24K char) çoğunu alır; aşanlar için **fıkra-bazlı alt-chunk'lama**
  (fıkra ağacı zaten `metadata.fikralar`'da hazır). Korpusun %0.08'i — erken-optimizasyon değil.
- **Not:** markdown tablo çıkarma + sadece-tablo filtresi YAPILDI (commit 5e5e86e); dev-chunk 35→26.

## 🟡 Mini-chunk'lar (<15 char) — anlamsız text (265 adet)
- **Bulgu:** `120179-Gecici1`='(1)', `104098-Ek1`='Yürürlük' gibi 265 chunk text'i ya tek fıkra
  işareti ya tek kelime başlık. Gerçek içerik parse'ta kayıp ya da madde gerçekten içeriksiz.
- **Karar:** Önce dev-chunk'lar çözüldü; mini-chunk boş-içerik filtresi sonraya bırakıldı.
- **Fix yönü:** text uzunluğu eşiği (ör. <15 char) + anlam kontrolü ile filtre; ama önce
  bunların gerçekten içeriksiz mi yoksa parse-kaybı mı olduğunu örnekle doğrula.

---

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

## 🟠 4. Tablolar (vergi tarifesi) flat metinde bozuluyor — AÇIK, ama KAYNAK BULUNDU (Faz B adayı)
- **Bulgu:** Madde 103 (gelir vergisi tarifesi) 2B tablo (gelir dilimi × oran). Mevcut pipeline
  bunu **karışık sayı dizisine** çeviriyor (%15/%20/%27/%35 dilimlerden kopmuş; parantez içi
  güncel değerler `(190.000 TL)` iç içe).
- **Etki:** Tarife sorgusunda RAG çöp gövde döner.
- **KÖK NEDEN (2026-06-22 kanıtlandı):** Kaynak metin DÜZ DEĞİL. `mevzuat-mcp` paketinin
  `bedesten_client.get_document_content(mevzuat_id)` metodu ham `text/html` döndürüyor ve
  GVK'da tarifeler GERÇEK `<table>`: GVK ham HTML'de 8 `<table>`, 401 `<tr>`, 1361 `<td>`.
  Madde 103 = temiz 2-sütun (`<td>gelir dilimi</td><td>%oran</td>` per `<tr>`). Tabloyu öldüren
  şey `bedesten_client._strip_html` (`re.sub(r'<[^>]+>','')`) — MCP tool'u `get_mevzuat_content`
  bu strip'li yoldan (`get_document_plain_text`) geçiyor; ham HTML expose edilmemiş ama
  `get_document_content` PUBLIC.
- **Faz B yönü (HTML-tablo cebi):** MD omurgayı koru; tablolu maddeleri tespit et (`has_table`),
  o maddelerin ham HTML'inden `<table>→Markdown` çıkar. Erişim = `get_document_content`'i
  kütüphane olarak import et (Yol 2 — yeni scraper değil, mevzuat-mcp'nin kendi client'ı).
  ⚠️ ADR-not gerekir: ilke #1 "yalnız mevzuat-mcp API'leri" — bu MCP-tool API'si değil, paketin
  iç public metodu; küçük gerekçeli sapma. Önceki #4 notu ("kaynak zaten düz, zor") YANLIŞTI.

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

## Faz 3 follow-up branch'inin final review'undan (DEFER, merge bloklamaz)
- **(N1, #4 ile bağlantılı)** GVK Geçici 5'in apendiks-sonrası gövdesi (~25.8K) hâlâ tablo
  (CBK/Tebliğ değişiklik geçmişi tablosu — `[n]` işaretsiz, #4 kapsamı) içeriyor. Eval
  `body_temiz < 30000` eşiği #1'i koruyor ama marjı dar (~4K). İyileştirme: eşiği `< 27000`'e
  çek + yorum ekle, veya `len(body) < len(ham_madde)*0.4` gibi daha güçlü invariant.
- **(N2)** #6 (bent-seviyesi yürürlük) ÇALIŞIYOR (gerçek veride 15 mülga bent) ama eval'de
  hiç #6 assertion'ı yok → sessizce bozulabilir. Öneri: `assert mülga_bent_sayısı > 0` ekle.
- enrich.py kullanılmayan `from mevzuat_tool.tree import TreeIndex` import'u (T6 review) — fırsat buldukça sil.
- fikra.py `Fikra.bentler` tip-anotasyonu `list` (eski `list[Bent]`) — forward-ref ile geri kazanılabilir.
- Diğer kozmetik Minor'lar (dipnot var-adı `l`, ids slug çift-çağrı, künye forward-ref, test kapsama boşlukları) — ledger'da kayıtlı, kozmetik.

---

**Durum:** #1, #2, #3, #5, #6, #7 phase-3/followup-amendments branch'inde KAPATILDI.
#4 (tablolar) Faz B'de büyük ölçüde KAPATILDI (aşağı bkz.). Açık kalan: Carry-forward maddeleri.

---

## Faz B — Tümleyici HTML modülü (phase-b/html-structure-analysis)

**Ne yapıldı:** MD omurgaya dokunmadan, ham HTML'den (bedesten_client `get_document_content`)
(1) **#4 içerik tabloları** `<table>→Markdown` cebine (apendiks blacklist'le 11 içerik tablosu;
GVK Madde 103 tarifesi dahil), ve (2) **dipnot `#_ftnN` anchor-bağı** pipeline'a eklendi.
`enrich` iki opsiyonel param kazandı (None-default → mevcut davranış birebir; 62 test yeşil).
Final whole-branch review (opus): "Ready with minor follow-ups (defer)", sıfır must-fix.

**Faz B gerçek-veri bulguları (gözlem, defer):**
- **Anchor yolu regex'ten daha eksiksiz:** VUK'ta 52 maddenin content.md gövdesinde `[n]` işareti
  HİÇ YOK → regex yolu yapısal kör; HTML anchor'ı bu dipnotları kurtarıyor. Bu Faz B'nin değer
  kanıtı. (Metin-örtüşme oranı: TCK %92, KVKK %88, GVK %89, VUK %53.) Gelecekte VUK'un dipnot
  apendiks formatı `split_dipnot_apendiksi`'ye eklenebilir, ama anchor yolu zaten kapatıyor.
- **Dipnot numara uzayları farklı:** HTML `[N]` belge-global (1..221), regex `[n]` madde-yerel.
  `eval_html.py` bu yüzden sayısal değil **metin-örtüşme** invariant'ı kullanıyor.

**Faz B defer-edilen Minor/Important (whole-branch review triage — merge bloklamaz):**
- **(fetch_html try/finally)** `scripts/fetch_html.py` 4 doc'tan biri exception atarsa `client.close()`
  atlanıyor (async client leak). Dev-only cache scripti (çıktı gitignored), etki ~0; `try/finally`
  ile temizlenebilir. Tek satırlık follow-up.
- **(eval _overlaps Important→nit)** Aynı maddede aynı kanun/maddeye 2 atıf teorik birleşebilir
  (+1/madde sınırlı). Eval-gözlem scriptinde, hiçbir teslim artefaktını etkilemez.
- **(eval total_regex)** Özet satırında global `total_regex` accumulator yok (oran denominatoru
  `total_anchor` doğru; sadece gözlem boşluğu).
- **(html_table _TABLE)** non-greedy `.*?` iç içe tabloyu ilk `</table>`'de keser; gerçek veride
  iç içe tablo yok (`irregular=0`, plan-kabul).
- **(html_split kozmetik)** `re.DOTALL` inert; `_canon_prefix` ulaşılamaz defansif dal; em-dash
  `—` testi yok. Hepsi zararsız.
- **(scripts/inspect_metadata.py)** Faz B diff'inin parçası DEĞİL — önceden var olan untracked
  scratch. Merge'e yanlışlıkla karışmamalı.
