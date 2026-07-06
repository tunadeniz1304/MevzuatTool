# Master Plan — Korpus Yapısal-Sadakat Düzeltmeleri

> **Bu bir MASTER PLAN'dır.** Fazlar buraya kaydedilir; **her faz başlamadan önce kendi detaylı alt-planı** ayrıca yazılır (bkz. "Faz Takip Tablosu"). Tek tek fazlara girilir.
>
> Kaynak: GVK m.2 "fıkra-kapanış son bende yapışıyor" sorununu çözerken yapılan korpus-geneli adversarial denetim → **29 bulgu, 6'sı yeni**. Tüm kök-nedenler kod + canlı korpus testleriyle doğrulandı.

---

## Faz Takip Tablosu

| Faz | Kapsam | Öncelik | Durum | Alt-plan dosyası |
|---|---|---|---|---|
| **FAZ 0** | Altyapı: `compare_corpus.py` + E-tuzağı koruma testleri | ŞİMDİ | ✅ Tamam (commit'li) | [faz-0-altyapi.md](faz-planlari/faz-0-altyapi.md) |
| **FAZ 1** | Yürürlük/mülga (A1+A2+A3) — MVP-kritik | ŞİMDİ | ✅ Tamam (commit'li) | [faz-1-yururluk.md](faz-planlari/faz-1-yururluk.md) |
| **FAZ 2** | Fıkra/bent sınır (B1, B2) | SONRA | ✅ Tamam (commit'li) | [faz-2-fikra-bent-sinir.md](faz-planlari/faz-2-fikra-bent-sinir.md) |
| **FAZ 3** | Numaralı asıl-grup (B3) — en riskli | DİKKATLİ | ✅ Tamam (commit'li) | [faz-3-numarali-grup.md](faz-planlari/faz-3-numarali-grup.md) |
| **FAZ 4** | Sızma (C1, C2) | SONRA | ✅ Tamam (commit'li, confusion FP=0) | [faz-4-sizma.md](faz-planlari/faz-4-sizma.md) |
| **FAZ 5** | Dipnot/tablo (D1; D2/D3 ertelendi) | ERTELENEBİLİR | ✅ Tamam (D1 commit'li) | [faz-5-dipnot-tablo.md](faz-planlari/faz-5-dipnot-tablo.md) |
| **FAZ 6** | Liste-kapanış cümlesi (B4) — GVK m.2 orijinal bug | SONRA | ✅ Tamam (B4 commit'li, 0 FP) | [faz-6-kapanis-cumlesi.md](faz-planlari/faz-6-kapanis-cumlesi.md) |
| **FAZ 7** | Roman-`i)` 3. seviye sızması (Z1) — en ağır zehir | YÜKSEK | ✅ Tamam (Z1 commit'li, 0 FP) | [faz-7-roman-i-3seviye.md](faz-planlari/faz-7-roman-i-3seviye.md) |
| **FAZ 8** | Sarkan kenar-numara (Z4) | DAR | ✅ Tamam (Z4 commit'li, 41 madde 0 FP) | [faz-8-sarkan-kenar-numara.md](faz-planlari/faz-8-sarkan-kenar-numara.md) |
| **FAZ 9** | Kapanış genişletme (Z2) | ORTA | ⏸️ Ertelendi (semantik, regex 0-FP veremez) | — (master Z2 notu) |
| **FAZ 10** | Bleed başlık genişletme (Z3) | YÜKSEK | ✅ Tamam (Z3 commit'li, 30 kesim FP=0) | [faz-10-bleed-baslik.md](faz-planlari/faz-10-bleed-baslik.md) |
| **FAZ 11** | Sarkan roman kenar-numara (Z4-roman) | DAR | ✅ Tamam (commit'li, 14 madde 0 FP) | (faz-8 alt-planı kapsar) |
| **FAZ 12** | Gömülü fıkra (E1) — adversarial denetimle bulundu | YÜKSEK | ✅ Tamam (commit'li, 75 madde, confusion matrix) | [faz-12-gomulu-fikra.md](faz-planlari/faz-12-gomulu-fikra.md) |
| **FAZ 13** | Kiril harf (E2) ✅ + Ezilmiş-liste (SINIF 2) ⏸️ertelendi | ÇOK YÜKSEK | ✅ Kiril commit'li (1 madde 0 FP); SINIF 2 ertelendi (semantik) | [faz-13-ezilmis-liste-kiril.md](faz-planlari/faz-13-ezilmis-liste-kiril.md) |
| **FAZ 14** | Yürürlük dipnot-künye (E3) ✅ + bleed-text/İKİNCİL B kozmetik | DÜŞÜK | ✅ E3 commit'li (2 madde mülga, 0 FP); bleed-text fix-yok | [faz-14-bleed-gecici-yururluk.md](faz-planlari/faz-14-bleed-gecici-yururluk.md) |
| **FAZ 15** | Son-madde kanun-sonu ek bleed (BUG 9) — altınset karşılaştırmasıyla bulundu | YÜKSEK | ✅ Tamam (commit'li, 424 kesim + künye-fix, confusion matrix FP=0, +5 yürürlük düzeltmesi; ~97 Title-Case kayıt ertelendi 0-FP imkansız) | [faz-15-kanun-sonu-bleed.md](faz-planlari/faz-15-kanun-sonu-bleed.md) |
| **FAZ 16** | Madde-bleed / yapışık başlık (BUG 2) — Türkçe `ı`+`M` arası `\b` oluşmaması | ORTA-DÜŞÜK | ✅ Tamam (commit'li, 4 madde HMK 6100, post-tespit + çift-başlık fix, confusion matrix FP=0, 6100-dışı 0 değişim) | [faz-16-madde-bleed.md](faz-planlari/faz-16-madde-bleed.md) |
| **FAZ 17-20** | Korpus zehir temizliği (3-kaynaklı analiz: altınset + cowork + ham-hakem) | YÜKSEK | ✅ Tamam (commit'li: anchor kör-nokta 6 + madde-arası bleed kolonlu/roma ~297 + tertip-çakışması mevzuat_id 14 kanun + gövde-kaybı 213:93/7143; toplam 303 text + 2 madde, status-flip 0, fıkra dağılımı değişmedi, 0-FP) | [faz-17-20-korpus-zehir-temizligi.md](faz-planlari/faz-17-20-korpus-zehir-temizligi.md) |

> Durum kodları: ⬜ Başlanmadı · 🟡 Planlanıyor · 🔵 Uygulanıyor · ✅ Tamam (commit'li) · ⏸️ Beklemede

**Açık karar (ÇÖZÜLDÜ):** Kapanış-kırpma fix'i (46 FP'li ilk deneme) → FAZ 6'da **dar imza (geri-atıflı kapanış, 3 madde, 0 FP)** ile yeniden tasarlanıp commit'lendi. Genişletme borcu (18 TP) aşağıda "Kalan Zehir Kalemleri"nde.

---

## Context

Türk mevzuat RAG parser'ı (`mevzuat-mcp` → yapısal `{id, text, metadata}` korpus, 31.416 madde / 916 kanun).

**Çekirdek tanı:** `text` bütünlüğü (embedding girdisi) **sağlam** — madde içeriği nadiren kaybolur. Ama **yapısal sadakat** (`fikralar[]`/`bentler[]` ağacı + `yurutluk`) **kanun-sınıfına göre çöküyor.** Retrieval'ın yarısı (semantik benzerlik) text'e dayanır ve iyi durumda; diğer yarısı (fıkra/bent atıf çözümü, mülga filtreleme) yapıya dayanır ve burada sistematik kırılmalar var.

**Hedef:** Yapısal sadakati MVP-kritikten kozmetiğe doğru, **her faz bağımsız commit'lenebilir + regresyon-güvenli (0 yanlış-pozitif)** olacak şekilde düzeltmek.

**Sıralama mantığı:** En tehlikeli sınıf **yürürlük hatası** — canlı maddeyi "mülga" gösterip retrieval'dan eler (CLAUDE.md: yürürlük birinci-sınıf metadata). En riskli düzeltme **numaralı-fıkra desteği** — 998 "kenar-numaralı" maddeyi (TMK/TBK/TTK/FSEK/Anayasa) toplu bozma tuzağı taşır; bu yüzden önce koruma testleri kurulur.

### Canlı doğrulanan kritik gerçekler (oturumda çalıştırılan testlerle)
- `(İptal madde: AYM...)` → **"yürürlükte"** ❌ (boş iptal maddesi canlı görünüyor; korpusta **11 madde**, 103326-1..5 zinciri dahil).
- `(İptal bent: AYM...)` → **"yürürlükte"** ❌ (asimetri: `_MULGA_MARKER`'da `fıkra` var, `bent` yok).
- Bent-içi gömülü `ç) (Mülga: tarih)` → `extract_status(konum_duyarli=False)`'ta **"mülga"** ❌ ama `True`'da **"yürürlükte"** ✓ → çözüm yönü: fıkra statüsünü bent ağacından türet.

---

## Sorun → Çözüm Listesi (kök-neden / dosya:satır / çözüm / YP-riski)

### A. Yürürlük/Mülga (MVP-KRİTİK — retrieval'ı doğrudan bozar)

| Kod | Sorun | Kök neden (dosya:satır) | Çözüm | YP-riski |
|---|---|---|---|---|
| **A1** | `(İptal bent:)`/`(Mülga bent:)` salt-iptal bent "yürürlükte" (~10 bent) | `chunker.py:133-135` `_MULGA_MARKER` `fıkra` dalı var, `bent` yok | Dalı `(?:fıkra\|bent)` yap | Düşük |
| **A2** | Bent-içi gömülü `ç) (Mülga:)` TÜM fıkrayı/maddeyi mülga yapıyor (~49 madde + ~129 bent; örn `103829-3` Nüfus K. **Tanımlar** maddesi 28 canlı bent ama "mülga") | `fikra.py:179` fıkra statüsü `extract_status(p)` ile tüm fıkra metninden; `enrich.py:180-182` tüm-fıkra-mülga→madde-mülga | **Fıkra statüsünü bent ağacından türet**: bentler varsa "tümü mülga ise fıkra mülga, değilse yürürlükte"; bentsiz fıkrada mevcut `extract_status` aynen kalır | Orta |
| **A3** | `(İptal madde:)` boş iptal maddesi "yürürlükte" (11 madde, korpusta doğrulandı) | `chunker.py:134` `\(\s*iptal\s*:` `iptal`+`:` bekliyor; `iptal madde:` araya `madde` girince eşleşmiyor | A1 ile aynı dala `madde` ekle: `(?:fıkra\|bent\|madde)` | Düşük |

> A1+A3 tek regex'te birikir → **tek atomik commit**. A2 düzeltmesi (fıkra statüsünü bent ağacından türetme) canlı testle doğrulandı: gerçekten gerekli.

### B. Fıkra/Bent Yapısı

| Kod | Sorun | Kök neden | Çözüm | YP-riski |
|---|---|---|---|---|
| **B1** | Dipnot `]` fıkra sınırını maskeliyor: `...yükümlüdür.[1] (2) Fona...` birleşiyor (605 kaçmış sınır, 582 dipnot) | `fikra.py:24-28` `_FIKRA_BOL` lookbehind `[.:!?]\s\|\n\|)\s`; `]` yok | Lookbehind'a `(?<=\]\s)\(\d+\)\s` dalı ekle | Düşük |
| **B2** | `(N) SAYILI LİSTE/CETVEL` ekli cetvel → sahte fıkra+bent (`104030-5`'te 862 sahte bent) | `fikra.py:24` `_FIKRA_BOL` + `fikra.py:146-161` `_bentler` cetvel bağlamı için negatif-lookahead yok; sıralı-koşu üst-sınırı yok | Cetvel-bağlam guard'ı (`SAYILI LİSTE/CETVEL/TARİFE` öncülü, AND) + bent sıralı-koşu üst-sınırı | Orta |
| **B3** | Numaralı asıl-grup ezilmesi: Gümrük `1. ... 2. a)...` üst-grup görülmüyor, `a)b)c)` tek düz listeye eziliyor (~54 madde) + sarkan-numara `...edilir. 5.` (~60 madde) | `fikra.py:155-160` "ilk-stil-kazanır": `harf` varsa numara yok sayılıyor | İki-seviye bent: harf-bent İÇEREN numaralı-grup varsa `1.`/`2.` üst-bent, `a)` alt-bent. **Yalnız** marjinal-numara değilken (E-tuzağı) | **YÜKSEK (998 md)** |

### C. Sızma (Bleed)

| Kod | Sorun | Kök neden | Çözüm | YP-riski |
|---|---|---|---|---|
| **C1** | Kolonsuz sonraki-madde başlığı (`Yürürlük`, `Hizmet puanı`) `fikralar[-1]`'e sızıyor (~1064 madde) | `enrich.py:72-83` `_strip_bleed` tree-marker'a güveniyor; kolonsuz başlık + `_MADDE_MARKER_SON_ORAN=0.85` kapısından kaçıyor | Tree-bilgili `_bleed_markers`'ı kolonsuz başlık için kullan; **mevcut over-truncation korumalarını** (`enrich.py:78-82`) yeniden kullan (son %15 + `rfind`) | **YÜKSEK** (over-trunc geçmişi) |
| **C2** | Kenar-numaralı başlık `2. Kefalet halinde` kuyrukta | C1 ile aynı mekanizma | C1'in parçası | Orta |

### D. Dipnot/Tablo (kozmetik, ertelenebilir)

| Kod | Sorun | Kök neden | Çözüm | YP-riski |
|---|---|---|---|---|
| **D1** | `[n]` işaretleri text/bent'ten temizlenmiyor (embedding gürültüsü) | `degisiklik.py:60` `temizle_kunyeler` yalnız künye siliyor | `corpus.py` text üretiminde, **dipnot-bağı SONRASI**, `re.sub(r"\[\d+\]","")` | Düşük |
| **D2** | 1-2 dipnotlu son maddede apendiks ayrılmıyor, tanım text'e sızıyor (~85 katı) | `dipnot.py:13` `_ESIK=3` | `_ESIK`'i 2'ye düşür, yoğunluk/kuyruk korumalarını koru | **YÜKSEK** (over-split) |
| **D3** | Tablo `tablolar[]` + `text`'te duplike (~27 chunk) | `corpus.py` `_tablo_duz` bazı varyantları kaçırıyor (Bug 1 kalanı) | `_tablo_duz` normalize eşleşmesini sağlamlaştır | Düşük |

### E. GİZLİ TUZAK (her ilgili fazda korunmalı, ayrı düzeltme değil)
**998 kenar-numaralı madde** (TMK 4721, TBK 6098, TTK 6102, FSEK 5846, Anayasa 2709): `madde_baslik` = `1. Genel olarak` / `A.` / `I.` = marjinal numara, fıkra/bent **değil**. Şu an doğru collapse ediliyor. **B3 (numaralı-fıkra) bu sınıfı bozmamalı** → koruma testleri zorunlu önkoşul (FAZ 0.2).

---

## Faz Bağımlılık Grafiği

```
FAZ 0  Altyapı (kod değişikliği yok) — TÜM fazların önkoşulu
         0.1 scripts/compare_corpus.py  (OLD-vs-NEW korpus diff)
         0.2 tests/test_marginal_numbers.py  (998-madde E-tuzağı koruma testleri)
   │
FAZ 1  Yürürlük/mülga (A1+A2+A3)        ◄── MVP-KRİTİK, ŞİMDİ
   │
FAZ 2  Fıkra/bent sınır (B1, B2)        ◄── güvenli hızlı kazanç, E-tuzağına dokunmaz
   │     (B2, FAZ 3'ten ÖNCE: cetvel sahte-bentleri numaralı-grup mantığını kirletmesin)
   │
FAZ 3  Numaralı asıl-grup (B3)          ◄── EN RİSKLİ, FAZ 0 koruma testleri yeşilken
   │
FAZ 4  Sızma (C1, C2)                   ◄── over-truncation riski, FAZ 1-3 stabil olunca
   │
FAZ 5  Dipnot/tablo (D1, D2, D3)        ◄── ERTELENEBİLİR (D1, B1'den SONRA)
```

**Kritik bağımlılıklar:**
- **B1 ↔ D1:** B1 lookbehind `[n]` VARKEN çalışır; D1 `[n]`'i SİLER. Farklı pipeline aşamaları (B1 parse-zamanı, D1 text-üretim) → çakışma yok, ama **D1 mutlaka FAZ 5'te (sonra)**.
- **B2 → B3:** cetvel guard'ı önce; aksi halde cetvel sahte-bentleri numaralı-grup dedektörünü kirletir.
- **FAZ 3 → FAZ 0.2:** E-tuzağı koruma testleri yeşil olmadan FAZ 3 başlamaz.

---

## Regresyon Test Stratejisi (her faz için aynı döngü)

Geçmiş desen: commit `2158ea7` (yürürlük regresyonu fıkra-ağacıyla düzeltildi, koruma testleri + 916-kanun oranı kontrol).

1. **🔴 Kırmızı birim test** — gerçek madde id'leriyle (yorumda kaynak ref; mevcut `test_fikra.py`/`test_chunker.py` inline-fixture stili). Düşüşü **izle**.
2. **🛡️ True-negative / güvenlik testi** — yanlış-pozitif önleme; her fazda E-tuzağı + over-truncation + atıf testleri yeşil.
3. **♻️ Tam `pytest`** — 173 test (`pytest.ini` `pythonpath=src`). 0 kırık.
4. **📊 916-kanun korpus diff** — `scripts/build_corpus.py` cache'ten ~saniyeler (ağ yok); `compare_corpus.py` ile OLD-vs-NEW:

| Faz | İzlenen metrik | Beklenti / kapı |
|---|---|---|
| 1 | Mülga oranı + **status-flip tablosu** | ~49 madde + ~129 bent → yürürlüğe döner; ~10 bent + 11 madde → mülga. Beklenmeyen flip = regresyon |
| 2 | **Sahte-bent sayısı**, bent dağılımı | 862→~0; atıf testleri korunur |
| 3 | TMK/TBK/TTK/FSEK/Anayasa'da **bent-işaret yapısı / numara-bent ortaya çıkması = 0** (KRİTİK KAPI); Gümrük-tipi bent-derinliği artar | Kenar-numara tetiği yok. ⚠️ Düzeltildi: "etkilenen-madde=0" YANLIŞ kapıydı — B1 dipnot-fıkra ayrımı bu kanunları meşru etkiler (text/bent-yapısı değişmeden); kapı **bent-işaret değişimine** bakmalı (bkz. FAZ 2 sonucu) |
| 4 | Etkilenen-madde ~1064; `fikralar[-1]` uzunluk dağılımı | Kısalma beklenir; aşırı-kısalma = regresyon |
| 5 | text-uzunluk kısalması; tablo-duplike 27→0 | — |

**`scripts/compare_corpus.py` (FAZ 0'da yazılır):** `korpus_OLD.jsonl` vs `korpus_NEW.jsonl` id-bazlı eşleştirir; mülga-oranı, bent-sayısı dağılımı, sahte-bent proxy'si (>30 ardışık bent / tekrarlayan `a)` koşusu), etkilenen-madde id listesi, status-flip tablosu üretir. `eval_corpus_report.py` agregat stilini taklit eder.

**Disiplin:** TDD (önce kırmızı), 0 yanlış-pozitif, atomik commit, AI co-author satırı YASAK, `phase-N/feature` branch (doğrudan `main` push yok).

---

## Verification (her faz sonunda)

1. `python -m pytest -q` → 173+ yeni testler, 0 kırık.
2. `CORPUS_LIMIT=5 python scripts/build_corpus.py` → smoke (parse hatası yok).
3. Tam korpus: `python scripts/build_corpus.py` (cache, ~saniyeler) → `korpus_NEW.jsonl`.
4. `python scripts/compare_corpus.py korpus_OLD.jsonl korpus_NEW.jsonl` → faza özgü metrik + status-flip/etkilenen-madde tablosu; **kritik kapılar** doğrulanır.
5. Spot-check: faza özgü gerçek id'ler (103829-3, 4458-M3, 104030-5, TMK-4721-M5, 103326-1) manuel kontrol.

---

## Kapsam Notu
- Bu plan **yalnız KANUN** türü kapsamında (ADR-0013); generation/embedding kapsam dışı (retrieval'da biter).
- İlgili: [decisions.md](decisions.md) (ADR-0004 atomik birim=madde, ADR-0005 yürürlük birinci-sınıf), [metadata-cikarim-raporu.md](metadata-cikarim-raporu.md) (metadata çıkarım algoritması), [commit_discipline.md](commit_discipline.md).

---

## Kalan Zehir Kalemleri (FAZ 1-6 sonrası, korpus-geneli ölçüldü 2026-06-29)

> "Zehir" = retrieval'ı bozan. `text` (embedding) genelde sağlam; risk **yapısal sadakatte**
> (atıf/filtre çözümünü kıran bozuk `bentler[]` ağacı). Aşağıdakiler ölçülmüş açık kalemlerdir.

| # | Sorun | Frekans | Zehir tipi | Öncelik |
|---|---|---|---|---|
| **Z1** | ✅ **ÇÖZÜLDÜ (FAZ 7)** — Roman-rakam `i)` 3. seviye sızması: `a) > i) ii)` üç-seviye hiyerarşide `i)` harf-bent sanılıyordu; harf-listesine kardeş giriyor → bir harf-bent BOŞ kalır | **5 madde düzeltildi** (488 Damga, 492 Harçlar, 4458 Gümrük×2, 193 GVK) | **Yapı (ağır):** boş düğüm + atıf çözülmez | ✅ commit `c82baee`, 0 FP |
| **Z2** | ⏸️ **ERTELENDİ (çözülemez-güvenle)** — Kapanış-cümlesi genişletme (B4'ün kaçırdığı geri-atıfsız kapanış). **Ölçüm (FAZ 9):** B4-imzalı 16 geri-atıfsız aday içinde kod-sinyali (kelime/fiil) FN-etiketleriyle yalnız **11/16** uyuşuyor; 1 tehlikeli yanlış (`103055-52` TP sanılıp kesilirse over-truncation FP). TP/FP ayrımı **semantik** (cümle listeye mi son bende mi atıf yapıyor), regex 0-FP veremez. B4'ün dar 3-madde kapsamı korunur. | 18 TP | **Yapı (orta)** | ⏸️ ertelendi (kullanıcı, 2026-06-29) |
| **Z3** | ✅ **ÇÖZÜLDÜ (FAZ 10)** — Bleed başlık kalanı: C1 sözlüğüne 7 güvenli başlık eklendi (Tanımlar/Kapsam/Yönetmelik...). Confusion matrix 30 kesim, **0 FP**. | 30 madde düzeltildi | **Yapı (orta)** | ✅ commit `1a45936` |
| **Z4** | ✅ **ÇÖZÜLDÜ (FAZ 8)** — Sarkan kenar-numara: sonraki maddenin kenar-numarası (`6.`) gövde kuyruğundan kırpılır. | **41 madde** (FSEK 16, Kooperatifler 22, KMK 3) | **Yapı (düşük)** | ✅ commit `4dcb7de`, 0 FP |
| **Z4-roman** | ✅ **ÇÖZÜLDÜ (FAZ 11)** — Roman kenar-numara kuyruğu (`...uygulanmaz. III.`); `_SARKAN_KENAR_NUMARA_RE`'ye `[IVX]+` dalı + iki-aşamalı kesim (Z3 sonrası). | **14 madde** (İcra-İflas, Orman, TBK) | Gürültü | ✅ commit `dd9aba6`, 0 FP |
| **Z3-geniş** | 🆕 Sonraki maddenin TAM içeriği sızmış (`104456-13`: `III. Ormanların muhafazası ...`); `Ormanların muhafazası` C1 sözlüğünde yok → bütün madde dahil sızma | ~2 madde + kuyruk | Yapı (orta) | ⬜ açık (Z3 kalanı) |
| **Z5** | **Append/dipnot bölgesi sızması** (`5648 SAYILI KANUNA EK...` alt-bende karışıyor) | birkaç (103983-22) | **Gürültü:** D2 alanı | DÜŞÜK (FAZ 5'te D2 ertelendi) |
| **Z6** | 🆕 **Parantez-atıf bent'e yapışması** (`104055-8`: `d) (c) ve (ç) bentlerinde...` → `d)` bendi `(`'de kesilip BOŞ kalıyor, `(c)`/`(ç)` atfı ayrı "bent" sanılıyor). E1'in (gömülü fıkra) bent-seviyesi kardeşi; `_ATIF_ONCUL` mantığının bent-içi versiyonu gerekir. | **1 madde** (korpus-sağlık taraması, 2026-07-01) | **Yapı (düşük):** `d)`+`e)` boş düğüm; AMA `text` sağlam (kelime kaybı 0), retrieval'a etki minimal | ⏸️ ertelendi (frekans 1 + riskli: `d) (c)` atıf ile `d) (1)` meşru-fıkra ayrımı semantik, 0-FP veremez; E-tuzağı riski) |

> **NOT — "dev bent ≠ zehir":** İlk tarama 329 ">2000 krk bent" buldu ama **307'si meşru uzun
> hüküm** (`102965-11` KDV istisna `c)` 2080 krk = gerçekten uzun, yapı sağlam; `103689-135`
> Avukatlık disiplin `1.` 22 alt-bent = doğru parse). Gerçek zehir kriteri **uzunluk değil
> yapı bozulması**: boş/kaçmış alt-bent VEYA harf-sırası kırılması (`a)...i)...b)...i)` tekrarı,
> veya konum-dışı `i)` = `f)` ile `g)` arasında). Bu filtreyle 329 → **12 gerçek-zehir**.

### Z1 kök neden + ÇÖZÜM (FAZ 7, doğrulandı — 103017-Ek2 Damga V.)
Gerçek yapı 3 seviyeli: `2.` (üst) → `a) b) c)...` (orta) → `i) ii)` (alt-alt, roman). Parser
`_BENT_HARF_ISARET = [a-zçğıöşü]\)` ile `i)`'yi orta-seviye harf-bent sanıyordu →
`a)`'nın altındaki `i)` bloğu `a)`'dan koparılıyor, `b)`'nin altındaki `i)` de `b)`'den
koparılıyor → **`b)` bomboş** (`len=2`). B3 (FAZ 3) iki-seviye destekliyor, **3. seviye yoktu**.

**ÇÖZÜM (`_roman_i_idx`, kullanıcı kararı=dar):** KESİN-ROMAN sinyali (0 FP) — `i)` işareti
(a) TEKRARLI (harf-listede `i` bir kez olur; 2+ = roman) VEYA (b) bir önceki harf-bent BOŞ
(`f) i)` bitişik). `_harf_alt_bentler` roman `i)`'yi işaret olarak ATLAR → dilimleme onu bir
önceki harf-bende yapıştırır. Meşru harf-bent `i)` (`...ı) i) j)...` veya tek+dolu `...h) i) j)`)
DOKUNULMAZ. **Kapsam kararı (kullanıcı, 2026-06-29): dar (kesin-roman), 3. seviye katmanı kurma.**

**Sonuç:** etkilenen 5 madde (hepsi text korundu), boş-alt-bent 3→0, 3 meşru-`i)` listesi
korundu (0 FP). Master "şüpheli" sayılan `103006-Mukerrer298`/`103161-Gecici11` doğru biçimde
MEŞRU çıktı, dokunulmadı. İlk tahmin "~12 üst-bent" abartılıydı — gerçek zehir 5, kalanı meşru.
