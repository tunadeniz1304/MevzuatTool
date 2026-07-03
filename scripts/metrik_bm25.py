# -*- coding: utf-8 -*-
"""ÖLÇÜM 4: Klasik BM25 üçüncü bacak katkı yapıyor mu?

Şu anki "sparse" = BGE-M3 ÖĞRENİLMİŞ sparse (sparse_linear.pt), klasik BM25 DEĞİL.
Burada klasik BM25'i (rank_bm25, istatistiksel TF-IDF+doc-len) korpus 'text' üzerine
kurup üçüncü bacak olarak ekleriz ve mevcut iki-bacak WSUM ile kıyaslarız:

  - WSUM_050        : dense + BGE-sparse (mevcut en iyi, baseline)
  - +BM25 (3-bacak) : dense + BGE-sparse + klasik-BM25, eşit ağırlık WSUM
  - BM25_ONLY       : sadece klasik BM25 (bacak tek başına ne yapıyor)

BM25 index korpus 'text' üzerine (embedding'in gördüğü AYNI metin — adil kıyas,
madde-no/metadata YOK → sızıntı yok). Türkçe için basit lower+kelime tokenizasyon.

Reranker YOK, tek embed modeli. Baseline ile aynı seed → aynı sorgu seti.
Çalıştır: .venv/Scripts/python.exe scripts/metrik_bm25.py [N]   (vars. 2000)
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
ADAY = 50           # dense/sparse her bacak; BM25 de aynı sayıda getirir
TOP_K = 10

_TOKEN = re.compile(r"[0-9a-zçğıöşü]+", re.UNICODE)


def tokenize(metin):
    """BM25 klasik: lower + kelime ayır (Türkçe harfler dahil)."""
    return _TOKEN.findall(metin.lower())


def norm(d):
    if not d:
        return {}
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in d.items()}


def wsum(*skor_sozlukleri):
    """Eşit ağırlıklı normalize skor toplamı (2 veya 3 bacak)."""
    normler = [norm(s) for s in skor_sozlukleri]
    tum = set()
    for nn in normler:
        tum |= set(nn)
    a = 1.0 / len(normler)
    puan = {}
    for m in tum:
        puan[m] = sum(a * nn.get(m, 0.0) for nn in normler)
    return [m for m, _ in sorted(puan.items(), key=lambda x: -x[1])]


def main():
    random.seed(SEED)

    # --- korpus: yürürlük + BM25 index (yalnız yürürlükte maddeler) ---
    print("Korpus okunuyor + BM25 index kuruluyor...")
    yur = {}
    bm25_maddeler = []   # (kanun_no, madde_no) sırası — index ile hizalı
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

    ranks = {"WSUM_050": [], "3BACAK": [], "BM25_ONLY": []}
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

        # klasik BM25: sorguyu tokenize et, tüm yürürlükte maddelere skor ver, top-ADAY al
        q_tok = tokenize(g["ilgi"])
        bm_skorlar = bm25.get_scores(q_tok)
        # en yüksek ADAY tanesini seç
        en_iyi = sorted(range(len(bm_skorlar)), key=lambda i: -bm_skorlar[i])[:ADAY]
        bm25_skor = {bm25_maddeler[i]: float(bm_skorlar[i]) for i in en_iyi if bm_skorlar[i] > 0}

        siralamalar = {
            "WSUM_050": wsum(dense_skor, sparse_skor),
            "3BACAK": wsum(dense_skor, sparse_skor, bm25_skor),
            "BM25_ONLY": [m for m, _ in sorted(bm25_skor.items(), key=lambda x: -x[1])],
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

    print("\n" + "=" * 70)
    print(f"ÖLÇÜM 4: KLASİK BM25 ÜÇÜNCÜ BACAK — {n} sorgu")
    print("=" * 70)
    print(f"{'Yöntem':<14}{'R@1':>10}{'R@5':>10}{'R@10':>10}{'MRR':>10}{'nDCG':>10}")
    print("-" * 70)
    for y in ["WSUM_050", "3BACAK", "BM25_ONLY"]:
        print(f"{y:<14}{R(ranks[y],1):>10.4f}{R(ranks[y],5):>10.4f}"
              f"{R(ranks[y],10):>10.4f}{MRR(ranks[y]):>10.4f}{nDCG(ranks[y]):>10.4f}")
    print("=" * 70)
    w10, t10 = R(ranks['WSUM_050'], 10), R(ranks['3BACAK'], 10)
    b10 = R(ranks['BM25_ONLY'], 10)
    print(f"3-bacak fark (WSUM'a gore): R@10 {t10-w10:+.4f}, "
          f"MRR {MRR(ranks['3BACAK'])-MRR(ranks['WSUM_050']):+.4f}")
    print(f"BM25 tek basina R@10={b10:.4f} "
          f"(BGE-sparse ablasyon 0.526 idi -> {'ustunde' if b10>0.526 else 'altinda'})")


if __name__ == "__main__":
    main()
