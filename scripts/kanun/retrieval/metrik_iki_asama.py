# -*- coding: utf-8 -*-
"""İki-aşamalı retrieval SİMÜLASYONU: önce kanun daralt, sonra madde seç.

Soru: KANUN R@10=0.91 ama MADDE R@10=0.72. "Önce kanunu getir, sonra o kanunda
madde seç" gerçekten kazandırır mı? DİKKAT: KANUN eğrisi bir ORACLE (doğru kanunu
bildiğimizi varsayar). Gerçekte Aşama-1 de hata yapar → o hata çarpan olarak vurur.

Bu script GERÇEK iki-aşamayı simüle eder (oracle değil):
  Aşama 1: 3-bacak sıralamasından ilk T FARKLI kanun_no'yu tut (T=1,3,5)
  Aşama 2: sadece o T kanunun maddelerini bırak → doğru madde ilk k'da mı?

Tek-aşama (mevcut, filtresiz) ile yan yana. T büyüdükçe iki-aşama → tek-aşamaya yakınsar.
T=1 en agresif (Aşama-1 %73 doğru kanun → tavanı o). Kazanç varsa ORTA T'de.

Füzyon = 3-bacak EŞİT (search_qdrant.py ile aynı). Sadece ölçüm, mimari değişikliği YOK.
Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_iki_asama.py [N]   (vars. 2000)
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
ADAY = 200
TOP_K = 100
KLER = [1, 5, 10, 20, 50]
T_KANUN = [1, 3, 5]   # Aşama-1'de tutulan farklı kanun sayısı

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


def ilk_t_kanun(siralama, t):
    """Sıralamadan ilk t FARKLI kanun_no'yu (görülme sırasıyla) döndür."""
    gorulen = []
    for kn, _mn in siralama:
        if kn not in gorulen:
            gorulen.append(kn)
            if len(gorulen) >= t:
                break
    return set(gorulen)


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

    # tek-aşama + her T için iki-aşama rank listeleri
    ranks = {"TEK_ASAMA": []}
    for t in T_KANUN:
        ranks[f"IKI_T{t}"] = []
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

        siralama = wsum([dense_skor, sparse_skor, bm25_skor], [0.33, 0.33, 0.34])

        # tek-aşama: filtresiz
        r_tek = next((i for i, a in enumerate(siralama[:TOP_K], 1) if a == hedef_madde), 0)
        ranks["TEK_ASAMA"].append(r_tek)

        # iki-aşama: Aşama-1 ilk T kanunu tut, Aşama-2 o kanunlara filtrele
        for t in T_KANUN:
            tutulan = ilk_t_kanun(siralama, t)
            filtreli = [a for a in siralama if a[0] in tutulan]
            r_iki = next((i for i, a in enumerate(filtreli[:TOP_K], 1) if a == hedef_madde), 0)
            ranks[f"IKI_T{t}"].append(r_iki)

        olculen += 1
        if olculen % 50 == 0:
            print(f"  {olculen}/{hedef}...", end="\r")

    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n

    print("\n" + "=" * 70)
    print(f"IKI-ASAMALI SIMULASYON - {n} sorgu (Asama-1 ilk T kanun -> Asama-2 madde)")
    print("=" * 70)
    print(f"{'Yontem':<14}{'R@1':>10}{'R@5':>10}{'R@10':>10}{'R@20':>10}{'MRR':>10}")
    print("-" * 70)
    for y in ["TEK_ASAMA"] + [f"IKI_T{t}" for t in T_KANUN]:
        print(f"{y:<14}{R(ranks[y],1):>10.4f}{R(ranks[y],5):>10.4f}"
              f"{R(ranks[y],10):>10.4f}{R(ranks[y],20):>10.4f}{MRR(ranks[y]):>10.4f}")
    print("=" * 70)
    tek = R(ranks['TEK_ASAMA'], 10)
    for t in T_KANUN:
        d = R(ranks[f'IKI_T{t}'], 10) - tek
        print(f"IKI_T{t} vs TEK (R@10): {d:+.4f}  "
              f"{'KAZANC' if d > 0 else 'KAYIP' if d < 0 else 'ESIT'}")
    print("\nNot: T=1 en agresif (Asama-1 yanlis kanun tutunca dogru madde ASLA gelmez).")
    print("Kazanc ORTA T'de olur: yeterli daralma + Asama-1 hata toleransi.")


if __name__ == "__main__":
    main()
