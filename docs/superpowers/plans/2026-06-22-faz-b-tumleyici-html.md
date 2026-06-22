# Faz B — Tümleyici HTML Modülü Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MD omurgaya dokunmadan, ham HTML'den 9 içerik tablosunu `<table>→Markdown` cebine ve dipnot `#_ftnN` anchor-bağını pipeline'a ekleyen tümleyici katman.

**Architecture:** MD omurgaya paralel HTML yolu; `enrich`'te birleşir. 4 yeni saf-fonksiyon modülü (`html_split`, `html_table`, `html_dipnot`) + 1 fetch script + 1 eval script. `enrich` iki opsiyonel parametre kazanır (None-default → mevcut davranış birebir). Mevcut 8 modül dokunulmaz.

**Tech Stack:** Python 3.11+ · stdlib `html.parser`/`re` (sıfır yeni bağımlılık) · pytest · mevzuat-mcp `bedesten_client` (kütüphane import).

## Global Constraints

- **Mevcut 8 modül DOKUNULMAZ:** normalize, chunker, tree, dipnot, degisiklik, fikra, ids, eval_tree.
- **`Madde` mevcut 16 alanı yerinde kalır;** tek yeni alan `tablolar: list[str]` (default_factory=list).
- **`enrich` geriye uyumlu:** `html_tables=None, html_dipnotlar=None` → mevcut davranış BİREBİR (46 test + recall=1.000 + metadata=%100 korunur).
- **Sıfır yeni bağımlılık:** yalnız stdlib `html.parser`, `re`, `html`. BeautifulSoup/markitdown YOK.
- **Tablo blacklist:** apendiks/değişiklik-künyesi tabloları (`Değiştiren`, `Yürürlüğe Giriş`, `Değişiklik Yapan`, `Resmî Gazete` başlıklı) ATLA — yalnız 9 içerik tablosu.
- **Dipnot anchor ASIL, regex korunur:** HTML varsa `madde.dipnotlar`=anchor; yoksa regex (fallback). `anchor==regex` karşılaştırması `eval_html.py`'nin işi, `enrich`'in değil.
- **HTML yapısı:** `charset=Windows-1254` (cp1254→utf8 decode), `\r\n` satır kırığı, iç içe `<span>/<i>/<b>`, Word-export gürültüsü (`<p class=MsoNormal>`). Regex `re.DOTALL` + tag-toleranslı.
- **Anchor format (doğrulandı):** işaret `<a href="#_ftn1" name="_ftnref1">[1]</a>`, tanım `<a href="#_ftnref1" name="_ftn1">[1]</a>` + metin (href↔name yer değiştirir).
- **HTML madde işareti tag-gömülü:** `...>Madde 1 – (Değişik...` (en-dash `–` veya `-`, `<span>` içinde).
- Test komutu: `.venv/Scripts/python.exe -m pytest` (pytest.ini: `pythonpath=src`, `testpaths=tests`).
- Import stili: `from mevzuat_tool.<modul> import <ad>`.
- Eval/script çıktısında Unicode tik YOK — ASCII `[OK]` (Windows cp1254).
- Commit: atomik, `type(scope): özet`; commit mesajında AI co-author / "Generated with" / "Co-Authored-By" **YOK**; main'e push yok. Branch `phase-b/html-structure-analysis`.

---

### Task 1: `html_split.py` — HTML madde bölme (paylaşılan temel)

**Files:**
- Create: `src/mevzuat_tool/html_split.py`
- Test: `tests/test_html_split.py`

**Interfaces:**
- Consumes: yok (saf string işleme).
- Produces: `split_html_articles(html: str) -> dict[str, str]` — HTML'i madde işaretiyle böl;
  `{madde_no: html_parça}`. Madde işareti `<span>` içinde tag-gömülü olabilir.

- [ ] **Step 1: Write the failing test**

`tests/test_html_split.py`:
```python
from mevzuat_tool.html_split import split_html_articles


def test_splits_tag_embedded_madde_markers():
    # Madde işareti <span> içinde gömülü, en-dash ayraçlı (gerçek HTML deseni)
    html = (
        "<p><span>Madde 1 – (1) Birinci madde gövdesi.</span></p>"
        "<p><span>Madde 2 - (1) İkinci madde gövdesi.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"1", "2"}
    assert "Birinci madde" in parts["1"]
    assert "İkinci madde" in parts["2"]
    assert "Madde 2" not in parts["1"]  # 1'in parçası 2'ye taşmaz


def test_handles_crlf_and_nested_tags():
    html = (
        "<p class=MsoNormal><span style='x'>Madde 5\r\n– (1) Beşinci.</span></p>"
        "<p><span>Madde 6 - (1) Altıncı.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"5", "6"}


def test_no_madde_returns_empty():
    assert split_html_articles("<p>başlık metni, madde yok</p>") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_split.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.html_split'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/html_split.py`:
```python
"""HTML'i madde işaretiyle böl (Faz B paylaşılan temel).

Ham HTML tek belge; madde işareti '<span>...Madde N – ...' biçiminde tag-gömülü.
split_html_articles bunu {madde_no: html_parça} sözlüğüne böler. html_table ve
html_dipnot bunu ortak kullanır (DRY).
"""
import re

# Madde işareti: 'Madde N -' veya 'Madde N –' (en-dash), whitespace/\r\n toleranslı.
# Tag-gömülü olduğu için sadece metin desenini arar (etrafındaki tag'leri umursamaz).
_MADDE_ISARET = re.compile(
    r"[Mm][Aa][Dd][Dd][Ee]\s+(\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?)\s*[-–]",
    re.DOTALL,
)


def split_html_articles(html: str) -> dict[str, str]:
    matches = list(_MADDE_ISARET.finditer(html))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        no = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        out[no] = html[start:end]
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_split.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/html_split.py tests/test_html_split.py
git commit -m "feat(html_split): HTML'i madde işaretiyle böl (paylaşılan temel)"
```

---

### Task 2: `html_table.py` — içerik `<table>` → Markdown

**Files:**
- Create: `src/mevzuat_tool/html_table.py`
- Test: `tests/test_html_table.py`

**Interfaces:**
- Consumes: `split_html_articles` (Task 1).
- Produces:
  - `parse_tables(html: str) -> dict[str, list[str]]` — `{madde_no: [markdown_table, ...]}`,
    apendiks tabloları hariç.
  - `_table_to_markdown(table_html: str) -> str` — tek `<table>` → pipe-table.
  - `_is_apendiks(table_html: str) -> bool` — başlık blacklist kontrolü.

- [ ] **Step 1: Write the failing test**

`tests/test_html_table.py`:
```python
from mevzuat_tool.html_table import parse_tables, _table_to_markdown, _is_apendiks


def test_table_to_markdown_pipe_format():
    html = (
        "<table><tr><td>18.000 TL kadar</td><td>%15</td></tr>"
        "<tr><td>40.000 TL fazlası</td><td>%20</td></tr></table>"
    )
    md = _table_to_markdown(html)
    assert "| 18.000 TL kadar | %15 |" in md
    assert "| 40.000 TL fazlası | %20 |" in md
    # markdown tablo ayraç satırı (header separator) içerir
    assert "---" in md


def test_unescapes_entities_and_nbsp():
    html = "<table><tr><td>a&nbsp;b</td><td>&quot;x&quot;</td></tr><tr><td>c</td><td>d</td></tr></table>"
    md = _table_to_markdown(html)
    assert "a b" in md          # &nbsp; -> boşluk
    assert '"x"' in md          # &quot; -> "


def test_is_apendiks_blacklist():
    apendiks = "<table><tr><td>Değiştiren Kanunun No</td><td>Yürürlüğe Giriş Tarihi</td></tr></table>"
    icerik = "<table><tr><td>18.000 TL</td><td>%15</td></tr></table>"
    assert _is_apendiks(apendiks) is True
    assert _is_apendiks(icerik) is False


def test_parse_tables_skips_apendiks_keeps_content():
    html = (
        "<p><span>Madde 103 - (1) Tarife:</span></p>"
        "<table><tr><td>18.000 TL</td><td>%15</td></tr><tr><td>40.000 TL</td><td>%20</td></tr></table>"
        "<p><span>Madde 999 - değişiklik cetveli:</span></p>"
        "<table><tr><td>Değiştiren Kanunun No</td><td>Yürürlüğe Giriş Tarihi</td></tr>"
        "<tr><td>5479</td><td>2006</td></tr></table>"
    )
    result = parse_tables(html)
    assert "103" in result               # içerik tablosu tutuldu
    assert len(result["103"]) == 1
    assert "%15" in result["103"][0]
    assert "999" not in result           # apendiks tablosu atlandı


def test_empty_html_returns_empty():
    assert parse_tables("") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_table.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.html_table'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/html_table.py`:
```python
"""İçerik <table> -> Markdown pipe-table (Faz B #4 tablo cebi).

Ham HTML'de vergi tarifeleri / ceza cetvelleri / kadro tabloları temiz <tr>/<td>.
Apendiks (değişiklik-künyesi) tabloları başlık-blacklist ile atlanır. stdlib html.parser
yerine basit regex (tablolar düzenli, irregular=0 — workflow kanıtı) + html.unescape.
"""
import html as _html
import re

from mevzuat_tool.html_split import split_html_articles

_TABLE = re.compile(r"<table[^>]*>.*?</table>", re.DOTALL | re.IGNORECASE)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")

_APENDIKS_BASLIK = ("Değiştiren", "Yürürlüğe Giriş", "Değişiklik Yapan", "Resmî Gazete")


def _cell_text(cell_html: str) -> str:
    text = _TAG.sub("", cell_html)
    text = _html.unescape(text)
    text = text.replace("\xa0", " ")          # &nbsp; -> boşluk
    return re.sub(r"\s+", " ", text).strip()


def _is_apendiks(table_html: str) -> bool:
    text = _html.unescape(_TAG.sub(" ", table_html))
    return any(b in text for b in _APENDIKS_BASLIK)


def _table_to_markdown(table_html: str) -> str:
    rows = []
    for tr in _TR.findall(table_html):
        cells = [_cell_text(c) for c in _TD.findall(tr)]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]   # eksik hücreleri doldur
    lines = ["| " + " | ".join(rows[0]) + " |",
             "| " + " | ".join(["---"] * ncol) + " |"]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def parse_tables(html: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for no, parca in split_html_articles(html).items():
        mds = []
        for tbl in _TABLE.findall(parca):
            if _is_apendiks(tbl):
                continue
            md = _table_to_markdown(tbl)
            if md:
                mds.append(md)
        if mds:
            out[no] = mds
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_table.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/html_table.py tests/test_html_table.py
git commit -m "feat(html_table): içerik tablolarını Markdown'a çevir, apendiks blacklist (#4)"
```

---

### Task 3: `html_dipnot.py` — dipnot anchor-bağı

**Files:**
- Create: `src/mevzuat_tool/html_dipnot.py`
- Test: `tests/test_html_dipnot.py`

**Interfaces:**
- Consumes: `split_html_articles` (Task 1); `Dipnot` (`mevzuat_tool.dipnot`, mevcut — `no:int, text:str`).
- Produces: `parse_anchors(html: str) -> dict[str, list]` — `{madde_no: [Dipnot, ...]}`.

- [ ] **Step 1: Write the failing test**

`tests/test_html_dipnot.py`:
```python
from mevzuat_tool.html_dipnot import parse_anchors
from mevzuat_tool.dipnot import Dipnot


def test_links_marker_to_definition():
    html = (
        # İşaret (gövdede): href=#_ftn1 name=_ftnref1
        "<p><span>Madde 1 - (1) Bu hüküm "
        "<a href=\"#_ftn1\" name=\"_ftnref1\"><span>[1]</span></a> ile değişti.</span></p>"
        # Tanım (kuyrukta): href=#_ftnref1 name=_ftn1 + metin
        "<div><a href=\"#_ftnref1\" name=\"_ftn1\"><span>[1]</span></a> "
        "9/4/2003-4842 sayılı Kanunla eklenmiştir.</div>"
    )
    result = parse_anchors(html)
    assert "1" in result
    assert len(result["1"]) == 1
    d = result["1"][0]
    assert isinstance(d, Dipnot)
    assert d.no == 1
    assert "4842 sayılı Kanunla" in d.text


def test_multiple_footnotes_in_one_madde():
    html = (
        "<p><span>Madde 2 - (1) Metin "
        "<a href=\"#_ftn5\" name=\"_ftnref5\">[5]</a> ve "
        "<a href=\"#_ftn6\" name=\"_ftnref6\">[6]</a>.</span></p>"
        "<div><a href=\"#_ftnref5\" name=\"_ftn5\">[5]</a> beşinci dipnot.</div>"
        "<div><a href=\"#_ftnref6\" name=\"_ftn6\">[6]</a> altıncı dipnot.</div>"
    )
    result = parse_anchors(html)
    assert [d.no for d in result["2"]] == [5, 6]


def test_marker_without_definition_skipped():
    html = (
        "<p><span>Madde 3 - (1) Eksik "
        "<a href=\"#_ftn9\" name=\"_ftnref9\">[9]</a> atıf.</span></p>"
    )  # tanım yok
    result = parse_anchors(html)
    assert result.get("3", []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_dipnot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.html_dipnot'`

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/html_dipnot.py`:
```python
"""Dipnot #_ftnN anchor-bağı (Faz B #2 — HTML-kesin [n]->dipnot).

İşaret (gövdede): <a href="#_ftnN" name="_ftnrefN">[N]</a>
Tanım (kuyrukta): <a href="#_ftnrefN" name="_ftnN">[N]</a> + serbest metin.
parse_anchors işaretin N'sini tanımın N'sine bağlar (benzersiz id, regex'ten yapısal üstün).
"""
import html as _html
import re

from mevzuat_tool.dipnot import Dipnot
from mevzuat_tool.html_split import split_html_articles

# İşaret: name="_ftnrefN" (gövde içi atıf işareti).
_ISARET = re.compile(r'name="_ftnref(\d+)"', re.IGNORECASE)
# Tanım: name="_ftnN" anchor'ı + onu izleyen serbest metin (sonraki anchor veya </div>'e kadar).
_TANIM = re.compile(
    r'name="_ftn(\d+)"[^>]*>.*?</a>(?P<text>.*?)(?=<a [^>]*name="_ftn(?:ref)?\d+"|</div>|</td>|$)',
    re.DOTALL | re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = _html.unescape(_TAG.sub(" ", text)).replace("\xa0", " ")
    # baştaki [N] tekrarını ve boşlukları temizle
    text = re.sub(r"^\s*\[\d+\]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_anchors(html: str) -> dict[str, list]:
    # Tüm tanımları topla: no -> metin (belge genelinde, tanımlar kuyrukta).
    tanimlar: dict[int, str] = {}
    for m in _TANIM.finditer(html):
        no = int(m.group(1))
        txt = _clean(m.group("text"))
        if txt and no not in tanimlar:
            tanimlar[no] = txt

    out: dict[str, list] = {}
    for madde_no, parca in split_html_articles(html).items():
        bagli = []
        gorulen = set()
        for mk in _ISARET.finditer(parca):
            no = int(mk.group(1))
            if no in tanimlar and no not in gorulen:
                bagli.append(Dipnot(no=no, text=tanimlar[no]))
                gorulen.add(no)
        if bagli:
            out[madde_no] = bagli
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_html_dipnot.py -v`
Expected: PASS (3 passed)

> NOT: `_TANIM` regex'i gerçek GVK HTML'inde ince ayar gerektirebilir (iç içe `<span>`,
> `\r\n`). Sentetik testler geçerse temel doğru; gerçek-veri doğrulaması Task 6 eval'de
> (`anchor==regex` invariant) yapılır. Eğer Task 6'da tanım metni bozuk/eksik çıkarsa,
> `_TANIM`/`_clean` orada sağlamlaştırılır (BLOCKED değil, ayar).

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/html_dipnot.py tests/test_html_dipnot.py
git commit -m "feat(html_dipnot): #_ftnN anchor-bağı ile [n]->dipnot (#2)"
```

---

### Task 4: `enrich.py` — opsiyonel HTML param + `Madde.tablolar` + orkestrasyon

**Files:**
- Modify: `src/mevzuat_tool/enrich.py`
- Modify: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `parse_tables` (Task 2), `parse_anchors` (Task 3); mevcut alt modüller.
- Produces:
  - `Madde` + yeni alan `tablolar: list[str]` (default_factory).
  - `enrich(articles, tree, kanun_no, html_tables=None, html_dipnotlar=None) -> (list[Madde], list[Dipnot])`.

- [ ] **Step 1: Write the failing test**

`tests/test_enrich.py`'a EKLE (mevcut testleri SİLME — geriye uyumluluğu onlar kanıtlar):
```python
def test_enrich_backward_compatible_without_html():
    # html_* verilmezse mevcut davranış birebir: tablolar boş, dipnotlar regex'ten.
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) içerik.")]
    maddeler, _ = enrich(arts, TREE, "193")
    m = maddeler[0]
    assert m.tablolar == []
    assert m.madde_baslik == "Beyanname çeşitleri"  # mevcut tree-join korunur


def test_enrich_injects_html_tables():
    arts = [Article(no="103", body="Tarife metni düz halde.")]
    html_tables = {"103": ["| dilim | oran |\n| --- | --- |\n| 18.000 TL | %15 |"]}
    maddeler, _ = enrich(arts, TREE, "193", html_tables=html_tables)
    m = maddeler[0]
    assert len(m.tablolar) == 1
    assert "%15" in m.tablolar[0]
    assert "| dilim | oran |" in m.body_temiz   # body_temiz'e gömüldü


def test_enrich_html_dipnot_overrides_regex():
    from mevzuat_tool.dipnot import Dipnot
    arts = [Article(no="5", body="Metin [1] atıf.\n[1] regex-tanımı.\n[2] x.\n[3] y.")]
    html_dipnotlar = {"5": [Dipnot(no=1, text="ANCHOR-tanımı")]}
    maddeler, _ = enrich(arts, TREE, "193", html_dipnotlar=html_dipnotlar)
    m = maddeler[0]
    assert [d.text for d in m.dipnotlar] == ["ANCHOR-tanımı"]   # anchor asıl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: FAIL — `TypeError: enrich() got an unexpected keyword argument 'html_tables'` ve `Madde` `tablolar` alanı yok.

- [ ] **Step 3: Write minimal implementation**

`src/mevzuat_tool/enrich.py`'da 3 değişiklik (YENİ import GEREKMEZ — `enrich` HTML dict'lerini
parametre olarak dışarıdan alır, `parse_tables`/`parse_anchors`'ı içeride çağırmaz):

(a) `Madde` dataclass'ına alan ekle (mevcut alanların sonuna, `dipnotlar`'dan sonra):
```python
    tablolar: list = field(default_factory=list)
```

(b) `enrich` imzasını değiştir:
```python
def enrich(articles, tree, kanun_no, html_tables=None, html_dipnotlar=None):
```

(c) Orkestrasyon: madde montaj döngüsünde, `Madde(...)` oluşturulduktan SONRA (her madde için),
tablo ve dipnot enjeksiyonu ekle. Mevcut `maddeler.append(Madde(...))` bloğundan sonra
`for m in maddeler:` ikinci geçişine (baglanan_dipnotlar geçişi) entegre et:
```python
    # İkinci geçiş: dipnot bağı + HTML enjeksiyonu.
    for m in maddeler:
        # Dipnot: HTML anchor varsa ASIL, yoksa regex fallback (mevcut).
        if html_dipnotlar is not None and m.no in html_dipnotlar:
            m.dipnotlar = html_dipnotlar[m.no]
        else:
            m.dipnotlar = baglanan_dipnotlar(m.body, global_dipnotlar)
        # Tablo: HTML markdown tablolar varsa tablolar alanına + body_temiz'e ekle.
        if html_tables is not None and m.no in html_tables:
            m.tablolar = html_tables[m.no]
            for md in m.tablolar:
                m.body_temiz = (m.body_temiz + "\n\n" + md).strip()
```
> Bu, mevcut `for m in maddeler: m.dipnotlar = baglanan_dipnotlar(...)` satırının YERİNE geçer.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: PASS (mevcut 11 + yeni 3 = 14 passed)

- [ ] **Step 5: Run FULL suite — regresyon yok**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS — mevcut 46 + yeni testler (html_split 3, html_table 5, html_dipnot 3, enrich +3) hepsi yeşil. Mevcut 8 modül testleri DOKUNULMADIĞI için aynen geçer.

- [ ] **Step 6: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "feat(enrich): opsiyonel HTML tablo/dipnot enjeksiyonu + Madde.tablolar (geriye uyumlu)"
```

---

### Task 5: `scripts/fetch_html.py` — ham HTML çek + cp1254 + cache

**Files:**
- Create: `scripts/fetch_html.py`

**Interfaces:**
- Consumes: mevzuat-mcp `bedesten_client.BedestenClient` (kütüphane import).
- Produces: `data/raw/html_<id>.html` cache dosyaları (4 kanun).

- [ ] **Step 1: Write the script**

`scripts/fetch_html.py`:
```python
"""Faz B: 4 kanunun ham HTML'ini get_document_content ile çek + cp1254-güvenli cache.

bedesten_client paket olarak import edilir (MCP server çalıştırılmaz; public metod).
Çıktı: data/raw/html_<id>.html (UTF-8). mevcut content_<id>.md deseni gibi.

Çalıştırma: .venv/Scripts/python.exe scripts/fetch_html.py
NOT: bedesten_client mevzuat-mcp venv'inde; bu script onun python'uyla VEYA bedesten_client
PATH'e eklenerek çalıştırılır. Detay: sys.path'e mevzuat-mcp site-packages eklenir.
"""
import asyncio
import os
import sys

# mevzuat-mcp paketinin client'ına eriş (kurulu uv tool site-packages).
_MCP_SP = os.path.expandvars(r"%APPDATA%\uv\tools\mevzuat-mcp\Lib\site-packages")
if os.path.isdir(_MCP_SP):
    sys.path.insert(0, _MCP_SP)

from bedesten_client import BedestenClient  # noqa: E402

OUT_DIR = os.path.join("data", "raw")
LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _ensure_utf8(html: str) -> str:
    """cp1254 mojibake kontrolü: 'Ã'/'Â' veya replacement char varsa cp1254 decode dene.
    bedesten_client base64->utf-8 decode ediyor; çoğu durumda HTML zaten UTF-8.
    Mojibake işareti yoksa olduğu gibi döndür."""
    if "�" in html or "Ã" in html[:2000]:
        try:
            return html.encode("latin-1").decode("cp1254")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return html
    return html


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    client = BedestenClient()
    for label, mid in LAWS.items():
        doc = await client.get_document_content(mid)
        html = _ensure_utf8(doc.content or "")
        path = os.path.join(OUT_DIR, f"html_{mid}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[OK] {label} ({mid}): {len(html)} krk -> {path}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the script — cache oluştur**

Run: `.venv/Scripts/python.exe scripts/fetch_html.py`
Expected: 4 satır `[OK] ... -> data/raw/html_<id>.html`, her biri >100K krk (GVK ~1.3M).

> Eğer `.venv` python'unda `httpx`/`bedesten_models` yoksa (ImportError), script'i mevzuat-mcp'nin
> kendi python'uyla çalıştır: `%APPDATA%\uv\tools\mevzuat-mcp\Scripts\python.exe scripts/fetch_html.py`.
> Bu BLOCKED değil — hangi python'un çalıştığını rapor et.

- [ ] **Step 3: Verify cache + UTF-8 (mojibake yok)**

Run: `.venv/Scripts/python.exe -c "import pathlib; t=pathlib.Path('data/raw/html_103111.html').read_text(encoding='utf-8'); print('len', len(t)); print('TÜRK' in t or 'Gelir' in t); print('table count', t.lower().count('<table'))"`
Expected: `len` >1M, `True` (Türkçe doğru), `table count` 8 (GVK).

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch_html.py
git commit -m "feat(fetch_html): ham HTML çek + cp1254-güvenli cache (Faz B)"
```

> NOT: `data/raw/html_*.html` `.gitignore`'da (`data/` zaten ignore) — cache versiyonlanmaz, sadece script.

---

### Task 6: `scripts/eval_html.py` — gerçek-veri invariant (anchor==regex + tablo)

**Files:**
- Create: `scripts/eval_html.py`

**Interfaces:**
- Consumes: `parse_tables`, `parse_anchors`, `baglanan_dipnotlar`, `split_articles`, `normalize_text`, `parse_tree`, `enrich`; cache `html_<id>.html` + `content_<id>.md` + `tree_<id>.txt`.

- [ ] **Step 1: Write the eval script**

`scripts/eval_html.py`:
```python
"""Faz B gerçek-veri doğrulaması — tablo dönüşümü + anchor==regex invariant (offline, cache'li).

Çalıştırma: .venv/Scripts/python.exe scripts/eval_html.py
ÖNKOŞUL: scripts/fetch_html.py çalıştırılmış (data/raw/html_<id>.html mevcut).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich
from mevzuat_tool.dipnot import split_dipnot_apendiksi, baglanan_dipnotlar
from mevzuat_tool.html_table import parse_tables
from mevzuat_tool.html_dipnot import parse_anchors

LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _load(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    html = pathlib.Path(f"data/raw/html_{mid}.html").read_text(encoding="utf-8")
    return content, tree_txt, html


# --- A) TABLO dönüşümü ---
toplam_tablo = 0
for label, mid in LAWS.items():
    _, _, html = _load(mid)
    tables = parse_tables(html)
    n = sum(len(v) for v in tables.values())
    toplam_tablo += n
    print(f"{label}: {n} içerik tablosu, {len(tables)} maddede")
assert toplam_tablo >= 7, f"Beklenen >=7 içerik tablosu, bulunan {toplam_tablo} — tablo parse eksik!"
print(f"[OK] Toplam {toplam_tablo} içerik tablosu Markdown'a çevrildi (apendiks hariç).")

# GVK Madde 103 tarife tablosu var mı
_, _, gvk_html = _load("103111")
gvk_tables = parse_tables(gvk_html)
assert "103" in gvk_tables, "GVK Madde 103 tarifesi tablo olarak çıkarılmadı!"
assert "%" in gvk_tables["103"][0], "Madde 103 tablosunda oran (%) yok!"
print("[OK] GVK Madde 103 tarifesi Markdown pipe-table olarak çıkarıldı.")

# --- B) ANCHOR == REGEX invariant (uyuşmazlık RAPORLA, çökme) ---
uyusmazlik = 0
for label, mid in LAWS.items():
    content, tree_txt, html = _load(mid)
    arts = split_articles(normalize_text(content))
    anchors = parse_anchors(html)
    # global dipnot listesi (regex yolu) için enrich'i çağır
    maddeler, global_dipnotlar = enrich(arts, parse_tree(tree_txt), mid)
    for m in maddeler:
        regex_nos = sorted(d.no for d in baglanan_dipnotlar(m.body, global_dipnotlar))
        anchor_nos = sorted(d.no for d in anchors.get(m.no, []))
        if regex_nos != anchor_nos:
            uyusmazlik += 1
            print(f"  [UYARI] {label} Madde {m.no}: regex={regex_nos} != anchor={anchor_nos}")
print(f"[OK] anchor==regex invariant: {uyusmazlik} uyuşmazlık (0 beklenir; >0 rapor edildi, çökme yok).")

print("\n[OK] Faz B eval tamamlandı (tablo dönüşümü + anchor doğrulama).")
```

- [ ] **Step 2: Run the eval**

Run: `.venv/Scripts/python.exe scripts/eval_html.py`
Expected: Her kanunun tablo sayısı + `[OK]` satırları; `anchor==regex` invariant 0 uyuşmazlık (veya raporlanmış); AssertionError yok.

> GERÇEK-VERİ AYARI (brief yetki verir): Eğer tablo sayısı 9'dan sapıyorsa (örn. blacklist
> bir içerik tablosunu yanlışlıkla atladı veya bir apendiks geçti), GERÇEK değeri rapor et;
> `_APENDIKS_BASLIK` blacklist'ini veya `_is_apendiks` eşiğini gerçek veriye göre düzelt
> (Task 2'ye dön), tekrar çalıştır. Eğer `anchor==regex` uyuşmazlık >0 ise `_TANIM`/`_clean`
> regex'ini (Task 3) sağlamlaştır. Bunlar BLOCKED değil — gerçek HTML'e göre ayar, raporla.

- [ ] **Step 3: Commit**

```bash
git add scripts/eval_html.py
git commit -m "test(eval): Faz B tablo dönüşümü + anchor==regex invariant (offline)"
```

---

## Self-Review

**1. Spec coverage:**
- §3 `fetch_html.py` (ham HTML + cp1254 + cache) → Task 5 ✓
- §5 `html_split.split_html_articles` → Task 1 ✓
- §5 `html_table.parse_tables` + apendiks blacklist (#4) → Task 2 ✓
- §5 `html_dipnot.parse_anchors` (#2 anchor) → Task 3 ✓
- §4 `Madde.tablolar` + §5 `enrich` opsiyonel param + §6 orkestrasyon (body_temiz'e ekleme, anchor asıl) → Task 4 ✓
- §9 gerçek-veri eval (anchor==regex, tablo) → Task 6 ✓
- §2 Hariç: tam migration, apendiks tabloları, vurgu/nbsp → plana dahil edilmedi ✓
- §1 Geriye uyumluluk (46 test korunur) → Task 4 Step 5 (full suite) ✓

**2. Placeholder scan:** Task 4 Step 3'te yanlışlıkla eklenen `import parse_tables` NOT ile
"atla" işaretlendi (enrich param alır, içeride çağırmaz). Başka placeholder yok — her kod adımı
tam, her test assert'li, her komut çalıştırılabilir.

**3. Type consistency:**
- `split_html_articles(html) -> dict[str,str]` — Task 1 tanımlar; Task 2, 3 kullanır ✓
- `Dipnot(no:int, text:str)` — mevcut dipnot.py'den; Task 3 üretir, Task 4 kullanır ✓
- `parse_tables -> dict[str, list[str]]` / `parse_anchors -> dict[str, list[Dipnot]]` — Task 2/3
  tanımlar; Task 4 (enrich param) ve Task 6 (eval) kullanır ✓
- `enrich(articles, tree, kanun_no, html_tables=None, html_dipnotlar=None)` — Task 4 tanımlar;
  Task 6 hem eski (3-arg) hem yeni imzayı çağırır — eski 3-arg çağrı geriye uyumlu ✓
- `Madde.tablolar: list` — Task 4 ekler; Task 6 okumaz ama parse_tables çıktısıyla tutarlı ✓

**Bağımlılık sırası:** 1 → (2,3) → 4 → 5 → 6. Task 6 (eval) hem 5'in cache'ine hem 2/3/4'e
bağlı → en sonda. Doğru.
