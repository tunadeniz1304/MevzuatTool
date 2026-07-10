"""Metadata parse kalitesi metrikleri — ağaç (ground-truth) vs enrich çıktısı.

İki ölçüm (ADR-0011 tree-as-ground-truth). Mevcut eval_metadata.py invariant/smoke
testidir; bu script ise NİCEL metrik (P/R/F1 + alan doğruluğu) üretir.

A) MADDE-SET (precision / recall / F1)
   Ground-truth = ağaçtaki madde no kümesi (by_no zaten UNIQUE → bitemporal tekrar düşer).
   Tahmin       = enrich çıktısındaki madde no kümesi.
     TP = ikisinde de var · FP = enrich'te var ağaçta yok · FN = ağaçta var enrich kaçırdı
   (TN yok — "madde olmayan" sonsuz; klasik 2x2 confusion uygulanmaz, set-bazlı P/R/F1 doğru.)

B) METADATA ALAN DOĞRULUĞU (yalnız TP maddelerde)
   enrich alanı ağaçtaki aynı maddenin alanıyla eşleşiyor mu:
     madde_baslik, kisim_baslik, bolum_baslik, maddeId, hiyerarsi_yolu
   yurutluk: ağaçta ground-truth yok → ayrı dağılım olarak raporlanır.

Çalıştırma:  ./.venv/Scripts/python.exe scripts/eval_metrics.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "src"))

from kanun.normalize import normalize_text
from kanun.chunker import split_articles
from kanun.tree import parse_tree
from kanun.enrich import enrich

LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}

FIELDS = [
    ("madde_baslik", "baslik"),
    ("kisim_baslik", "kisim_baslik"),
    ("bolum_baslik", "bolum_baslik"),
    ("maddeId", "maddeId"),
    ("hiyerarsi_yolu", "hiyerarsi_yolu"),
]


def _load(mid: str):
    content = pathlib.Path(f"data/kanun/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/kanun/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    tree = parse_tree(tree_txt)
    maddeler, _dipnotlar = enrich(split_articles(normalize_text(content)), tree, mid)
    return tree, maddeler


def main() -> None:
    set_rows = []
    field_tot = {f[0]: {"match": 0, "mismatch": 0, "both_none": 0} for f in FIELDS}
    yur_tot = {"yürürlükte": 0, "mülga": 0}
    fp_examples = []

    for label, mid in LAWS.items():
        tree, maddeler = _load(mid)

        # --- A) MADDE-SET ---
        gt = set(tree.by_no.keys())
        pred = set(m.no for m in maddeler)
        tp, fp, fn = gt & pred, pred - gt, gt - pred
        prec = len(tp) / (len(tp) + len(fp)) if (tp or fp) else 0.0
        rec = len(tp) / (len(tp) + len(fn)) if (tp or fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        set_rows.append((label, len(gt), len(pred), len(tp), len(fp), len(fn), prec, rec, f1))
        if fp:
            fp_examples.append((label, sorted(fp)[:8]))

        # --- B) ALAN DOĞRULUĞU (TP maddelerde) ---
        by_no_pred = {m.no: m for m in maddeler}
        for no in tp:
            m, node = by_no_pred[no], tree.by_no[no]
            for mattr, tattr in FIELDS:
                mv, tv = getattr(m, mattr), getattr(node, tattr)
                if mv is None and tv is None:
                    field_tot[mattr]["both_none"] += 1
                elif mv == tv:
                    field_tot[mattr]["match"] += 1
                else:
                    field_tot[mattr]["mismatch"] += 1

        for m in maddeler:
            yur_tot[m.yurutluk] = yur_tot.get(m.yurutluk, 0) + 1

    # ---- RAPOR ----
    print("=" * 78)
    print("A) MADDE-SET — precision / recall / F1  (ground-truth = ağaç UNIQUE)")
    print("=" * 78)
    print(f"{'Kanun':6} {'GT':>4} {'Pred':>5} {'TP':>4} {'FP':>4} {'FN':>4} "
          f"{'Prec':>6} {'Rec':>6} {'F1':>6}")
    for r in set_rows:
        print(f"{r[0]:6} {r[1]:>4} {r[2]:>5} {r[3]:>4} {r[4]:>4} {r[5]:>4} "
              f"{r[6]:>6.3f} {r[7]:>6.3f} {r[8]:>6.3f}")
    print("\nFP örnekleri (enrich'te var, ağaçta yok — beklenen: Ek/Geçici/Mükerrer):")
    for label, ex in fp_examples:
        print(f"  {label}: {ex}")

    print("\n" + "=" * 78)
    print("B) METADATA ALAN DOĞRULUĞU  (yalnız TP maddelerde, ağaçla karşılaştırma)")
    print("=" * 78)
    print(f"{'Alan':16} {'Match':>6} {'Mismatch':>9} {'BothNone':>9} {'Doğruluk%':>10}")
    for mattr, _ in FIELDS:
        c = field_tot[mattr]
        denom = c["match"] + c["mismatch"]
        acc_s = f"{c['match'] / denom * 100:>9.1f}" if denom else f"{'—':>9}"
        print(f"{mattr:16} {c['match']:>6} {c['mismatch']:>9} {c['both_none']:>9} {acc_s}")

    print("\n" + "=" * 78)
    print("yürürlük dağılımı (gözlem — ağaç ground-truth yok):")
    print(f"  yürürlükte={yur_tot.get('yürürlükte', 0)}  mülga={yur_tot.get('mülga', 0)}")


if __name__ == "__main__":
    main()
