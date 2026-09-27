# -*- coding: utf-8 -*-
"""Ölçüm protokolü yardımcıları — gold sorgu seti + sıra metrikleri (R@k, MRR@10, nDCG@10).

Protokol (docs/retrieval-metrikleri.md, değişmez): `data/gold/altinset_temiz.jsonl`, `random.seed(4721)`
+ `shuffle`, doğru maddesi korpusta olmayan ya da mülga olan sorgu atlanır, ilk N uygun sorgu.
Metrik tanımları `metrik_bm25.py` ile aynı: sıra 1-tabanlı, 0 = ilk 10'da yok; MRR ve nDCG@10 ilk 10
üzerinden (MRR@10). Genel bir benchmark çerçevesi DEĞİL (compliance B, ADR-0016) — yalnız bu protokol.
"""
import json
import math
import random

GOLD_YOL = "data/gold/altinset_temiz.jsonl"
SEED = 4721


def gold_sorgular(n, korpus_yol="data/kanun/korpus.jsonl", gold_yol=GOLD_YOL, seed=SEED):
    """[(sorgu, (kanun_no, madde_no)), ...] — ilk n uygun sorgu, protokol sırasıyla."""
    yur = {}
    with open(korpus_yol, encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)["metadata"]
            yur[(str(m["kanun_no"]), str(m["madde_no"]))] = m["yurutluk"]
    with open(gold_yol, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.seed(seed)
    random.shuffle(gold)
    cikti = []
    for g in gold:
        if len(cikti) >= n:
            break
        hedef = (str(g["kanun_no"]), str(g["madde_no"]))
        if yur.get(hedef) in (None, "mülga"):
            continue
        cikti.append((g["ilgi"], hedef))
    return cikti


def sira(liste, hedef, k=10):
    """hedef'in ilk k içindeki 1-tabanlı sırası; yoksa 0."""
    return next((i for i, a in enumerate(liste[:k], 1) if a == hedef), 0)


def metrikler(siralar):
    """Sıra listesi → {R@1, R@5, R@10, MRR, nDCG@10, N}."""
    n = len(siralar)
    if n == 0:
        return {"R@1": 0.0, "R@5": 0.0, "R@10": 0.0, "MRR": 0.0, "nDCG@10": 0.0, "N": 0}

    def R(k):
        return sum(1 for r in siralar if 1 <= r <= k) / n

    return {"R@1": R(1), "R@5": R(5), "R@10": R(10),
            "MRR": sum(1.0 / r for r in siralar if 1 <= r <= 10) / n,
            "nDCG@10": sum(1.0 / math.log2(r + 1) for r in siralar if 1 <= r <= 10) / n,
            "N": n}


def rerank_uygula(adaylar, skorlar, rerank_aday):
    """WSUM sırasındaki adayların ilk rerank_aday'ını skorlarla (kararlı) yeniden sırala; kalan dokunulmaz.
    HybridArama.ara ile aynı kural — ölçüm, önceden çıkarılmış adaylar üzerinde bunu uygular."""
    bas = list(zip(adaylar[:rerank_aday], skorlar[:rerank_aday]))
    bas.sort(key=lambda x: -x[1])
    return [a for a, _ in bas] + list(adaylar[rerank_aday:])
