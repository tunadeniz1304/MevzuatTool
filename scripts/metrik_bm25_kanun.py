# -*- coding: utf-8 -*-
"""3-bacak EŞİT: MADDE-seviyesi vs KANUN-seviyesi tam eğri (R@1..100 + MRR + nDCG).

Soru: R@50/75/100 düşük (~0.79-0.82) görünüyor. Ama ÖLÇÜM 1: sistem doğru KANUNU
%89, doğru MADDEYİ %67 buluyor → metrik "doğru kanun ama yanlış madde"yi 0 sayar.
Burada iki hedef tanımıyla aynı sıralamayı puanlarız:
  - MADDE : (kanun_no, madde_no) tam eşleşme (katı, mevcut)
  - KANUN : yalnız kanun_no eşleşme (madde-ince-ayrımını affeder)

KANUN eğrisi = sistemin ham erişim gücü (doğru mevzuata ulaşıyor mu?).
MADDE eğrisi = üretim katılığı (tam maddeyi ayırt ediyor mu?).
İkisinin farkı = "madde-ayrımı darboğazı"nın k'ya göre büyüklüğü.

Füzyon = 3-bacak EŞİT (0.33/0.33/0.34), search_qdrant.py ile aynı.
Çalıştır: .venv/Scripts/python.exe scripts/metrik_bm25_kanun.py [N]   (vars. 2000)
"""
import re
import sys
import json
import math
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from mevzuat_tool.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/corpus/korpus.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ADAY = 200
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

    # her sorgu için KANUN-rank (0 = bulunamadı). MADDE zaten profil ölçümünde var.
    kanun_ranks = []
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

        siralama = wsum([dense_skor, sparse_skor, bm25_skor], [0.33, 0.33, 0.34])[:TOP_K]

        # KANUN rank: aynı kanun_no'lu İLK madde (madde önemsiz)
        k_rank = next((i for i, a in enumerate(siralama, 1) if a[0] == kn), 0)
        kanun_ranks.append(k_rank)
        olculen += 1
        if olculen % 50 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    # madde profili (metrik_bm25_profil.py N=2000, referans — yan yana okumak için)
    MADDE = {1: 0.4900, 5: 0.6680, 10: 0.7155, 20: 0.7550,
             50: 0.7925, 75: 0.8120, 100: 0.8220, "MRR": 0.5708, "nDCG": 0.6025}

    print("\n" + "=" * 58)
    print(f"3-BACAK EŞİT: KANUN-seviyesi eğrisi — {n} sorgu")
    print("(MADDE = metrik_bm25_profil.py referansı)")
    print("=" * 58)
    print(f"{'Metrik':<12}{'MADDE':>14}{'KANUN':>14}{'Fark':>12}")
    print("-" * 58)
    for k in KLER:
        kk = R(kanun_ranks, k)
        print(f"R@{k:<10}{MADDE[k]:>14.4f}{kk:>14.4f}{kk-MADDE[k]:>+12.4f}")
    km = MRR(kanun_ranks)
    print(f"{'MRR':<12}{MADDE['MRR']:>14.4f}{km:>14.4f}{km-MADDE['MRR']:>+12.4f}")
    kn2 = nDCG(kanun_ranks)
    print(f"{'nDCG@10':<12}{MADDE['nDCG']:>14.4f}{kn2:>14.4f}{kn2-MADDE['nDCG']:>+12.4f}")
    print("=" * 58)
    print("KANUN >> MADDE ise: dogru mevzuata ulasiliyor, madde-ayrimi darbogaz.")
    print(f"Darbogaz (R@10): madde {MADDE[10]:.3f} vs kanun {R(kanun_ranks,10):.3f}")


if __name__ == "__main__":
    main()
