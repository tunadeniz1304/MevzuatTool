# -*- coding: utf-8 -*-
"""BM25 sürümleri x WSUM ağırlıkları: tekrarlı grup çapraz doğrulaması + eşli bootstrap (ölçüm seti v2; ADR-0022).

BM25 sürümleri (tokenizer):
  eski         : str.lower() + regex — 'İ' -> 'i' + U+0307, kelime bölünür ("İş" -> "i", "ş") (ADR-0022 öncesi)
  duzeltilmis  : Türkçe küçük harf (search.tr_kucuk) + aynı regex
  duz+f5       : düzeltilmiş + ilk 5 harf (sayılar kesilmez) = bugünkü search.tokenize
  duz+f6       : düzeltilmiş + ilk 6 harf
Ağırlıklar: toplamı 1 olan (dense, sparse, bm25) üçlüleri, 0.05 adım (231) + eski eşit (0.33, 0.33, 0.34).
WSUM search.wsum_puan ile birebir: bacak başına min-max, olmayan aday 0, eşitlikte ilk görünme sırası.
Seçim: hedef maddeye göre gruplanmış 5 katlı CV, 20 tekrar; eğitimde en yüksek MRR@10 (eşitlikte R@10) seçilir,
testte ölçülür. Girdi: data/gold/retrieval_v2/set.jsonl + colab/outputs/sorgu_* (bkz. metrik_v2.py); Qdrant ayakta.

Çalıştır: .venv/Scripts/python.exe scripts/kanun/retrieval/metrik_agirlik_cv.py
"""
import collections
import json
import math
import pathlib
import random
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
import kanun.retrieval.search as S  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from kanun.retrieval.config import ayarlar_oku  # noqa: E402

SET = ROOT / "data" / "gold" / "retrieval_v2" / "set.jsonl"
VEK = ROOT / "colab" / "outputs"
OUT = SET.parent
ADAY_K = 50
_ORIJINAL = S.tokenize


def tok_eski(m):
    return S._TOKEN.findall(m.lower())


def tok_duz(m):
    return S._TOKEN.findall(S.tr_kucuk(m))


def tok_f(n):
    return lambda m: [t if t.isdigit() else t[:n] for t in tok_duz(m)]


SURUMLER = {"eski": tok_eski, "duzeltilmis": tok_duz, "duz+f5": S.tokenize, "duz+f6": tok_f(6)}


def izgara():
    w = [(round(a / 20, 2), round(b / 20, 2), round(1 - a / 20 - b / 20, 2)) for a in range(21) for b in range(21 - a)]
    return [(0.33, 0.33, 0.34)] + w


def normla(d):
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    r = (hi - lo) or 1.0
    return {k: (v - lo) / r for k, v in d.items()}


def metrik(r):
    r = np.asarray(r)
    n = len(r)
    ic = (r >= 1) & (r <= 10)
    return {"R@1": float(np.mean(r == 1)), "R@5": float(np.mean(ic & (r <= 5))), "R@10": float(np.mean(ic)),
            "MRR": float(np.sum(1.0 / r[ic]) / n), "nDCG@10": float(np.sum(1.0 / np.log2(r[ic] + 1)) / n), "N": n}


def main():
    kayitlar = [json.loads(l) for l in SET.open(encoding="utf-8")]
    meta = json.loads((VEK / "sorgu_meta.json").read_text(encoding="utf-8"))
    dense = np.load(VEK / "sorgu_dense.npy").astype(np.float32)
    sparse = json.loads((VEK / "sorgu_sparse.json").read_text(encoding="utf-8"))
    vek = {s: (dense[i].tolist(), sparse[i]) for i, s in enumerate(meta["sorgular"])}
    hedef = [(k["mevzuat_id"], k["madde_no"]) for k in kayitlar]

    # --- dense + sparse bacakları (Qdrant, bir kez) ---
    client = QdrantClient(url="http://localhost:6333")
    S.tokenize = _ORIJINAL
    bm_ilk = S.bm25_kur(str(ROOT / "data" / "kanun" / "korpus.jsonl"))
    arama = S.HybridArama(lambda s: vek[s], client, bm_ilk)
    flt = arama._filtre(True)
    ds_bacak = []
    for k in kayitlar:
        d, s = vek[k["ilgi"]]
        dres = client.query_points("mevzuat", query=d, using="dense", limit=ADAY_K, query_filter=flt, with_payload=True).points
        sres = client.query_points("mevzuat", query=arama._sparse_vektor(s), using="sparse", limit=ADAY_K,
                                   query_filter=flt, with_payload=True).points
        kim, dd, ss = {}, {}, {}
        for p in dres:
            m = bm_ilk.kimlik(str(p.payload["madde_id"]), p.payload.get("madde_no"))
            dd[m] = p.score
            kim[m] = (str(m).split("-")[0], str(p.payload.get("madde_no")))
        for p in sres:
            m = bm_ilk.kimlik(str(p.payload["madde_id"]), p.payload.get("madde_no"))
            ss[m] = p.score
            kim[m] = (str(m).split("-")[0], str(p.payload.get("madde_no")))
        ds_bacak.append((dd, ss, kim))

    W = np.array(izgara())                                 # (231+1, 3)
    siralar = {}                                           # sürüm -> (len(W), Nsorgu) sıra matrisi (0 = ilk 10'da yok)
    bm25_tek = {}
    for ad, tok in SURUMLER.items():
        S.tokenize = tok
        bm = S.bm25_kur(str(ROOT / "data" / "kanun" / "korpus.jsonl"))
        R = np.zeros((len(W), len(kayitlar)), dtype=np.int16)
        tek = []
        for qi, (k, (dd, ss, kim)) in enumerate(zip(kayitlar, ds_bacak)):
            sk = np.asarray(bm.bm25.get_scores(tok(k["ilgi"])))
            bb, kim2 = {}, dict(kim)
            for i in np.argsort(-sk, kind="stable")[:ADAY_K]:
                if sk[i] > 0:
                    m = str(bm.maddeler[i][2])
                    bb[m] = float(sk[i])
                    kim2.setdefault(m, (m.split("-")[0], str(bm.payload(i).get("madde_no"))))
            bm_sira = next((j for j, m in enumerate(list(bb)[:10], 1) if kim2[m] == hedef[qi]), 0)
            tek.append(bm_sira)
            nd, ns, nb = normla(dd), normla(ss), normla(bb)
            adaylar = list(dict.fromkeys(list(nd) + list(ns) + list(nb)))
            M = np.array([[nd.get(a, 0.0), ns.get(a, 0.0), nb.get(a, 0.0)] for a in adaylar])   # (n, 3)
            hedef_mi = np.array([kim2[a] == hedef[qi] for a in adaylar])
            P = W @ M.T                                                                        # (|W|, n)
            sira = np.argsort(-P, axis=1, kind="stable")[:, :10]
            isabet = hedef_mi[sira]                                                            # (|W|, 10)
            R[:, qi] = np.where(isabet.any(axis=1), isabet.argmax(axis=1) + 1, 0)
        siralar[ad] = R
        bm25_tek[ad] = metrik(tek)
    S.tokenize = _ORIJINAL

    # --- tekrarlı grup CV ---
    gruplar = sorted(set(hedef))
    g_idx = {g: i for i, g in enumerate(gruplar)}
    q_grup = np.array([g_idx[h] for h in hedef])

    def mrr_r10(R, maske):
        r = R[:, maske]
        ic = (r >= 1) & (r <= 10)
        mrr = np.where(ic, 1.0 / np.maximum(r, 1), 0).sum(axis=1) / maske.sum()
        return mrr, ic.mean(axis=1)

    cv = {}
    for ad, R in siralar.items():
        tekrar_metrik, secilen = [], collections.Counter()
        for t in range(20):
            rnd = random.Random(4721 + t)
            g = list(range(len(gruplar)))
            rnd.shuffle(g)
            kat = {gi: i % 5 for i, gi in enumerate(g)}
            test_sira = np.zeros(len(kayitlar), dtype=np.int16)
            for f in range(5):
                test = np.array([kat[gi] == f for gi in q_grup])
                mrr, r10 = mrr_r10(R, ~test)
                en_iyi = max(range(len(W)), key=lambda i: (round(mrr[i], 6), round(r10[i], 6)))
                secilen[tuple(W[en_iyi])] += 1
                test_sira[test] = R[en_iyi, test]
            tekrar_metrik.append(metrik(test_sira))
        cv[ad] = {k: (float(np.mean([m[k] for m in tekrar_metrik])), float(np.std([m[k] for m in tekrar_metrik])))
                  for k in ("R@1", "R@5", "R@10", "MRR", "nDCG@10")}
        cv[ad]["en_cok_secilen"] = [(list(w), n) for w, n in secilen.most_common(5)]

    # --- tam veride yüzey + bugünkü ayar ---
    tam = {}
    for ad, R in siralar.items():
        mrr, r10 = mrr_r10(R, np.ones(len(kayitlar), dtype=bool))
        sira = sorted(range(len(W)), key=lambda i: (-mrr[i], -r10[i]))
        tam[ad] = {"en_iyi": [(list(W[i]), round(float(mrr[i]), 4), round(float(r10[i]), 4)) for i in sira[:8]],
                   "esit_0.33": metrik(R[0]),
                   "plato_mrr_0.005": [list(W[i]) for i in range(len(W)) if mrr[i] >= mrr[sira[0]] - 0.005]}

    print("BM25 tek başına (R@10 / MRR):", {k: (round(v["R@10"], 3), round(v["MRR"], 3)) for k, v in bm25_tek.items()})
    print(f"\n{'sürüm':12s} | CV test (ort ± ss, 20x5 kat)                          | en çok seçilen ağırlık")
    for ad in siralar:
        c = cv[ad]
        print(f"{ad:12s} | R@1 {c['R@1'][0]:.3f}  R@10 {c['R@10'][0]:.3f}±{c['R@10'][1]:.3f}  MRR {c['MRR'][0]:.3f}±{c['MRR'][1]:.3f}"
              f"  nDCG {c['nDCG@10'][0]:.3f} | {c['en_cok_secilen'][:3]}")
    print(f"\n{'sürüm':12s} | eşit ağırlık (tam veri)             | tam veride en iyi 3 (ağırlık, MRR, R@10)")
    for ad in siralar:
        e = tam[ad]["esit_0.33"]
        print(f"{ad:12s} | R@10 {e['R@10']:.3f} MRR {e['MRR']:.3f} | {tam[ad]['en_iyi'][:3]}")

    # --- eşli bootstrap: servis ayarı (search.tokenize = duz+f5 + config ağırlıkları) vs eski (eski + eşit) ---
    en_iyi_surum = "duz+f5"
    w_oneri = tuple(round(float(x), 2) for x in ayarlar_oku().agirliklar)
    i_oneri = next(i for i in range(len(W)) if tuple(round(float(x), 2) for x in W[i]) == w_oneri)
    a_sira = siralar[en_iyi_surum][i_oneri].astype(float)
    b_sira = siralar["eski"][0].astype(float)

    def q_mrr(r):
        return np.where((r >= 1) & (r <= 10), 1.0 / np.maximum(r, 1), 0.0)

    rng = np.random.default_rng(4721)
    farklar_mrr, farklar_r10 = [], []
    qa, qb = q_mrr(a_sira), q_mrr(b_sira)
    ia, ib = ((a_sira >= 1) & (a_sira <= 10)).astype(float), ((b_sira >= 1) & (b_sira <= 10)).astype(float)
    for _ in range(5000):
        o = rng.integers(0, len(qa), len(qa))
        farklar_mrr.append(qa[o].mean() - qb[o].mean())
        farklar_r10.append(ia[o].mean() - ib[o].mean())
    ci = lambda x: (round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4))  # noqa: E731
    stil = collections.defaultdict(lambda: ([], []))
    for k, ra, rb in zip(kayitlar, a_sira, b_sira):
        stil[k["stil"]][0].append(ra)
        stil[k["stil"]][1].append(rb)
    print(f"\nSERVİS AYARI: BM25 '{en_iyi_surum}' + ağırlık (dense, sparse, bm25) = {w_oneri}")
    print(f"  tam veri: servis {metrik(a_sira)} \n            eski   {metrik(b_sira)}")
    print(f"  fark %95 GA (bootstrap 5000): MRR {ci(farklar_mrr)}  R@10 {ci(farklar_r10)}")
    for st, (ra, rb) in stil.items():
        print(f"  {st:9s}: servis R@10 {metrik(ra)['R@10']:.3f} MRR {metrik(ra)['MRR']:.3f} | eski R@10 {metrik(rb)['R@10']:.3f} MRR {metrik(rb)['MRR']:.3f}")
    (OUT / "agirlik_opt.json").write_text(json.dumps({"bm25_tek": bm25_tek, "cv": cv, "tam": tam, "oneri": {
        "bm25": en_iyi_surum, "agirlik": w_oneri, "oneri_metrik": metrik(a_sira), "bugun_metrik": metrik(b_sira),
        "fark_ci_mrr": ci(farklar_mrr), "fark_ci_r10": ci(farklar_r10)}}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
