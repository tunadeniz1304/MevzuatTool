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
print(f"[OK] anchor==regex invariant: {uyusmazlik} uyusmazlik (0 beklenir; >0 rapor edildi, cokme yok).")

print("\n[OK] Faz B eval tamamlandi (tablo donusumu + anchor dogrulama).")
