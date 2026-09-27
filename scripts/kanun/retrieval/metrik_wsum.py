# -*- coding: utf-8 -*-
"""WSUM_050 tam metrik profili — R@1/5/10/20/50/75/100 + MRR + nDCG.

Ölçüm 2'de WSUM_050 (ağırlıklı skor füzyonu, eşit) R@1/MRR'de RRF'i geçmişti.
Burada TAM profilini çıkar + baseline RRF ile yan yana.

WSUM: skorları min-max normalize et, 0.5*dense + 0.5*sparse, sırala.
(RRF sadece sırayı kullanır; WSUM gerçek skoru → sıralama bilgisi korunur.)

Reranker YOK, tek model. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_wsum.py [N]   (vars. 2000)
"""
import sys
import json
import math
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from qdrant_client import QdrantClient, models
from kanun.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/kanun/korpus.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ADAY = 200          # geniş k için bol aday (R@100 için)
RRF_K = 60
TOP_K = 100
KLER = [1, 5, 10, 20, 50, 75, 100]


def norm(d):
    if not d:
        return {}
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in d.items()}


def wsum(dense_skor, sparse_skor, a=0.5):
    dn, sn = norm(dense_skor), norm(sparse_skor)
    puan = {}
    for m in set(dn) | set(sn):
        puan[m] = a * dn.get(m, 0) + (1 - a) * sn.get(m, 0)
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def rrf(dense_list, sparse_list):
    puan = {}
    for s, m in enumerate(dense_list, 1):
        puan[m] = puan.get(m, 0) + 1.0 / (RRF_K + s)
    for s, m in enumerate(sparse_list, 1):
        puan[m] = puan.get(m, 0) + 1.0 / (RRF_K + s)
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def main():
    random.seed(SEED)
    yur = {}
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            yur[(str(m["kanun_no"]), str(m["madde_no"]))] = m["yurutluk"]

    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    client = QdrantClient(url=QDRANT_URL)
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    ranks = {"RRF_ESIT": [], "WSUM_050": []}
    hedef = min(N, len(gold))
    olculen = 0

    for g in gold:
        if olculen >= hedef:
            break
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        if yur.get((kn, mn)) in (None, "mülga"):
            continue
        hedef_madde = (kn, mn)

        dense, sparse = embed_sorgu(g["ilgi"])
        sp_idx = [int(k) for k in sparse.keys()]
        sp_val = list(sparse.values())

        dres = client.query_points(collection_name=COLLECTION, query=dense, using="dense",
                                   limit=ADAY, query_filter=flt, with_payload=True)
        dense_list = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in dres.points]
        dense_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in dres.points}

        sres = client.query_points(collection_name=COLLECTION,
                                   query=models.SparseVector(indices=sp_idx, values=sp_val),
                                   using="sparse", limit=ADAY, query_filter=flt, with_payload=True)
        sparse_list = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in sres.points]
        sparse_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in sres.points}

        siralamalar = {
            "RRF_ESIT": rrf(dense_list, sparse_list),
            "WSUM_050": wsum(dense_skor, sparse_skor, 0.5),
        }
        for y, sr in siralamalar.items():
            rank = next((i for i, a in enumerate(sr[:TOP_K], 1) if a == hedef_madde), 0)
            ranks[y].append(rank)
        olculen += 1
        if olculen % 100 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    print("\n" + "=" * 56)
    print(f"WSUM_050 TAM PROFİL — {n} sorgu (vs RRF baseline)")
    print("=" * 56)
    print(f"{'Metrik':<12}{'RRF_ESIT':>14}{'WSUM_050':>14}{'Fark':>12}")
    print("-" * 56)
    for k in KLER:
        h, w = R(ranks['RRF_ESIT'], k), R(ranks['WSUM_050'], k)
        print(f"R@{k:<10}{h:>14.4f}{w:>14.4f}{w-h:>+12.4f}")
    hm, wm = MRR(ranks['RRF_ESIT']), MRR(ranks['WSUM_050'])
    print(f"{'MRR':<12}{hm:>14.4f}{wm:>14.4f}{wm-hm:>+12.4f}")
    hn, wn = nDCG(ranks['RRF_ESIT']), nDCG(ranks['WSUM_050'])
    print(f"{'nDCG@10':<12}{hn:>14.4f}{wn:>14.4f}{wn-hn:>+12.4f}")
    print("=" * 56)


if __name__ == "__main__":
    main()
