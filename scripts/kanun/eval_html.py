"""Faz B gercek-veri dogrulamasi --- tablo donusumu + metin-ortusme invariant (offline, cache'li).

Calistirma: .venv/Scripts/python.exe scripts/eval_html.py
ONKOSUL: scripts/fetch_html.py calistirilmis (data/kanun/raw/html_<id>.html mevcut).
"""
import pathlib
import sys
import re as _re

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "src"))

from kanun.normalize import normalize_text
from kanun.chunker import split_articles
from kanun.tree import parse_tree
from kanun.enrich import enrich
from kanun.dipnot import split_dipnot_apendiksi, baglanan_dipnotlar
from kanun.html_table import parse_tables
from kanun.html_dipnot import parse_anchors

LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _load(mid: str):
    content = pathlib.Path(f"data/kanun/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/kanun/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    html = pathlib.Path(f"data/kanun/raw/html_{mid}.html").read_text(encoding="utf-8")
    return content, tree_txt, html


# --- A) TABLO donusumu ---
toplam_tablo = 0
for label, mid in LAWS.items():
    _, _, html = _load(mid)
    tables = parse_tables(html)
    n = sum(len(v) for v in tables.values())
    toplam_tablo += n
    print(f"{label}: {n} icerik tablosu, {len(tables)} maddede")
assert toplam_tablo >= 7, f"Beklenen >=7 icerik tablosu, bulunan {toplam_tablo} --- tablo parse eksik!"
print(f"[OK] Toplam {toplam_tablo} icerik tablosu Markdown'a cevrildi (apendiks haric).")

# GVK Madde 103 tarife tablosu var mi
_, _, gvk_html = _load("103111")
gvk_tables = parse_tables(gvk_html)
assert "103" in gvk_tables, "GVK Madde 103 tarifesi tablo olarak cikarilmadi!"
assert "%" in gvk_tables["103"][0], "Madde 103 tablosunda oran (%) yok!"
print("[OK] GVK Madde 103 tarifesi Markdown pipe-table olarak cikarildi.")

# --- B) METIN-ORTUSME invariant (anchor metin == regex metin; numerik karsilastirma YOK) ---

def _norm(t):
    t = (t or "").lower()
    t = _re.sub(r"\s+", " ", t).strip()
    return t


def _key(t):
    return _norm(t)[:80]


def _overlaps(a, r):
    if not a or not r:
        return False
    if a == r or a.startswith(r) or r.startswith(a):
        return True
    n = 40
    return len(a) >= n and len(r) >= n and a[:n] == r[:n]


total_anchor = 0
total_matched = 0
total_anchor_only = 0
total_regex_only = 0

# Accumulate mismatch examples for reporting (capped at ~12 lines)
mismatch_examples = []

for label, mid in LAWS.items():
    content, tree_txt, html = _load(mid)
    arts = split_articles(normalize_text(content))
    anchors = parse_anchors(html)
    maddeler, global_dipnotlar = enrich(arts, parse_tree(tree_txt), mid)

    law_anchor = 0
    law_regex = 0
    law_matched = 0
    law_anchor_only = 0
    law_regex_only = 0

    for m in maddeler:
        anchor_dips = anchors.get(m.no, [])
        regex_dips = baglanan_dipnotlar(m.body, global_dipnotlar)

        anchor_keys = [_key(d.text) for d in anchor_dips if _norm(d.text)]
        regex_keys = [_key(d.text) for d in regex_dips if _norm(d.text)]
        law_regex += len(regex_keys)

        # For each anchor key, check if it overlaps any regex key
        madde_matched = 0
        madde_anchor_only = []
        for ak in anchor_keys:
            if any(_overlaps(ak, rk) for rk in regex_keys):
                madde_matched += 1
            else:
                madde_anchor_only.append(ak)

        # For each regex key, check if it overlaps any anchor key
        madde_regex_only = []
        for rk in regex_keys:
            if not any(_overlaps(ak, rk) for ak in anchor_keys):
                madde_regex_only.append(rk)

        law_anchor += len(anchor_keys)
        law_matched += madde_matched
        law_anchor_only += len(madde_anchor_only)
        law_regex_only += len(madde_regex_only)

        # Collect mismatch examples (cap total at ~12)
        if (madde_anchor_only or madde_regex_only) and len(mismatch_examples) < 12:
            for ak in madde_anchor_only[:2]:
                if len(mismatch_examples) < 12:
                    mismatch_examples.append(
                        f"  [ORNEK] {label} Madde {m.no} anchor-only: \"{ak[:60]}\""
                    )
            for rk in madde_regex_only[:2]:
                if len(mismatch_examples) < 12:
                    mismatch_examples.append(
                        f"  [ORNEK] {label} Madde {m.no} regex-only:  \"{rk[:60]}\""
                    )

    total_anchor += law_anchor
    total_matched += law_matched
    total_anchor_only += law_anchor_only
    total_regex_only += law_regex_only

    print(
        f"{label}: anchor={law_anchor}, regex={law_regex}, "
        f"matched={law_matched}, anchor_only={law_anchor_only}, regex_only={law_regex_only}"
    )

# Print mismatch examples
if mismatch_examples:
    print("Ornek eslesmeyen dipnotlar (ilk 12 satir):")
    for ex in mismatch_examples:
        print(ex)

# Compute text-match rate
if total_anchor > 0:
    rate = total_matched / total_anchor * 100.0
else:
    rate = 0.0

print(
    f"[OK] anchor metin-ortusme: matched/total = {total_matched}/{total_anchor} "
    f"(oran {rate:.1f}%); anchor_only={total_anchor_only}, regex_only={total_regex_only} "
    f"(gozlem, cokme yok)."
)

# Light hard guard: catches total failure (e.g. _clean garbling every text)
assert total_anchor == 0 or total_matched > 0, \
    "Hicbir anchor dipnot metni regex ile ortusmuyor --- gercek bag kopuklugu!"

print("\n[OK] Faz B eval tamamlandi (tablo donusumu + anchor dogrulama).")
