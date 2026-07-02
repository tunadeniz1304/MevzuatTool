# -*- coding: utf-8 -*-
"""Reranker ölçümü için Colab girdisi hazırla (PC'de, hızlı).

Her sorgu için: hybrid retriever → top-50 aday (kanun_no, madde_no, METİN) + gold.
Reranker YOK (bu PC'de hızlı: sadece BGE-M3 embed + Qdrant retriever).
Çıktı Colab'a taşınır, reranker orada (T4) çalışır.

Çıktı: colab/rerank_input.jsonl
  Her satır: {sorgu, dogru:[kn,mn], adaylar:[{kn,mn,text}, ...50]}

Çalıştır: .venv/Scripts/python.exe scripts/rerank_hazirla.py [N]   (vars. 2000)
"""
import sys
import json
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from qdrant_client import QdrantClient, models
from mevzuat_tool.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/corpus/korpus.jsonl"
OUT = "colab/rerank_input.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
ADAY = 50


def main():
    random.seed(SEED)   # metrik_olc.py ile AYNI seed → aynı sorgu seti (adil kıyas)

    # korpus: yürürlük + metin
    yur, metin_map = {}, {}
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            key = (str(m["kanun_no"]), str(m["madde_no"]))
            yur[key] = m["yurutluk"]
            metin_map[key] = r.get("text") or ""

    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    client = QdrantClient(url=QDRANT_URL)
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    pathlib.Path("colab").mkdir(exist_ok=True)
    yazilan = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for g in gold:
            if yazilan >= N:
                break
            kn, mn = str(g["kanun_no"]), str(g["madde_no"])
            durum = yur.get((kn, mn))
            if durum is None or durum == "mülga":
                continue

            dense, sparse = embed_sorgu(g["ilgi"])
            sp_idx = [int(k) for k in sparse.keys()]
            sp_val = list(sparse.values())
            res = client.query_points(
                collection_name=COLLECTION,
                prefetch=[
                    models.Prefetch(query=dense, using="dense", limit=ADAY, filter=flt),
                    models.Prefetch(query=models.SparseVector(indices=sp_idx, values=sp_val),
                                    using="sparse", limit=ADAY, filter=flt),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=ADAY,
                with_payload=True,
            )
            adaylar = []
            for p in res.points:
                akn, amn = str(p.payload["kanun_no"]), str(p.payload["madde_no"])
                adaylar.append({
                    "kn": akn, "mn": amn,
                    "text": metin_map.get((akn, amn), "")[:1500],  # reranker 512 token yeter
                })
            out.write(json.dumps({
                "sorgu": g["ilgi"],
                "dogru": [kn, mn],
                "adaylar": adaylar,
            }, ensure_ascii=False) + "\n")
            yazilan += 1
            if yazilan % 100 == 0:
                print(f"  {yazilan}/{N} hazırlandı...", end="\r")

    print(f"\n✓ {yazilan} sorgu -> {OUT}")
    import os
    print(f"  boyut: {os.path.getsize(OUT)/1e6:.1f} MB")
    print("  Bu dosyayı Colab'a yükle (Drive) -> reranker orada ölçer.")


if __name__ == "__main__":
    main()
