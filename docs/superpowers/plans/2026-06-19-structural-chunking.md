# Yapısal Chunking (Faz 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** mevzuat `content` metnini madde-seviyesi yapısal chunk'lara ayıran, çeşitli 5 örnek belgede çalışan bir chunker.

**Architecture:** İki katmanlı content-parse: önce metni normalize et (satır kırığı birleştir + tire/en-dash tek tip), sonra esnek regex ile madde → fıkra ayır; değişiklik/mülga şerhinden yürürlük durumunu çıkar. Kalite, `get_mevzuat_madde_tree`'nin madde sayısına karşı ölçülür (ücretsiz ground-truth; ADR-0011).

**Tech Stack:** Python 3.11, pytest, stdlib `re` + `dataclasses`. Girdi: `data/raw/content_<id>.md` + `tree_<id>.txt` (ADR-0012, gitignored yerel).

## Global Constraints
- Vanilla RAG, retrieval-only (ADR-0010); generation YOK.
- Atomik birim = madde; uzun madde fıkra bazında (CLAUDE.md ilke 3); naive token chunking YOK.
- Yürürlük durumu (yürürlükte/mülga) birinci sınıf metadata (ADR-0005).
- Commit: `type(scope): özet`, AI co-author satırı YOK; branch `phase-2/structural-chunking` (commit_discipline.md).
- `src/` layout: testler `pytest.ini` ile `pythonpath = src` üzerinden import eder.

---

### Task 1: Metin normalizasyonu

**Files:**
- Create: `src/mevzuat_tool/normalize.py`
- Create: `tests/test_normalize.py`
- Create: `pytest.ini`
- Modify: `requirements.txt` (pytest ekle)

**Interfaces:**
- Produces: `normalize_text(raw: str) -> str`

- [ ] **Step 1: pytest kur + yapılandır**
Run: `.venv/Scripts/python.exe -m pip install pytest`
`requirements.txt`'e satır ekle: `pytest==8.*`
`pytest.ini` oluştur:
```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 2: Failing test yaz**
```python
# tests/test_normalize.py
from mevzuat_tool.normalize import normalize_text

def test_joins_wrapped_lines_and_unifies_dashes():
    raw = "Madde\n2 – (Değişik)\n\nMadde 3"
    assert normalize_text(raw) == "Madde 2 - (Değişik)\n\nMadde 3"
```

- [ ] **Step 3: Test'i çalıştır, fail gör**
Run: `.venv/Scripts/python.exe -m pytest tests/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: mevzuat_tool.normalize`

- [ ] **Step 4: Minimal implementasyon**
```python
# src/mevzuat_tool/normalize.py
import re

_DASHES = ("–", "—", "‒")  # – — ‒ → -

def normalize_text(raw: str) -> str:
    text = raw
    for d in _DASHES:
        text = text.replace(d, "-")
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # tek satır kırığı → boşluk; \n\n korunur
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
```

- [ ] **Step 5: Test'i çalıştır, pass gör**
Run: `.venv/Scripts/python.exe -m pytest tests/test_normalize.py -v`  Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add requirements.txt pytest.ini src/mevzuat_tool/normalize.py tests/test_normalize.py
git commit -m "feat(chunking): add text normalization (line-join + dash unify)"
```

---

### Task 2: Madde ayrıştırma

**Files:**
- Create: `src/mevzuat_tool/chunker.py`
- Create: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `normalize_text` (Task 1)
- Produces: `@dataclass Article(no: str, body: str)` · `split_articles(text: str) -> list[Article]`

- [ ] **Step 1: Failing test yaz**
```python
# tests/test_chunker.py
from mevzuat_tool.chunker import split_articles

def test_splits_on_madde_markers_case_insensitive():
    text = "Madde 1- (1) Birinci. MADDE 2- (1) İkinci. Madde 3 - (1) Üçüncü."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2", "3"]
    assert arts[0].body.startswith("(1) Birinci")
```

- [ ] **Step 2: Çalıştır, fail gör**
Run: `.venv/Scripts/python.exe -m pytest tests/test_chunker.py -v`  Expected: FAIL

- [ ] **Step 3: Minimal implementasyon**
```python
# src/mevzuat_tool/chunker.py
import re
from dataclasses import dataclass

_MADDE = re.compile(r"(?i)\bmadde\s+(\d+)\s*-\s*")

@dataclass
class Article:
    no: str
    body: str

def split_articles(text: str) -> list[Article]:
    matches = list(_MADDE.finditer(text))
    out: list[Article] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append(Article(no=m.group(1), body=text[start:end].strip()))
    return out
```

- [ ] **Step 4: Çalıştır, pass gör** — Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "feat(chunking): split text into articles by flexible madde regex"
```

---

### Task 3: Fıkra ayrıştırma

**Files:** Modify `src/mevzuat_tool/chunker.py`, `tests/test_chunker.py`
**Interfaces:** Produces `split_fikralar(body: str) -> list[str]`

- [ ] **Step 1: Failing test**
```python
def test_splits_fikralar_on_paren_numbers():
    from mevzuat_tool.chunker import split_fikralar
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    assert split_fikralar(body) == ["(1) Birinci fıkra.", "(2) İkinci fıkra."]
```
- [ ] **Step 2: Çalıştır, fail gör**
- [ ] **Step 3: Implementasyon (chunker.py'ye ekle)**
```python
def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]
```
- [ ] **Step 4: Çalıştır, pass gör**
- [ ] **Step 5: Commit** — `feat(chunking): split article body into fıkralar`

---

### Task 4: Yürürlük durumu (şerh) çıkarımı

**Files:** Modify `src/mevzuat_tool/chunker.py`, `tests/test_chunker.py`
**Interfaces:** Produces `extract_status(body: str) -> str` → `"mülga"` | `"yürürlükte"`

- [ ] **Step 1: Failing test**
```python
def test_detects_mulga_else_yururlukte():
    from mevzuat_tool.chunker import extract_status
    assert extract_status("(Mülga: 1/1/2020-1234 md.) ...") == "mülga"
    assert extract_status("(Değişik: ...) hüküm") == "yürürlükte"
    assert extract_status("normal hüküm") == "yürürlükte"
```
- [ ] **Step 2: Çalıştır, fail gör**
- [ ] **Step 3: Implementasyon**
```python
def extract_status(body: str) -> str:
    return "mülga" if re.search(r"(?i)\(\s*mülga", body) else "yürürlükte"
```
- [ ] **Step 4: Çalıştır, pass gör**
- [ ] **Step 5: Commit** — `feat(chunking): extract yürürlük status from şerh`

---

### Task 5: Ağaca karşı eval (ground-truth skor)

**Files:**
- Create: `src/mevzuat_tool/eval_tree.py`
- Create: `tests/test_eval_tree.py`
- Create: `scripts/eval_chunker.py`

**Interfaces:** Produces `count_tree_articles(tree_text: str) -> int`

- [ ] **Step 1: Failing test**
```python
# tests/test_eval_tree.py
from mevzuat_tool.eval_tree import count_tree_articles

def test_counts_madde_nodes():
    tree = "- BİRİNCİ KİTAP - x\n  - Madde No: 1 - a\n  - Madde No: 2 - b\n"
    assert count_tree_articles(tree) == 2
```
- [ ] **Step 2: Çalıştır, fail gör**
- [ ] **Step 3: Implementasyon**
```python
# src/mevzuat_tool/eval_tree.py
import re

def count_tree_articles(tree_text: str) -> int:
    return len(re.findall(r"(?m)^\s*-\s*Madde No:\s*\d+", tree_text))
```
- [ ] **Step 4: Çalıştır, pass gör**
- [ ] **Step 5: Gerçek-veri eval script'i**
```python
# scripts/eval_chunker.py — chunker'ı 4 ağaçlı örnekte ağaç sayısına karşı skorla
from pathlib import Path
from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.eval_tree import count_tree_articles

PAIRS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "KKY": "352791"}
for label, mid in PAIRS.items():
    content = Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree = Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    got = len(split_articles(normalize_text(content)))
    exp = count_tree_articles(tree)
    print(f"{label}: chunker={got} tree={exp} fark={got - exp}")
```
Run: `.venv/Scripts/python.exe scripts/eval_chunker.py`
Beklenen: KVKK/KKY (düz, temiz) ≈ eşleşir; TCK/VUK'ta fark çıkarsa regex'i (Ek/Geçici/Mükerrer Madde) genişlet → yeni task.
- [ ] **Step 6: Commit** — `feat(chunking): add tree-count ground-truth eval`

---

## Self-Review
- **Kapsam:** normalize (T1), madde (T2), fıkra (T3), yürürlük (T4), eval (T5) — pipeline'ın her parçası bir task'ta. Hiyerarşi-path (KİTAP/KISIM/BÖLÜM) MVP'de YOK → eval farkı büyükse ayrı task olarak eklenir (YAGNI).
- **Placeholder yok:** her code step'te gerçek kod var.
- **Tip tutarlılığı:** `Article(no,body)`, `split_articles→list[Article]`, `split_fikralar(str)→list[str]`, `extract_status(str)→str`, `count_tree_articles(str)→int` — tasklar arası tutarlı.
