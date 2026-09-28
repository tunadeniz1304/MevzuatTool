# -*- coding: utf-8 -*-
"""Gecikme × kalite tablosu — FP32 vs int8, reranker açık/kapalı, CPU (ADR-0015/0016, F4).

TEK script, SABİT protokol, TEK tablo — genel bir benchmark çerçevesi değil (compliance B, V-5).

Satırlar (her biri AYRI süreçte → bellek ve ısınma izolasyonu):
  A  torch FP32 embed      | reranker kapalı              (bugünkü sistem)
  B  ONNX FP32 embed       | kapalı                       (ORT'nin quantization'sız katkısı)
  C  ONNX int8 embed       | kapalı
  D  torch FP32 embed      | torch FP32 reranker (önerilen ADAY/max_len)
  E  ONNX int8 embed       | ONNX int8 reranker  (önerilen ADAY/max_len)
  F  ONNX int8 embed       | ONNX int8 reranker  (ADAY=50, max_len=512 — "tam" maliyet)
  E-http / C-http          | E'nin / C'nin FastAPI servisi üzerinden ölçümü (servis ek yükü = X-http − X).
                             Servis varsayılanı reranker KAPALI olduğundan (ADR-0015) asıl HTTP satırı C-http.

Protokol: gold SEED 4721 ilk N=200 uygun sorgu; 10 ısınma sorgusu (N'den sonraki 10) ölçüm dışı;
sıralı tek istek; torch.set_num_threads(4), ORT_THREADS=4 (fiziksel çekirdek); model yükleme ve
BM25 kurulumu ölçüm dışı; Qdrant yerel Docker. p50/p95/p99 = numpy.percentile (N=200'de p99 ≈ en
yavaş 2 sorgu → düşük güvenilirlik). Tepe bellek = süreç peak working set (psutil).
Kalite sütunları (2000 sorgu) data/kanun/olcum/rerank_3bacak_rapor.json'dan (metrik_rerank_3bacak.py --rapor).

Çalıştır:
  .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_gecikme.py --satir C --n 20      (duman testi)
  .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_gecikme.py --satir hepsi         (A–F, ayrı süreçler)
  .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_gecikme.py --satir E-http --url http://127.0.0.1:8000
  .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_gecikme.py --tablo               (JSON + markdown)
"""
import os
import sys
import json
import time
import pathlib
import argparse
import datetime
import platform
import subprocess
import dataclasses

KOK = pathlib.Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(KOK / "src"))

import numpy as np

from kanun.retrieval.config import ayarlar_oku
from kanun.retrieval.olcum import gold_sorgular, metrikler, sira

OLCUM = "data/kanun/olcum"
RAPOR = f"{OLCUM}/rerank_3bacak_rapor.json"
SONUC_DIR = "docs/olcum-sonuclari"
ISINMA = 10
ASAMALAR = ("embed", "dense", "sparse", "bm25", "fuzyon", "rerank", "toplam")


def satirlar(onerilen_aday, onerilen_len):
    return {
        "A": dict(embed="torch", rerank="kapali", aday=None, max_len=None, not_="bugünkü sistem"),
        "B": dict(embed="onnx-fp32", rerank="kapali", aday=None, max_len=None,
                  not_="ORT'nin quantization'sız katkısı"),
        "C": dict(embed="onnx-int8", rerank="kapali", aday=None, max_len=None, not_=""),
        "D": dict(embed="torch", rerank="torch", aday=onerilen_aday, max_len=onerilen_len,
                  not_="önerilen ADAY/max_len"),
        "E": dict(embed="onnx-int8", rerank="onnx-int8", aday=onerilen_aday, max_len=onerilen_len,
                  not_="önerilen ADAY/max_len"),
        "F": dict(embed="onnx-int8", rerank="onnx-int8", aday=50, max_len=512, not_="tam reranker maliyeti"),
        "E-http": dict(embed="onnx-int8", rerank="onnx-int8", aday=onerilen_aday, max_len=onerilen_len,
                       not_="E, FastAPI üzerinden (istemci tarafı duvar saati)"),
        "C-http": dict(embed="onnx-int8", rerank="kapali", aday=None, max_len=None,
                       not_="C, FastAPI üzerinden — servis varsayılanı (istemci tarafı duvar saati)"),
    }


def _yuzdelik(degerler):
    a = np.asarray(degerler, dtype=float)
    return {"p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99)), "ort": float(a.mean()), "max": float(a.max())}


def _dosya_boyut_mb(yol):
    if not yol:
        return None
    return round(sum(os.path.getsize(p) for p in (yol, yol + ".data") if os.path.exists(p)) / 1e6, 1)


def _model_yollari(ayar, cfg):
    def yol(klasor, backend):
        if backend in ("torch", "kapali"):
            return None
        return os.path.join(ayar.model_dir, klasor, "model.int8.onnx" if backend.endswith("int8") else "model.onnx")
    return yol("bge-m3", cfg["embed"]), yol("bge-reranker-v2-m3", cfg["rerank"])


def _tepe_rss_mb():
    import psutil
    mi = psutil.Process().memory_info()
    return round(getattr(mi, "peak_wset", mi.rss) / 1e6, 1)


# ---- çocuk süreç: tek satırı ölç -----------------------------------------
def cocuk(args, cfg):
    if "torch" in (cfg["embed"], cfg["rerank"]) and not args.satir.endswith("http"):
        import torch
        torch.set_num_threads(4)
    from kanun.retrieval.fabrika import arama_kur

    ayar = ayarlar_oku()
    ayar = dataclasses.replace(ayar, embed_backend=cfg["embed"], rerank_backend=cfg["rerank"],
                               rerank_aday=cfg["aday"] or ayar.rerank_aday,
                               rerank_max_len=cfg["max_len"] or ayar.rerank_max_len, ort_threads=4)
    acik = cfg["rerank"] != "kapali"
    sorgular = gold_sorgular(args.n + ISINMA, ayar.korpus_yol)
    olculen, isinma = sorgular[: args.n], sorgular[args.n:]

    t0 = time.perf_counter()
    http = args.satir.endswith("http")
    if http:
        import httpx
        istemci = httpx.Client(base_url=args.url, timeout=120)
        saglik = istemci.get("/saglik").json()
        print(f"  servis: {saglik}")

        def ara(sorgu):
            t = time.perf_counter()
            r = istemci.post("/ara", json={"sorgu": sorgu, "top_k": 10, "rerank": acik})
            r.raise_for_status()
            j = r.json()
            sure = dict(j["sure_ms"])
            sure["sunucu_toplam"] = sure.get("toplam", 0.0)
            sure["toplam"] = (time.perf_counter() - t) * 1000.0
            return [(s["kanun_no"], s["madde_no"]) for s in j["sonuclar"]], sure
    else:
        arama = arama_kur(ayar)

        def ara(sorgu):
            s = arama.ara(sorgu, top_k=10, rerank=acik)
            return [x.anahtar for x in s], s.sure_ms
    yukleme_sn = time.perf_counter() - t0

    for sorgu, _ in isinma:
        ara(sorgu)
    sureler = {k: [] for k in ASAMALAR}
    sureler["sunucu_toplam"] = []
    siralar, listeler = [], []
    t_olcum = time.perf_counter()
    for i, (sorgu, hedef) in enumerate(olculen, 1):
        liste, sure = ara(sorgu)
        for k in sureler:
            if k in sure:
                sureler[k].append(sure[k])
        siralar.append(sira(liste, hedef))
        listeler.append(liste)
        if i % 20 == 0:
            print(f"  {args.satir}: {i}/{len(olculen)}", end="\r", flush=True)
    olcum_sn = time.perf_counter() - t_olcum

    esdeger = None
    if http and args.esdeger:
        # servis == in-process: aynı config ile yerel HybridArama, aynı sorgular, top-10 birebir
        arama = arama_kur(ayar)
        ayni = sum(1 for (sorgu, _), l in zip(olculen, listeler)
                   if [x.anahtar for x in arama.ara(sorgu, top_k=10, rerank=acik)] == [tuple(a) for a in l])
        esdeger = f"{ayni}/{len(olculen)}"
        print(f"\n  HTTP == in-process: {esdeger}")

    emb_yol, rr_yol = _model_yollari(ayar, cfg)
    sonuc = {
        "satir": args.satir, **{k: v for k, v in cfg.items() if k != "not_"}, "not": cfg["not_"],
        "n": len(olculen), "isinma": ISINMA, "yukleme_sn": round(yukleme_sn, 1),
        "olcum_sn": round(olcum_sn, 1),
        "sure_ms": {k: _yuzdelik(v) for k, v in sureler.items() if v},
        "kalite_n": metrikler(siralar), "tepe_rss_mb": _tepe_rss_mb(),
        "model_mb": {"embed": _dosya_boyut_mb(emb_yol), "rerank": _dosya_boyut_mb(rr_yol)},
        "http_esdeger": esdeger,
    }
    os.makedirs(OLCUM, exist_ok=True)
    with open(f"{OLCUM}/gecikme_{args.satir}.json", "w", encoding="utf-8") as f:
        json.dump(sonuc, f, indent=1, ensure_ascii=False)
    s = sonuc["sure_ms"]["toplam"]
    print(f"\n  {args.satir}: p50 {s['p50']:.0f} / p95 {s['p95']:.0f} / p99 {s['p99']:.0f} ms  "
          f"(N={len(olculen)}, {olcum_sn:.0f} sn, RSS {sonuc['tepe_rss_mb']} MB)")


# ---- ortam + tablo -------------------------------------------------------
def ortam():
    import psutil
    bilgi = {"os": platform.platform(), "python": platform.python_version(),
             "cpu": platform.processor(), "cekirdek": psutil.cpu_count(logical=False),
             "thread": psutil.cpu_count(logical=True),
             "ram_gb": round(psutil.virtual_memory().total / 2**30, 1), "qdrant": None}
    try:
        out = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True, timeout=10)
        ad = [l.strip() for l in out.stdout.splitlines() if l.strip() and l.strip() != "Name"]
        if ad:
            bilgi["cpu"] = ad[0]
    except Exception:
        pass
    for paket in ("torch", "onnxruntime", "transformers", "qdrant_client", "numpy"):
        try:
            bilgi[paket] = __import__(paket).__version__
        except Exception as e:
            bilgi[paket] = f"yok ({type(e).__name__})"
    try:
        import onnxruntime
        bilgi["ort_providers"] = onnxruntime.get_available_providers()
    except Exception:
        pass
    try:
        import httpx
        bilgi["qdrant"] = httpx.get(ayarlar_oku().qdrant_url, timeout=5).json().get("version")
    except Exception:
        pass
    return bilgi


def _kalite(cfg):
    if not os.path.exists(RAPOR):
        return None
    for k in json.load(open(RAPOR, encoding="utf-8")):
        if k["embed"] != cfg["embed"] or k["rerank"] != cfg["rerank"]:
            continue
        if cfg["rerank"] == "kapali" or (k["aday"] == cfg["aday"] and k["max_len"] == cfg["max_len"]):
            return k
    return None


def tablo(args):
    satir_cfg = satirlar(args.onerilen_aday, args.onerilen_len)
    sonuc = {"tarih": datetime.date.today().isoformat(), "ortam": ortam(), "protokol": {
        "n": args.n, "isinma": ISINMA, "seed": 4721, "threads": 4, "cihaz": "CPU",
        "aday_k": ayarlar_oku().aday_k, "kalite_kaynagi": RAPOR + " (2000 sorgu)"}, "satirlar": []}
    print("| # | Embed | Reranker | p50 | p95 | p99 | p95 embed | p95 rerank | R@1 | R@10 | MRR@10 "
          "| nDCG@10 | Tepe RSS (MB) | N | Not |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for ad, cfg in satir_cfg.items():
        yol = f"{OLCUM}/gecikme_{ad}.json"
        k = _kalite(cfg)
        rr = "kapalı" if cfg["rerank"] == "kapali" else f"{cfg['rerank']} ({cfg['aday']}/{cfg['max_len']})"
        if not os.path.exists(yol):
            print(f"| {ad} | {cfg['embed']} | {rr} | ölçülmedi | | | | | | | | | | | {cfg['not_']} |")
            continue
        g = json.load(open(yol, encoding="utf-8"))
        s = g["sure_ms"]
        f = lambda x: f"{x:.3f}" if isinstance(x, float) else "ölçülmedi"
        rer = s.get("rerank", {}).get("p95", 0.0)
        print(f"| {ad} | {cfg['embed']} | {rr} | {s['toplam']['p50']:.0f} | {s['toplam']['p95']:.0f} "
              f"| {s['toplam']['p99']:.0f} | {s.get('embed', {}).get('p95', float('nan')):.0f} "
              f"| {rer:.0f} | {f(k['R@1']) if k else 'ölçülmedi'} | {f(k['R@10']) if k else 'ölçülmedi'} "
              f"| {f(k['MRR']) if k else 'ölçülmedi'} | {f(k['nDCG@10']) if k else 'ölçülmedi'} "
              f"| {g['tepe_rss_mb']:.0f} | {g['n']} | {cfg['not_']} |")
        sonuc["satirlar"].append(dict(g, kalite_2000=k))
    os.makedirs(SONUC_DIR, exist_ok=True)
    yol = f"{SONUC_DIR}/gecikme-{sonuc['tarih']}.json"
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, indent=1, ensure_ascii=False)
    print(f"\n✓ {yol}")


def main():
    ayar = ayarlar_oku()
    p = argparse.ArgumentParser()
    p.add_argument("--satir", default=None, help="A|B|C|D|E|F|E-http|C-http|hepsi")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--onerilen-aday", type=int, default=ayar.rerank_aday)
    p.add_argument("--onerilen-len", type=int, default=ayar.rerank_max_len)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--esdeger", action="store_true", help="E-http: sonuçları in-process ile kıyasla")
    p.add_argument("--tablo", action="store_true")
    args = p.parse_args()
    cfgs = satirlar(args.onerilen_aday, args.onerilen_len)

    if args.satir == "hepsi":
        for ad in ("A", "B", "C", "D", "E", "F"):
            print(f"[{ad}] ayrı süreçte ölçülüyor...", flush=True)
            subprocess.run([sys.executable, __file__, "--satir", ad, "--n", str(args.n),
                            "--onerilen-aday", str(args.onerilen_aday),
                            "--onerilen-len", str(args.onerilen_len)], check=False)
    elif args.satir:
        cocuk(args, cfgs[args.satir])
    if args.tablo:
        tablo(args)


if __name__ == "__main__":
    main()
