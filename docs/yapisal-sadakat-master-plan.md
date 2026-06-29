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

> Durum kodları: ⬜ Başlanmadı · 🟡 Planlanıyor · 🔵 Uygulanıyor · ✅ Tamam (commit'li) · ⏸️ Beklemede

**Açık karar (FAZ'lardan bağımsız):** Kapanış-kırpma fix'i (çalışma ağacında, **46 yanlış-pozitifli**) — geri al / yeniden tasarla / FAZ olarak ekle? 46 FP'nin 14'ü zaten B3 sınıfı.

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
