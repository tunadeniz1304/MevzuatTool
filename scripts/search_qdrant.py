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
ADAY_K = 50   # her bacak (dense/sparse) bu kadar aday getirir, RRF birleştirir


def ara(client, sorgu, yururlukte_only=True, top_k=TOP_K):
    dense, sparse = embed_sorgu(sorgu)
    sp_indices = [int(k) for k in sparse.keys()]
    sp_values = list(sparse.values())

    # yürürlük filtresi (payload)
    flt = None
    if yururlukte_only:
        flt = models.Filter(
            must=[models.FieldCondition(
                key="yurutluk",
                match=models.MatchValue(value="yürürlükte"),
            )]
        )

    # Hybrid: iki prefetch (dense + sparse) -> RRF füzyon
    sonuc = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(
                query=dense,
                using="dense",
                limit=ADAY_K,
                filter=flt,
            ),
            models.Prefetch(
                query=models.SparseVector(indices=sp_indices, values=sp_values),
                using="sparse",
                limit=ADAY_K,
                filter=flt,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return sonuc.points


def yazdir(sorgu, points):
    print(f"\nSorgu: {sorgu}")
    print("-" * 70)
    for i, p in enumerate(points, 1):
        pl = p.payload
        baslik = (pl.get("kanun_ad") or "")[:40]
        print(f"{i:2}. [RRF {p.score:.4f}] {pl['madde_id']} | {baslik} m.{pl.get('madde_no')}")


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
