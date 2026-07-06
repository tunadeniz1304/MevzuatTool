# Korpus Zehir Temizliği Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Korpustaki 4 gerçek zehri doğru katmanda temizle — anchor kör noktası + madde-arası bleed (parser), tertip-çakışması (retrieval), gövde-kaybı (fetch) — hiçbir çalışan davranışı bozmadan, 0-FP.

**Architecture:** Parser fazları (17/18a/18b) `chunker.py`'deki mevcut bleed-kırpma desenlerini (`_KANUN_SONU_ANCHOR`, `_BLEED_BASLIK`) genişletir; ana `_MADDE` deseni ve mevcut testler dokunulmaz. Retrieval (19) ve fetch (20) fazları ayrı katman — teşhis-önce.

**Tech Stack:** Python 3.11 · `re` · pytest · mevcut `mevzuat_tool.chunker` · `scripts/compare_corpus.py` · mevzuat-mcp (fetch teşhisi)

## Global Constraints

- `text` (embedding gövdesi) BOZULMAZ — yalnız YAPI/bleed-kuyruk kırpılır (içerik kaybı/tekrarı YOK).
- Her parser fix **0-yanlış-pozitif (0-FP)**. Ölçümde FP>0 çıkarsa guard daralt veya ERTELE.
- Ana `_MADDE` deseni DEĞİŞTİRİLMEZ. Mevcut 230 testin TAMAMI yeşil kalır.
- `analiz/` (cowork) klasörüne DOKUNULMAZ — `git add .` KULLANMA, dosyaları tek tek ekle.
- Commit'te AI co-author / "Generated with" YASAK. Atomik commit. Branch: `bugfix/korpus-zehir-temizligi`.
- Build tek süreçte (segfault). Windows: `PYTHONIOENCODING=utf-8`, ASCII çıktı. `/tmp` yerine Windows Temp yolu.
- Test: `.venv/Scripts/python.exe -m pytest -q` (baz: 230 passed). korpus.jsonl git-ignored → commit'lenmez.

---

### Task 1: FAZ 17 — Anchor kör noktası ("X Bakanı yürütür")

**Files:**
- Modify: `src/mevzuat_tool/chunker.py` (`_KANUN_SONU_ANCHOR` deseni, satır ~91-93)
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `_strip_kanun_sonu_ek(body: str) -> str` (chunker.py:128), `split_articles`. Bunlar DEĞİŞMEZ.
- Produces: (yok — mevcut anchor deseni genişler)

**Bağlam:** FAZ 15'te `_KANUN_SONU_ANCHOR = (?i)(?:bakanlar\s+kurulu|cumhurbaşkanı)\s+yürütür\s*\.?`. Eski kanunlarda yürütme cümlesi `<Bakanlık> Bakanı/Bakanları yürütür` (269:6 "Savunma ve Maliye Bakanları yürütür"). Bu anchor'a uymadığı için 6 madde bleed'li. Anchor'a yeni dal eklenince `_strip_kanun_sonu_ek`'in mevcut tümü-büyük-kuyruk guard'ı (>0.85, küçük-harf→kesme) AYNEN çalışır → 0-FP korunur.

- [ ] **Step 1: Hedef + FP-koruma testini yaz (RED)**

`tests/test_chunker.py` sonuna ekle:

```python
def test_strips_kanun_sonu_ek_after_bakan_yurutur():
    # FAZ 17: eski kanunlarda 'X Bakanı/Bakanları yürütür' anchor'ı. Gerçek veri: 269:6
    # '...Savunma ve Maliye Bakanları yürütür. 269 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN ...LİSTE'
    text = ("MADDE 6- (1) Bu Kanunu Millî Savunma ve Maliye Bakanları yürütür. "
            "269 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR LİSTE "
            "KANUN NO FARKLI TARİHTE YÜRÜRLÜĞE GİREN MADDELER")
    arts = split_articles(text)
    assert arts[0].body == "(1) Bu Kanunu Millî Savunma ve Maliye Bakanları yürütür."  # kuyruk kesildi


def test_bakan_yurutur_with_lowercase_tail_not_cut():
    # FP-koruma: 'X Bakanı yürütür' + KÜÇÜK-harf hüküm devamı → KESME (tümü-büyük değil).
    text = ("MADDE 6- (1) Bu Kanunu Maliye Bakanı yürütür ve ilgili kurumlar bu hükme göre "
            "işlemlerini yürütür.")
    arts = split_articles(text)
    assert "ilgili kurumlar" in arts[0].body  # küçük-harf kuyruk kesilmedi
```

- [ ] **Step 2: RED doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_strips_kanun_sonu_ek_after_bakan_yurutur -v`
Expected: FAIL — anchor "Bakanları yürütür"ü yakalamıyor, kuyruk kesilmiyor.

- [ ] **Step 3: `_KANUN_SONU_ANCHOR` desenini genişlet**

`chunker.py` mevcut (satır ~91-93):
```python
_KANUN_SONU_ANCHOR = re.compile(
    r"(?i)(?:bakanlar\s+kurulu|cumhurbaşkanı)\s+yürütür\s*\.?"
)
```
Yerine (yeni dal ekle — `<kelime>(ve <kelime>)? Bakanı/Bakanları`):
```python
_KANUN_SONU_ANCHOR = re.compile(
    r"(?i)(?:"
    r"(?:bakanlar\s+kurulu|cumhurbaşkanı)"
    r"|(?:\w+\s+)?(?:\w+\s+ve\s+)?\w+\s+bakan(?:ı|ları)"   # 'Millî Savunma ve Maliye Bakanları'
    r")\s+yürütür\s*\.?"
)
```

- [ ] **Step 4: GREEN doğrula (hedef + FP-koruma + mevcut anchor testleri)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py -k "kanun_sonu or bakan_yurutur" -v`
Expected: PASS (yeni 2 + mevcut `test_strips_kanun_sonu_ek_*` hepsi yeşil).

- [ ] **Step 5: Tüm suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `232 passed` (230 + 2). Herhangi bir mevcut test kırılırsa DUR.

- [ ] **Step 6: Commit**

```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "feat(chunker): FAZ 17 anchor genisletme (X Bakani/Bakanlari yururtur)

- FAZ 15 anchor sadece Bakanlar Kurulu/Cumhurbaskani yakaliyor
- Eski kanunlarda 'Savunma ve Maliye Bakanlari yururtur' -> 6 madde bleed kaciyor
- Yeni dal: <kelime>(ve <kelime>)? Bakani/Bakanlari yururtur; mevcut guard aynen
- 269:6, 1473:8, 1264:12, 1053:12, 439:17, 168:7"
```

---

### Task 2: FAZ 18a — Madde-arası bleed, kolonlu başlık genişletme

**Files:**
- Modify: `src/mevzuat_tool/chunker.py` (`_BLEED_BASLIK` deseni, satır ~59-61; + liste-başı guard)
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `split_articles` (chunker.py:219, `if not son_madde: body = _BLEED_BASLIK.sub("", body)`). Bu koşul KORUNUR.
- Produces: (yok — `_BLEED_BASLIK` genişler + guard)

**Bağlam:** Mevcut `_BLEED_BASLIK = (?<=[.!?])\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî]*(?:\s+[\wçğıöşüâî]+){0,4}:\s*$` kolonlu başlığı kırpıyor ama DAR: (1) kelime `{0,4}` (max 5) → uzun başlık (7201:53=8 kelime) kaçıyor; (2) virgül yok → `Müracaat, şikayet...` (657:20) kaçıyor. Genişletme: virgül ekle + `{0,9}` + liste-başı guard (633:37 tek FP'yi eler). Ölçüldü: 316 madde EK yakalanır, 0-FP.

- [ ] **Step 1: Hedef + FP-koruma + mevcut-davranış-korunur testini yaz (RED)**

`tests/test_chunker.py` sonuna ekle:

```python
def test_bleed_baslik_wide_comma_and_long_title():
    # FAZ 18a: uzun/virgüllü sonraki-madde başlığı gövde kuyruğuna sızmış. Gerçek veri:
    # 657:20 '...çekilebilirler. Müracaat, şikayet ve dava açma:'; 7201:53 (8 kelime başlık).
    text = ("MADDE 20- (1) Memurlar esaslara göre memurluktan çekilebilirler. "
            "Müracaat, şikayet ve dava açma: MADDE 21- (1) Sonraki madde.")
    arts = split_articles(text)
    assert arts[0].body == "(1) Memurlar esaslara göre memurluktan çekilebilirler."  # başlık kırpıldı
    assert [a.no for a in arts] == ["20", "21"]


def test_bleed_baslik_list_intro_not_cut():
    # FP-koruma: 'aşağıdakiler şunlardır:' gerçek LİSTE-BAŞI → kırpılmaz (guard).
    text = ("MADDE 20- (1) Bu maddede sayılanlar aşağıdaki şunlardır: MADDE 21- (1) Sonraki.")
    arts = split_articles(text)
    assert "şunlardır:" in arts[0].body  # liste-başı korundu


def test_bleed_baslik_existing_short_title_still_cut():
    # Mevcut davranış KORUNUR: kısa (≤4 kelime) kolonlu başlık hâlâ kırpılıyor. Gerçek veri: 3402:40.
    text = "MADDE 40- (1) Kadastro mahkemesine bildirilir. Hatalar ve düzeltme işlemleri: MADDE 41- (1) X."
    arts = split_articles(text)
    assert arts[0].body == "(1) Kadastro mahkemesine bildirilir."
```

- [ ] **Step 2: RED doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_bleed_baslik_wide_comma_and_long_title -v`
Expected: FAIL — mevcut `{0,4}` + virgülsüz desen uzun/virgüllü başlığı kırpmıyor.

- [ ] **Step 3: `_BLEED_BASLIK` genişlet + liste-başı guard ekle**

`chunker.py` mevcut (satır ~59-61):
```python
_BLEED_BASLIK = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî]*(?:\s+[\wçğıöşüâî]+){0,4}:\s*$"
)
```
Yerine:
```python
# Liste-başı sözcükleriyle biten cümle (şunlardır:, aşağıdakiler:) gerçek liste açılışıdır → kırpma.
_LISTE_BASI = re.compile(
    r"(?i)(?:şunlar|aşağıdaki|şöyle|gibidir|belirtilen|sayılanlar|hususlar|kimseler|olanlar|halinde)"
    r"[\wçğıöşüâî ]*:\s*$"
)
# Gövde-taşma (genişletilmiş): sonraki maddenin BAŞLIĞI ('Müracaat, şikayet ve dava açma:') gövde
# kuyruğuna sızmış. Virgül + max 10 kelime kapsanır (uzun/virgüllü başlıklar). Liste-başı guard ayrı.
_BLEED_BASLIK = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî,]*(?:\s+[\wçğıöşüâî,]+){0,9}:\s*$"
)
```

Sonra `split_articles` içinde `_BLEED_BASLIK.sub` çağrısını guard'la sar. Mevcut (chunker.py:219 civarı):
```python
        if not son_madde:  # sonraki maddenin (kolonlu) başlığı gövde kuyruğuna sızmışsa kırp
            body = _BLEED_BASLIK.sub("", body).strip()
```
Yerine:
```python
        if not son_madde:  # sonraki maddenin (kolonlu) başlığı gövde kuyruğuna sızmışsa kırp
            m_bleed = _BLEED_BASLIK.search(body)
            if m_bleed and not _LISTE_BASI.search(body[m_bleed.start():]):  # liste-başı değilse kırp
                body = body[:m_bleed.start()].strip()
```

- [ ] **Step 4: GREEN doğrula (hedef + FP + mevcut-davranış + eski _BLEED testleri)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py -k "bleed" -v`
Expected: PASS — yeni 3 + mevcut `test_body_does_not_swallow_next_article_title` + `test_real_body_ending_with_colon_kept_when_last` yeşil.

- [ ] **Step 5: Tüm suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `235 passed` (232 + 3). Mevcut test kırılırsa DUR (özellikle liste-başı/son-madde testleri).

- [ ] **Step 6: Commit**

```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "feat(chunker): FAZ 18a madde-arasi bleed kolonlu baslik genisletme

- Mevcut _BLEED_BASLIK dar: {0,4} kelime + virgulsuz -> uzun/virgullu baslik kaciyor
- Genislet: virgul + {0,9} kelime; _LISTE_BASI guard (sunlardir: liste-basi korunur)
- Olculdu: 316 madde EK yakalanir, 0-FP (633:37 tek FP guard'la elendi)
- 657:20, 7201:53, 3402:40 (mevcut kisa baslik korunur)"
```

---

### Task 3: FAZ 18a — 916-kanun regresyon kapısı + confusion matrix

**Files:** (kod değişmez — controller yürütür, doğrulama)

**Interfaces:** Consumes `scripts/build_corpus.py`, `scripts/compare_corpus.py`.

**Bağlam:** ⚠️ Build korpusu EZER → baseline kopyala. Beklenen: FAZ 17 (6 madde) + FAZ 18a (~316 madde) = ~322 etkilenen madde, text-kuyruk kısalması. Status-flip 0. Fıkra/bent DEĞİŞMEZ. Bu task CONTROLLER tarafından yürütülür (subagent değil — segfault/tek-süreç + baseline yönetimi).

- [ ] **Step 1: Baseline yedekle**

```bash
cp data/corpus/korpus.jsonl "C:/Users/tuna9/AppData/Local/Temp/zehir_baseline.jsonl"
```

- [ ] **Step 2: Build (tek süreç)**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/build_corpus.py`
Expected: ~66s, `data/corpus/korpus.jsonl` yazılır.

- [ ] **Step 3: Regresyon diff**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/compare_corpus.py "C:/Users/tuna9/AppData/Local/Temp/zehir_baseline.jsonl" data/corpus/korpus.jsonl --flips`
Expected: Etkilenen ~322 madde (FAZ 17 6 + FAZ 18a ~316), eklenen/silinen 0/0, status-flip 0, fıkra/bent dağılımı DEĞİŞMEDİ.

- [ ] **Step 4: Confusion matrix (FP=0 doğrulama)**

Etkilenen maddelerden 30 rastgele örnekle: her kırpım TP (gerçek sonraki-başlık/kanun-sonu-ek) mi FP (meşru içerik) mi? Adversarial agent (kaynak-doğrulamalı) veya controller elle. FP=0 → devam; FP>0 → guard daralt, Task 2'ye dön.

- [ ] **Step 5: E-tuzağı kontrolü**

TMK/TBK/TTK/FSEK/Anayasa (4721/6098/6102/5846/2709) fıkra/bent YAPISI değişmemeli (text-kuyruk kısalması meşru). Doğrula.

- [ ] **Step 6: Ledger'a kaydet** (kod commit yok — korpus git-ignored). Regresyon sonucunu progress ledger'a yaz.

---

### Task 4: FAZ 18b — kolonsuz/roma/bent imzaları (KOŞULLU: ölç → uygula/ertele)

**Files:** (ölçüm-önce; sonuç 0-FP ise chunker.py + test)

**Bağlam:** Kolonsuz başlık (2559:4 `Durdurma ve kimlik sorma` — `:` yok), roma-madde (926:100 `II - Esir astsubaylar:`), bent-harf (6102:1073 `bb) Defter tutma`). Kolonsuz büyük olasılıkla ERTELE (0-FP zor); roma/bent dar olabilir. Master plan kuralı: 0-FP veremezse ERTELE.

- [ ] **Step 1: Her imza için FP-ölçümü**

Controller: roma (`[.!?]\s+[IVX]{1,4}\s*-\s+[A-ZÇĞİÖŞÜ]...`) ve bent (`[.!?]\s+[a-zçğıöşü]{2}\)\s+`) imzalarını korpusta tara; gerçek-bleed vs meşru-içerik (roma madde-içi liste / bent madde-içi olabilir) ayır. Kolonsuz başlık: cümle-sonu + Title-Case kelime dizisi (kolon yok) → meşru cümleden ayırt edilemezse ERTELE.

- [ ] **Step 2: Karar (0-FP ise devam, değilse ertele)**

Her imza için: FP=0 mümkünse Task 2 kalıbıyla TDD + guard uygula; değilse spec'e "ertele (HTML-tabanlı)" not düş. Bu bir DISIPLIN kararı — controller verir, raporlar.

- [ ] **Step 3: (uygulanırsa) TDD + regresyon + commit; (ertelenirse) docs not**

---

### Task 5: FAZ 19 — Tertip-çakışması (retrieval katmanı)

**Files:**
- Modify: retrieval modülü (plan aşamasında taranacak — `grep -rn kanun_no src/` retrieval kullanımları)
- Test: retrieval testleri

**Bağlam:** 14 kanun_no, 2 farklı kanun. İçerik güvende (chunk id/mevzuat_id benzersiz). Sorun: retrieval `kanun_no` filtresi karıştırır. Korpus (chunker/enrich) DEĞİŞMEZ.

- [ ] **Step 1: Retrieval'da kanun_no kullanımını tara**

Run: `grep -rn "kanun_no" src/ | grep -iv "chunker\|enrich\|corpus.py\|fetch"` — retrieval/arama/filtre yollarını bul.
Expected: kanun-bazlı filtre/arama noktaları listesi.

- [ ] **Step 2: Teşhis + tasarım**

Retrieval kanun-filtresi nerede `kanun_no` kullanıyor tespit et. Eğer retrieval modülü henüz yoksa/minimalsa: metadata'da zaten `id` (mevzuat_id tabanlı) var → filtre bunu kullanmalı. Tasarımı bu taramaya göre netleştir.

- [ ] **Step 3: TDD fix (retrieval kanun-filtresi mevzuat_id kullanır)**

14 çakışan kanun_no'dan biriyle (657) test: kanun-filtresi doğru kanunun maddelerini getirmeli (Devlet Memurları vs Harita GM ayrışmalı). Fix + test. Korpus build gerekmez (metadata zaten var).

- [ ] **Step 4: Commit**

```bash
git add <retrieval dosyalari>
git commit -m "fix(retrieval): FAZ 19 tertip-cakismasi mevzuat_id filtre (14 kanun_no)"
```

---

### Task 6: FAZ 20 — Gövde-kaybı 213:93 (fetch teşhisi)

**Files:**
- Investigate: `src/mevzuat_tool/fetch.py`, mevzuat-mcp `get_mevzuat_madde_tree`
- (fix kök-nedene göre)

**Bağlam:** VUK 213 madde 93 kaynakta var, 92/94 korpusta var, 93 YOK. Metin hiç çekilmemiş. Teşhis-önce — kör fix yok.

- [ ] **Step 1: 213 madde-ağacını yeniden çek**

Controller: mevzuat-mcp `search_mevzuat +213` → mevzuat_id; `get_mevzuat_madde_tree` → 93 node var mı? `get_mevzuat_content` → 93 içeriği geliyor mu? Kök: node eksik mi, parse mi atlıyor.

- [ ] **Step 2: Kapsam ölç (tek mi sistematik mi)**

213 madde-ağacında başka atlama var mı; altınset-eksik 406'nın gerçek-eksik alt kümesi (~14-54) bu desende mi. Sistematik ise kök-neden, değilse hedefli.

- [ ] **Step 3: Fix (kök-nedene göre) + doğrula**

Fetch/madde-ağacı parse'ında kök neden düzeltilir; 213 yeniden çekilir; 93 korpusa girer. Doğrula: 213:93 korpusta VAR + içerik kaynakla eşleşir.

- [ ] **Step 4: Commit**

```bash
git add <fetch dosyalari>
git commit -m "fix(fetch): FAZ 20 213:93 govde-kaybi (madde-agaci atlama koku)"
```

---

## Self-Review (plan yazarı — inline)

**1. Spec coverage:**
- FAZ 17 (anchor) → Task 1. ✓
- FAZ 18a (kolonlu bleed) → Task 2 + 3 (regresyon). ✓
- FAZ 18b (kolonsuz/roma/bent, koşullu) → Task 4 (ölç→karar). ✓
- FAZ 19 (tertip, retrieval) → Task 5. ✓
- FAZ 20 (213:93, fetch) → Task 6. ✓
- 5-katmanlı regresyon → Task 3 (build/diff/confusion/E-tuzağı). ✓

**2. Placeholder scan:** Task 1-2 tam kod. Task 3-4-6 controller-yürütür/teşhis-önce (doğası gereği ölçüm — beklenen değerler verildi: ~322 madde, status-flip 0). Task 5 retrieval taraması gerekli (kod henüz haritalanmadı — Step 1 taraması bunun için). Bunlar placeholder değil, teşhis-adımları. FAZ 18b/19/20 doğaları gereği "ölç→karar" — spec de böyle tanımladı.

**3. Type consistency:** `_KANUN_SONU_ANCHOR`, `_BLEED_BASLIK`, `_LISTE_BASI` (yeni), `split_articles`, `_strip_kanun_sonu_ek` — hepsi chunker.py mevcut isimleriyle tutarlı. `_BLEED_BASLIK.search` (sub yerine, guard için) — Task 2 Step 3'te tutarlı kullanıldı.

**Not:** Task 4/5/6 subagent yerine büyük ölçüde CONTROLLER tarafından yürütülür (build/mcp/teşhis, tek-süreç + segfault + katman-geçişi). Task 1-2 saf TDD → subagent-uygun.
