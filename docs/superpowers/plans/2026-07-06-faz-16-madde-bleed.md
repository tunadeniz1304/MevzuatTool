# FAZ 16 — Madde-bleed / Yapışık Başlık Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kaynak metinde önceki maddenin gövdesine boşluksuz yapışık gelen madde başlıklarını (`...şartlarıMADDE 132- (1)`) tespit edip ayrı chunk'lara böl — 6100 (HMK) 132/133/135/165 maddeleri korpusa ayrı girsin.

**Architecture:** `split_articles` (chunker.py) içinde, madde bölündükten sonra çalışan yeni bir post-tespit adımı. Ana `_MADDE` regex'i DEĞİŞMEZ (Yaklaşım B). Her `body` içinde `<sözcük-karakteri>MADDE <no>- (` yapışık deseni aranır; bulunursa gövde cümle-sonu (`[.!?]`) sınırından bölünüp gömülü madde(ler) ayrı `Article` olarak üretilir. Mevcut `_BLEED_BASLIK` / `_SEVIYE_BASLIK_BLEED` kardeşi mimari.

**Tech Stack:** Python 3.11 · `re` (stdlib) · pytest · mevcut `mevzuat_tool.chunker`

## Global Constraints

- `text` (embedding gövdesi) BOZULMAZ — yalnız YAPI düzelir (bir chunk ikiye/üçe ayrılır, içerik korunur).
- Her fix **0-yanlış-pozitif (0-FP)** olmalı. Veremezse ERTELE.
- Yalnız KANUN türü. Ana `_MADDE` deseni DEĞİŞTİRİLMEZ (regresyon yüzeyi minimum).
- Commit mesajlarında **AI co-author / "Generated with" satırı YASAK**.
- Atomik commit, `type(scope): özet` formatı. Branch: `bugfix/phase-16-madde-bleed`.
- Build tek süreçte (aynı anda iki ağır python = segfault). Windows: `PYTHONIOENCODING=utf-8`, ASCII çıktı.
- Test komutu: `.venv/Scripts/python.exe -m pytest -q` (baz: 224 passed).

---

### Task 1: Yapışık-madde tespit deseni + bölme fonksiyonu (TDD)

**Files:**
- Modify: `src/mevzuat_tool/chunker.py` (yeni `_YAPISIK_MADDE` deseni + `_split_yapisik_madde` fonksiyonu, `split_articles` içine çağrı)
- Test: `tests/test_chunker.py` (yeni test fonksiyonları)

**Interfaces:**
- Consumes: `Article` dataclass (`no: str`, `body: str`) — chunker.py:48-51. `split_articles(text: str) -> list[Article]` — chunker.py:155.
- Produces: `_split_yapisik_madde(no: str, body: str) -> list[Article]` — bir maddenin `(no, body)`'sini alır; gövdede yapışık gömülü madde varsa `[Article(no, ust_body), Article(gomulu_no, gomulu_body), ...]` sırasıyla döner; yoksa `[Article(no, body)]` döner.

**Bağlam (implementer için — sıfır bağlam varsayımı):**
Türk kanunlarında bir maddenin başlığı (`Karşı davanın şartları`) genelde önceki maddenin son cümlesinden sonra, `MADDE N- (1)` işaretiyle başlar. Kaynak HTML'de bazen bu başlık önceki gövdeye boşluksuz yapışır: `"...ileri sürülemez. Karşı dava açılabilmesinin şartlarıMADDE 132- (1) Karşı dava..."`. Ana `_MADDE` regex'i `MADDE` öncesi `\b` (sözcük-sınırı) beklediği için, Türkçe küçük harf (`ı`) + `M` arasında `\b` oluşmaz → bu madde yakalanamaz → önceki maddenin gövdesine gömülür.

`body` formatı: `"<başlık>\n<gövde>"` VEYA başlıksız düz gövde. Bölme noktası: gömülü `MADDE`'den GERİYE en yakın cümle-sonu (`[.!?]`). O noktaya kadarki metin üst-maddede kalır; cümle-sonundan `MADDE`'ye kadarki metin gömülü maddenin BAŞLIĞI; `MADDE N- (1)` sonrası gömülü maddenin gövdesi.

- [ ] **Step 1: Yapışık-madde bölme testini yaz (RED)**

`tests/test_chunker.py` dosyasının SONUNA ekle:

```python
def test_splits_embedded_madde_stuck_to_previous_body():
    # FAZ 16 (BUG 2): kaynak metinde sonraki maddenin başlığı önceki gövdeye BOŞLUKSUZ yapışık.
    # Türkçe küçük 'ı' + 'M' arası \b oluşmaz → _MADDE yakalayamaz → madde gömülür. Gerçek veri:
    # 6100 (HMK) M131 '...şartlarıMADDE 132- (1)...' ve '...süresiMADDE 133- (1)...'.
    text = ("MADDE 131- (1) Süresinden sonra karşı dava açılamaz. "
            "Karşı dava açılabilmesinin şartlarıMADDE 132- (1) Karşı dava açılabilmesi için şu şartlar aranır. "
            "Karşı davanın açılması ve süresiMADDE 133- (1) Karşı dava cevap dilekçesiyle açılır.")
    arts = split_articles(text)
    assert [a.no for a in arts] == ["131", "132", "133"]
    assert arts[0].body == "(1) Süresinden sonra karşı dava açılamaz."
    assert arts[1].body == "Karşı dava açılabilmesinin şartları\n(1) Karşı dava açılabilmesi için şu şartlar aranır."
    assert arts[2].body == "Karşı davanın açılması ve süresi\n(1) Karşı dava cevap dilekçesiyle açılır."


def test_splits_single_embedded_madde():
    # Tek gömülü madde vakası. Gerçek veri: 6100 M134 '...hükümlerMADDE 135- (1)...', M164 '...sorunMADDE 165- (1)...'.
    text = ("MADDE 134- (1) Asıl dava sona erer. "
            "Uygulanacak hükümlerMADDE 135- (1) Bu Kanunun hükümleri uygulanır.")
    arts = split_articles(text)
    assert [a.no for a in arts] == ["134", "135"]
    assert arts[0].body == "(1) Asıl dava sona erer."
    assert arts[1].body == "Uygulanacak hükümler\n(1) Bu Kanunun hükümleri uygulanır."
```

- [ ] **Step 2: Testi çalıştır, RED doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_splits_embedded_madde_stuck_to_previous_body tests/test_chunker.py::test_splits_single_embedded_madde -v`
Expected: FAIL — mevcut parser 131'i tek Article yapar (132/133 gövdeye gömülü), `[a.no for a in arts] == ["131"]` çıkar → assert kırılır.

- [ ] **Step 3: `_YAPISIK_MADDE` desenini + `_split_yapisik_madde` fonksiyonunu ekle**

`chunker.py`'de, `_ISLENEMEYEN_EKI` tanımından SONRA (satır ~152, `split_articles`'tan ÖNCE) ekle. Tek, net implementasyon (kes-noktalarını önce topla, sonra ardışık dilimle):

```python
# Yapışık madde-bleed (FAZ 16 / BUG 2): kaynak metinde sonraki maddenin başlığı önceki gövdeye
# BOŞLUKSUZ yapışık ('...şartlarıMADDE 132- (1)'). Türkçe küçük 'ı'/'i'/'r'/'n' + 'M' arası \b
# OLUŞMAZ → ana _MADDE deseni yakalayamaz → madde önceki gövdeye gömülür. Post-tespit: gövdede
# '<sözcük-karakteri>MADDE <no>- (' yapışık imzası aranır. Dar imza (tam-büyük MADDE + tire + '(' fıkra)
# atıfları ('MADDE 5'e göre', '132 nci maddesi') ELER. Ölçüm: korpus-genelinde desen 4/4 gerçek, 0 FP.
_YAPISIK_MADDE = re.compile(
    r"(?<=[\wçğıöşüâîÇĞİÖŞÜ])"                          # ÖNÜNDE sözcük-karakteri (asıl bug: \b yok)
    rf"MADDE\s+({_NUM})-\s*(?=\()"                      # MADDE <no>- ( → fıkra imzası (0-FP dar)
)


def _split_yapisik_madde(no: str, body: str) -> list[Article]:
    """Gövdede önceki içeriğe yapışık gömülü madde(ler) varsa ayrı Article'lara böl (FAZ 16, 0-FP).
    Bölme noktası: gömülü 'MADDE'den geriye en yakın cümle-sonu ([.!?]) = gömülü maddenin başlık başı.
    Cümle-sonu bulunamazsa (başlık önceki gövdeden ayrılamaz) o gömülü madde bölünmez (0-FP korunur).
    Yapışık madde yoksa [Article(no, body)] döner (davranış değişmez)."""
    marks = list(_YAPISIK_MADDE.finditer(body))
    if not marks:
        return [Article(no=no, body=body)]
    # 1) Kesim noktalarını topla: (baslik_bas, MADDE-isareti-sonu, gomulu_no). baslik_bas = gömülü
    #    'MADDE'den geriye en yakın cümle-sonu + 1. Cümle-sonu yoksa o gömülü madde atlanır.
    kesimler: list[tuple[int, int, str]] = []
    tarama_bas = 0  # cümle-sonu araması bir önceki gömülü maddenin gövde-başından itibaren
    for m in marks:
        kesim = max((body.rfind(ch, tarama_bas, m.start()) for ch in ".!?"), default=-1)
        if kesim < 0:
            continue  # cümle-sonu yok → başlığı ayıramayız → bu gömülü maddeyi bölme (0-FP)
        kesimler.append((kesim + 1, m.end(), m.group(1)))
        tarama_bas = m.end()
    if not kesimler:
        return [Article(no=no, body=body)]
    # 2) Ardışık dilimle. Üst madde: body başından ilk başlık-başına kadar. Sonra her gömülü madde:
    #    (başlık = kesim..MADDE) + (gövde = MADDE-sonu.. sonraki başlık-başı VEYA body sonu).
    out: list[Article] = [Article(no=no, body=body[:kesimler[0][0]].strip())]
    for i, (baslik_bas, madde_sonu, gomulu_no) in enumerate(kesimler):
        baslik = body[baslik_bas:_yapisik_madde_baslik_sonu(body, madde_sonu)].strip()
        govde_son = kesimler[i + 1][0] if i + 1 < len(kesimler) else len(body)
        govde = body[madde_sonu:govde_son].strip()
        out.append(Article(no=gomulu_no, body=f"{baslik}\n{govde}" if baslik else govde))
    return out


def _yapisik_madde_baslik_sonu(body: str, madde_sonu: int) -> int:
    """Başlık, kesim noktasından gömülü 'MADDE' işaretinin BAŞINA kadar uzanır. madde_sonu = 'MADDE N- '
    işaretinin SONU; başlık için işaretin başını geri hesapla ('MADDE' kelimesinin ilk harfi)."""
    # madde_sonu'ndan geriye 'MADDE' kelimesinin başını bul (regex zaten eşleşti, güvenli).
    return body.rfind("MADDE", 0, madde_sonu)
```

**NOT (implementer):** `_yapisik_madde_baslik_sonu` yardımcısı, başlığın nerede bittiğini (`MADDE` kelimesinin başı) verir. `body.rfind("MADDE", 0, madde_sonu)` her zaman geçerli bir indeks döndürür çünkü `madde_sonu` zaten bir `MADDE N- ` eşleşmesinin sonu. Alternatif: `_YAPISIK_MADDE` desenine `MADDE`'nin başını da capture eden ikinci grup eklenebilir; ama yukarıdaki yardımcı yeterli ve deseni sade tutar. Davranış: başlık = `body[baslik_bas : MADDE-başı]`, gövde = `body[MADDE N- sonu : sonraki-başlık-başı]`.

- [ ] **Step 4: `split_articles`'ta `_split_yapisik_madde` çağrısını ekle**

`chunker.py:155` `split_articles` içinde, mevcut döngünün SONUNDA `out.append(Article(...))` satırını (chunker.py:177) DEĞİŞTİR. Mevcut:

```python
        out.append(Article(no=no, body=body))
    return out
```

Yerine:

```python
        out.extend(_split_yapisik_madde(no, body))
    return out
```

(Böylece her madde gövdesi, ana bleed-kırpma zincirinden GEÇTİKTEN sonra yapışık-madde tespitine girer — sıra korunur: `_SEVIYE_BASLIK_BLEED` → `_strip_kanun_sonu_ek` → `_BLEED_BASLIK` → `_split_yapisik_madde`.)

- [ ] **Step 5: Hedef testleri çalıştır, GREEN doğrula**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_splits_embedded_madde_stuck_to_previous_body tests/test_chunker.py::test_splits_single_embedded_madde -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "feat(chunker): FAZ 16 yapisik madde-bleed bolme (BUG 2, post-tespit)

- Kaynak metinde baslik onceki govdeye yapisik (...sartlariMADDE 132-)
- Ana _MADDE deseni degismez; split sonrasi _split_yapisik_madde post-tespiti
- Bolme noktasi: gomulu MADDE'den geriye en yakin cumle-sonu = baslik basi
- Cumle-sonu yoksa bolme YAPMA (0-FP korunur)
- 6100 HMK: 131->131,132,133; 134->134,135; 164->164,165"
```

---

### Task 2: Yanlış-pozitif koruma testleri (0-FP disiplini)

**Files:**
- Test: `tests/test_chunker.py` (yeni FP-koruma testleri)

**Interfaces:**
- Consumes: `split_articles`, `Article` (Task 1'den, davranış değişmedi).
- Produces: (yok — yalnız test)

**Bağlam:** Master plan disiplini: her fix 0-FP olmalı. Bu task, bölmenin YANLIŞ yerde tetiklenmediğini kanıtlar. Üç tuzak: (a) boşluklu normal `MADDE` çift-bölünmemeli (ana `_MADDE` zaten yakalıyor); (b) gövde-içi atıf (`MADDE 5'e göre`, `132 nci maddesi`) madde sayılmamalı; (c) cümle-sonu-yok senaryosunda bölme yapılmamalı.

- [ ] **Step 1: FP-koruma testlerini yaz**

`tests/test_chunker.py` sonuna ekle:

```python
def test_normal_spaced_madde_not_double_split():
    # FP-koruma: boşlukla ayrılmış normal 'MADDE 2- (1)' zaten ana _MADDE ile yakalanır;
    # yapışık-tespit onu TEKRAR bölmemeli (lookbehind sözcük-karakteri şartı boşluğu eler).
    text = "MADDE 1- (1) Birinci hüküm. MADDE 2- (1) İkinci hüküm."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2"]
    assert arts[0].body == "(1) Birinci hüküm."
    assert arts[1].body == "(1) İkinci hüküm."


def test_embedded_reference_not_split_as_madde():
    # FP-koruma: gövde-içi atıf yapışık-madde SAYILMAZ. 'maddeMADDE' gibi kapama görülse bile,
    # imza 'MADDE <no>- (' (tire + fıkra parantezi) gerektirir; atıf bu biçimde değil.
    text = "MADDE 1- (1) Bu Kanunun 5 inci maddesine göre işlem yapılır ve MADDE 5 hükmü saklıdır."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1"]  # atıf madde olarak bölünmez
    assert "5 inci maddesine göre" in arts[0].body


def test_embedded_madde_without_sentence_boundary_not_split():
    # FP-koruma / edge: yapışık 'MADDE N- (' var AMA öncesinde cümle-sonu ([.!?]) YOK →
    # başlığı önceki gövdeden ayıramayız → o gömülü madde bölünmez (yanlış başlık üretme).
    text = "MADDE 1- (1) baslangicMADDE 2- (1) devam"
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1"]  # cümle-sonu yok → bölme yok
```

- [ ] **Step 2: FP-koruma testlerini çalıştır**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_normal_spaced_madde_not_double_split tests/test_chunker.py::test_embedded_reference_not_split_as_madde tests/test_chunker.py::test_embedded_madde_without_sentence_boundary_not_split -v`
Expected: PASS (3 passed). Kırılırsa Task 1 deseni fazla geniş → daralt (lookbehind/imza).

- [ ] **Step 3: Commit**

```bash
git add tests/test_chunker.py
git commit -m "test(chunker): FAZ 16 FP-koruma (bosluklu-MADDE cift-bolunmez/atif/cumle-sonu-yok)"
```

---

### Task 3: Tam test suite + 916-kanun baseline diff (regresyon kapısı)

**Files:**
- (kod değişmez — yalnız doğrulama)
- Scratchpad: baseline korpus kopyası

**Interfaces:**
- Consumes: `scripts/build_corpus.py`, `scripts/compare_corpus.py` (mevcut araçlar).
- Produces: (yok — regresyon kanıtı)

**Bağlam:** ⚠️ Build korpusu EZER → önce baseline kopyala. Aynı anda iki ağır python = segfault → tek süreç. `data/corpus/korpus.jsonl` mevcut (FAZ 15 sonrası) = baseline. Beklenen etki: YALNIZ 6100'de 3 madde (131,134,164) + 4 yeni doğan (132,133,135,165). Başka kanun/madde değişmemeli.

- [ ] **Step 1: Tüm test suite'i çalıştır (mevcut 224 + yeni 5 yeşil)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `229 passed` (224 baz + Task1'den 2 + Task2'den 3). Herhangi bir mevcut test kırılırsa fix YANLIŞ → dur, incele.

- [ ] **Step 2: Baseline korpusu yedekle**

```bash
cp data/corpus/korpus.jsonl "C:/Users/tuna9/AppData/Local/Temp/faz16_baseline.jsonl"
```
Expected: dosya kopyalandı (sessiz). Doğrula: `ls -la "C:/Users/tuna9/AppData/Local/Temp/faz16_baseline.jsonl"`

- [ ] **Step 3: Korpusu yeniden inşa et (tek süreç)**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/build_corpus.py`
Expected: ~52s, cache'li, `data/corpus/korpus.jsonl` yazılır. Başka ağır python süreci ÇALIŞTIRMA (segfault).

- [ ] **Step 4: Baseline diff (regresyon kapısı)**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/compare_corpus.py "C:/Users/tuna9/AppData/Local/Temp/faz16_baseline.jsonl" data/corpus/korpus.jsonl --kanun 6100 --flips`
Expected:
- Etkilenen madde: yalnız 6100 (131,134,164 değişti; 132,133,135,165 YENİ doğdu).
- Status-flip: 0 (yürürlük değişmez).
- 6100 DIŞI hiçbir kanun/madde değişmemeli. Değiştiyse → desen fazla geniş, dur ve incele.

- [ ] **Step 5: Genel diff (6100 dışı sıfır-değişim kanıtı)**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/compare_corpus.py "C:/Users/tuna9/AppData/Local/Temp/faz16_baseline.jsonl" data/corpus/korpus.jsonl --gate`
Expected: Yalnız 6100 kaynaklı değişim raporlanır (yeni/değişen madde sayısı 6100 ile sınırlı). Gate PASS. Başka kanunda flip/değişim = regresyon → dur.

- [ ] **Step 6: Spot-check (hedef id'ler kaynak-doğrulama)**

Run:
```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
import json
tgt = {'131','132','133','134','135','164','165'}
found = {}
for line in open('data/corpus/korpus.jsonl', encoding='utf-8'):
    r = json.loads(line); md = r.get('metadata', {})
    if str(md.get('kanun_no'))=='6100' and str(md.get('madde_no')) in tgt:
        found[str(md.get('madde_no'))] = r['text'][:70]
for t in ['131','132','133','134','135','164','165']:
    print(t, ':', 'VAR' if t in found else 'YOK', '|', found.get(t,''))
"
```
Expected: 131-135, 164, 165 hepsi **VAR** (ayrı chunk). 132 metni `Karşı dava...` ile başlar (131'in içinde değil). 135 `Uygulanacak hükümler...`, 165 `Bekletici sorun...`.

- [ ] **Step 7: (Kötüyse) baseline geri yükle — aksi halde geç**

Eğer Step 4/5 regresyon gösterdiyse:
```bash
cp "C:/Users/tuna9/AppData/Local/Temp/faz16_baseline.jsonl" data/corpus/korpus.jsonl
```
Ve Task 1'e dön (deseni daralt). Regresyon YOKSA bu adımı atla.

- [ ] **Step 8: Commit (yeni korpus + varsa doküman güncellemesi)**

```bash
git add data/corpus/korpus.jsonl
git commit -m "build(corpus): FAZ 16 madde-bleed sonrasi yeniden insa (6100 +4 madde)"
```
(NOT: korpus git'te izleniyorsa commit'le; büyük dosya git-ignore'daysa bu adımı atla ve yalnız regresyon kanıtını raporla.)

---

### Task 4: Confusion matrix + master plan/faz-planı dokümantasyonu

**Files:**
- Create: `docs/faz-planlari/faz-16-madde-bleed.md` (faz raporu)
- Modify: `docs/yapisal-sadakat-master-plan.md` (FAZ 16 ✅ işaretle)

**Interfaces:**
- Consumes: Task 3 diff sonuçları, spot-check.
- Produces: (yok — dokümantasyon)

**Bağlam:** FAZ 15 modeli: her faz master tablo + faz-planı dokümanı. Confusion matrix = yeni her bölmenin TP (gerçek gömülü madde) mi FP (yanlış bölme) mi. Ölçüm zaten net: 4 bölme (132,133,135,165), 4/4 TP.

- [ ] **Step 1: Faz-16 raporu yaz**

`docs/faz-planlari/faz-16-madde-bleed.md` oluştur (varsa `docs/faz-planlari/` dizinini kontrol et; yoksa faz-15 dosyasının konumuna bak ve aynı yere koy):

```markdown
# FAZ 16 — Madde-bleed / Yapışık Başlık (BUG 2) ✅

> Tasarım: [../superpowers/specs/2026-07-06-faz-16-madde-bleed-yapisik-baslik-design.md](../superpowers/specs/2026-07-06-faz-16-madde-bleed-yapisik-baslik-design.md)
> Plan: [../superpowers/plans/2026-07-06-faz-16-madde-bleed.md](../superpowers/plans/2026-07-06-faz-16-madde-bleed.md)
> Branch: `bugfix/phase-16-madde-bleed`

## Sorun
Kaynak metinde madde başlığı önceki gövdeye boşluksuz yapışık (`...şartlarıMADDE 132- (1)`). Türkçe küçük
harf + `M` arası `\b` oluşmadığı için ana `_MADDE` deseni yakalayamıyor → madde önceki gövdeye gömülüyor.

## Çözüm
Yaklaşım B (post-tespit): ana `_MADDE` deseni değişmez; `split_articles`'ta madde bölündükten sonra
`_split_yapisik_madde` gövdede `<sözcük-karakteri>MADDE <no>- (` imzasını arar, cümle-sonu (`[.!?]`)
sınırından böler. Cümle-sonu yoksa bölme yapmaz (0-FP).

## Confusion Matrix (kaynak-doğrulamalı)
| Yeni bölme | Kanun:Madde | TP/FP | Not |
|---|---|---|---|
| 132 | 6100:132 | TP | `Karşı dava açılabilmesinin şartları` |
| 133 | 6100:133 | TP | `Karşı davanın açılması ve süresi` |
| 135 | 6100:135 | TP | `Uygulanacak hükümler` |
| 165 | 6100:165 | TP | `Bekletici sorun` |

**FP = 0.** 4/4 gerçek gömülü madde. Adversarial tarama (916 kanun) deseni yalnız bu 4 yerde buldu.

## Regresyon Kapısı
- Test: 229 passed (224 baz + 5 yeni).
- Baseline diff: yalnız 6100 (+4 madde), status-flip 0, 6100-dışı değişim 0.
- E-tuzağı (TMK/TBK/TTK/FSEK/Anayasa): 6100 listede değil, yapı değişmedi.

## Etki
6100 (HMK): 3 chunk → 7 chunk. 132/133/135/165 retrieval'a kazandırıldı. 0-FP.
```

(Gerçek sayıları Task 3 çıktısından doğrula ve yerleştir — yukarıdaki 229/0 beklenen değerler; farklıysa gerçek değerleri yaz.)

- [ ] **Step 2: Master planı güncelle**

`docs/yapisal-sadakat-master-plan.md`'de FAZ 16 satırını bul, ✅ olarak işaretle (FAZ 15 satırının biçimine bak, birebir aynı biçimi kullan). Eğer FAZ 16 satırı yoksa FAZ 15'ten sonra ekle.

- [ ] **Step 3: Commit**

```bash
git add docs/faz-planlari/faz-16-madde-bleed.md docs/yapisal-sadakat-master-plan.md
git commit -m "docs(faz-16): madde-bleed tamam, confusion matrix FP=0 (4 TP)"
```

---

## Self-Review (plan yazarı — inline)

**1. Spec coverage:** Spec'in her bölümü plana bağlı mı?
- Sorun/vakalar → Task 1 (hedef testler 6100:131/134/164). ✓
- Çözüm (post-tespit, desen, bölme algoritması, cümle-sonu sınırı) → Task 1 Step 3-4. ✓
- Edge-case (cümle-sonu yok, çift-bölme yok) → Task 2 FP-testleri. ✓
- 5-katmanlı regresyon kapısı → Task 3 (TDD Task1, 224 test, baseline diff, spot-check) + Task 4 (confusion matrix). ✓
- Etki (3→7 chunk) → Task 3 Step 6 + Task 4. ✓

**2. Placeholder scan:** "TBD"/"uygun hata yönetimi ekle" yok. Task 1 tek net implementasyon verir (kesim-topla → ardışık-dilimle, `\x00` hile'si veya tuple-genişletme yok). Task 3/4'te "gerçek değeri doğrula" notu var ama beklenen değer (229, 0-flip) verildi — placeholder değil, doğrulama talimatı.

**3. Type consistency:** `_split_yapisik_madde(no: str, body: str) -> list[Article]` her yerde aynı. `Article(no, body)` chunker.py:48 ile tutarlı. `_YAPISIK_MADDE.finditer` → `m.group(1)` = no (tek capture grubu; lookbehind capture etmez). `_yapisik_madde_baslik_sonu(body, madde_sonu) -> int` yardımcısı başlık-sonu (MADDE başı) indeksini verir. `split_articles` çağrısı `out.extend(_split_yapisik_madde(no, body))`. Tutarlı.
