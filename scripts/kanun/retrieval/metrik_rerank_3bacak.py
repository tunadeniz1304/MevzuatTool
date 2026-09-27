# -*- coding: utf-8 -*-
"""Reranker ölçümü — 3-bacak WSUM aday havuzu üzerinde (ADR-0015) + eski 2-bacak RRF çapası.

İki aşama (rerank_hazirla.py deseni): adaylar BİR KEZ çıkarılır, reranker ayrı aşamada puanlar.
Bir çiftin (sorgu, madde) cross-encoder skoru diğer adaylardan bağımsızdır → top-50 bir kez
puanlanınca RERANK_ADAY ∈ {10,20,30,50} sonuçları aynı skorlardan türetilir (ek model maliyeti yok).

Modlar:
  --capa [--backend torch]           colab/rerank_input.jsonl (2-bacak RRF top-50, metin 1500 krk)
                                     üzerinde ADR-0009 ölçümünü yeniden üret (hedef R@10 0.7060 ± 0.005).
  --aday-cikar [--embed E] [--n N]  3-bacak WSUM top-50 → data/kanun/olcum/rerank_aday_3bacak[_<E>].jsonl
                                     E (sorgu embed backend): torch (vars.) | onnx-fp32 | onnx-int8
  --skorla --max-len L [--backend B] [--embed E] [--aday A] [--n N]
                                     adayların ilk A'sını puanla → rerank_skor_[<E>__]<B>_<L>.jsonl
                                     (kaldığı yerden devam eder). B: torch | onnx-fp32 | onnx-int8
  --rapor                            tüm aday/skor dosyalarından embed × reranker × ADAY × max_len tablosu

GPU (4 GB) yalnız bu çevrimdışı FP32 kalite ölçümünde kullanılır (V-4): --cihaz auto.
Metrikler olcum.py (MRR@10 — metrik_bm25 tanımı). Çapa modu orijinal metrik_rerank tanımını
(MRR tüm 50 aday üzerinden) da yazdırır.

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_rerank_3bacak.py --rapor
"""
import os
import sys
import glob
import json
import time
import math
import pathlib
import argparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "src"))

from kanun.retrieval.config import ayarlar_oku
from kanun.retrieval.olcum import gold_sorgular, metrikler, rerank_uygula, sira

OLCUM = "data/kanun/olcum"


def aday_dosya(embed):
    return f"{OLCUM}/rerank_aday_3bacak.jsonl" if embed == "torch" else f"{OLCUM}/rerank_aday_3bacak_{embed}.jsonl"


def skor_dosya(embed, backend, max_len):
    on = "" if embed == "torch" else f"{embed}__"
    return f"{OLCUM}/rerank_skor_{on}{backend}_{max_len}.jsonl"

CAPA_DOSYA = "colab/rerank_input.jsonl"
ADAYLAR = (10, 20, 30, 50)
CIFT_BATCH = 256   # bu kadar çift biriktir → uzunluğa göre sırala → reranker batch'leri


def _reranker(backend, max_len, cihaz):
    ayar = ayarlar_oku()
    if backend == "torch":
        from kanun.retrieval.rerank import TorchReranker
        return TorchReranker(max_length=max_len, cihaz=cihaz)
    from kanun.retrieval.rerank import OnnxReranker
    dosya = "model.int8.onnx" if backend.endswith("int8") else "model.onnx"
    return OnnxReranker(os.path.join(ayar.model_dir, "bge-reranker-v2-m3", dosya),
                        max_length=max_len, threads=ayar.ort_threads)


def _puanla_toplu(rr, satirlar, metin_fn, aday):
    """Birden çok sorgunun çiftlerini tek listede puanla → sorgu başına skor listesi."""
    ciftler, sinir = [], []
    for s in satirlar:
        adaylar = s["adaylar"][:aday]
        sinir.append(len(adaylar))
        ciftler += [[s["sorgu"], metin_fn(a)] for a in adaylar]
    skor = rr.skorla_ciftler(ciftler)
    cikti, i = [], 0
    for n in sinir:
        cikti.append(skor[i:i + n])
        i += n
    return cikti


# ---- çapa: ADR-0009 ölçümünü aynı girdiyle yeniden üret -------------------
def capa(args):
    satirlar = [json.loads(l) for l in open(CAPA_DOSYA, encoding="utf-8")][: args.n]
    rr = _reranker(args.backend, 512, args.cihaz)
    h_sira, r_sira, h50, r50 = [], [], [], []
    t0 = time.time()
    for bas in range(0, len(satirlar), 8):
        grup = satirlar[bas: bas + 8]
        for s in grup:
            s["adaylar"] = [dict(a, key=(a["kn"], a["mn"])) for a in s["adaylar"]]
        skorlar = _puanla_toplu(rr, grup, lambda a: a["text"], 50)
        for s, sk in zip(grup, skorlar):
            hedef = tuple(s["dogru"])
            keys = [a["key"] for a in s["adaylar"]]
            yeni = rerank_uygula(keys, sk, 50)
            h_sira.append(sira(keys, hedef)); r_sira.append(sira(yeni, hedef))
            h50.append(sira(keys, hedef, 50)); r50.append(sira(yeni, hedef, 50))
        print(f"  {len(h_sira)}/{len(satirlar)}  ({time.time() - t0:.0f} sn)", end="\r", flush=True)
    h, r = metrikler(h_sira), metrikler(r_sira)
    print(f"\nÇAPA — 2-bacak RRF top-50 + {args.backend} reranker, {h['N']} sorgu")
    print(f"{'Metrik':<10}{'Hybrid':>10}{'+Rerank':>10}{'Fark':>10}")
    for k in ("R@1", "R@5", "R@10", "MRR", "nDCG@10"):
        print(f"{k:<10}{h[k]:>10.4f}{r[k]:>10.4f}{r[k] - h[k]:>+10.4f}")
    mrr50 = lambda rl: sum(1.0 / x for x in rl if x > 0) / len(rl)   # metrik_rerank.py tanımı
    print(f"{'MRR(50)':<10}{mrr50(h50):>10.4f}{mrr50(r50):>10.4f}{mrr50(r50) - mrr50(h50):>+10.4f}")
    json.dump({"hybrid": h, "rerank": r, "mrr50": [mrr50(h50), mrr50(r50)], "backend": args.backend},
              open(f"{OLCUM}/rerank_capa_{args.backend}.json", "w", encoding="utf-8"), indent=1)


# ---- 3-bacak adaylarını çıkar --------------------------------------------
def aday_cikar(args):
    import dataclasses
    from kanun.retrieval.fabrika import arama_kur
    ayar = dataclasses.replace(ayarlar_oku(), embed_backend=args.embed)
    arama = arama_kur(ayar, reranker=None)
    hedef_dosya = aday_dosya(args.embed)
    sorgular = gold_sorgular(args.n, ayar.korpus_yol)
    os.makedirs(OLCUM, exist_ok=True)
    t0 = time.time()
    with open(hedef_dosya, "w", encoding="utf-8") as out:
        for i, (sorgu, hedef) in enumerate(sorgular, 1):
            sirali, _, _ = arama.adaylar(sorgu)
            out.write(json.dumps({"sorgu": sorgu, "dogru": list(hedef),
                                  "adaylar": [list(k) for k, _ in sirali[:50]]},
                                 ensure_ascii=False) + "\n")
            if i % 50 == 0:
                print(f"  {i}/{len(sorgular)}  ({time.time() - t0:.0f} sn)", end="\r", flush=True)
    print(f"\n✓ {len(sorgular)} sorgu → {hedef_dosya}")


# ---- adayları puanla ------------------------------------------------------
def skorla(args):
    from kanun.retrieval.search import bm25_kur
    ayar = ayarlar_oku()
    idx = bm25_kur(ayar.korpus_yol)   # yalnız metin haritası için
    krk = ayar.rerank_max_krk

    def metin(a):
        return (idx.metinler.get(tuple(a)) or "")[:krk]

    satirlar = [json.loads(l) for l in open(aday_dosya(args.embed), encoding="utf-8")][: args.n]
    cikti = skor_dosya(args.embed, args.backend, args.max_len)
    yapilan = sum(1 for _ in open(cikti, encoding="utf-8")) if os.path.exists(cikti) else 0
    print(f"{cikti}: {yapilan}/{len(satirlar)} hazır, devam ediliyor (aday={args.aday})")
    rr = _reranker(args.backend, args.max_len, args.cihaz)
    t0 = time.time()
    with open(cikti, "a", encoding="utf-8") as out:
        for bas in range(yapilan, len(satirlar), max(1, CIFT_BATCH // args.aday)):
            grup = satirlar[bas: bas + max(1, CIFT_BATCH // args.aday)]
            for sk in _puanla_toplu(rr, grup, metin, args.aday):
                out.write(json.dumps(sk) + "\n")
            out.flush()
            biten = bas + len(grup)
            hiz = (biten - yapilan) / max(1e-9, time.time() - t0)
            print(f"  {biten}/{len(satirlar)}  {hiz:.2f} sorgu/sn  "
                  f"kalan ~{(len(satirlar) - biten) / max(hiz, 1e-9) / 60:.0f} dk", end="\r", flush=True)
    print(f"\n✓ {cikti}")


# ---- rapor ---------------------------------------------------------------
def _siralar(satirlar):
    return [sira([tuple(a) for a in s["adaylar"]], tuple(s["dogru"])) for s in satirlar]


def rapor(args):
    print("| Embed | Reranker | ADAY | max_len | N | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 | ΔR@10 | ΔMRR | ΔR@1 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    kayit = []

    def yaz(embed, rr, aday, max_len, m, t):
        print(f"| {embed} | {rr} | {aday} | {max_len} | {m['N']} | {m['R@1']:.4f} | {m['R@5']:.4f} "
              f"| {m['R@10']:.4f} | {m['MRR']:.4f} | {m['nDCG@10']:.4f} | {m['R@10'] - t['R@10']:+.4f} "
              f"| {m['MRR'] - t['MRR']:+.4f} | {m['R@1'] - t['R@1']:+.4f} |")
        kayit.append(dict(m, embed=embed, rerank=rr, aday=aday, max_len=max_len,
                          taban_R10=t["R@10"], taban_MRR=t["MRR"], taban_R1=t["R@1"]))

    for embed in ("torch", "onnx-fp32", "onnx-int8"):
        if not os.path.exists(aday_dosya(embed)):
            continue
        satirlar = [json.loads(l) for l in open(aday_dosya(embed), encoding="utf-8")]
        taban = metrikler(_siralar(satirlar))
        yaz(embed, "kapali", "-", "-", taban, taban)
        on = "" if embed == "torch" else f"{embed}__"
        for dosya in sorted(glob.glob(f"{OLCUM}/rerank_skor_{on}*.jsonl")):
            ad = os.path.basename(dosya)[len(f"rerank_skor_{on}"):-len(".jsonl")]
            if "__" in ad:
                continue          # başka bir embed'in skor dosyası
            backend, max_len = ad.rsplit("_", 1)
            skorlar = [json.loads(l) for l in open(dosya, encoding="utf-8")]
            n = len(skorlar)
            t_n = metrikler(_siralar(satirlar[:n]))   # eşleştirilmiş kıyas: aynı n sorgu
            for aday in ADAYLAR:
                if any(len(sk) < min(aday, len(s["adaylar"])) for sk, s in zip(skorlar, satirlar)):
                    continue      # bu dosya o kadar aday puanlamamış
                m = metrikler([sira(rerank_uygula([tuple(a) for a in s["adaylar"]], sk, aday),
                                    tuple(s["dogru"])) for s, sk in zip(satirlar, skorlar)])
                yaz(embed, backend, aday, int(max_len), m, t_n)
    json.dump(kayit, open(f"{OLCUM}/rerank_3bacak_rapor.json", "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capa", action="store_true")
    p.add_argument("--aday-cikar", action="store_true")
    p.add_argument("--skorla", action="store_true")
    p.add_argument("--rapor", action="store_true")
    p.add_argument("--backend", default="torch")
    p.add_argument("--embed", default="torch")
    p.add_argument("--max-len", type=int, default=512)
    p.add_argument("--aday", type=int, default=50)
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--cihaz", default="auto")
    args = p.parse_args()
    os.makedirs(OLCUM, exist_ok=True)
    if args.capa:
        capa(args)
    if args.aday_cikar:
        aday_cikar(args)
    if args.skorla:
        skorla(args)
    if args.rapor:
        rapor(args)


if __name__ == "__main__":
    main()
