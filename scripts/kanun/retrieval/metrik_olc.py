# -*- coding: utf-8 -*-
"""Retrieval metrik ölçümü — altınset temiz gold set ile hybrid sistemi değerlendir.

Gold: altinset_temiz.jsonl (ilgi=sorgu, kanun_no+madde_no=doğru madde).
Sistem: hybrid arama (dense+sparse+RRF, yürürlük filtreli).

Metrikler:
  - Recall@1/5/10 : doğru madde ilk k'da var mı? (RAG ana metriği)
  - MRR           : doğru madde ortalama kaçıncı sırada? (1/sıra)
  - nDCG@10       : üste ne kadar iyi sıralandı? (akademik standart)

Eşleşme: sistemin getirdiği (payload kanun_no+madde_no) == gold (kanun_no+madde_no).

ÖNEMLİ: Doğru maddesi MÜLGA olan sorgular ölçüm-dışı bırakılır — çünkü arama
yürürlük filtreli, mülga maddeyi hiç getiremez (haksız 0 olurdu). Bu ayrı raporlanır.

Çalıştır: .venv/Scripts/python.exe scripts/metrik_olc.py [N]   (N=örnek sayısı, vars. 2000)
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
TOP_K = 10
ADAY_K = 50


def hybrid_ara(client, sorgu, top_k=TOP_K):
    dense, sparse = embed_sorgu(sorgu)
    sp_idx = [int(k) for k in sparse.keys()]
    sp_val = list(sparse.values())
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])
    res = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(query=dense, using="dense", limit=ADAY_K, filter=flt),
            models.Prefetch(query=models.SparseVector(indices=sp_idx, values=sp_val),
                            using="sparse", limit=ADAY_K, filter=flt),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    # dönen maddelerin (kanun_no, madde_no) listesi — sıralı
    return [(p.payload["kanun_no"], p.payload["madde_no"]) for p in res.points]


def main():
    random.seed(SEED)

    # Korpustaki yürürlük durumunu öğren (mülga gold'ları ayırmak için)
    yur = {}
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            yur[(str(m["kanun_no"]), str(m["madde_no"]))] = m["yurutluk"]

    # Gold yükle + örnekle
    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    client = QdrantClient(url=QDRANT_URL)

    # Metrik biriktiriciler
    ranks = []          # doğru maddenin sırası (0=bulunamadı)
    mulga_atlanan = 0
    eslesmeyen = 0      # korpusta olmayan (variant/ek farkı)
    olculen = 0

    hedef = min(N, len(gold))
    for g in gold:
        if olculen >= hedef:
            break
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        durum = yur.get((kn, mn))
        if durum is None:
            eslesmeyen += 1
            continue
        if durum == "mülga":
            mulga_atlanan += 1
            continue   # yürürlük filtreli arama bunu getiremez → ölçüm-dışı

        sorgu = g["ilgi"]
        donen = hybrid_ara(client, sorgu)
        # doğru madde kaçıncı sırada?
        rank = 0
        for sira, (dkn, dmn) in enumerate(donen, 1):
            if str(dkn) == kn and str(dmn) == mn:
                rank = sira
                break
        ranks.append(rank)
        olculen += 1
        if olculen % 100 == 0:
            print(f"  {olculen}/{hedef} ölçüldü...", end="\r")

    # ---- Metrikleri hesapla ----
    n = len(ranks)
    def recall_at(k):
        return sum(1 for r in ranks if 1 <= r <= k) / n
    mrr = sum((1.0 / r) for r in ranks if r > 0) / n
    # nDCG@10: tek doğru madde → DCG = 1/log2(rank+1) eğer rank<=10, IDCG=1
    ndcg = sum((1.0 / math.log2(r + 1)) for r in ranks if 1 <= r <= 10) / n

    print("\n" + "=" * 60)
    print(f"METRIK RAPORU — hybrid (dense+sparse+RRF, yürürlük filtreli)")
    print("=" * 60)
    print(f"Ölçülen sorgu       : {n}")
    print(f"Mülga (ölçüm-dışı)  : {mulga_atlanan}")
    print(f"Korpusta yok (atlan): {eslesmeyen}")
    print("-" * 60)
    print(f"Recall@1            : {recall_at(1):.4f}")
    print(f"Recall@5            : {recall_at(5):.4f}")
    print(f"Recall@10           : {recall_at(10):.4f}")
    print(f"MRR                 : {mrr:.4f}")
    print(f"nDCG@10             : {ndcg:.4f}")
    print("=" * 60)
    print(f"(Kıyas: supervisor kanun-embedder-v1 R@10 = 0.76)")


if __name__ == "__main__":
    main()
