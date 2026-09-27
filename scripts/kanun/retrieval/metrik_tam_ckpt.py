# -*- coding: utf-8 -*-
"""3-bacak EStT TAM olcum (tum gold, 21.737 sorgu) - CHECKPOINT'li.

Final sistemin (3-bacak WSUM EStT) madde + kanun seviyesi tam profili, TUM gold
uzerinde (buyuk orneklem -> guvenilir). ~1.5-2 saat surer -> checkpoint sart.

CHECKPOINT mantigi:
  - Her CKPT_HER sorguda ilerleme diske yazilir (JSON): olculen + rank listeleri.
  - Baslarken checkpoint varsa OKUR, kaldigi sorgudan devam eder (ayni seed ->
    ayni sorgu sirasi, ilk 'olculen' sorgu atlanir).
  - Ctrl+C ile kesince son checkpoint yazilir, temiz cikar. Kayip max CKPT_HER sorgu.
  - Bitince checkpoint SiLiNiR, sonuc .olcum_tam.txt'e yazilir.

Cikti ASCII-guvenli (cp1254). Calistir (utf-8 io ile onerilir):
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -u scripts/kanun/retrieval/metrik_tam_ckpt.py
Devam icin ayni komutu tekrar calistir - kaldigi yerden surer.
"""
import re
import os
import sys
import json
import math
import signal
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
CKPT_YOL = "data/gold/.ckpt_tam.json"
SONUC_YOL = ".olcum_tam.txt"
SEED = 4721
ADAY = 200
TOP_K = 100
CKPT_HER = 500           # kac sorguda bir checkpoint
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


def ckpt_yaz(olculen, madde_ranks, kanun_ranks):
    tmp = CKPT_YOL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"olculen": olculen, "madde": madde_ranks, "kanun": kanun_ranks}, f)
    os.replace(tmp, CKPT_YOL)   # atomik yazim (yarim dosya olmaz)


def ckpt_oku():
    if not os.path.exists(CKPT_YOL):
        return 0, [], []
    with open(CKPT_YOL, encoding="utf-8") as f:
        d = json.load(f)
    return d["olculen"], d["madde"], d["kanun"]


def main():
    random.seed(SEED)

    print("Korpus okunuyor + BM25 index kuruluyor...", flush=True)
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
    print(f"  BM25 index: {len(bm25_dokumanlar)} yururlukte madde", flush=True)

    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)   # SEED sabit -> her calismada AYNI sira

    client = QdrantClient(url=QDRANT_URL)
    flt = models.Filter(must=[models.FieldCondition(
        key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    # checkpoint'ten devam
    olculen, madde_ranks, kanun_ranks = ckpt_oku()
    if olculen > 0:
        print(f"  CHECKPOINT bulundu: {olculen} sorgu islenmis, devam ediliyor.", flush=True)

    # gold uzerinde 'gecerli' (yururlukte hedef) sorgular sirayla islenir.
    # atla-sayaci: checkpoint'teki 'olculen' kadar GECERLI sorgu zaten islendi.
    atlanacak = olculen
    islenen_gecerli = 0

    # Ctrl+C: bayrak koy, dongu sonunda temiz cik
    kesildi = {"flag": False}
    def _sigint(signum, frame):
        kesildi["flag"] = True
        print("\n  [Ctrl+C alindi - son checkpoint yazilip cikilacak...]", flush=True)
    signal.signal(signal.SIGINT, _sigint)

    for g in gold:
        kn, mn = str(g["kanun_no"]), str(g["madde_no"])
        if yur.get((kn, mn)) in (None, "mülga"):
            continue   # gecersiz hedef - hic sayilmaz (checkpoint'le tutarli)
        # bu bir GECERLI sorgu
        if islenen_gecerli < atlanacak:
            islenen_gecerli += 1
            continue   # checkpoint'te zaten islenmis, atla
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
        m_rank = next((i for i, a in enumerate(siralama, 1) if a == hedef_madde), 0)
        k_rank = next((i for i, a in enumerate(siralama, 1) if a[0] == kn), 0)
        madde_ranks.append(m_rank)
        kanun_ranks.append(k_rank)
        olculen += 1

        if olculen % CKPT_HER == 0:
            ckpt_yaz(olculen, madde_ranks, kanun_ranks)
            print(f"  {olculen} islendi (checkpoint kaydedildi)...", flush=True)

        if kesildi["flag"]:
            ckpt_yaz(olculen, madde_ranks, kanun_ranks)
            print(f"  KESiLDi: {olculen} sorgu guvende. Ayni komutla devam edebilirsin.", flush=True)
            return

    # bitti - son checkpoint + sonuc
    ckpt_yaz(olculen, madde_ranks, kanun_ranks)
    n = olculen
    def R(rl, k): return sum(1 for r in rl if 1 <= r <= k) / n
    def MRR(rl): return sum((1.0/r) for r in rl if r > 0) / n
    def nDCG(rl): return sum((1.0/math.log2(r+1)) for r in rl if 1 <= r <= 10) / n

    satirlar = []
    satirlar.append("=" * 58)
    satirlar.append(f"3-BACAK ESiT TAM PROFiL (TUM GOLD) - {n} sorgu")
    satirlar.append("=" * 58)
    satirlar.append(f"{'Metrik':<12}{'MADDE':>14}{'KANUN':>14}{'Fark':>12}")
    satirlar.append("-" * 58)
    for k in KLER:
        m, kk = R(madde_ranks, k), R(kanun_ranks, k)
        satirlar.append(f"R@{k:<10}{m:>14.4f}{kk:>14.4f}{kk-m:>+12.4f}")
    mm, km = MRR(madde_ranks), MRR(kanun_ranks)
    satirlar.append(f"{'MRR':<12}{mm:>14.4f}{km:>14.4f}{km-mm:>+12.4f}")
    mn, kn2 = nDCG(madde_ranks), nDCG(kanun_ranks)
    satirlar.append(f"{'nDCG@10':<12}{mn:>14.4f}{kn2:>14.4f}{kn2-mn:>+12.4f}")
    satirlar.append("=" * 58)
    cikti = "\n".join(satirlar)
    print("\n" + cikti, flush=True)
    with open(SONUC_YOL, "w", encoding="utf-8") as f:
        f.write(cikti + "\n")
    os.remove(CKPT_YOL)   # bitti, checkpoint temizle
    print(f"\nBitti. Sonuc: {SONUC_YOL} (checkpoint silindi).", flush=True)


if __name__ == "__main__":
    main()
