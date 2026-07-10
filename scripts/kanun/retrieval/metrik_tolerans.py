# -*- coding: utf-8 -*-
"""ÖLÇÜM 1: Çok-versiyon toleransı — sistem AYNI, ölçüm daha adil.

Sorun: yapılandırma kanunları (6111/6736/7143/7326/7440 m.5) aynı konu, farklı no.
Gold "6111" derken sistem "7326" getirir → katı eşleşme haksız 0 verir.

Çözüm: 3 farklı "doğru" tanımıyla AYNI aramaları yeniden puanla, yan yana:
  - KATI      : (kanun_no, madde_no) birebir (baseline)
  - AYNI_AD   : kanun ADI aynı (versiyon farkı tolere) + madde_no aynı
  - AYNI_KANUN: sadece aynı kanun (madde farkı da tolere) — en gevşek

Reranker YOK, tek model. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/metrik_tolerans.py [N]   (vars. 2000)
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


def main():
    random.seed(SEED)
    # korpus: yürürlük + kanun adı
    yur, kanun_ad = {}, {}
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            key = (str(m["kanun_no"]), str(m["madde_no"]))
            yur[key] = m["yurutluk"]
            kanun_ad[str(m["kanun_no"])] = (m.get("kanun_ad") or "").strip()

    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    client = QdrantClient(url=QDRANT_URL)
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    # her tanım için ranks listesi
    ranks = {"KATI": [], "AYNI_AD": [], "AYNI_KANUN": []}
    hedef = min(N, len(gold))
    olculen = 0

    for g in gold:
        if olculen >= hedef:
            break
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        if yur.get((kn, mn)) in (None, "mülga"):
            continue
        gold_ad = kanun_ad.get(kn, "")

        dense, sparse = embed_sorgu(g["ilgi"])
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
        donen = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in res.points]

        # 3 tanım için sıra bul
        r_kati = r_ad = r_kanun = 0
        for sira, (dkn, dmn) in enumerate(donen, 1):
            dad = kanun_ad.get(dkn, "")
            if r_kati == 0 and dkn == kn and dmn == mn:
                r_kati = sira
            if r_ad == 0 and dad and dad == gold_ad and dmn == mn:
                r_ad = sira
            if r_kanun == 0 and dad and dad == gold_ad:
                r_kanun = sira
        ranks["KATI"].append(r_kati)
        ranks["AYNI_AD"].append(r_ad)
        ranks["AYNI_KANUN"].append(r_kanun)
        olculen += 1
        if olculen % 100 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    print("\n" + "=" * 62)
    print(f"ÖLÇÜM 1: ÇOK-VERSİYON TOLERANSI — {n} sorgu (sistem AYNI)")
    print("=" * 62)
    print(f"{'Metrik':<10}{'KATI':>13}{'AYNI_AD':>13}{'AYNI_KANUN':>13}")
    print("-" * 62)
    for k in [1, 5, 10]:
        print(f"R@{k:<8}{R(ranks['KATI'],k):>13.4f}{R(ranks['AYNI_AD'],k):>13.4f}{R(ranks['AYNI_KANUN'],k):>13.4f}")
    print(f"{'MRR':<10}{MRR(ranks['KATI']):>13.4f}{MRR(ranks['AYNI_AD']):>13.4f}{MRR(ranks['AYNI_KANUN']):>13.4f}")
    print(f"{'nDCG@10':<10}{nDCG(ranks['KATI']):>13.4f}{nDCG(ranks['AYNI_AD']):>13.4f}{nDCG(ranks['AYNI_KANUN']):>13.4f}")
    print("=" * 62)
    print("KATI=baseline | AYNI_AD=versiyon tolere | AYNI_KANUN=en gevsek")
    print("AYNI_AD >> KATI ise -> cok-versiyon artefakti gercek; sistem daha iyi.")


if __name__ == "__main__":
    main()
