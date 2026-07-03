# -*- coding: utf-8 -*-
"""Hybrid arama — sorgu -> dense + sparse -> Qdrant RRF füzyon -> top-k.

Qdrant Query API + Fusion.RRF: dense ve sparse aramasını ayrı yapar,
Reciprocal Rank Fusion ile birleştirir (native, elle RRF yazmaya gerek yok).

Yürürlük filtresi: yalnız 'yürürlükte' maddeler (mülga elenir) — MVP-kritik.

Çalıştır:
  .venv/Scripts/python.exe scripts/search_qdrant.py "kira artışı nasıl belirlenir"
  .venv/Scripts/python.exe scripts/search_qdrant.py         (interaktif mod)
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from qdrant_client import QdrantClient, models
from mevzuat_tool.retrieval.embed import embed_sorgu

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
TOP_K = 10
ADAY_K = 50   # her bacak (dense/sparse) bu kadar aday getirir
WSUM_A = 0.5  # füzyon ağırlığı: A*dense + (1-A)*sparse (ölçümde WSUM_050 en iyi: R@1 +0.038)


def _norm(skor):
    """min-max normalize (0-1). Dense/sparse skorları farklı ölçekte → toplamadan önce şart."""
    if not skor:
        return {}
    vals = list(skor.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in skor.items()}


def ara(client, sorgu, yururlukte_only=True, top_k=TOP_K):
    """Hybrid WSUM füzyon: dense+sparse ayrı çek → skor normalize → ağırlıklı topla → sırala.
    RRF yerine WSUM_050 (ölçüm: R@1 0.42→0.46, MRR +0.029, nDCG +0.024; R@50+ değişmez)."""
    dense, sparse = embed_sorgu(sorgu)
    sp_indices = [int(k) for k in sparse.keys()]
    sp_values = list(sparse.values())

    flt = None
    if yururlukte_only:
        flt = models.Filter(must=[models.FieldCondition(
            key="yurutluk", match=models.MatchValue(value="yürürlükte"))])

    # dense adayları (skorlarıyla)
    dres = client.query_points(collection_name=COLLECTION, query=dense, using="dense",
                               limit=ADAY_K, query_filter=flt, with_payload=True)
    # sparse adayları (skorlarıyla)
    sres = client.query_points(
        collection_name=COLLECTION,
        query=models.SparseVector(indices=sp_indices, values=sp_values),
        using="sparse", limit=ADAY_K, query_filter=flt, with_payload=True)

    # point_id -> (skor, payload) hafızası
    d_skor = {p.id: p.score for p in dres.points}
    s_skor = {p.id: p.score for p in sres.points}
    payload = {p.id: p.payload for p in dres.points}
    for p in sres.points:
        payload.setdefault(p.id, p.payload)

    # WSUM füzyon
    dn, sn = _norm(d_skor), _norm(s_skor)
    puan = {}
    for pid in set(dn) | set(sn):
        puan[pid] = WSUM_A * dn.get(pid, 0.0) + (1 - WSUM_A) * sn.get(pid, 0.0)

    sirali = sorted(puan.items(), key=lambda x: -x[1])[:top_k]
    # Qdrant point nesnesi taklidi yerine basit sonuç: (score, payload)
    return [type("P", (), {"score": sk, "payload": payload[pid]})() for pid, sk in sirali]


def yazdir(sorgu, points):
    print(f"\nSorgu: {sorgu}")
    print("-" * 70)
    for i, p in enumerate(points, 1):
        pl = p.payload
        baslik = (pl.get("kanun_ad") or "")[:40]
        print(f"{i:2}. [WSUM {p.score:.4f}] {pl['madde_id']} | {baslik} m.{pl.get('madde_no')}")


def main():
    client = QdrantClient(url=QDRANT_URL)
    if not client.collection_exists(COLLECTION):
        print(f"HATA: '{COLLECTION}' collection yok. Önce: python scripts/ingest_qdrant.py")
        return

    if len(sys.argv) > 1:
        sorgu = " ".join(sys.argv[1:])
        yazdir(sorgu, ara(client, sorgu))
    else:
        print("Hybrid arama (çıkmak için boş Enter). Model ilk sorguda yüklenir (~60s)...")
        while True:
            try:
                sorgu = input("\nSorgu> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not sorgu:
                break
            yazdir(sorgu, ara(client, sorgu))


if __name__ == "__main__":
    main()
