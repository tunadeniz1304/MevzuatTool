# -*- coding: utf-8 -*-
"""Retrieval ölçümü — ölçüm seti v2 ile servis ayarını (config.Ayarlar) bacak bacak değerlendir (ADR-0022).

Set v2: data/gold/retrieval_v2/set.jsonl (442 soru; ilgi, kanun_no, madde_no, mevzuat_id, stil, kaynak).
Sorgu vektörleri önceden hesaplanmış (Colab, BGE-M3 fp16): colab/outputs/sorgu_{dense.npy,sparse.json,meta.json}
→ yerelde model gerekmez. Qdrant 'mevzuat' collection'ı ayakta olmalı (docker compose up -d qdrant).

Eşleşme (mevzuat_id, madde_no) — kanun_no çakışmalarından bağımsız. Bacaklar (dense / BGE-sparse / BM25) ayrı
ayrı ve 3-bacak WSUM (config ağırlıkları; W_DENSE/W_SPARSE/W_BM25 ile ezilebilir) ölçülür; kırılım: stil
(vatandas/hukukcu), kaynak (yaygin/populer). Metrikler olcum.metrikler (sıra 1-tabanlı, 0 = ilk 10'da yok).

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_v2.py
"""
import collections
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from qdrant_client import QdrantClient  # noqa: E402
from kanun.retrieval.config import ayarlar_oku  # noqa: E402
from kanun.retrieval.olcum import metrikler  # noqa: E402
from kanun.retrieval.search import HybridArama, bm25_kur, tokenize  # noqa: E402

SET = ROOT / "data" / "gold" / "retrieval_v2" / "set.jsonl"
VEK = ROOT / "colab" / "outputs"


def vektorler():
    meta = json.loads((VEK / "sorgu_meta.json").read_text(encoding="utf-8"))
    dense = np.load(VEK / "sorgu_dense.npy").astype(np.float32)
    sparse = json.loads((VEK / "sorgu_sparse.json").read_text(encoding="utf-8"))
    return {s: (dense[i].tolist(), sparse[i]) for i, s in enumerate(meta["sorgular"])}


def anahtar(madde_id, madde_no):
    return (str(madde_id).split("-")[0], str(madde_no))


def main():
    ayar = ayarlar_oku()
    kayitlar = [json.loads(l) for l in SET.open(encoding="utf-8")]
    vek = vektorler()
    eksik = [k["ilgi"] for k in kayitlar if k["ilgi"] not in vek]
    assert not eksik, f"{len(eksik)} sorgunun vektörü yok"
    bm25 = bm25_kur(str(ROOT / ayar.korpus_yol))
    client = QdrantClient(url=ayar.qdrant_url)
    arama = HybridArama(lambda s: vek[s], client, bm25, collection=ayar.collection, aday_k=ayar.aday_k,
                        agirliklar=ayar.agirliklar)
    flt = arama._filtre(True)
    print(f"ayar: agirliklar={ayar.agirliklar} aday_k={ayar.aday_k} | {len(kayitlar)} soru")

    siralar = collections.defaultdict(list)
    for k in kayitlar:
        hedef = (k["mevzuat_id"], k["madde_no"])
        sirali, payload, _ = arama.adaylar(k["ilgi"])
        d, s = vek[k["ilgi"]]
        dres = client.query_points(ayar.collection, query=d, using="dense", limit=10, query_filter=flt,
                                   with_payload=True).points
        sres = client.query_points(ayar.collection, query=arama._sparse_vektor(s), using="sparse", limit=10,
                                   query_filter=flt, with_payload=True).points
        bms = np.asarray(bm25.bm25.get_scores(tokenize(k["ilgi"])))
        bm_ilk = [i for i in np.argsort(-bms, kind="stable")[:10] if bms[i] > 0]
        bacak = {
            "dense": [anahtar(p.payload["madde_id"], p.payload.get("madde_no")) for p in dres],
            "sparse": [anahtar(p.payload["madde_id"], p.payload.get("madde_no")) for p in sres],
            "bm25": [anahtar(bm25.maddeler[i][2], bm25.payload(i).get("madde_no")) for i in bm_ilk],
            "hybrid": [anahtar(m, payload.get(m, {}).get("madde_no")) for m, _ in sirali[:10]],
        }
        for sis, liste in bacak.items():
            r = next((i for i, a in enumerate(liste, 1) if a == hedef), 0)
            for kir in ("hepsi", "stil:" + k["stil"], "kaynak:" + k["kaynak"]):
                siralar[(sis, kir)].append(r)
    print(f"{'sistem':8s} {'kırılım':16s} {'N':>4s} {'R@1':>6s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s} {'nDCG':>6s}")
    for (sis, kir), sr in sorted(siralar.items(), key=lambda x: (x[0][1] != "hepsi", x[0][1], x[0][0])):
        m = metrikler(sr)
        print(f"{sis:8s} {kir:16s} {m['N']:4d} {m['R@1']:6.3f} {m['R@5']:6.3f} {m['R@10']:6.3f} {m['MRR']:6.3f} {m['nDCG@10']:6.3f}")


if __name__ == "__main__":
    main()
