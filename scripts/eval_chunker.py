"""Chunker'ı 4 ağaçlı örnekte ağaç madde sayısına karşı skorla (ADR-0011 ground-truth)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.eval_tree import count_tree_articles

# Kanun-only set (ADR-0013). GVK 193 eski kanun: fıkra '(1)' yerine '1.' stili (varyasyon).
PAIRS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}

for label, mid in PAIRS.items():
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    nos = [a.no for a in split_articles(normalize_text(content))]
    got, uniq = len(nos), len(set(nos))
    exp = count_tree_articles(tree)
    print(f"{label}: chunker={got} unique={uniq} tree={exp} fark={got - exp} dup={got - uniq}")
