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
