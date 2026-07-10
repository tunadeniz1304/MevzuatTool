# -*- coding: utf-8 -*-
"""3-bacak EŞİT tam metrik profili — R@1/5/10/20/50/75/100 + MRR + nDCG.

ÖLÇÜM 5'te EŞİT (0.33/0.33/0.34) seçildi ama sadece R@1/5/10 ölçülmüştü.
Burada TAM profilini çıkar (geniş recall dahil) + WSUM_050 (2-bacak) yan yana.

Geniş k için ADAY büyütülür (her bacak 200 aday) → R@100 anlamlı.
Füzyon = 3 bacağın min-max normalize skorlarının eşit ağırlıklı toplamı.

Reranker YOK, tek embed modeli. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/metrik_bm25_profil.py [N]   (vars. 2000)
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
ADAY = 200          # geniş k (R@100) için bol aday
TOP_K = 100
KLER = [1, 5, 10, 20, 50, 75, 100]

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


def wsum(skorlar, agirliklar):
    """skorlar = [dense_skor, sparse_skor, bm25_skor]; agirliklar aynı sırada."""
    normler = [norm(s) for s in skorlar]
    tum = set()
    for nn in normler:
        tum |= set(nn)
    puan = {}
    for m in tum:
        puan[m] = sum(w * nn.get(m, 0.0) for w, nn in zip(agirliklar, normler))
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def main():
    random.seed(SEED)

    print("Korpus okunuyor + BM25 index kuruluyor...")
    yur = {}
    bm25_maddeler, bm25_dokumanlar = [], []
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

    ranks = {"WSUM_050": [], "3BACAK_ESIT": []}
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

        siralamalar = {
            "WSUM_050": wsum([dense_skor, sparse_skor], [0.5, 0.5]),
            "3BACAK_ESIT": wsum([dense_skor, sparse_skor, bm25_skor], [0.33, 0.33, 0.34]),
        }
        for y, sr in siralamalar.items():
            rank = next((i for i, a in enumerate(sr[:TOP_K], 1) if a == hedef_madde), 0)
            ranks[y].append(rank)
        olculen += 1
        if olculen % 50 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    print("\n" + "=" * 58)
    print(f"3-BACAK EŞİT TAM PROFİL — {n} sorgu (vs WSUM_050 2-bacak)")
    print("=" * 58)
    print(f"{'Metrik':<12}{'WSUM_050':>15}{'3BACAK_ESIT':>15}{'Fark':>12}")
    print("-" * 58)
    for k in KLER:
        w, t = R(ranks['WSUM_050'], k), R(ranks['3BACAK_ESIT'], k)
        print(f"R@{k:<10}{w:>15.4f}{t:>15.4f}{t-w:>+12.4f}")
    wm, tm = MRR(ranks['WSUM_050']), MRR(ranks['3BACAK_ESIT'])
    print(f"{'MRR':<12}{wm:>15.4f}{tm:>15.4f}{tm-wm:>+12.4f}")
    wn, tn = nDCG(ranks['WSUM_050']), nDCG(ranks['3BACAK_ESIT'])
    print(f"{'nDCG@10':<12}{wn:>15.4f}{tn:>15.4f}{tn-wn:>+12.4f}")
    print("=" * 58)


if __name__ == "__main__":
    main()
