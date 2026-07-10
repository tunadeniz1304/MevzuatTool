# -*- coding: utf-8 -*-
"""Hybrid arama — sorgu -> dense + BGE-sparse + klasik-BM25 -> 3-bacak WSUM füzyon -> top-k.

3 bacak (ölçümle seçilen ağırlık EŞİT, ÖLÇÜM 5):
  - dense       : BGE-M3 anlam (embedding), ağırlık 0.33
  - BGE-sparse  : BGE-M3 öğrenilmiş sparse (eş-anlam), ağırlık 0.33
  - klasik-BM25 : rank_bm25 korpus 'text' üzerine (nadir-terim keskin), ağırlık 0.34

EŞİT seçildi: R@1/R@5/MRR (üst-sıra kalitesi) en iyi; ağırlık-ayarı yok → overfit yok.
(DENSE_AĞIR R@10'da +0.01 önde ama R@1/MRR gerisinde; üst-sıra tercih edildi.)

Füzyon = min-max normalize skorların ağırlıklı toplamı (RRF/iki-bacak değil).
Ölçüm yolculuğu: RRF 0.667 -> WSUM_050 0.685 -> 3-bacak EŞİT 0.700 (R@10), R@1 0.49.

Yürürlük filtresi: yalnız 'yürürlükte' maddeler (mülga elenir) — MVP-kritik.
BM25 index başlangıçta bir kez kurulur (korpus 'text', yürürlükte maddeler ~3sn).

Çalıştır:
  .venv/Scripts/python.exe scripts/search_qdrant.py "kira artışı nasıl belirlenir"
  .venv/Scripts/python.exe scripts/search_qdrant.py         (interaktif mod)
"""
import re
import sys
import json
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from kanun.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
KORPUS_YOL = "data/kanun/korpus.jsonl"
TOP_K = 10
ADAY_K = 50   # her bacak (dense/BGE-sparse/BM25) bu kadar aday getirir
# füzyon ağırlıkları (d, s, b) — ÖLÇÜM 5 EŞİT (R@1/MRR en iyi, R@10 0.700)
W_DENSE, W_SPARSE, W_BM25 = 0.33, 0.33, 0.34

_TOKEN = re.compile(r"[0-9a-zçğıöşü]+", re.UNICODE)


def _tokenize(metin):
    """BM25 klasik: lower + kelime ayır (Türkçe harfler dahil)."""
    return _TOKEN.findall(metin.lower())


def _norm(skor):
    """min-max normalize (0-1). Üç bacağın skoru farklı ölçekte → toplamadan önce şart."""
    if not skor:
        return {}
    vals = list(skor.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in skor.items()}


def bm25_kur():
    """Korpus 'text' üzerine BM25 index (yalnız yürürlükte). madde-anahtarı sırayla hizalı."""
    maddeler, dokumanlar = [], []
    with open(KORPUS_YOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            if m["yurutluk"] != "yürürlükte":
                continue
            maddeler.append((str(m["kanun_no"]), str(m["madde_no"]), r["id"]))
            dokumanlar.append(_tokenize(r["text"]))
    return BM25Okapi(dokumanlar), maddeler


def ara(client, bm25, bm25_maddeler, sorgu, yururlukte_only=True, top_k=TOP_K):
    """3-bacak WSUM füzyon: dense + BGE-sparse + klasik-BM25 → normalize → ağırlıklı topla → sırala.
    Ağırlık EŞİT (0.33/0.33/0.34, ÖLÇÜM 5). BM25 madde-anahtarıyla eşlenir (point-id yok)."""
    dense, sparse = embed_sorgu(sorgu)
    sp_indices = [int(k) for k in sparse.keys()]
    sp_values = list(sparse.values())

    flt = None
    if yururlukte_only:
        flt = models.Filter(must=[models.FieldCondition(
            key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    # dense + BGE-sparse adayları (Qdrant, skorlarıyla) — madde-anahtarı bazında topla
    dres = client.query_points(collection_name=COLLECTION, query=dense, using="dense",
                               limit=ADAY_K, query_filter=flt, with_payload=True)
    sres = client.query_points(
        collection_name=COLLECTION,
        query=models.SparseVector(indices=sp_indices, values=sp_values),
        using="sparse", limit=ADAY_K, query_filter=flt, with_payload=True)

    def anahtar(p):
        return (str(p.payload["kanun_no"]), str(p.payload["madde_no"]))

    d_skor = {anahtar(p): p.score for p in dres.points}
    s_skor = {anahtar(p): p.score for p in sres.points}
    payload = {anahtar(p): p.payload for p in dres.points}
    for p in sres.points:
        payload.setdefault(anahtar(p), p.payload)

    # klasik-BM25 adayları (korpus text üzerine) — top-ADAY
    bm_skorlar = bm25.get_scores(_tokenize(sorgu))
    en_iyi = sorted(range(len(bm_skorlar)), key=lambda i: -bm_skorlar[i])[:ADAY_K]
    b_skor = {}
    for i in en_iyi:
        if bm_skorlar[i] <= 0:
            continue
        kn, mn, _mid = bm25_maddeler[i]
        b_skor[(kn, mn)] = float(bm_skorlar[i])
        payload.setdefault((kn, mn), {"kanun_no": kn, "madde_no": mn,
                                      "kanun_ad": "", "madde_id": _mid})

    # 3-bacak WSUM füzyon
    dn, sn, bn = _norm(d_skor), _norm(s_skor), _norm(b_skor)
    puan = {}
    for k in set(dn) | set(sn) | set(bn):
        puan[k] = (W_DENSE * dn.get(k, 0.0) + W_SPARSE * sn.get(k, 0.0)
                   + W_BM25 * bn.get(k, 0.0))

    sirali = sorted(puan.items(), key=lambda x: -x[1])[:top_k]
    return [type("P", (), {"score": sk, "payload": payload[k]})() for k, sk in sirali]


def yazdir(sorgu, points):
    print(f"\nSorgu: {sorgu}")
    print("-" * 70)
    for i, p in enumerate(points, 1):
        pl = p.payload
        baslik = (pl.get("kanun_ad") or "")[:40]
        print(f"{i:2}. [WSUM3 {p.score:.4f}] {pl.get('madde_id')} | {baslik} m.{pl.get('madde_no')}")


def main():
    client = QdrantClient(url=QDRANT_URL)
    if not client.collection_exists(COLLECTION):
        print(f"HATA: '{COLLECTION}' collection yok. Önce: python scripts/ingest_qdrant.py")
        return

    print("BM25 index kuruluyor (korpus text)...")
    bm25, bm25_maddeler = bm25_kur()
    print(f"  {len(bm25_maddeler)} yürürlükte madde indexlendi.")

    if len(sys.argv) > 1:
        sorgu = " ".join(sys.argv[1:])
        yazdir(sorgu, ara(client, bm25, bm25_maddeler, sorgu))
    else:
        print("3-bacak hybrid arama (çıkmak için boş Enter). Model ilk sorguda yüklenir (~60s)...")
        while True:
            try:
                sorgu = input("\nSorgu> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not sorgu:
                break
            yazdir(sorgu, ara(client, bm25, bm25_maddeler, sorgu))


if __name__ == "__main__":
    main()
