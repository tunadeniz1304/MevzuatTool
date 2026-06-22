# Ağaç-tabanlı Metadata Zenginleştirme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `madde_tree`'yi content chunk'larıyla birleştirip her madde için zengin metadata (başlık, kısım/bölüm, tip flag, hiyerarşi, maddeId, yürürlük) üreten ve gövde sızmasını temizleyen bir katman ekle.

**Architecture:** İki yeni saf modül — `tree.py` (ağaç metni → `TreeIndex`) ve `enrich.py` (`Article` + `TreeIndex` → zengin `Madde`). `chunker.py`/`normalize.py`/`eval_tree.py` değişmez. TDD: önce test, sonra minimal kod.

**Tech Stack:** Python 3 (stdlib: `re`, `dataclasses`), pytest. Yeni bağımlılık yok.

## Global Constraints

- Yalnız `KANUN` türü (ADR-0013); doğrulama TCK/VUK/KVKK/GVK cache'inde.
- `chunker.py`, `normalize.py`, `eval_tree.py` **değiştirilmez** (mevcut 6 test yeşil kalmalı).
- Atomik commit; format `type(scope): özet`; commit mesajında **AI co-author / "Generated with" YOK**.
- `main`'e doğrudan push yok; branch `phase-3/tree-metadata`.
- Testler: `./.venv/Scripts/python.exe -m pytest -v`.

---

### Task 1: tree.py — TreeNode/TreeIndex + parse_tree (KISIM/BÖLÜM/Madde)

**Files:**
- Create: `src/mevzuat_tool/tree.py`
- Test: `tests/test_tree.py`

**Interfaces:**
- Produces: `TreeNode(no, baslik, kisim_no, kisim_baslik, bolum_no, bolum_baslik, hiyerarsi_yolu, maddeId)`; `TreeIndex(by_no: dict[str, TreeNode], ordered: list[dict])`; `parse_tree(text: str) -> TreeIndex`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tree.py
from mevzuat_tool.tree import parse_tree

SAMPLE = """Article Tree for mevzuatId: 999
Total nodes: 3

- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
"""


def test_parse_tree_joins_madde_to_section():
    idx = parse_tree(SAMPLE)
    n = idx.by_no["84"]
    assert n.baslik == "Beyanname çeşitleri"   # trailing ':' kırpılır
    assert n.kisim_no == "DÖRDÜNCÜ KISIM"
    assert n.kisim_baslik == "Verginin Tarhı"
    assert n.bolum_no == "BİRİNCİ BÖLÜM"
    assert n.bolum_baslik == "Beyan Esası"
    assert n.maddeId == "1279029"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tree.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.tree'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mevzuat_tool/tree.py
"""madde_tree metnini yapısal index'e ayrıştır (Faz 3 metadata join girdisi).

get_mevzuat_madde_tree çıktısı girintili bir ağaçtır:
    - DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
      - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
        - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
parse_tree bunu by_no lookup + ordered olay listesine çevirir.
"""
import re
from dataclasses import dataclass

_LEVEL_KW = ("KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "AYRIM")
_MADDE_RE = re.compile(
    r"Madde No:\s*(?P<no>\S+?)\s*-\s*(?P<title>.*?)\s*\(maddeId:(?P<mid>\d+)\)\s*$"
)
_LEVEL_RE = re.compile(
    r"(?P<label>.+?)\s*-\s*(?P<title>.*?)\s*\(maddeId:(?P<mid>\d+)\)\s*$"
)


def _clean_title(t: str) -> str | None:
    t = (t or "").strip().rstrip(":").strip()
    return t or None


@dataclass
class TreeNode:
    no: str
    baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None


@dataclass
class TreeIndex:
    by_no: dict
    ordered: list


def parse_tree(text: str) -> TreeIndex:
    by_no: dict = {}
    ordered: list = []
    stack: list = []  # (indent, label, title) ancestor yığını

    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)
        if not stripped.startswith("- "):
            continue
        content = stripped[2:]

        m = _MADDE_RE.match(content)
        if m:
            no = m.group("no")
            kisim = next(((l, t) for (i, l, t) in stack if "KISIM" in l), (None, None))
            bolum = next(((l, t) for (i, l, t) in stack if "BÖLÜM" in l), (None, None))
            path_parts = [f"{l} - {t}" for (i, l, t) in stack]
            path_parts.append(f"Madde {no}")
            node = TreeNode(
                no=no, baslik=_clean_title(m.group("title")),
                kisim_no=kisim[0], kisim_baslik=kisim[1],
                bolum_no=bolum[0], bolum_baslik=bolum[1],
                hiyerarsi_yolu=" › ".join(path_parts), maddeId=m.group("mid"),
            )
            by_no[no] = node
            ordered.append({"kind": "madde", "node": node})
            continue

        if any(kw in content for kw in _LEVEL_KW):
            ml = _LEVEL_RE.match(content)
            if ml:
                label = ml.group("label").strip()
                title = _clean_title(ml.group("title"))
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                stack.append((indent, label, title))
                ordered.append({"kind": "level", "label": label, "title": title})
    return TreeIndex(by_no=by_no, ordered=ordered)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tree.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/tree.py tests/test_tree.py
git commit -m "feat(tree): parse madde_tree into TreeIndex with section join"
```

---

### Task 2: tree.py — KİTAP/AYIRIM seviyeleri + hiyerarsi_yolu

**Files:**
- Modify: `src/mevzuat_tool/tree.py` (kod Task 1'de zaten KİTAP/AYIRIM'ı destekliyor; bu task doğrular)
- Test: `tests/test_tree.py`

**Interfaces:**
- Consumes: `parse_tree`, `TreeNode.hiyerarsi_yolu` (Task 1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tree.py — ekle
KITAP_SAMPLE = """- BİRİNCİ KİTAP - Cezalar (maddeId:1)
  - İKİNCİ KISIM - Suçlar (maddeId:2)
    - ÜÇÜNCÜ BÖLÜM - Hükümler (maddeId:3)
      - Madde No: 5 - Tanımlar: (maddeId:50)
"""


def test_parse_tree_keeps_full_path_including_kitap():
    idx = parse_tree(KITAP_SAMPLE)
    n = idx.by_no["5"]
    assert n.kisim_no == "İKİNCİ KISIM"
    assert n.bolum_no == "ÜÇÜNCÜ BÖLÜM"
    assert n.hiyerarsi_yolu == (
        "BİRİNCİ KİTAP - Cezalar › İKİNCİ KISIM - Suçlar › "
        "ÜÇÜNCÜ BÖLÜM - Hükümler › Madde 5"
    )
```

- [ ] **Step 2: Run test to verify it passes (Task 1 kodu zaten destekliyor)**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tree.py::test_parse_tree_keeps_full_path_including_kitap -v`
Expected: PASS (KİTAP, ancestor stack'te tutuluyor; hiyerarsi_yolu tam yolu içeriyor)

> Not: PASS ise Task 1'in `parse_tree`'i KİTAP'ı doğru ele alıyor demektir. FAIL olursa `_LEVEL_KW`/stack mantığını düzelt.

- [ ] **Step 3: Commit**

```bash
git add tests/test_tree.py
git commit -m "test(tree): cover KİTAP level and full hierarchy path"
```

---

### Task 3: tree.py — baş/boş/bozuk satır dayanıklılığı

**Files:**
- Modify: `src/mevzuat_tool/tree.py` (gerekirse)
- Test: `tests/test_tree.py`

**Interfaces:**
- Consumes: `parse_tree` (Task 1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tree.py — ekle
MESSY_SAMPLE = """Article Tree for mevzuatId: 999
Total nodes: 1

- BİRİNCİ BÖLÜM - Genel (maddeId:10)
    - Madde No: 1 - İlk: (maddeId:11)
- bozuk satır maddeId olmadan
"""


def test_parse_tree_skips_non_data_lines():
    idx = parse_tree(MESSY_SAMPLE)
    assert set(idx.by_no.keys()) == {"1"}        # sadece geçerli madde
    assert idx.by_no["1"].bolum_no == "BİRİNCİ BÖLÜM"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_tree.py::test_parse_tree_skips_non_data_lines -v`
Expected: PASS (baş satırlar `- ` ile başlamadığı için atlanır; "bozuk satır" hiçbir regex'e uymaz → atlanır)

> FAIL olursa: parse_tree'de `if not stripped.startswith("- "): continue` ve regex-eşleşmeyen satırların atlandığını doğrula.

- [ ] **Step 3: Commit**

```bash
git add tests/test_tree.py
git commit -m "test(tree): ignore header/blank/malformed lines"
```

---

### Task 4: enrich.py — Madde dataclass + _madde_tipi

**Files:**
- Create: `src/mevzuat_tool/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `Article`, `extract_status` (mevcut `chunker.py`); `TreeIndex` (Task 1).
- Produces: `Madde(no, body, madde_tipi, madde_baslik, kisim_no, kisim_baslik, bolum_no, bolum_baslik, hiyerarsi_yolu, maddeId, yurutluk)`; `_madde_tipi(no: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich.py
from mevzuat_tool.enrich import _madde_tipi


def test_madde_tipi_from_no():
    assert _madde_tipi("84") == "asil"
    assert _madde_tipi("257/A") == "asil"
    assert _madde_tipi("Geçici 84") == "gecici"
    assert _madde_tipi("Ek 2") == "ek"
    assert _madde_tipi("Mükerrer 80") == "mukerrer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mevzuat_tool.enrich'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mevzuat_tool/enrich.py
"""Article + TreeIndex → zengin Madde (Faz 3 metadata join).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma (sonraki bölüm/madde başlığı) kırpılır.
"""
import re
from dataclasses import dataclass

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


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


def _madde_tipi(no: str) -> str:
    for prefix, tipi in _TIPI:
        if no.startswith(prefix + " "):
            return tipi
    return "asil"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "feat(enrich): add Madde dataclass and madde_tipi detection"
```

---

### Task 5: enrich.py — enrich() join (asil ağaçtan + prefixli miras)

**Files:**
- Modify: `src/mevzuat_tool/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `Article`, `_madde_tipi`, `Madde`, `extract_status`, `TreeIndex` (Task 1/4).
- Produces: `enrich(articles: list[Article], tree: TreeIndex) -> list[Madde]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich.py — ekle
from mevzuat_tool.chunker import Article
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich

TREE = parse_tree(
    "- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
)


def test_enrich_asil_joins_tree():
    arts = [Article(no="84", body="Gelir Vergisi beyanları: ...")]
    m = enrich(arts, TREE)[0]
    assert m.madde_tipi == "asil"
    assert m.madde_baslik == "Beyanname çeşitleri"
    assert m.bolum_no == "BİRİNCİ BÖLÜM"
    assert m.maddeId == "1279029"
    assert m.yurutluk == "yürürlükte"


def test_enrich_prefixed_inherits_section_and_flags():
    arts = [
        Article(no="84", body="asıl madde."),
        Article(no="Geçici 84", body="(Ek: 3/4/2013) geçici hüküm."),
    ]
    g = enrich(arts, TREE)[1]
    assert g.madde_tipi == "gecici"
    assert g.maddeId is None
    assert g.madde_baslik is None
    assert g.bolum_no == "BİRİNCİ BÖLÜM"   # bir önceki asil maddeden miras
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -k enrich -v`
Expected: FAIL — `ImportError: cannot import name 'enrich'`

- [ ] **Step 3: Write minimal implementation (enrich.py'ye `enrich` ekle)**

```python
def enrich(articles, tree):
    out = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None
    for art in articles:
        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
        else:
            baslik, maddeId = None, None
        out.append(Madde(
            no=art.no, body=art.body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(art.body),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -k enrich -v`
Expected: PASS (her iki test)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "feat(enrich): join asil maddeler to tree, inherit section for prefixed"
```

---

### Task 6: enrich.py — _strip_bleed (gövde sızma kırpma)

**Files:**
- Modify: `src/mevzuat_tool/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `enrich`, `Madde` (Task 5).
- Produces: `_strip_bleed(body: str, next_title: str | None) -> str` (enrich içinde gövdeye uygulanır).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich.py — ekle
def test_enrich_strips_section_header_bleed():
    arts = [
        Article(no="84", body="asıl içerik. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="sonraki."),
    ]
    m = enrich(arts, TREE)[0]
    assert "YEDİNCİ BÖLÜM" not in m.body
    assert m.body == "asıl içerik."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py::test_enrich_strips_section_header_bleed -v`
Expected: FAIL — gövde hâlâ "YEDİNCİ BÖLÜM..." içeriyor (assert hatası)

- [ ] **Step 3: Write implementation (enrich.py'ye `_strip_bleed` ekle + enrich'te kullan)**

`enrich.py` başına (importların altına) ekle:
```python
_HEADER_RE = re.compile(r"[A-ZÇĞİÖŞÜ]{2,}\s+(?:KİTAP|KISIM|BÖLÜM|AYIRIM|AYRIM)\b")


def _strip_bleed(body: str, next_title: str | None) -> str:
    cut = len(body)
    m = _HEADER_RE.search(body)
    if m:
        cut = min(cut, m.start())
    if next_title:
        idx = body.find(next_title)
        if idx != -1:
            cut = min(cut, idx)
    return body[:cut].strip()
```

`enrich` döngüsünü, gövdeyi kırpacak şekilde güncelle (Task 5'teki gövdesini değiştir):
```python
def enrich(articles, tree):
    out = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None
    for i, art in enumerate(articles):
        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
        else:
            baslik, maddeId = None, None
        next_title = None
        if i + 1 < len(articles):
            nxt = tree.by_no.get(articles[i + 1].no)
            next_title = nxt.baslik if nxt else None
        body = _strip_bleed(art.body, next_title)
        out.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(body),
        ))
    return out
```

- [ ] **Step 4: Run all enrich tests to verify pass (regresyon dahil)**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: PASS (Task 5 testleri + yeni sızma testi)

- [ ] **Step 5: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "feat(enrich): strip trailing section/title bleed from madde body"
```

---

### Task 7: enrich.py — ağaçta olmayan düz madde (hata yönetimi)

**Files:**
- Modify: `tests/test_enrich.py` (kod Task 5/6'da zaten graceful; bu task doğrular)

**Interfaces:**
- Consumes: `enrich` (Task 6).

- [ ] **Step 1: Write the failing/confirming test**

```python
# tests/test_enrich.py — ekle
def test_enrich_plain_madde_missing_in_tree_does_not_crash():
    arts = [
        Article(no="84", body="ağaçtaki."),
        Article(no="999", body="ağaçta olmayan düz madde."),  # TREE'de yok
    ]
    res = enrich(arts, TREE)
    m = res[1]
    assert m.madde_tipi == "asil"
    assert m.maddeId is None          # ağaçta yok → None
    assert m.bolum_no == "BİRİNCİ BÖLÜM"  # önceki asil maddeden miras
```

- [ ] **Step 2: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_enrich.py::test_enrich_plain_madde_missing_in_tree_does_not_crash -v`
Expected: PASS (node None → else dalı: baslik/maddeId None, cur_* miras; çökme yok)

> FAIL olursa enrich'te `node is not None` kontrolünün else dalını doğrula.

- [ ] **Step 3: Commit**

```bash
git add tests/test_enrich.py
git commit -m "test(enrich): plain madde absent from tree degrades gracefully"
```

---

### Task 8: scripts/eval_metadata.py — gerçek-veri doğrulaması (4 kanun)

**Files:**
- Create: `scripts/eval_metadata.py`

**Interfaces:**
- Consumes: `normalize_text`, `split_articles`, `parse_tree`, `enrich` (önceki task'lar).

- [ ] **Step 1: Write the script**

```python
# scripts/eval_metadata.py
"""Faz 3 metadata enrichment doğrulaması — kanun-only cache'inde invariant kontrolü.

Çalıştırma: ./.venv/Scripts/python.exe scripts/eval_metadata.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich

LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _load(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    arts = split_articles(normalize_text(content))
    return enrich(arts, parse_tree(tree_txt))


for label, mid in LAWS.items():
    maddeler = _load(mid)
    asil = sum(1 for m in maddeler if m.madde_tipi == "asil")
    pref = len(maddeler) - asil
    eksik = sum(1 for m in maddeler if m.madde_tipi == "asil" and m.maddeId is None)
    print(f"{label}: {len(maddeler)} madde (asil={asil}, prefixli={pref}, ağaçta-yok-asil={eksik})")

# GVK-spesifik invariant'lar
gvk = {m.no: m for m in _load("103111")}
assert "YEDİNCİ BÖLÜM" not in gvk["79"].body, "Madde 79 sızması temizlenmedi!"
assert gvk["84"].madde_baslik == "Beyanname çeşitleri", f"Madde 84 başlık yanlış: {gvk['84'].madde_baslik!r}"
assert "Geçici 84" in gvk and gvk["Geçici 84"].madde_tipi == "gecici", "Geçici 84 flag yanlış!"
print("\n✓ GVK invariant'lar geçti (79 sızmasız, 84 başlık='Beyanname çeşitleri', Geçici 84 flag='gecici').")
```

- [ ] **Step 2: Run the eval script**

Run: `./.venv/Scripts/python.exe scripts/eval_metadata.py`
Expected: 4 kanun için satır + "✓ GVK invariant'lar geçti" (assert hatası YOK)

> Assert patlarsa: ilgili madde için `enrich` çıktısını incele (sızma kırpma string'i eşleşmedi mi, başlık colon kırpılmadı mı). Düzelt, tekrar çalıştır.

- [ ] **Step 3: Run full test suite (regresyon: mevcut 6 + yeni testler)**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: tüm testler PASS (chunker'ın 6 testi dahil, dokunulmadığı için)

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_metadata.py
git commit -m "feat(scripts): add eval_metadata real-data invariant check"
```

---

## Self-Review

**1. Spec coverage:**
- tree.py ayrıştırıcı → Task 1-3 ✓
- Madde veri modeli + madde_tipi → Task 4 ✓
- Join (asil) + prefixli miras → Task 5 ✓
- Sızma kırpma → Task 6 ✓
- Hata yönetimi (ağaçta-yok düz madde) → Task 7 ✓
- 4 kanun gerçek-veri doğrulaması → Task 8 ✓
- chunker dokunulmazlığı → Task 8 Step 3 (regresyon) ✓
- `hiyerarsi_yolu` (KİTAP) → Task 2 ✓

**2. Placeholder scan:** Tüm adımlarda tam kod var; "TBD/TODO" yok. ✓

**3. Type consistency:** `parse_tree`, `TreeNode`, `TreeIndex`, `Madde`, `_madde_tipi`, `enrich`, `_strip_bleed` imzaları task'lar arası tutarlı; `enrich(articles, tree)` ve `Madde(...)` alan adları sabit. ✓
