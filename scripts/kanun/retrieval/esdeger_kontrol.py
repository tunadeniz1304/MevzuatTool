# -*- coding: utf-8 -*-
"""Eşdeğerlik kontrolü: kütüphane `HybridArama.ara` == eski `search_qdrant.ara` (top-10, birebir).

F1 refactor'ü davranış-koruyan olmalı. Eski fonksiyonun main'deki (2026-07) gövdesi aşağıda
DONDURULMUŞ kopya olarak durur (`_eski_ara`) — referans; değiştirilmez.
Sorgu seti ölçüm protokolüyle aynı: altınset_temiz, random.seed(4721) + shuffle, doğru maddesi
mülga/yok olan sorgular atlanır, ilk N uygun sorgu.

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/esdeger_kontrol.py [N]   (vars. 50)
"""
import sys
import json
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from qdrant_client import QdrantClient, models
from kanun.retrieval.config import ayarlar_oku
from kanun.retrieval.embed import embed_sorgu
from kanun.retrieval.search import HybridArama, bm25_kur, norm, tokenize

GOLD_YOL = "data/gold/altinset_temiz.jsonl"
SEED = 4721
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50


def _eski_ara(client, collection, bm25, bm25_maddeler, sorgu, top_k=10, aday_k=50,
              w=(0.33, 0.33, 0.34)):
    """main'deki search_qdrant.ara'nın dondurulmuş kopyası (yalnız sabitler parametre)."""
    dense, sparse = embed_sorgu(sorgu)
    sp_indices = [int(k) for k in sparse.keys()]
    sp_values = list(sparse.values())
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])
    dres = client.query_points(collection_name=collection, query=dense, using="dense",
                               limit=aday_k, query_filter=flt, with_payload=True)
    sres = client.query_points(
        collection_name=collection,
        query=models.SparseVector(indices=sp_indices, values=sp_values),
        using="sparse", limit=aday_k, query_filter=flt, with_payload=True)

    def anahtar(p):
        return (str(p.payload["kanun_no"]), str(p.payload["madde_no"]))

    d_skor = {anahtar(p): p.score for p in dres.points}
    s_skor = {anahtar(p): p.score for p in sres.points}
    bm_skorlar = bm25.get_scores(tokenize(sorgu))
    en_iyi = sorted(range(len(bm_skorlar)), key=lambda i: -bm_skorlar[i])[:aday_k]
    b_skor = {}
    for i in en_iyi:
        if bm_skorlar[i] <= 0:
            continue
        kn, mn, _mid = bm25_maddeler[i]
        b_skor[(kn, mn)] = float(bm_skorlar[i])
    dn, sn, bn = norm(d_skor), norm(s_skor), norm(b_skor)
    puan = {}
    for k in set(dn) | set(sn) | set(bn):
        puan[k] = w[0] * dn.get(k, 0.0) + w[1] * sn.get(k, 0.0) + w[2] * bn.get(k, 0.0)
    return [k for k, _ in sorted(puan.items(), key=lambda x: -x[1])[:top_k]]


def main():
    ayar = ayarlar_oku()
    client = QdrantClient(url=ayar.qdrant_url)
    print("BM25 index kuruluyor...")
    idx = bm25_kur(ayar.korpus_yol)
    arama = HybridArama(embed_sorgu, client, idx, collection=ayar.collection)

    yur = {}
    with open(ayar.korpus_yol, encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)["metadata"]
            yur[(str(m["kanun_no"]), str(m["madde_no"]))] = m["yurutluk"]
    random.seed(SEED)
    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    ayni = kontrol = 0
    for g in gold:
        if kontrol >= N:
            break
        if yur.get((str(g["kanun_no"]), str(g["madde_no"]))) in (None, "mülga"):
            continue
        # eski yol ORİJİNAL rank_bm25 get_scores'u kullanır (HizliBM25 de böylece doğrulanır)
        eski = _eski_ara(client, ayar.collection, getattr(idx.bm25, "okapi", idx.bm25), idx.maddeler,
                         g["ilgi"])
        yeni = [s.anahtar for s in arama.ara(g["ilgi"], top_k=10, rerank=False)]
        kontrol += 1
        if eski == yeni:
            ayni += 1
        else:
            print(f"  FARK: {g['ilgi'][:60]!r}\n    eski={eski}\n    yeni={yeni}")
    print(f"\n{ayni}/{kontrol} aynı")
    sys.exit(0 if ayni == kontrol else 1)


if __name__ == "__main__":
    main()
