# -*- coding: utf-8 -*-
"""ÖLÇÜM 5: 3-bacak ağırlık taraması — dense/BGE-sparse/klasik-BM25 dengesi.

ÖLÇÜM 4 (eşit ağırlık) 3-bacağın WSUM'a +0.03/+0.05 kazandırdığını gösterdi.
Ama eşit (1/3 her biri) rastgele bir seçim. Bacak güçleri farklı (ablasyon):
  dense 0.637 > BM25 0.588 > BGE-sparse 0.526.
Bu yüzden dense+BM25 ağır, BGE-sparse zayıf setleri deneriz. DENSE_BM25 seti
BGE-sparse'ı tamamen atar (belki gereksiz).

Ağırlıklar (d=dense, s=BGE-sparse, b=BM25), skorlar min-max normalize:
  EŞİT        0.33 0.33 0.33   (ÖLÇÜM 4 = baseline)
  DENSE_AGIR  0.50 0.20 0.30
  BM25_AGIR   0.35 0.15 0.50
  SPARSE_KIS  0.45 0.10 0.45
  DENSE_BM25  0.50 0.00 0.50   (BGE-sparse YOK)

Ayrıca WSUM_050 (iki-bacak, mevcut sistem) referans olarak.

Reranker YOK, tek embed modeli. Aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_bm25_agirlik.py [N]   (vars. 2000)
"""
import re
import sys
import json
import math
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from kanun.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/kanun/korpus.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ADAY = 50
TOP_K = 10

# (d, s, b) — dense, BGE-sparse, klasik-BM25
AGIRLIKLAR = {
    "WSUM_050":   (0.50, 0.50, 0.00),   # iki-bacak, mevcut sistem (referans)
    "ESIT":       (0.33, 0.33, 0.34),   # ÖLÇÜM 4
    "DENSE_AGIR": (0.50, 0.20, 0.30),
    "BM25_AGIR":  (0.35, 0.15, 0.50),
    "SPARSE_KIS": (0.45, 0.10, 0.45),
    "DENSE_BM25": (0.50, 0.00, 0.50),   # BGE-sparse atıldı
}

_TOKEN = re.compile(r"[0-9a-zçğıöşü]+", re.UNICODE)


def tokenize(metin):
    return _TOKEN.findall(metin.lower())


def norm(d):
    if not d:
        return {}
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in d.items()}


def wsum3(dense_skor, sparse_skor, bm25_skor, wd, ws, wb):
    dn, sn, bn = norm(dense_skor), norm(sparse_skor), norm(bm25_skor)
    tum = set(dn) | set(sn) | set(bn)
    puan = {}
    for m in tum:
        puan[m] = wd * dn.get(m, 0.0) + ws * sn.get(m, 0.0) + wb * bn.get(m, 0.0)
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def main():
    random.seed(SEED)

    print("Korpus okunuyor + BM25 index kuruluyor...")
    yur = {}
    bm25_maddeler = []
    bm25_dokumanlar = []
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            key = (str(m["kanun_no"]), str(m["madde_no"]))
            yur[key] = m["yurutluk"]
            if m["yurutluk"] == "yürürlükte":
                bm25_maddeler.append(key)
                bm25_dokumanlar.append(tokenize(r["text"]))
    bm25 = BM25Okapi(bm25_dokumanlar)
    print(f"  BM25 index: {len(bm25_dokumanlar)} yürürlükte madde")

    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    client = QdrantClient(url=QDRANT_URL)
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    ranks = {y: [] for y in AGIRLIKLAR}
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
        dense_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in dres.points}

        sres = client.query_points(collection_name=COLLECTION,
                                   query=models.SparseVector(indices=sp_idx, values=sp_val),
                                   using="sparse", limit=ADAY, query_filter=flt, with_payload=True)
        sparse_skor = {(str(p.payload["kanun_no"]), str(p.payload["madde_no"])): p.score for p in sres.points}

        q_tok = tokenize(g["ilgi"])
        bm_skorlar = bm25.get_scores(q_tok)
        en_iyi = sorted(range(len(bm_skorlar)), key=lambda i: -bm_skorlar[i])[:ADAY]
        bm25_skor = {bm25_maddeler[i]: float(bm_skorlar[i]) for i in en_iyi if bm_skorlar[i] > 0}

        for y, (wd, ws, wb) in AGIRLIKLAR.items():
            sr = wsum3(dense_skor, sparse_skor, bm25_skor, wd, ws, wb)
            rank = next((i for i, a in enumerate(sr[:TOP_K], 1) if a == hedef_madde), 0)
            ranks[y].append(rank)
        olculen += 1
        if olculen % 50 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    print("\n" + "=" * 74)
    print(f"ÖLÇÜM 5: 3-BACAK AĞIRLIK TARAMASI — {n} sorgu (d=dense s=sparse b=bm25)")
    print("=" * 74)
    print(f"{'Yöntem':<12}{'(d,s,b)':>16}{'R@1':>9}{'R@5':>9}{'R@10':>9}{'MRR':>9}{'nDCG':>9}")
    print("-" * 74)
    for y, (wd, ws, wb) in AGIRLIKLAR.items():
        etk = f"({wd:.2f},{ws:.2f},{wb:.2f})"
        print(f"{y:<12}{etk:>16}{R(ranks[y],1):>9.4f}{R(ranks[y],5):>9.4f}"
              f"{R(ranks[y],10):>9.4f}{MRR(ranks[y]):>9.4f}{nDCG(ranks[y]):>9.4f}")
    print("=" * 74)
    # en iyi R@10 hangisi
    en = max(AGIRLIKLAR, key=lambda y: R(ranks[y], 10))
    print(f"En yuksek R@10: {en} = {R(ranks[en],10):.4f} "
          f"(WSUM_050'ye gore {R(ranks[en],10)-R(ranks['WSUM_050'],10):+.4f})")


if __name__ == "__main__":
    main()
