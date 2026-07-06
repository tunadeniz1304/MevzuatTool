# FAZ 15 — Son-madde kanun-sonu ek bleed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kanunun son maddesine ("...Bakanlar Kurulu/Cumhurbaşkanı yürütür") yapışan kanun-sonu ek çöpünü (değişiklik-listesi tablosu, kadro/tarife cetvelleri, tümü-büyük belge başlıkları) gövdeden 0-yanlış-pozitif kırpmak.

**Architecture:** `chunker.py`'de mevcut `_SEVIYE_BASLIK_BLEED` / `_ISLENEMEYEN_EKI` kardeşi yeni `_KANUN_SONU_EK_BLEED` regex + `split_articles` içinde gövde-kuyruğu kırpma. Madde ağacı DEĞİŞMEZ; yalnız son-madde gövde kuyruğundaki çöp kesilir. `text` içindeki meşru içerik korunur.

**Tech Stack:** Python 3.11, `re` (regex), pytest, `scripts/compare_corpus.py` (916-kanun regresyon).

## Global Constraints

- **AI co-author / "Generated with" satırı YASAK** commit mesajlarında (CLAUDE.md).
- **Branch:** `bugfix/phase-15-corpus-fixes`. `main`'e doğrudan push YASAK.
- **Atomik commit**, `type(scope): özet` formatı.
- **0-yanlış-pozitif (0-FP):** meşru içerik kesilmemeli. FP>0 → daralt veya ertele.
- **`text` (embedding) bozulmaz**, yalnız yapı düzelir.
- **Mevcut 217 test YEŞİL kalmalı** — özellikle B1/B2/B3/A2/E-tuzağı/`_SEVIYE_BASLIK_BLEED`/E1-E3.
- **E-tuzağı 5-kanun** (TMK 4721 / TBK 6098 / TTK 6102 / FSEK 5846 / Anayasa 2709) DEĞİŞMEZ (sert kapı).

---

## Desen (gerçek-veri doğrulaması — bu oturumda ölçüldü)

**Sınır kuralı:** ANCHOR `(Bakanlar Kurulu|Cumhurbaşkanı)\s+yürütür\s*\.?` + kuyruk (anchor sonrası,
baştaki `. \n` atılmış) **tümü-büyük blokla** başlıyorsa (ilk 80 kar'ın büyük-harf oranı >0.85),
kuyruğu (anchor sonundan madde sonuna) kes.

**Ölçüm (korpus 31.416):** 432 kesim, hepsi gerçek çöp ("X SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN...",
"SAYILI LİSTE/CETVEL", "EK GÖSTERGE CETVELİ"). 0 meşru kayıp. 85 küçük-harf-kuyruk vaka ERTELENİR
(bu fazın dışı — semantik, tümü-büyük değil: 7326:18 CB Kararı düz metin).

**Güvenlik (0-FP anahtarı):**
- Anchor ŞART (anchorsuz salt-sınır = 299 tüm-madde-kaybı felaketi).
- Kuyruk tümü-büyük OLMALI — küçük-harf başlarsa (meşru hüküm cümlesi/düz-metin çöp) KESME.
- Meşru "Yürürlük" maddeleri "yürütür" içermez → anchor dokunmaz.

---

## File Structure

- **Modify:** `src/mevzuat_tool/chunker.py` — yeni `_KANUN_SONU_EK_BLEED` regex + yardımcı fonksiyon
  `_strip_kanun_sonu_ek(body)` + `split_articles` içinde çağrı. Sorumluluk: son-madde gövde-kuyruğu
  çöp kırpma (mevcut bleed ailesine paralel).
- **Test:** `tests/test_chunker.py` — kesim + FP-koruma testleri (mevcut bleed testleri modeli).

---

### Task 1: `_KANUN_SONU_EK_BLEED` deseni + kırpma fonksiyonu (TDD)

**Files:**
- Modify: `src/mevzuat_tool/chunker.py` (yeni regex + `_strip_kanun_sonu_ek`, `split_articles` çağrısı ~114)
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `split_articles(text: str) -> list[Article]` (mevcut), `Article.body: str`.
- Produces: `_strip_kanun_sonu_ek(body: str) -> str` — anchor sonrası tümü-büyük kuyruğu kesip döndürür;
  eşleşme yoksa `body`'yi değiştirmeden döndürür. `split_articles` bunu her maddenin body'sine uygular.

- [ ] **Step 1: Kesim testini yaz (RED)**

`tests/test_chunker.py` sonuna ekle:

```python
def test_strips_kanun_sonu_ek_after_yurutme():
    # BUG 9 (FAZ 15): son madde 'yürütür' + kanun-sonu ek (tümü-büyük cetvel/liste) gövdeye sızmış.
    # Gerçek veri (5996:50 Gıda K., 7440:25): '...Bakanlar Kurulu yürütür. GIDA VE YEM İŞLETMELERİ...
    # 5996 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN...'. Anchor sonrası tümü-büyük kuyruk kırpılmalı.
    text = ("MADDE 49- (1) Bu Kanun yayımı tarihinde yürürlüğe girer. "
            "MADDE 50- (1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür. "
            "7440 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN VEYA ANAYASA "
            "MAHKEMESİ KARARLARININ YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR LİSTE "
            "Değiştiren Kanunun Numarası 7456 Yürürlüğe Giriş Tarihi 15/7/2023")
    arts = split_articles(text)
    assert [a.no for a in arts] == ["49", "50"]
    assert arts[1].body == "(1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür."  # kuyruk kesildi
```

- [ ] **Step 2: Testi çalıştır, FAIL doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_strips_kanun_sonu_ek_after_yurutme -v`
Expected: FAIL — `arts[1].body` "7440 SAYILI KANUNA..." kuyruğunu içeriyor (kırpma yok henüz).

- [ ] **Step 3: Regex + fonksiyonu ekle (minimal)**

`chunker.py`'de `_SEVIYE_BASLIK_BLEED` tanımından SONRA (satır ~79) ekle:

```python
# Kanun-sonu ek bleed (FAZ 15 / BUG 9): kanunun SON maddesi 'yürütme'dir ('...Bakanlar Kurulu/
# Cumhurbaşkanı yürütür') — kısa, tek cümle. Ama split_articles son maddede end=len(text) olduğu
# için, ardından gelen kanun-sonu ekleri (değişiklik-listesi tablosu 'X SAYILI KANUNA EK VE
# DEĞİŞİKLİK GETİREN...', kadro/tarife cetvelleri 'N SAYILI LİSTE/CETVEL', 'EK GÖSTERGE CETVELİ')
# gövdeye giriyor (5996:50=5791 kar, 7440:25...). ANCHOR = 'yürütür' cümlesi; kuyruk (anchor sonrası)
# TÜMÜ-BÜYÜK belge başlığıyla başlıyorsa oradan sona kes. Ölçüm: 432 kesim, 0 FP (hepsi çöp).
# 0-FP KAPILARI: (1) anchor ŞART (anchorsuz salt-sınır 299 tüm-madde-kaybı); (2) kuyruk tümü-büyük
# OLMALI — küçük-harf başlarsa (meşru hüküm/düz-metin çöp: 7326:18 CB Kararı) KESME → ertelenen semantik;
# (3) meşru 'Yürürlük' maddeleri 'yürütür' içermez, anchor dokunmaz.
_KANUN_SONU_ANCHOR = re.compile(
    r"(?i)(?:bakanlar\s+kurulu|cumhurbaşkanı)\s+yürütür\s*\.?"
)


def _strip_kanun_sonu_ek(body: str) -> str:
    """Son-madde 'yürütür' anchor'ı sonrası TÜMÜ-BÜYÜK kanun-sonu ek kuyruğunu kırp (0-FP).
    Anchor yoksa VEYA kuyruk tümü-büyük değilse body değişmez."""
    a = _KANUN_SONU_ANCHOR.search(body)
    if not a:
        return body
    kuyruk = body[a.end():].lstrip(". \n")
    if len(kuyruk) < 30:            # kuyruk yok/kısa → temiz madde
        return body
    ilk = kuyruk[:80]
    harf = [c for c in ilk if c.isalpha()]
    if not harf:
        return body
    buyuk_oran = sum(c.isupper() for c in harf) / len(harf)
    if buyuk_oran <= 0.85:          # küçük-harf kuyruk (meşru/düz-metin çöp) → KESME (ertele)
        return body
    return body[:a.end()].strip()   # anchor'a kadar tut, tümü-büyük kuyruğu at
```

Sonra `split_articles` içinde, `_SEVIYE_BASLIK_BLEED.sub` satırından (satır ~111) SONRA ekle:

```python
        body = _strip_kanun_sonu_ek(body)
```

- [ ] **Step 4: Testi çalıştır, PASS doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_strips_kanun_sonu_ek_after_yurutme -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "feat(chunker): FAZ 15 kanun-sonu ek bleed kirpma (BUG 9, anchor+tumu-buyuk)"
```

---

### Task 2: FP-koruma testleri (meşru içerik kesilmez)

**Files:**
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `split_articles`, `_strip_kanun_sonu_ek` (Task 1).

- [ ] **Step 1: FP-koruma testlerini yaz (bunlar İLK SEFERDE PASS olmalı — Task 1 kodu zaten korumalı)**

`tests/test_chunker.py` sonuna ekle:

```python
def test_yurutme_without_ek_kept():
    # Koruma: 'yürütür' + kanun-sonu ek YOK (temiz yürütme maddesi) → kırpma yapılmaz.
    text = "MADDE 10- (1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür."
    arts = split_articles(text)
    assert arts[0].body == "(1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür."


def test_yurutme_with_lowercase_tail_not_cut():
    # Koruma: 'yürütür' sonrası KÜÇÜK-harf devam (meşru hüküm/düz-metin çöp) → KESME (bu faz dışı,
    # ertelenen semantik vaka: 7326:18 CB Kararı düz metin). Sadece tümü-büyük çöp kesilir.
    text = ("MADDE 18- (1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür. Bu Kanunun uygulanması "
            "ile ilgili olarak Cumhurbaşkanı Kararı ile düzenleme yapılır.")
    arts = split_articles(text)
    assert arts[0].body.endswith("düzenleme yapılır.")  # küçük-harf kuyruk KESİLMEZ


def test_yururluk_madde_with_uppercase_law_ref_not_over_cut():
    # Koruma: 'yürürlük' maddesi (yürürlüğe-giriş) 'yürütür' içermez → anchor hiç eşleşmez,
    # tümü-büyük kanun-adı atfı olsa bile dokunulmaz.
    text = ("MADDE 20- (1) Bu Kanunun 5 inci maddesi 6098 SAYILI TÜRK BORÇLAR KANUNU ile birlikte "
            "1/1/2024 tarihinde yürürlüğe girer.")
    arts = split_articles(text)
    assert "6098 SAYILI" in arts[0].body  # yürürlük maddesi kesilmez (anchor yok)
```

- [ ] **Step 2: Testleri çalıştır, PASS doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py -k "yurutme or yururluk" -v`
Expected: 3 PASS (Task 1 kodu bu korumaları zaten sağlıyor — anchor+tümü-büyük şartları).

Eğer biri FAIL ederse: Task 1 deseni yanlış (FP üretiyor); düzelt, tekrar çalıştır.

- [ ] **Step 3: Commit**

```bash
git add tests/test_chunker.py
git commit -m "test(chunker): FAZ 15 FP-koruma (temiz yurutme/kucuk-harf/yururluk kesilmez)"
```

---

### Task 3: Tüm test suite + build + 916-kanun regresyon kapısı

**Files:**
- (kod değişikliği yok — doğrulama task'ı)

- [ ] **Step 1: Tüm testleri çalıştır (217+3 yeni = 220)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: TÜMÜ PASS (220 passed). Bir tek kırılırsa Task 1 deseni bir mevcut davranışı bozdu → incele/düzelt.

- [ ] **Step 2: Baseline korpusu yedekle (build ÖNCESİ)**

Mevcut `data/corpus/korpus.jsonl` = OLD baseline (FAZ 14 çıktısı). Yedekle:

Run: `cp data/corpus/korpus.jsonl /tmp/korpus_OLD_faz14.jsonl`
Expected: dosya kopyalandı.

- [ ] **Step 3: Korpusu yeniden üret (NEW — FAZ 15 kodu)**

Korpus üretici cache'li fetch kullanır (916 kanun, ~dakikalar). Proje kökünde:

Run: `.venv/Scripts/python.exe scripts/build_corpus.py`
Expected: `data/corpus/korpus.jsonl` yeniden yazıldı (NEW, FAZ 15 kırpması dahil). Çıktı: "916 kanun işlenecek -> data/corpus/korpus.jsonl" + süre.

> ⚠️ Build korpusu ezer. Kötü çıkarsa Step 2 yedeğinden geri yükle: `cp /tmp/korpus_OLD_faz14.jsonl data/corpus/korpus.jsonl`
> ⚠️ **KOORDİNASYON:** Arka plandaki retrieval tam-ölçümü (`metrik_tam_ckpt.py`) `korpus.jsonl`'i
> BAŞLANGIÇTA okuyup belleğe alır (BM25 index). Çalışan ölçüm build'den etkilenmez AMA:
> (a) ölçüm devam-ettirilirse yeni korpusu okur → tutarsızlık. **Build'i ölçüm BİTENE kadar beklet**
> (`.olcum_tam.txt` oluşana kadar), VEYA Task 1-2'yi (kod+test, korpusu ezmez) şimdi yap, Task 3 build'i
> ölçüm bitince çalıştır. (b) Task 1-2 hiç build gerektirmez (sadece birim test) — güvenle şimdi yapılır.

- [ ] **Step 4: 916-kanun compare — etkilenen madde + status-flip + E-tuzağı**

Run: `.venv/Scripts/python.exe scripts/compare_corpus.py /tmp/korpus_OLD_faz14.jsonl data/corpus/korpus.jsonl`
Expected kontroller:
- **Etkilenen-madde:** ~432 (yürütme/son-madde), hepsi "yürütür"lu. Beklenenden çok fazlaysa (örn. >500) FP şüphesi.
- **Status-flip:** 0 (bleed kırpma yürürlüğü değiştirmemeli).
- **Yalnız-OLD/yalnız-NEW id:** 0 (madde ekleme/silme olmamalı — sadece gövde kısaldı).

- [ ] **Step 5: E-tuzağı sert kapısı**

Run: `.venv/Scripts/python.exe scripts/compare_corpus.py /tmp/korpus_OLD_faz14.jsonl data/corpus/korpus.jsonl --kanun 4721,6098,6102,5846,2709`
Expected: **0 etkilenen** (E-tuzağı 5 kanunu değişmemeli — bunlarda "yürütür+tümü-büyük ek" yok). Etkilenirse → desen bu kanunlara sızmış, DUR ve incele.

- [ ] **Step 6: Commit (baseline diff notu)**

```bash
git add data/corpus/korpus.jsonl
git commit -m "build(corpus): FAZ 15 kanun-sonu bleed kirpma uygulandi (~432 madde, status-flip 0)"
```

---

### Task 4: Confusion matrix — adversarial FP doğrulaması (0-FP kanıtı)

**Files:**
- (kod yok — adversarial doğrulama; sonuç master plan + faz-planı dokümanına yazılır)

- [ ] **Step 1: Etkilenen 432 maddenin listesini çıkar**

Run: `.venv/Scripts/python.exe scripts/compare_corpus.py /tmp/korpus_OLD_faz14.jsonl data/corpus/korpus.jsonl --flips` (VEYA etkilenen-madde id dökümü; compare çıktısındaki etkilenen-madde listesini `.tmp_faz15/etkilenen.txt`'e yaz)
Expected: ~432 (kanun_no, madde_no) id listesi.

- [ ] **Step 2: Adversarial confusion matrix (agent)**

Bir subagent'a etkilenen maddelerin OLD (kesim-öncesi) vs NEW (kesim-sonrası) body'lerini ver; her kesimi
TP (gerçek kanun-sonu çöp) / FP (meşru içerik kaybı) sınıflandırt. Kaynak-doğrulamalı (mevzuat-mcp opsiyonel).
Örneklem: en az 30 madde tek tek + desen analizi.

- [ ] **Step 3: KARAR KURALI uygula**

- **FP=0** ve E-tuzağı+çürütülen değişmemiş → FAZ 15 ONAYLANDI, commit'ler kalır.
- **FP>0** → deseni daralt (örn. buyuk_oran eşiğini 0.90'a çıkar VEYA 'SAYILI/CETVEL/LİSTE' anahtar-şartı ekle),
  Task 1-3'ü tekrarla. Daraltılamıyorsa ETKİLENEN alt-kümeyi ertele.

- [ ] **Step 4: Faz-planı dokümanı + master plan güncelle**

`docs/faz-planlari/faz-15-kanun-sonu-bleed.md` oluştur (E1-E3 planları modeli: sonuç + confusion matrix +
sert kapılar). `docs/yapisal-sadakat-master-plan.md` faz tablosuna FAZ 15 satırı ekle (✅ Tamam, N madde, 0 FP).

```bash
git add docs/faz-planlari/faz-15-kanun-sonu-bleed.md docs/yapisal-sadakat-master-plan.md
git commit -m "docs(faz-15): kanun-sonu bleed tamam, confusion matrix FP=0"
```

---

## Self-Review Notu

- **Spec coverage:** FAZ 15'in tüm gereksinimleri (anchor+tümü-büyük, 0-FP, 5-katmanlı kapı) Task 1-4'te.
  FAZ 16 (madde-bleed) AYRI plan — bu plan yalnız FAZ 15.
- **Ertelenen (85 küçük-harf-kuyruk) vaka:** Task 2'de `test_yurutme_with_lowercase_tail_not_cut` ile
  bilinçli korunuyor (kesilmiyor) — spec'in "ertele" kararıyla tutarlı.
- **Build komutu belirsizliği:** Task 3 Step 3'te korpus üretim komutu `ls` ile doğrulanacak (proje-özel).
  Bu tek belirsizlik; executor build script'ini teyit edip çalıştırır.
