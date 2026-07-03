# -*- coding: utf-8 -*-
"""Recall eğrisi — R@1/5/10/50/100 (hybrid sistemi, altınset gold).

Amaç: doğru madde nerede "yakalanıyor"? R@100 yüksek + R@10 düşükse ->
doğru madde GETİRİLİYOR ama SIRALAMA kötü (reranker işe yarar).
R@100 da düşükse -> doğru madde HİÇ getirilmiyor (embedding/gold sorunu).

Çalıştır: .venv/Scripts/python.exe scripts/metrik_egri.py [N]   (vars. 2000)
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
TOP_K = 100          # en geniş k
ADAY_K = 200         # her bacak bu kadar aday (RRF top-100 için bol)
KLER = [1, 5, 10, 20, 50, 75, 100]


def hybrid_ara(client, sorgu, flt):
    dense, sparse = embed_sorgu(sorgu)
    sp_idx = [int(k) for k in sparse.keys()]
    sp_val = list(sparse.values())
    res = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(query=dense, using="dense", limit=ADAY_K, filter=flt),
            models.Prefetch(query=models.SparseVector(indices=sp_idx, values=sp_val),
                            using="sparse", limit=ADAY_K, filter=flt),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=TOP_K,
        with_payload=True,
    )
    return [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in res.points]


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

    ranks = []
    mulga = eslesmeyen = 0
    hedef = min(N, len(gold))
    for g in gold:
        if len(ranks) >= hedef:
            break
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        durum = yur.get((kn, mn))
        if durum is None:
            eslesmeyen += 1
            continue
        if durum == "mülga":
            mulga += 1
            continue
        donen = hybrid_ara(client, g["ilgi"], flt)
        rank = 0
        for sira, (dkn, dmn) in enumerate(donen, 1):
            if dkn == kn and dmn == mn:
                rank = sira
                break
        ranks.append(rank)
        if len(ranks) % 100 == 0:
            print(f"  {len(ranks)}/{hedef}...", end="\r")

    n = len(ranks)
    print("\n" + "=" * 60)
    print("RECALL EĞRİSİ — hybrid (dense+sparse+RRF)")
    print("=" * 60)
    print(f"Ölçülen: {n} | Mülga atlanan: {mulga} | Korpusta yok: {eslesmeyen}")
    print("-" * 60)
    onceki = 0
    for k in KLER:
        r = sum(1 for x in ranks if 1 <= x <= k) / n
        artis = r - onceki
        bar = "#" * int(r * 40)
        print(f"  Recall@{k:<4}: {r:.4f}  (+{artis:.3f})  {bar}")
        onceki = r
    # bulunamayanlar (top-100'de bile yok)
    hic = sum(1 for x in ranks if x == 0) / n
    print("-" * 60)
    print(f"  Top-100'de HİÇ yok : {hic:.4f}  (embedding/gold ulaşamıyor)")
    print("=" * 60)
    # yorum ipucu
    r10 = sum(1 for x in ranks if 1 <= x <= 10) / n
    r100 = sum(1 for x in ranks if 1 <= x <= 100) / n
    print(f"\nYORUM: R@10={r10:.3f} vs R@100={r100:.3f}")
    if r100 - r10 > 0.10:
        print(f"  -> Fark BÜYÜK ({r100-r10:.3f}): doğru madde GETİRİLİYOR ama SIRALAMA kötü.")
        print("     RERANKER işe yarar (adayı 10'a iyi sıralar).")
    else:
        print(f"  -> Fark küçük ({r100-r10:.3f}): sıralama zaten iyi; kaçanlar HİÇ getirilemiyor.")


if __name__ == "__main__":
    main()
