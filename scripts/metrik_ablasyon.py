# -*- coding: utf-8 -*-
"""ÖLÇÜM 3: Ablasyon — dense-only vs sparse-only vs hybrid.

En baştan sorulan soru: her bacak ne kadar katkı yapıyor?
  - DENSE_ONLY  : sadece anlam (embedding)
  - SPARSE_ONLY : sadece kelime (BGE-M3 sparse, BM25-benzeri)
  - HYBRID_RRF  : ikisi RRF ile birleşik (baseline)

Sparse tek başına ne kadar iyi? Hybrid, dense-only'dan ne kadar ileri?
Bu üçlü = vanilla RAG'ın ablasyonu.

Reranker YOK. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/metrik_ablasyon.py [N]   (vars. 2000)
"""
import sys
import json
import math
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from qdrant_client import QdrantClient, models
from mevzuat_tool.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/corpus/korpus.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ADAY = 50
RRF_K = 60
TOP_K = 10


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

    ranks = {"DENSE_ONLY": [], "SPARSE_ONLY": [], "HYBRID_RRF": []}
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

        sres = client.query_points(collection_name=COLLECTION,
                                   query=models.SparseVector(indices=sp_idx, values=sp_val),
                                   using="sparse", limit=ADAY, query_filter=flt, with_payload=True)
        sparse_list = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in sres.points]

        siralamalar = {
            "DENSE_ONLY": dense_list,
            "SPARSE_ONLY": sparse_list,
            "HYBRID_RRF": rrf(dense_list, sparse_list),
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

    print("\n" + "=" * 66)
    print(f"ÖLÇÜM 3: ABLASYON — {n} sorgu (dense vs sparse vs hybrid)")
    print("=" * 66)
    print(f"{'Yöntem':<14}{'R@1':>10}{'R@5':>10}{'R@10':>10}{'MRR':>10}{'nDCG':>10}")
    print("-" * 66)
    for y in ["DENSE_ONLY", "SPARSE_ONLY", "HYBRID_RRF"]:
        print(f"{y:<14}{R(ranks[y],1):>10.4f}{R(ranks[y],5):>10.4f}{R(ranks[y],10):>10.4f}{MRR(ranks[y]):>10.4f}{nDCG(ranks[y]):>10.4f}")
    print("=" * 66)
    d10, s10, h10 = R(ranks['DENSE_ONLY'],10), R(ranks['SPARSE_ONLY'],10), R(ranks['HYBRID_RRF'],10)
    print(f"Hybrid kazanci: dense-only'dan +{h10-d10:.3f}, sparse-only'dan +{h10-s10:.3f}")
    print(f"Sparse tek basina R@10={s10:.3f} (dense'in {'ustunde' if s10>d10 else 'altinda'})")


if __name__ == "__main__":
    main()
