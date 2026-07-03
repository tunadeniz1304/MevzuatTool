# -*- coding: utf-8 -*-
"""Colab'da üretilmiş korpus vektörlerini Qdrant'a yükle (hybrid: dense + sparse).

Girdi (colab/outputs/):
  - dense.npy   : (N, 1024) float
  - sparse.json : N adet {token-id: ağırlık}
  - meta.json   : {ids: [...], payloadlar: [{kanun_no, kanun_ad, madde_no, yurutluk}]}

Çıktı: Qdrant'ta 'mevzuat' collection'ı, N point (her madde: dense+sparse+payload).

Qdrant çalışıyor olmalı: docker run -p 6333:6333 qdrant/qdrant
Çalıştır: .venv/Scripts/python.exe scripts/ingest_qdrant.py
"""
import json
import numpy as np
from qdrant_client import QdrantClient, models

QDRANT_URL = "http://localhost:6333"
COLLECTION = "mevzuat"
DENSE_YOL = "colab/outputs/dense.npy"
SPARSE_YOL = "colab/outputs/sparse.json"
META_YOL = "colab/outputs/meta.json"
BATCH = 256


def main():
    # 1) Veriyi yükle
    print("Vektörler yükleniyor...")
    dense = np.load(DENSE_YOL).astype(np.float32)   # fp16 -> fp32 (Qdrant fp32 ister)
    with open(SPARSE_YOL, encoding="utf-8") as f:
        sparse = json.load(f)
    with open(META_YOL, encoding="utf-8") as f:
        meta = json.load(f)
    ids, payloadlar = meta["ids"], meta["payloadlar"]
    N, DIM = dense.shape
    assert N == len(sparse) == len(ids) == len(payloadlar), "HİZASIZ veri!"
    print(f"  {N} madde, dense boyut {DIM}")

    # 2) Qdrant'a bağlan + collection oluştur
    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(COLLECTION):
        print(f"  '{COLLECTION}' zaten var — siliniyor (temiz başlangıç)")
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        # dense vektör: cosine (BGE-M3 normalize → cosine=dot)
        vectors_config={
            "dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE),
        },
        # sparse vektör: BM25-benzeri (dot product)
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(),
        },
    )
    print(f"  '{COLLECTION}' collection oluşturuldu (dense + sparse)")

    # 3) Point'leri batch'ler halinde yükle
    print("Point'ler yükleniyor...")
    for bas in range(0, N, BATCH):
        son = min(bas + BATCH, N)
        points = []
        for i in range(bas, son):
            # sparse dict -> Qdrant SparseVector (indices + values)
            sp = sparse[i]
            indices = [int(k) for k in sp.keys()]
            values = list(sp.values())
            points.append(
                models.PointStruct(
                    id=i,   # Qdrant point id (0..N-1); gerçek madde id payload'da
                    vector={
                        "dense": dense[i].tolist(),
                        "sparse": models.SparseVector(indices=indices, values=values),
                    },
                    payload={
                        "madde_id": ids[i],           # "103907-9"
                        **payloadlar[i],              # kanun_no, kanun_ad, madde_no, yurutluk
                    },
                )
            )
        client.upsert(collection_name=COLLECTION, points=points)
        print(f"  {son}/{N}", end="\r")

    print(f"\n✓ {N} point yüklendi -> Qdrant '{COLLECTION}'")
    # Doğrulama
    say = client.count(COLLECTION).count
    print(f"  Qdrant'ta toplam point: {say}")


if __name__ == "__main__":
    main()
