# -*- coding: utf-8 -*-
"""Reranker DENEYİ — hybrid top-50 → reranker yeniden sırala → R@10 kıyasla.

Amaç: reranker R@10'u yükseltiyor mu? (Recall eğrisi R@100=0.81 >> R@10=0.67
     olduğunu gösterdi → doğru madde getiriliyor ama sıralama kötü → reranker adayı.)

Akış (her sorgu):
  1. hybrid retriever → top-ADAY madde + METİNLERİ getir
  2. reranker (cross-encoder) → (sorgu, madde-metni) çiftlerini puanla
  3. yeniden sırala → yeni sıralama
  4. HEM hybrid HEM reranked için doğru maddenin sırasını kaydet

Çıktı: iki R@1/5/10 tablosu yan yana (hybrid vs +reranker).

Reranker: BAAI/bge-reranker-v2-m3 (transformers ile, ilk sefer ~2GB iner).
Çalıştır: .venv/Scripts/python.exe scripts/metrik_rerank.py [N]   (vars. 500)
"""
import sys
import json
import math
import pathlib
import random

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from qdrant_client import QdrantClient, models
from mevzuat_tool.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
GOLD_YOL = "data/gold/altinset_temiz.jsonl"
KORPUS_YOL = "data/corpus/korpus.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
ADAY = 50        # reranker'a kaç aday gidecek
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# --- Reranker (lazy) ---
_rtok = None
_rmodel = None
_device = "cuda" if torch.cuda.is_available() else "cpu"

def _rerank_yukle():
    global _rtok, _rmodel
    if _rmodel is not None:
        return
    _rtok = AutoTokenizer.from_pretrained(RERANK_MODEL)
    _rmodel = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL)
    _rmodel.eval()
    _rmodel.to(_device)   # GPU varsa reranker'ı GPU'da çalıştır (çok daha hızlı)
    print(f"  reranker cihaz: {_device}", flush=True)

def rerank_skorla(sorgu, metinler):
    """(sorgu, her metin) çiftini puanla → skor listesi."""
    _rerank_yukle()
    ciftler = [[sorgu, m] for m in metinler]
    with torch.no_grad():
        inp = _rtok(ciftler, padding=True, truncation=True, max_length=512, return_tensors="pt")
        inp = {k: v.to(_device) for k, v in inp.items()}
        skor = _rmodel(**inp).logits.view(-1).float()
    return skor.cpu().tolist()


def main():
    random.seed(SEED)

    # Korpus: yürürlük + metin (reranker metin ister)
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

    hybrid_ranks = []
    rerank_ranks = []
    hedef = min(N, len(gold))

    for g in gold:
        if len(hybrid_ranks) >= hedef:
            break
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        durum = yur.get((kn, mn))
        if durum is None or durum == "mülga":
            continue

        sorgu = g["ilgi"]
        # 1) hybrid retriever → top-ADAY
        dense, sparse = embed_sorgu(sorgu)
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
        adaylar = [(str(p.payload["kanun_no"]), str(p.payload["madde_no"])) for p in res.points]

        # hybrid sırası
        h_rank = next((i for i, a in enumerate(adaylar, 1) if a == (kn, mn)), 0)
        hybrid_ranks.append(h_rank)

        # 2) reranker → adayların metinlerini puanla, yeniden sırala
        metinler = [metin_map.get(a, "") for a in adaylar]
        skorlar = rerank_skorla(sorgu, metinler)
        # skora göre azalan sırala
        sirali = sorted(zip(adaylar, skorlar), key=lambda x: -x[1])
        yeni_sira = [a for a, _ in sirali]
        r_rank = next((i for i, a in enumerate(yeni_sira, 1) if a == (kn, mn)), 0)
        rerank_ranks.append(r_rank)

        if len(hybrid_ranks) % 50 == 0:
            print(f"  {len(hybrid_ranks)}/{hedef}...", end="\r")

    # --- karşılaştırmalı rapor ---
    def metr(ranks, k):
        return sum(1 for r in ranks if 1 <= r <= k) / len(ranks)
    def mrr(ranks):
        return sum((1.0/r) for r in ranks if r > 0) / len(ranks)
    def ndcg(ranks):
        return sum((1.0/math.log2(r+1)) for r in ranks if 1 <= r <= 10) / len(ranks)

    n = len(hybrid_ranks)
    print("\n" + "=" * 60)
    print(f"RERANKER DENEYİ — {n} sorgu (aday havuzu: top-{ADAY})")
    print("=" * 60)
    print(f"{'Metrik':<12}{'Hybrid':>12}{'+Reranker':>12}{'Fark':>10}")
    print("-" * 60)
    for k in [1, 5, 10]:
        h, r = metr(hybrid_ranks, k), metr(rerank_ranks, k)
        print(f"Recall@{k:<6}{h:>12.4f}{r:>12.4f}{r-h:>+10.4f}")
    hm, rm = mrr(hybrid_ranks), mrr(rerank_ranks)
    print(f"{'MRR':<12}{hm:>12.4f}{rm:>12.4f}{rm-hm:>+10.4f}")
    hn, rn = ndcg(hybrid_ranks), ndcg(rerank_ranks)
    print(f"{'nDCG@10':<12}{hn:>12.4f}{rn:>12.4f}{rn-hn:>+10.4f}")
    print("=" * 60)
    print("Fark POZİTİF ve büyükse -> reranker işe yarıyor, kalıcı yap.")
    print("Fark küçük/negatifse -> reranker gereksiz, kaldır.")


if __name__ == "__main__":
    main()
