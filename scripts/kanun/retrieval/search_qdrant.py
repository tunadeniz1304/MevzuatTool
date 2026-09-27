# -*- coding: utf-8 -*-
"""Hybrid arama CLI — sorgu -> dense + BGE-sparse + klasik-BM25 -> 3-bacak WSUM füzyon -> top-k.

Arama mantığı artık kütüphanede: `src/kanun/retrieval/search.py` (`HybridArama`). Bu script
yalnız CLI kabuğudur; ayarlar `src/kanun/retrieval/config.py` ortam değişkenlerinden gelir
(QDRANT_URL, MEVZUAT_COLLECTION, EMBED_BACKEND, RERANK_BACKEND, ...). Varsayılan: torch embed,
reranker kapalı — bugünkü sistem.

3 bacak (ölçümle seçilen ağırlık EŞİT, ÖLÇÜM 5):
  - dense       : BGE-M3 anlam (embedding), ağırlık 0.33
  - BGE-sparse  : BGE-M3 öğrenilmiş sparse (eş-anlam), ağırlık 0.33
  - klasik-BM25 : rank_bm25 korpus 'text' üzerine (nadir-terim keskin), ağırlık 0.34

Füzyon = min-max normalize skorların ağırlıklı toplamı (RRF/iki-bacak değil).
Ölçüm yolculuğu: RRF 0.667 -> WSUM_050 0.685 -> 3-bacak EŞİT 0.700 (R@10), R@1 0.49.
Yürürlük filtresi: yalnız 'yürürlükte' maddeler (mülga elenir) — MVP-kritik.

Çalıştır:
  .venv/Scripts/python.exe scripts/kanun/retrieval/search_qdrant.py "kira artışı nasıl belirlenir"
  .venv/Scripts/python.exe scripts/kanun/retrieval/search_qdrant.py         (interaktif mod)
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from qdrant_client import QdrantClient
from kanun.retrieval.config import ayarlar_oku
from kanun.retrieval.fabrika import arama_kur
from kanun.retrieval.search import bm25_kur


def yazdir(sorgu, sonuclar):
    print(f"\nSorgu: {sorgu}")
    print("-" * 70)
    etiket = "RERANK" if sonuclar.rerank else "WSUM3"
    for i, s in enumerate(sonuclar, 1):
        skor = s.rerank_skor if s.rerank_skor is not None else s.skor
        print(f"{i:2}. [{etiket} {skor:.4f}] {s.madde_id} | {s.kanun_ad[:40]} m.{s.madde_no}")


def main():
    ayar = ayarlar_oku()
    client = QdrantClient(url=ayar.qdrant_url)
    if not client.collection_exists(ayar.collection):
        print(f"HATA: '{ayar.collection}' collection yok. Önce: "
              f"python scripts/kanun/retrieval/ingest_qdrant.py")
        return

    print("BM25 index kuruluyor (korpus text)...")
    bm25 = bm25_kur(ayar.korpus_yol)
    print(f"  {len(bm25)} yürürlükte madde indexlendi.")
    arama = arama_kur(ayar, client=client, bm25=bm25)

    if len(sys.argv) > 1:
        sorgu = " ".join(sys.argv[1:])
        yazdir(sorgu, arama.ara(sorgu))
    else:
        print("3-bacak hybrid arama (çıkmak için boş Enter). Model ilk sorguda yüklenir (~60s)...")
        while True:
            try:
                sorgu = input("\nSorgu> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not sorgu:
                break
            yazdir(sorgu, arama.ara(sorgu))


if __name__ == "__main__":
    main()
