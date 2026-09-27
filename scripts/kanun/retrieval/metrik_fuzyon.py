# -*- coding: utf-8 -*-
"""ÖLÇÜM 2: Füzyon ağırlığı — dense/sparse dengesi R@10'u değiştiriyor mu?

Qdrant native RRF ağırlık almaz (sabit). Bu yüzden dense + sparse aday listelerini
AYRI çekip, füzyonu KENDİ elimizde farklı ağırlıklarla deneriz:

  - RRF_ESIT      : klasik RRF, dense+sparse eşit (baseline ~0.667)
  - RRF_DENSE_AGIR: RRF ama dense sıralarına daha çok ağırlık
  - WSUM_070      : ağırlıklı skor toplamı, 0.7*dense + 0.3*sparse (normalize skor)
  - WSUM_050      : 0.5*dense + 0.5*sparse
  - WSUM_085      : 0.85*dense + 0.15*sparse
  - DENSE_ONLY    : sadece dense (füzyon yok — sparse katkısını görmek için)

Reranker YOK. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_fuzyon.py [N]   (vars. 2000)
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
ADAY = 50          # her bacaktan aday
RRF_K = 60
TOP_K = 10


def rrf_puanla(dense_list, sparse_list, w_dense=1.0, w_sparse=1.0):
    """RRF: her adaya (1/(k+sıra)) puanı, ağırlıklı."""
    puan = {}
    for sira, mid in enumerate(dense_list, 1):
        puan[mid] = puan.get(mid, 0) + w_dense * (1.0 / (RRF_K + sira))
    for sira, mid in enumerate(sparse_list, 1):
        puan[mid] = puan.get(mid, 0) + w_sparse * (1.0 / (RRF_K + sira))
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def wsum_puanla(dense_skor, sparse_skor, a):
    """Ağırlıklı skor toplamı: a*dense + (1-a)*sparse (skorlar min-max normalize)."""
    def norm(d):
        if not d:
            return {}
        vals = list(d.values())
        lo, hi = min(vals), max(vals)
        rng = (hi - lo) or 1.0
        return {k: (v - lo) / rng for k, v in d.items()}
    dn, sn = norm(dense_skor), norm(sparse_skor)
    puan = {}
    for m in set(dn) | set(sn):
        puan[m] = a * dn.get(m, 0) + (1 - a) * sn.get(m, 0)
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

    yontemler = ["RRF_ESIT", "RRF_DENSE_AGIR", "WSUM_050", "WSUM_070", "WSUM_085", "DENSE_ONLY"]
    ranks = {y: [] for y in yontemler}
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

        # dense ADAY listesi (ayrı sorgu)
        dres = client.query_points(collection_name=COLLECTION, query=dense, using="dense",
                                   limit=ADAY, query_filter=flt, with_payload=True)
        dense_list = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in dres.points]
        dense_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in dres.points}

        # sparse ADAY listesi (ayrı sorgu)
        sres = client.query_points(collection_name=COLLECTION,
                                   query=models.SparseVector(indices=sp_idx, values=sp_val),
                                   using="sparse", limit=ADAY, query_filter=flt, with_payload=True)
        sparse_list = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in sres.points]
        sparse_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in sres.points}

        siralamalar = {
            "RRF_ESIT": rrf_puanla(dense_list, sparse_list, 1.0, 1.0),
            "RRF_DENSE_AGIR": rrf_puanla(dense_list, sparse_list, 2.0, 1.0),
            "WSUM_050": wsum_puanla(dense_skor, sparse_skor, 0.5),
            "WSUM_070": wsum_puanla(dense_skor, sparse_skor, 0.7),
            "WSUM_085": wsum_puanla(dense_skor, sparse_skor, 0.85),
            "DENSE_ONLY": dense_list,
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

    print("\n" + "=" * 74)
    print(f"ÖLÇÜM 2: FÜZYON AĞIRLIĞI — {n} sorgu")
    print("=" * 74)
    print(f"{'Yöntem':<16}{'R@1':>10}{'R@5':>10}{'R@10':>10}{'MRR':>10}")
    print("-" * 74)
    for y in yontemler:
        print(f"{y:<16}{R(ranks[y],1):>10.4f}{R(ranks[y],5):>10.4f}{R(ranks[y],10):>10.4f}{MRR(ranks[y]):>10.4f}")
    print("=" * 74)
    print("RRF_ESIT = baseline. En yuksek R@10 hangi yontemde?")
    print("DENSE_ONLY < hybrid ise -> sparse katki yapiyor (ablasyon on-bulgu).")


if __name__ == "__main__":
    main()
