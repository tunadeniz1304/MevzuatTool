# Faz 3 Follow-up Metadata Zenginleştirme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GVK-analizinde bulunan 6 metadata boşluğunu (dipnot ayıklama, dipnot yapısallaştırma, değişiklik künyeleri, fıkra/bent ağacı, bent-seviyesi yürürlük, benzersiz id) kapatan, ayrık parser modülleri + ince `enrich` orkestratörü.

**Architecture:** Her özellik tek-işli saf-fonksiyon modülünde (`dipnot.py`, `degisiklik.py`, `fikra.py`, `ids.py`), bağımsız test edilir. `enrich.py` bunları sırayla çağıran ince orkestratöre dönüşür ve `(list[Madde], list[Dipnot])` tuple döndürür. `chunker.py`/`tree.py`/`normalize.py` dokunulmaz.

**Tech Stack:** Python 3.11+ · dataclasses · re (regex) · pytest. Vektör/embedding YOK (Faz 5+).

## Global Constraints

- Yalnız `KANUN` türü (ADR-0013); başka mevzuat türü yok.
- `chunker.py`, `tree.py`, `normalize.py`, `eval_tree.py` **dokunulmaz** (regresyon kanıtı).
- `Madde` dataclass'ında **mevcut alanlar yerinde kalır** (eklemeli değişiklik); eski testler + `eval_metadata.py` invariant'ları korunur.
- `body` (ham gövde) künyeler/dipnot işaretleri yerinde **değişmez**; temizlenmiş sürüm ayrı `body_temiz` alanıdır.
- Her künyede `ham_metin` **her zaman dolu** (parse-fail'de bile veri kaybı yok).
- Dipnot apendiksi eşiği: **≥3 ardışık `[n]` satırı** (kuyrukta).
- Tarih ISO formatı `YYYY-MM-DD`; parse edilemezse `None`.
- #4 tablolar **kapsam dışı** — dokunulmaz.
- Commit: atomik, `type(scope): özet`; commit mesajında AI co-author / "Generated with" / "Co-Authored-By" **YOK**; `main`'e doğrudan push yok. Branch `phase-3/followup-amendments`.
- Test komutu: `.venv/Scripts/python.exe -m pytest` (pytest.ini: `pythonpath = src`, `testpaths = tests`).
- Import stili: `from mevzuat_tool.<modul> import <ad>`.
- Eval script çıktısında Unicode tik/işaret YOK — ASCII `[OK]` kullan (Windows cp1254).

---

### Task 1: `dipnot.py` — dipnot apendiksi ayırma (#1)

**Files:**
- Create: `src/mevzuat_tool/dipnot.py`
- Test: `tests/test_dipnot.py`

**Interfaces:**
- Consumes: yok (saf string işleme).
- Produces:
  - `@dataclass Dipnot: no: int; text: str`
  - `split_dipnot_apendiksi(body: str) -> tuple[str, list[Dipnot]]` — gövde kuyruğundaki
    ardışık `[n]` bloğunu (≥3 satır) ayırır; `(temiz_body, [Dipnot...])`. Eşik altı / yok → `(body, [])`.

- [ ] **Step 1: Write the failing test**

`tests/test_dipnot.py`:
```python
from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi


def test_splits_trailing_footnote_block_of_three_or_more():
    body = (
        "Madde gövdesi burada biter.\n"
        "[1] 9/4/2003-4842 sayılı Kanunla eklenmiştir.\n"
        "[2] 22/7/1998-4369 sayılı Kanunla değiştirilmiştir.\n"
        "[3] İptal: Anayasa Mahkemesi kararı.\n"
    )
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi burada biter."
    assert [d.no for d in dipnotlar] == [1, 2, 3]
    assert dipnotlar[0].text == "9/4/2003-4842 sayılı Kanunla eklenmiştir."
    assert dipnotlar[2].text == "İptal: Anayasa Mahkemesi kararı."


def test_below_threshold_is_noop():
    body = "Gövde metni. [5] tek referans satırı.\n[6] ikinci satır."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []


def test_no_footnotes_returns_body_unchanged():
    body = "Sıradan madde gövdesi, dipnot yok."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dipnot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.dipnot'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/dipnot.py`:
```python
"""Dipnot apendiksi ayırma + [n]→madde bağı (Faz 3 follow-up #1, #2).

Mevzuat içeriğinin sonunda toplu dipnot tanımları (`[1] ... [2] ...`) son maddenin
gövdesine sızar. Bu modül kuyruktan ardışık dipnot bloğunu ayırır ve gövde içi `[n]`
işaretlerini ilgili dipnotlara bağlar.
"""
import re
from dataclasses import dataclass

_DIPNOT_SATIR = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
_ESIK = 3  # apendiks sayılması için min ardışık [n] satırı


@dataclass
class Dipnot:
    no: int
    text: str


def split_dipnot_apendiksi(body: str) -> tuple[str, list["Dipnot"]]:
    lines = body.splitlines()
    # Kuyruktan geriye, ardışık [n] satırlarının başlangıç indeksini bul.
    start = len(lines)
    i = len(lines) - 1
    while i >= 0:
        if _DIPNOT_SATIR.match(lines[i]):
            start = i
            i -= 1
        elif lines[i].strip() == "":
            i -= 1  # boş satırlar bloğu bölmez
        else:
            break
    blok = [l for l in lines[start:] if _DIPNOT_SATIR.match(l)]
    if len(blok) < _ESIK:
        return body, []
    dipnotlar = []
    for l in blok:
        m = _DIPNOT_SATIR.match(l)
        dipnotlar.append(Dipnot(no=int(m.group(1)), text=m.group(2).strip()))
    clean = "\n".join(lines[:start]).strip()
    return clean, dipnotlar
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dipnot.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/dipnot.py tests/test_dipnot.py
git commit -m "feat(dipnot): dipnot apendiksini gövde kuyruğundan ayır (#1)"
```

---

### Task 2: `dipnot.py` — `[n]→madde` bağı (#2)

**Files:**
- Modify: `src/mevzuat_tool/dipnot.py`
- Test: `tests/test_dipnot.py`

**Interfaces:**
- Consumes: `Dipnot` (Task 1).
- Produces:
  - `baglanan_dipnotlar(body: str, tum_dipnotlar: list[Dipnot]) -> list[Dipnot]` — gövde içi
    `[n]` işaretlerini bulur, `no`'ya göre `tum_dipnotlar`'dan eşleşenleri (sırasıyla, tekrarsız) döndürür.

- [ ] **Step 1: Write the failing test**

`tests/test_dipnot.py`'a ekle:
```python
from mevzuat_tool.dipnot import baglanan_dipnotlar


def test_links_inline_markers_to_footnotes():
    tum = [Dipnot(1, "birinci"), Dipnot(2, "ikinci"), Dipnot(3, "üçüncü")]
    body = "Bu hüküm [2] ve ayrıca [3] ile değişti."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [2, 3]


def test_unmatched_marker_is_skipped():
    tum = [Dipnot(1, "birinci")]
    body = "Atıf [9] global listede yok."
    assert baglanan_dipnotlar(body, tum) == []


def test_duplicate_markers_dedup_keep_order():
    tum = [Dipnot(5, "beş"), Dipnot(7, "yedi")]
    body = "[7] sonra yine [7] ve [5]."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [7, 5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dipnot.py -v`
Expected: FAIL — `ImportError: cannot import name 'baglanan_dipnotlar'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/dipnot.py`'a ekle (dosya sonuna):
```python
_ISARET = re.compile(r"\[(\d+)\]")


def baglanan_dipnotlar(body: str, tum_dipnotlar: list["Dipnot"]) -> list["Dipnot"]:
    by_no = {d.no: d for d in tum_dipnotlar}
    out: list[Dipnot] = []
    gorulen: set[int] = set()
    for m in _ISARET.finditer(body):
        no = int(m.group(1))
        if no in by_no and no not in gorulen:
            out.append(by_no[no])
            gorulen.add(no)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dipnot.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/dipnot.py tests/test_dipnot.py
git commit -m "feat(dipnot): gövde içi [n] işaretlerini dipnotlara bağla (#2)"
```

---

### Task 3: `degisiklik.py` — değişiklik künyesi parser (#3)

**Files:**
- Create: `src/mevzuat_tool/degisiklik.py`
- Test: `tests/test_degisiklik.py`

**Interfaces:**
- Consumes: yok (saf string işleme).
- Produces:
  - `@dataclass Degisiklik: tip: str; tarih: str|None; kanun_no: str|None; madde: str|None; kapsam: str|None; ham_metin: str`
  - `parse_kunyeler(body: str) -> list[Degisiklik]`
  - `temizle_kunyeler(body: str) -> str` — künyeleri gövdeden çıkarıp döndürür.

- [ ] **Step 1: Write the failing test**

`tests/test_degisiklik.py`:
```python
from mevzuat_tool.degisiklik import Degisiklik, parse_kunyeler, temizle_kunyeler


def test_parses_degisik_with_date_law_madde():
    body = "(Değişik: 9/4/2003-4842/3 md.) Bu fıkra değişti."
    k = parse_kunyeler(body)
    assert len(k) == 1
    assert k[0].tip == "degisik"
    assert k[0].tarih == "2003-04-09"
    assert k[0].kanun_no == "4842"
    assert k[0].madde == "3"
    assert k[0].ham_metin == "(Değişik: 9/4/2003-4842/3 md.)"


def test_parses_ek_and_mulga_types():
    body = "(Ek: 22/7/1998-4369/29 md.) ... (Mülga: 1/1/2006-5436/5 md.) ..."
    tipler = [k.tip for k in parse_kunyeler(body)]
    assert tipler == ["ek", "mulga"]


def test_parses_kapsam_phrase():
    body = "(Değişik birinci fıkra: 16/6/2009-5904/1 md.) içerik."
    k = parse_kunyeler(body)[0]
    assert k.tip == "degisik"
    assert k.kapsam == "birinci fıkra"


def test_anayasa_mahkemesi_iptal_is_iptal_type():
    body = "Hüküm. (İptal: Anayasa Mahkemesi'nin 12/11/2020 tarihli kararı.)"
    k = parse_kunyeler(body)
    assert any(x.tip == "iptal" for x in k)


def test_parse_failure_keeps_ham_metin():
    # Tarih/kanun parse edilemese de künye yakalanır, ham_metin dolu kalır.
    body = "(Değişik: bozuk-format-tarihsiz) içerik."
    k = parse_kunyeler(body)
    assert len(k) == 1
    assert k[0].ham_metin == "(Değişik: bozuk-format-tarihsiz)"
    assert k[0].tarih is None
    assert k[0].kanun_no is None


def test_temizle_kunyeler_removes_them():
    body = "(Değişik: 9/4/2003-4842/3 md.) Asıl içerik burada."
    assert temizle_kunyeler(body) == "Asıl içerik burada."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_degisiklik.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.degisiklik'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/degisiklik.py`:
```python
"""Değişiklik künyesi parser (Faz 3 follow-up #3).

Mevzuat gövdesindeki `(Değişik: 9/4/2003-4842/3 md.)` gibi inline künyeler ham metin
yerine yapısal `Degisiklik` kayıtlarına dönüştürülür. ham_metin her zaman korunur.
"""
import re
from dataclasses import dataclass

# Dış kalıp: (Değişik|Ek|Mülga ... : içerik) — kapsam = tip ile ":" arası serbest metin.
_KUNYE = re.compile(
    r"\((Değişik|Ek|Mülga|Ekleme|İptal)([^:)]*?):\s*([^)]*)\)"
)
_TARIH_KANUN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})-(\d+)/(\d+)\s*md\.")
_AYM = re.compile(r"Anayasa\s+Mahkemesi")

_TIP = {
    "Değişik": "degisik",
    "Ek": "ek",
    "Ekleme": "ek",
    "Mülga": "mulga",
    "İptal": "iptal",
}


@dataclass
class Degisiklik:
    tip: str
    tarih: str | None
    kanun_no: str | None
    madde: str | None
    kapsam: str | None
    ham_metin: str


def _iso_tarih(g, a, y) -> str:
    return f"{int(y):04d}-{int(a):02d}-{int(g):02d}"


def parse_kunyeler(body: str) -> list["Degisiklik"]:
    out: list[Degisiklik] = []
    for m in _KUNYE.finditer(body):
        anahtar, kapsam_raw, icerik = m.group(1), m.group(2), m.group(3)
        tip = _TIP.get(anahtar, "degisik")
        if anahtar != "İptal" and _AYM.search(icerik):
            tip = "iptal"
        kapsam = kapsam_raw.strip() or None
        tarih = kanun_no = madde = None
        tk = _TARIH_KANUN.search(icerik)
        if tk:
            tarih = _iso_tarih(tk.group(1), tk.group(2), tk.group(3))
            kanun_no = tk.group(4)
            madde = tk.group(5)
        out.append(Degisiklik(
            tip=tip, tarih=tarih, kanun_no=kanun_no, madde=madde,
            kapsam=kapsam, ham_metin=m.group(0),
        ))
    return out


def temizle_kunyeler(body: str) -> str:
    return re.sub(r"\s+", " ", _KUNYE.sub("", body)).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_degisiklik.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/degisiklik.py tests/test_degisiklik.py
git commit -m "feat(degisiklik): değişiklik künyelerini yapısal parse et (#3)"
```

---

### Task 4: `fikra.py` — fıkra/bent ağacı + bent yürürlük (#5, #6)

**Files:**
- Create: `src/mevzuat_tool/fikra.py`
- Test: `tests/test_fikra.py`

**Interfaces:**
- Consumes: `extract_status` (`mevzuat_tool.chunker`, mevcut).
- Produces:
  - `@dataclass Bent: isaret: str; text: str; yurutluk: str`
  - `@dataclass Fikra: no: str|None; text: str; bentler: list[Bent]; yurutluk: str`
  - `parse_fikralar(body: str) -> list[Fikra]`

- [ ] **Step 1: Write the failing test**

`tests/test_fikra.py`:
```python
from mevzuat_tool.fikra import Bent, Fikra, parse_fikralar


def test_splits_paren_numbered_fikralar():
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)"]
    assert fs[0].text.startswith("(1) Birinci")


def test_no_paren_number_is_single_unnumbered_fikra():
    body = "Numarasız tek paragraf gövde."
    fs = parse_fikralar(body)
    assert len(fs) == 1
    assert fs[0].no is None
    assert fs[0].text == "Numarasız tek paragraf gövde."


def test_splits_letter_bentler_within_fikra():
    body = "Aşağıdakiler kazançtır:\na) birinci bent\nb) ikinci bent"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    assert f.bentler[1].text == "b) ikinci bent"


def test_splits_numbered_bentler_within_fikra():
    body = "Şunlar:\n1. birinci\n2. ikinci\n3. üçüncü"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]


def test_bent_level_yurutluk():
    body = "Liste:\na) yürürlükteki bent\nb) (Mülga: 1/1/2020-1234 md.) kaldırılan bent"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].yurutluk == "yürürlükte"
    assert f.bentler[1].yurutluk == "mülga"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fikra.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.fikra'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/fikra.py`:
```python
"""Fıkra/bent ağacı + bent-seviyesi yürürlük (Faz 3 follow-up #5, #6).

Madde gövdesi iç içe `fikralar → bentler` yapısına bölünür. Fıkra: `(1)` (yeni stil) veya
numarasız tek paragraf. Bent (fıkra içinde): `a)` (harf) veya `1.` (numara). Her fıkra ve
bent kendi yürürlük durumunu `extract_status` ile alır.
"""
import re
from dataclasses import dataclass

from mevzuat_tool.chunker import extract_status

_FIKRA_BOL = re.compile(r"(?=\(\d+\)\s)")
_FIKRA_NO = re.compile(r"^(\(\d+\))")
_BENT_HARF = re.compile(r"(?m)(?=^\s*[a-zçğıöşü]\)\s)")
_BENT_NUM = re.compile(r"(?m)(?=^\s*\d+\.\s)")
_BENT_HARF_ISARET = re.compile(r"^\s*([a-zçğıöşü]\))")
_BENT_NUM_ISARET = re.compile(r"^\s*(\d+\.)")


@dataclass
class Bent:
    isaret: str
    text: str
    yurutluk: str


@dataclass
class Fikra:
    no: str | None
    text: str
    bentler: list[Bent]
    yurutluk: str


def _bentler(text: str) -> list[Bent]:
    # İlk eşleşen stil kazanır (karışık stil tek fıkrada varsayılmaz).
    harf = [p for p in _BENT_HARF.split(text) if _BENT_HARF_ISARET.match(p)]
    num = [p for p in _BENT_NUM.split(text) if _BENT_NUM_ISARET.match(p)]
    if harf:
        parcalar, isaret_re = harf, _BENT_HARF_ISARET
    elif num:
        parcalar, isaret_re = num, _BENT_NUM_ISARET
    else:
        return []
    out: list[Bent] = []
    for p in parcalar:
        p = p.strip()
        isaret = isaret_re.match(p).group(1)
        out.append(Bent(isaret=isaret, text=p, yurutluk=extract_status(p)))
    return out


def parse_fikralar(body: str) -> list["Fikra"]:
    body = body.strip()
    if not body:
        return []
    parcalar = [p.strip() for p in _FIKRA_BOL.split(body) if p.strip()]
    fikralar: list[Fikra] = []
    if not parcalar or not _FIKRA_NO.match(parcalar[0]):
        # Hiç (N) yok → tek numarasız fıkra.
        fikralar.append(Fikra(no=None, text=body, bentler=_bentler(body),
                              yurutluk=extract_status(body)))
        return fikralar
    for p in parcalar:
        mno = _FIKRA_NO.match(p)
        no = mno.group(1) if mno else None
        fikralar.append(Fikra(no=no, text=p, bentler=_bentler(p),
                              yurutluk=extract_status(p)))
    return fikralar
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fikra.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/fikra.py tests/test_fikra.py
git commit -m "feat(fikra): iç içe fıkra/bent ağacı + bent-seviyesi yürürlük (#5, #6)"
```

---

### Task 5: `ids.py` — benzersiz id atama (#7)

**Files:**
- Create: `src/mevzuat_tool/ids.py`
- Test: `tests/test_ids.py`

**Interfaces:**
- Consumes: yok (yalnız `no` string'lerine bakar — `Madde` dataclass Task 6'da `id` alanı kazanır).
  Bu task'ta `assign_ids` bir nesne listesi üzerinde `.no` okur, `.id` yazar (duck-typed).
- Produces:
  - `slug(no: str) -> str` — "Geçici 1"→"Gecici1", "123/A"→"123A".
  - `assign_ids(maddeler, kanun_no: str) -> None` — in-place `.id` atar; çakışmada `-{sıra}`.

- [ ] **Step 1: Write the failing test**

`tests/test_ids.py`:
```python
from dataclasses import dataclass

from mevzuat_tool.ids import slug, assign_ids


@dataclass
class _Stub:
    no: str
    id: str = ""


def test_slug_normalizes_turkish_and_suffix():
    assert slug("84") == "84"
    assert slug("Geçici 1") == "Gecici1"
    assert slug("Ek 2") == "Ek2"
    assert slug("Mükerrer 257") == "Mukerrer257"
    assert slug("123/A") == "123A"


def test_assign_basic_id():
    ms = [_Stub("84"), _Stub("85")]
    assign_ids(ms, "193")
    assert ms[0].id == "193-84"
    assert ms[1].id == "193-85"


def test_duplicate_no_gets_sequence_suffix():
    ms = [_Stub("Geçici 1"), _Stub("Geçici 1")]
    assign_ids(ms, "193")
    assert ms[0].id == "193-Gecici1-1"
    assert ms[1].id == "193-Gecici1-2"


def test_all_ids_unique():
    ms = [_Stub("84"), _Stub("Geçici 1"), _Stub("Geçici 1"), _Stub("123/A")]
    assign_ids(ms, "193")
    ids = [m.id for m in ms]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ids.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.ids'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/ids.py`:
```python
"""Benzersiz chunk id atama (Faz 3 follow-up #7).

Çifte madde no (iki ayrı `Geçici 1`) ve sonek maddeler (`123/A`) için çakışmasız id üretir.
Faz 4 JSONL `{id, ...}` bu id'ye dayanır. Deterministik (content sırasına bağlı).
"""


def slug(no: str) -> str:
    # Türkçe karakter sadeleştir, boşluk/eğik çizgi at.
    s = (no
         .replace("ç", "c").replace("Ç", "C")
         .replace("ğ", "g").replace("Ğ", "G")
         .replace("ı", "i").replace("İ", "I")
         .replace("ş", "s").replace("Ş", "S")
         .replace("ü", "u").replace("Ü", "U")
         .replace("ö", "o").replace("Ö", "O"))
    return "".join(ch for ch in s if ch.isalnum())


def assign_ids(maddeler, kanun_no: str) -> None:
    # Önce her slug için kaç kez geçtiğini say (çakışma tespiti).
    sayim: dict[str, int] = {}
    for m in maddeler:
        sayim[slug(m.no)] = sayim.get(slug(m.no), 0) + 1
    gorulen: dict[str, int] = {}
    for m in maddeler:
        s = slug(m.no)
        if sayim[s] > 1:
            gorulen[s] = gorulen.get(s, 0) + 1
            m.id = f"{kanun_no}-{s}-{gorulen[s]}"
        else:
            m.id = f"{kanun_no}-{s}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ids.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/ids.py tests/test_ids.py
git commit -m "feat(ids): çakışmasız benzersiz chunk id ataması (#7)"
```

---

### Task 6: `enrich.py` — orkestratör + genişletilmiş `Madde` + tuple dönüş

**Files:**
- Modify: `src/mevzuat_tool/enrich.py` (tamamı yeniden yazılır — mevcut mantık korunarak genişletilir)
- Modify: `tests/test_enrich.py` (mevcut çağrılar tuple dönüşe uyarlanır + yeni alan testleri)

**Interfaces:**
- Consumes:
  - `dipnot.split_dipnot_apendiksi`, `dipnot.baglanan_dipnotlar`, `dipnot.Dipnot` (Task 1, 2)
  - `degisiklik.parse_kunyeler`, `degisiklik.temizle_kunyeler`, `degisiklik.Degisiklik` (Task 3)
  - `fikra.parse_fikralar`, `fikra.Fikra` (Task 4)
  - `ids.assign_ids` (Task 5)
  - `chunker.Article`, `chunker.extract_status` (mevcut); `tree.TreeIndex` (mevcut)
- Produces:
  - Genişletilmiş `@dataclass Madde` (mevcut alanlar + `id`, `body_temiz`, `fikralar`,
    `degisiklik_gecmisi`, `dipnotlar`).
  - `enrich(articles, tree, kanun_no: str) -> tuple[list[Madde], list[Dipnot]]`
  - `_madde_tipi(no: str) -> str` (mevcut, korunur — test edilir).

- [ ] **Step 1: Write/Update the failing test**

`tests/test_enrich.py`'ı TAMAMEN şu içerikle değiştir (mevcut invariant'lar korunur, tuple dönüşe uyarlanır, yeni alan testleri eklenir):
```python
from mevzuat_tool.enrich import _madde_tipi, enrich, Madde
from mevzuat_tool.chunker import Article
from mevzuat_tool.tree import parse_tree

TREE = parse_tree(
    "- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
)

TREE_BLEED = parse_tree(
    "- DÖRDÜNCÜ KISIM - X (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
    "  - YEDİNCİ BÖLÜM - Diğer Kazanç (maddeId:20)\n"
    "    - Madde No: 85 - Gelire giren: (maddeId:30)\n"
)


def _maddeler(arts, tree):
    maddeler, _dipnotlar = enrich(arts, tree, "193")
    return maddeler


def test_madde_tipi_from_no():
    assert _madde_tipi("84") == "asil"
    assert _madde_tipi("257/A") == "asil"
    assert _madde_tipi("Geçici 84") == "gecici"
    assert _madde_tipi("Ek 2") == "ek"
    assert _madde_tipi("Mükerrer 80") == "mukerrer"


def test_enrich_returns_tuple_of_maddeler_and_dipnotlar():
    arts = [Article(no="84", body="içerik.")]
    res = enrich(arts, TREE, "193")
    assert isinstance(res, tuple) and len(res) == 2
    maddeler, dipnotlar = res
    assert isinstance(maddeler, list) and isinstance(dipnotlar, list)


def test_enrich_asil_joins_tree():
    arts = [Article(no="84", body="Gelir Vergisi beyanları: ...")]
    m = _maddeler(arts, TREE)[0]
    assert m.madde_tipi == "asil"
    assert m.madde_baslik == "Beyanname çeşitleri"
    assert m.bolum_no == "BİRİNCİ BÖLÜM"
    assert m.maddeId == "1279029"
    assert m.yurutluk == "yürürlükte"


def test_enrich_prefixed_inherits_section_and_flags():
    arts = [
        Article(no="84", body="asıl madde."),
        Article(no="Geçici 84", body="(Ek: 3/4/2013-6456/1 md.) geçici hüküm."),
    ]
    g = _maddeler(arts, TREE)[1]
    assert g.madde_tipi == "gecici"
    assert g.maddeId is None
    assert g.madde_baslik is None
    assert g.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_strips_section_header_bleed():
    arts = [
        Article(no="84", body="asıl içerik. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert "YEDİNCİ BÖLÜM" not in m.body
    assert m.body == "asıl içerik."


def test_enrich_status_uses_clean_body_not_next_madde_bleed():
    arts = [
        Article(no="84", body="bu madde yürürlükte. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="(Mülga: 1/1/2020-1234 md.) sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert m.yurutluk == "yürürlükte"


def test_enrich_plain_madde_missing_in_tree_does_not_crash():
    arts = [
        Article(no="84", body="ağaçtaki."),
        Article(no="999", body="ağaçta olmayan düz madde."),
    ]
    m = _maddeler(arts, TREE)[1]
    assert m.madde_tipi == "asil"
    assert m.maddeId is None
    assert m.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_populates_new_fields():
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) (1) Birinci fıkra.")]
    m = _maddeler(arts, TREE)[0]
    assert m.id == "193-84"
    assert len(m.degisiklik_gecmisi) == 1
    assert m.degisiklik_gecmisi[0].kanun_no == "4842"
    assert "Değişik" not in m.body_temiz
    assert len(m.fikralar) == 1


def test_enrich_separates_footnote_appendix_into_global():
    arts = [Article(
        no="84",
        body=(
            "Madde gövdesi.\n"
            "[1] birinci dipnot tanımı.\n"
            "[2] ikinci dipnot tanımı.\n"
            "[3] üçüncü dipnot tanımı."
        ),
    )]
    maddeler, dipnotlar = enrich(arts, TREE, "193")
    assert "[1]" not in maddeler[0].body_temiz
    assert [d.no for d in dipnotlar] == [1, 2, 3]


def test_enrich_links_inline_footnote_to_madde():
    arts = [Article(
        no="84",
        body=(
            "Bu hüküm [2] ile değişti.\n"
            "[1] birinci.\n"
            "[2] ikinci.\n"
            "[3] üçüncü."
        ),
    )]
    maddeler, _ = enrich(arts, TREE, "193")
    assert [d.no for d in maddeler[0].dipnotlar] == [2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: FAIL — `TypeError: enrich() missing 1 required positional argument: 'kanun_no'` ve/veya yeni alanlar yok.

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/enrich.py`'ı TAMAMEN şu içerikle değiştir:
```python
"""Article + TreeIndex → zengin Madde (Faz 3 metadata join + follow-up zenginleştirme).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma kırpılır. Ek olarak: dipnot apendiksi
ayrılır (#1), [n]→madde bağlanır (#2), değişiklik künyeleri yapısallaştırılır (#3),
fıkra/bent ağacı + bent yürürlük (#5, #6), benzersiz id (#7).
"""
from dataclasses import dataclass, field

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex
from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi, baglanan_dipnotlar
from mevzuat_tool.degisiklik import Degisiklik, parse_kunyeler, temizle_kunyeler
from mevzuat_tool.fikra import Fikra, parse_fikralar
from mevzuat_tool.ids import assign_ids

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


def _bleed_markers(tree, no):
    idx = None
    for k, ev in enumerate(tree.ordered):
        if ev["kind"] == "madde" and ev["node"].no == no:
            idx = k
            break
    if idx is None:
        return []
    markers = []
    for ev in tree.ordered[idx + 1:]:
        if ev["kind"] == "level":
            if ev["label"]:
                markers.append(ev["label"])
            if ev["title"]:
                markers.append(ev["title"])
        else:
            if ev["node"].baslik:
                markers.append(ev["node"].baslik)
            break
    return markers


def _strip_bleed(body, markers):
    cut = len(body)
    for mk in markers:
        idx = body.find(mk)
        if idx != -1:
            cut = min(cut, idx)
    return body[:cut].strip()


@dataclass
class Madde:
    no: str
    body: str
    madde_tipi: str
    madde_baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None
    yurutluk: str
    id: str = ""
    body_temiz: str = ""
    fikralar: list = field(default_factory=list)
    degisiklik_gecmisi: list = field(default_factory=list)
    dipnotlar: list = field(default_factory=list)


def _madde_tipi(no: str) -> str:
    for prefix, tipi in _TIPI:
        if no.startswith(prefix + " "):
            return tipi
    return "asil"


def enrich(articles, tree, kanun_no: str):
    maddeler: list[Madde] = []
    global_dipnotlar: list[Dipnot] = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None

    for art in articles:
        # 1. Dipnot apendiksini gövde kuyruğundan ayır (#1).
        body_no_apdx, apdx = split_dipnot_apendiksi(art.body)
        global_dipnotlar.extend(apdx)

        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
            markers = _bleed_markers(tree, art.no)
        else:
            baslik, maddeId = None, None
            markers = []

        # 2. Sızma kırpma (mevcut mantık) — apendiks ayrılmış gövde üzerinde.
        body = _strip_bleed(body_no_apdx, markers)

        # 3. Değişiklik künyeleri (#3) + temiz gövde.
        kunyeler = parse_kunyeler(body)
        body_temiz = temizle_kunyeler(body)

        # 4. Fıkra/bent ağacı + bent yürürlük (#5, #6).
        fikralar = parse_fikralar(body)

        maddeler.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(body),
            body_temiz=body_temiz, fikralar=fikralar,
            degisiklik_gecmisi=kunyeler,
        ))

    # 5. [n]→madde bağı (#2) — global dipnot listesi tamamlandıktan sonra.
    for m in maddeler:
        m.dipnotlar = baglanan_dipnotlar(m.body, global_dipnotlar)

    # 6. Benzersiz id (#7).
    assign_ids(maddeler, kanun_no)

    return maddeler, global_dipnotlar
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Run FULL suite to verify no regression**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS — tüm testler (test_chunker, test_tree, test_normalize, test_eval_tree dokunulmamış ve yeşil; dipnot/degisiklik/fikra/ids/enrich yeni testler yeşil).

- [ ] **Step 6: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "feat(enrich): parser modüllerini orkestre et + Madde zenginleştir + tuple dönüş"
```

---

### Task 7: `scripts/eval_metadata.py` — gerçek-veri invariant'ları genişlet

**Files:**
- Modify: `scripts/eval_metadata.py`

**Interfaces:**
- Consumes: `enrich(arts, tree, kanun_no) -> (maddeler, dipnotlar)` (Task 6 — yeni imza).

- [ ] **Step 1: Update `_load` for the new tuple signature and law-number param**

`scripts/eval_metadata.py`'da `_load` fonksiyonunu değiştir. LAWS sözlüğünün değeri zaten
mevzuat id (mid); kanun_no olarak aynı mid'i geç (eval amaçlı benzersizlik yeterli):
```python
def _load(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    arts = split_articles(normalize_text(content))
    maddeler, _dipnotlar = enrich(arts, parse_tree(tree_txt), mid)
    return maddeler


def _load_full(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    arts = split_articles(normalize_text(content))
    return enrich(arts, parse_tree(tree_txt), mid)  # (maddeler, dipnotlar)
```

- [ ] **Step 2: Add follow-up invariants after the existing GVK block**

`scripts/eval_metadata.py` sonuna (mevcut GVK invariant `print` satırından sonra) ekle:
```python
# --- Faz 3 follow-up invariant'ları (GVK) ---
gvk_maddeler, gvk_dipnotlar = _load_full("103111")
gvk = {m.no: m for m in gvk_maddeler}

# #1 dipnot apendiksi: Geçici 5 body_temiz makul boyutta (83K apendiks ayrıldı).
if "Geçici 5" in gvk:
    assert len(gvk["Geçici 5"].body_temiz) < 5000, \
        f"Geçici 5 body_temiz hâlâ şişkin: {len(gvk['Geçici 5'].body_temiz)} krk — dipnot apendiksi ayrılmadı!"

# #2 dipnotlar global listede toplandı.
assert len(gvk_dipnotlar) > 50, f"GVK global dipnot sayısı düşük: {len(gvk_dipnotlar)} — apendiks ayrıştırma eksik!"

# #5 fıkra/bent: Madde 70 birden çok bent içerir.
if "70" in gvk:
    toplam_bent = sum(len(f.bentler) for f in gvk["70"].fikralar)
    assert toplam_bent >= 5, f"Madde 70 bent sayısı düşük: {toplam_bent} — bent bölme eksik!"

# #3 değişiklik künyeleri: en az bir maddede yapısal künye var.
assert any(m.degisiklik_gecmisi for m in gvk_maddeler), "GVK'da hiç değişiklik künyesi parse edilmedi!"
ornek = next(k for m in gvk_maddeler for k in m.degisiklik_gecmisi if k.kanun_no)
assert ornek.kanun_no, "Değişiklik künyesinde kanun_no boş!"

# #7 benzersiz id: tüm id'ler çakışmasız.
ids = [m.id for m in gvk_maddeler]
assert len(ids) == len(set(ids)), "GVK'da çakışan chunk id'leri var — benzersiz id bozuk!"

print("[OK] Follow-up invariant'lar geçti (dipnot ayrıldı, künyeler parse, Madde 70 bentli, id benzersiz).")
```

- [ ] **Step 3: Run the eval script**

Run: `.venv/Scripts/python.exe scripts/eval_metadata.py`
Expected: Tüm satırlar yazdırılır ve `[OK] Follow-up invariant'lar geçti ...` ile biter; hiçbir AssertionError yok.

> Eğer bir invariant gerçek veride beklenenden saparsa (ör. Geçici 5 eşiği, Madde 70 bent
> sayısı), bu BLOCKED değildir — gerçek değeri rapor et, eşiği gerçek veriye göre düzelt
> (over-fit etmeden, makul sınır), tekrar çalıştır. Değişikliği commit mesajında belirt.

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_metadata.py
git commit -m "test(eval): Faz 3 follow-up invariant'ları (dipnot/künye/bent/id)"
```

---

### Task 8: `followups.md` güncelle — kapatılan maddeleri işaretle

**Files:**
- Modify: `docs/superpowers/followups.md`

**Interfaces:** yok (dokümantasyon).

- [ ] **Step 1: Mark closed items**

`docs/superpowers/followups.md`'de #1, #2, #3, #5, #6, #7 başlıklarının her birinin başına
`✅ KAPATILDI (phase-3/followup-amendments)` etiketi ekle. #4 tablolar AÇIK kalır. Dosya
sonundaki "Durum" paragrafını güncelle: kalan açık tek aday #4 (tablolar) + carry-forward.

Tam değişiklik — her başlığı şu şekilde güncelle (örnek #1):
```markdown
## 🔴 1. Dipnot apendiksi son maddeye sızıyor (en kritik) — ✅ KAPATILDI (phase-3/followup-amendments)
```
Aynısını #2, #3, #5, #6, #7 için yap. #4 başlığı değişmez. Sonra dosyanın en sonundaki
`**Durum:**` bloğunu şununla değiştir:
```markdown
**Durum:** #1, #2, #3, #5, #6, #7 phase-3/followup-amendments branch'inde KAPATILDI.
Açık kalan: #4 (tablolar — zor, ayrı) + Carry-forward maddeleri.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/followups.md
git commit -m "docs(followups): kapatılan #1/#2/#3/#5/#6/#7 maddelerini işaretle"
```

---

## Self-Review

**1. Spec coverage:**
- §1/§4 #1 dipnot apendiksi → Task 1 ✓
- §4 #2 `[n]→madde` bağı + global → Task 2 + Task 6 (global toplama) ✓
- §6.2 #3 künye parser → Task 3 ✓
- §6.3 #5 fıkra/bent + #6 bent yürürlük → Task 4 ✓
- §6.4 #7 benzersiz id → Task 5 ✓
- §3/§5 enrich orkestratör + tuple dönüş + genişletilmiş Madde → Task 6 ✓
- §8 gerçek-veri doğrulama → Task 7 ✓
- followups.md kapama (süreç) → Task 8 ✓
- §2 Hariç: #4 tablolar, Faz 4 JSONL — plana dahil edilmedi ✓

**2. Placeholder scan:** Placeholder yok — her kod adımı tam içerik taşır, her test gerçek
assert'li, her komut çalıştırılabilir.

**3. Type consistency:**
- `Dipnot(no:int, text:str)` — Task 1 tanımlar, Task 2 & 6 kullanır ✓
- `Degisiklik(...)` — Task 3 tanımlar, Task 6 & 7 kullanır ✓
- `Fikra(no, text, bentler, yurutluk)` / `Bent(isaret, text, yurutluk)` — Task 4 tanımlar,
  Task 6 & 7 kullanır ✓
- `enrich(articles, tree, kanun_no) -> (maddeler, dipnotlar)` — Task 6 tanımlar, Task 7 kullanır ✓
- `assign_ids(maddeler, kanun_no)` in-place `.id` — Task 5 (duck-typed stub), Task 6 (gerçek Madde) ✓
- `Madde.id`/`body_temiz`/`fikralar`/`degisiklik_gecmisi`/`dipnotlar` — Task 6'da default'lu
  alanlar; Task 5 stub'ı `id` alanını ayrı tanımlar (bağımsız test) ✓

**Bağımlılık sırası:** 1→2 (dipnot), 3, 4, 5 bağımsız; 6 hepsine bağlı; 7 → 6'ya bağlı; 8 bağımsız (süreç).
Sıra: 1, 2, 3, 4, 5, 6, 7, 8 — doğru.
