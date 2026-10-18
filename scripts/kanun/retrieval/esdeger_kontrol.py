# -*- coding: utf-8 -*-
"""Eşdeğerlik kontrolü: kütüphane `HybridArama` == eski `search_qdrant.ara` (gerçek index + korpus).

F1 refactor'ü davranış-koruyan olmalı. Eski fonksiyonun main'deki (2026-07) gövdesi aşağıda
DONDURULMUŞ kopya olarak durur (`_eski_ara`) — referans; algoritması değiştirilmez (yalnız tüm adayları
puanlarıyla döndürür). İki yol aynı sorgu vektörünü kullanır, puanlar birebir karşılaştırılır.
Sorgu seti ölçüm protokolüyle aynı: altınset_temiz, random.seed(4721) + shuffle, doğru maddesi
mülga/yok olan sorgular atlanır, ilk N uygun sorgu.

Kütüphanenin aday kimliği madde_id'dir (eski: (kanun_no, madde_no)) → sorgu başına sınıf (`sinifla`):
  ayni      : top-10 (kanun_no, madde_no) ve puanları birebir aynı
  esit_puan : adaylar ve puanları aynı; yalnız puanı TAM eşit adayların sırası farklı (eski set birleşimi
              bu sırayı anahtar hash'ine bağlıyordu, yeni sıra ilk görünme)
  cakisma   : yeni adaylarda aynı (kanun_no, madde_no) birden çok madde (tertip çakışması / tekrarlı madde
              no) — eski kod bunları tek adaya çökertiyordu; fark beklenen düzeltmedir
  fark      : açıklanamayan fark → çıkış kodu 1

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/esdeger_kontrol.py [N]   (vars. 50)
"""
import sys
import json
import random
import pathlib
import functools

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from kanun.retrieval.config import ayarlar_oku
from kanun.retrieval.search import HybridArama, bm25_kur, norm, tokenize

GOLD_YOL = "data/gold/altinset_temiz.jsonl"
SEED = 4721


def _eski_ara(embed_sorgu, client, collection, bm25, bm25_maddeler, sorgu, aday_k=50,
              w=(0.33, 0.33, 0.34)):
    """main'deki search_qdrant.ara'nın dondurulmuş kopyası (yalnız sabitler ve embedder parametre).
    → TÜM adaylar [((kanun_no, madde_no), puan)], azalan puan (eskiden top-10 anahtar; algoritma aynı)."""
    from qdrant_client import models
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
    return sorted(puan.items(), key=lambda x: -x[1])


def sinifla(eski, sirali, payload, k=10):
    """eski: `_eski_ara` çıktısı; sirali, payload: yeni `HybridArama.adaylar()` çıktısı (madde_id anahtarlı).
    → 'ayni' | 'esit_puan' | 'cakisma' | 'fark' (modül docstring'i)."""
    yeni = [((str(payload[m]["kanun_no"]), str(payload[m]["madde_no"])), p) for m, p in sirali]
    if eski[:k] == yeni[:k]:
        return "ayni"
    if len({c for c, _ in yeni}) < len(yeni):
        return "cakisma"
    return "esit_puan" if dict(eski) == dict(yeni) else "fark"


def main():
    from qdrant_client import QdrantClient
    from kanun.retrieval.embed import embed_sorgu
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    ayar = ayarlar_oku()
    client = QdrantClient(url=ayar.qdrant_url)
    print("BM25 index kuruluyor...")
    idx = bm25_kur(ayar.korpus_yol)
    # iki yol aynı sorgu vektörünü kullanır → Qdrant puanları birebir karşılaştırılabilir
    embed = functools.lru_cache(maxsize=1)(embed_sorgu)
    arama = HybridArama(embed, client, idx, collection=ayar.collection)

    yur = {}
    with open(ayar.korpus_yol, encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)["metadata"]
            yur[(str(m["kanun_no"]), str(m["madde_no"]))] = m["yurutluk"]
    random.seed(SEED)
    with open(GOLD_YOL, encoding="utf-8") as f:
        gold = [json.loads(l) for l in f]
    random.shuffle(gold)

    sayac = dict.fromkeys(("ayni", "esit_puan", "cakisma", "fark"), 0)
    for g in gold:
        if sum(sayac.values()) >= n:
            break
        if yur.get((str(g["kanun_no"]), str(g["madde_no"]))) in (None, "mülga"):
            continue
        # eski yol ORİJİNAL rank_bm25 get_scores'u kullanır (HizliBM25 de böylece doğrulanır)
        eski = _eski_ara(embed, client, ayar.collection, getattr(idx.bm25, "okapi", idx.bm25), idx.maddeler,
                         g["ilgi"])
        sirali, payload, _ = arama.adaylar(g["ilgi"])
        sinif = sinifla(eski, sirali, payload)
        sayac[sinif] += 1
        if sinif in ("cakisma", "fark"):
            yeni = [((payload[m]["kanun_no"], payload[m]["madde_no"]), round(p, 4)) for m, p in sirali[:10]]
            print(f"  {sinif.upper()}: {g['ilgi'][:60]!r}\n"
                  f"    eski={[(c, round(p, 4)) for c, p in eski[:10]]}\n    yeni={yeni}")
    kontrol = sum(sayac.values())
    print(f"\n{sayac['ayni']}/{kontrol} aynı · {sayac['esit_puan']} yalnız eşit-puan sırası · "
          f"{sayac['cakisma']} çakışma (beklenen) · {sayac['fark']} FARK")
    sys.exit(0 if sayac["fark"] == 0 else 1)


if __name__ == "__main__":
    main()
