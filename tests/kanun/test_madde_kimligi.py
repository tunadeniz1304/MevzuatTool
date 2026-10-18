# -*- coding: utf-8 -*-
"""Doğal dil yolunda madde kimliği — iç anahtar (kanun_no, madde_no) DEĞİL, madde_id (korpus chunk id'si).

kanun_no globalde benzersiz değil (14 kanun_no altında 2 kanun, tertip çakışması — ör. 6551) ve aynı kanunda
iki 'Geçici 1' olabilir (ids.py -1/-2). (kanun_no, madde_no) ile anahtarlanan BM25 sözlükleri ve WSUM füzyonu
bu maddeleri TEK adaya çökertir: skorlar karışır, `metin` / `kanun_ad` yanlış kanundan gelebilir.

1. Eşdeğerlik: çakışma yokken `HybridArama` eski davranışla (main 9e7601b — aşağıda DONDURULMUŞ kopya)
   birebir aynı: skorlar, sıra, alanlar ve /ara yanıtı. Tek istisna: puanı TAM eşit adayların kendi
   aralarındaki sırası — eski set birleşimi bu sırayı anahtar hash'ine (PYTHONHASHSEED) bağlıyordu; burada
   eşit puanlılar grup olarak (sırasız) karşılaştırılır. Sahte Qdrant + sahte BM25 skorları, rastgele senaryolar.
2. Çakışma: iki ayrı aday, doğru `metin`, doğru `kanun_ad`, reranker'a doğru metin, BM25-only adayda
   korpustan gerçek payload.
3. Ölçüm script'leri: gold eşleştirmesi (kanun_no, madde_no) ile kalır (metrik tanımı); iç anahtarın
   madde_id olması dosya biçimini ve değerlerini değiştirmez.
"""
import functools
import importlib.util
import json
import operator
import os
import pathlib
import random
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from kanun.api.app import uygulama_olustur
from kanun.ids import slug
from kanun.retrieval.config import Ayarlar
from kanun.retrieval.search import HybridArama, bm25_kur, tokenize

YUR, MULGA = "yürürlükte", "mülga"


# =================================================================================================
# ESKİ davranış — main 9e7601b `search.py` (norm, wsum_puan, bm25_kur haritaları, HybridArama.adaylar /
# _sonuc / ara / metin). DONDURULMUŞ kopya: referans; değiştirilmez.
# =================================================================================================
def _eski_norm(skor):
    if not skor:
        return {}
    vals = list(skor.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in skor.items()}


def _eski_wsum_puan(skorlar, agirliklar):
    normler = [_eski_norm(s) for s in skorlar]
    tum = functools.reduce(operator.or_, (set(n) for n in normler))
    puan = {}
    for k in tum:
        puan[k] = sum(w * n.get(k, 0.0) for w, n in zip(agirliklar, normler))
    return puan


def _eski_haritalar(korpus):
    """bm25_kur: maddeler (yalnız yürürlükte) + (kanun_no, madde_no) → metin / kanun_ad (tüm korpus)."""
    maddeler, metinler, adlar = [], {}, {}
    for r in korpus:
        m = r["metadata"]
        key = (str(m["kanun_no"]), str(m["madde_no"]))
        metinler[key] = r.get("text") or ""
        adlar[key] = m.get("kanun_ad") or ""
        if m["yurutluk"] != YUR:
            continue
        maddeler.append((key[0], key[1], r["id"]))
    return maddeler, metinler, adlar


class _EskiArama:
    def __init__(self, client, bm25, maddeler, metinler, kanun_adlari, aday_k=50,
                 agirliklar=(0.33, 0.33, 0.34), reranker=None, rerank_aday=20, rerank_max_krk=3000):
        self.client, self.bm25, self.maddeler = client, bm25, maddeler
        self.metinler, self.kanun_adlari = metinler, kanun_adlari
        self.aday_k, self.agirliklar = aday_k, tuple(agirliklar)
        self.reranker, self.rerank_aday, self.rerank_max_krk = reranker, rerank_aday, rerank_max_krk

    def metin(self, anahtar):
        return (self.metinler.get(anahtar) or "")[: self.rerank_max_krk]

    def adaylar(self, sorgu, yururlukte_only=True):
        flt = object() if yururlukte_only else None          # sahte Qdrant yalnız None olup olmadığına bakar
        dres = self.client.query_points(collection_name="mevzuat", query=[0.1], using="dense",
                                        limit=self.aday_k, query_filter=flt, with_payload=True)
        sres = self.client.query_points(collection_name="mevzuat", query=None, using="sparse",
                                        limit=self.aday_k, query_filter=flt, with_payload=True)

        def anahtar(p):
            return (str(p.payload["kanun_no"]), str(p.payload["madde_no"]))

        d_skor = {anahtar(p): p.score for p in dres.points}
        s_skor = {anahtar(p): p.score for p in sres.points}
        payload = {anahtar(p): p.payload for p in dres.points}
        for p in sres.points:
            payload.setdefault(anahtar(p), p.payload)
        bm_skorlar = np.asarray(self.bm25.get_scores(tokenize(sorgu)))
        en_iyi = np.argsort(-bm_skorlar, kind="stable")[: self.aday_k]
        b_skor = {}
        for i in en_iyi:
            if bm_skorlar[i] <= 0:
                continue
            kn, mn, mid = self.maddeler[i]
            b_skor[(kn, mn)] = float(bm_skorlar[i])
            payload.setdefault((kn, mn), {"kanun_no": kn, "madde_no": mn, "kanun_ad": "", "madde_id": mid})
        puan = _eski_wsum_puan([d_skor, s_skor, b_skor], self.agirliklar)
        return sorted(puan.items(), key=lambda x: -x[1]), payload

    def _sonuc(self, anahtar, payload, skor, rerank_skor=None):
        pl = payload.get(anahtar, {})
        return SimpleNamespace(madde_id=str(pl.get("madde_id", "")), kanun_no=anahtar[0],
                               kanun_ad=pl.get("kanun_ad") or self.kanun_adlari.get(anahtar, ""),
                               madde_no=anahtar[1], skor=float(skor),
                               rerank_skor=None if rerank_skor is None else float(rerank_skor),
                               metin=self.metinler.get(anahtar))      # app.py: metinler.get(s.anahtar)

    def ara(self, sorgu, top_k=10, yururlukte_only=True, rerank=False):
        sirali, payload = self.adaylar(sorgu, yururlukte_only)
        rerank_skor = {}
        if rerank and sirali:
            bas = sirali[: self.rerank_aday]
            skorlar = self.reranker.skorla(sorgu, [self.metin(k) for k, _ in bas])
            rerank_skor = {k: s for (k, _), s in zip(bas, skorlar)}
            bas = sorted(bas, key=lambda x: -rerank_skor[x[0]])
            sirali = bas + sirali[self.rerank_aday:]
        return [self._sonuc(k, payload, sk, rerank_skor.get(k)) for k, sk in sirali[:top_k]]


# =================================================================================================
# Sahte bileşenler + korpus yardımcıları
# =================================================================================================
def _chunk(mid, kanun_no, kanun_ad, madde_no, yurutluk=YUR, text=None, ek=None):
    """Korpus satırı; id `ids.assign_ids` biçiminde ('MID-slug', tekrarlı madde no'da 'MID-slug-N')."""
    cid = f"{mid}-{slug(madde_no)}" + ("" if ek is None else f"-{ek}")
    return {"id": cid, "text": text or f"{kanun_ad} m.{madde_no} metni",
            "metadata": {"mevzuat_id": mid, "mevzuat_tur": "KANUN", "kanun_no": kanun_no, "kanun_ad": kanun_ad,
                         "resmi_gazete_tarihi": "2014-03-06", "resmi_gazete_sayisi": f"2{mid}",
                         "madde_no": madde_no, "madde_baslik": None, "madde_tipi": "asil",
                         "yurutluk": yurutluk, "fikralar": []}}


def _qdrant_payload(r, madde_id=None):
    """Qdrant point payload'ı: ingest_qdrant `madde_id` + colab/bge_m3_embed.ipynb `payloadlar` alanları."""
    m = r["metadata"]
    return {"madde_id": madde_id or r["id"], "kanun_no": m["kanun_no"], "kanun_ad": m["kanun_ad"],
            "madde_no": m["madde_no"], "yurutluk": m["yurutluk"], "mevzuat_tur": m.get("mevzuat_tur"),
            "resmi_gazete_tarihi": m.get("resmi_gazete_tarihi"),
            "resmi_gazete_sayisi": m.get("resmi_gazete_sayisi")}


class SahteQdrant:
    """Bacak başına [(payload, skor)] → skor azalan ilk `limit` nokta; filtre verilirse yalnız yürürlükte."""

    def __init__(self, dense=(), sparse=()):
        self.noktalar = {"dense": list(dense), "sparse": list(sparse)}

    def query_points(self, collection_name, query, using, limit, query_filter, with_payload):
        noktalar = [SimpleNamespace(payload=pl, score=sk) for pl, sk in self.noktalar[using]
                    if query_filter is None or pl["yurutluk"] == YUR]
        noktalar.sort(key=lambda p: -p.score)
        return SimpleNamespace(points=noktalar[:limit])

    def collection_exists(self, ad):
        return True


class SahteBM25Skor:
    """get_scores: BM25 doküman sırasıyla hizalı sabit skorlar ({madde_id: skor}, olmayan 0)."""

    def __init__(self, maddeler, skor):
        self.skorlar = np.array([float(skor.get(mid, 0.0)) for _, _, mid in maddeler])

    def get_scores(self, tokenler):
        return self.skorlar


class SahteReranker:
    """skorla: metin → sabit skor (bilinmeyen metin -100); gelen metinleri kaydeder."""

    def __init__(self, skor):
        self.skor = skor
        self.gelen = []

    def skorla(self, sorgu, metinler):
        self.gelen.append(list(metinler))
        return [self.skor.get(m, -100.0) for m in metinler]


def _embedder(sorgu):
    return [0.1] * 4, {"5": 0.3, "9": 0.1}


def _korpus_yaz(tmp_path, korpus):
    yol = tmp_path / "korpus.jsonl"
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in korpus), encoding="utf-8")
    return str(yol)


def _yeni(tmp_path, korpus, dense=(), sparse=(), bm25=None, **kw):
    """Gerçek bm25_kur (korpus haritaları) + sahte BM25 skorları + sahte Qdrant → HybridArama."""
    idx = bm25_kur(_korpus_yaz(tmp_path, korpus))
    idx.bm25 = SahteBM25Skor(idx.maddeler, bm25 or {})
    return HybridArama(_embedder, SahteQdrant(dense, sparse), idx, **kw)


def _eski(korpus, dense=(), sparse=(), bm25=None, **kw):
    maddeler, metinler, adlar = _eski_haritalar(korpus)
    return _EskiArama(SahteQdrant(dense, sparse), SahteBM25Skor(maddeler, bm25 or {}), maddeler, metinler,
                      adlar, **kw)


def _istemci(arama):
    return TestClient(uygulama_olustur(arama_fabrika=lambda: arama,
                                       ayar=Ayarlar(embed_backend="onnx-int8", rerank_backend="kapali")))


# =================================================================================================
# 1. Eşdeğerlik — çakışma yokken eski davranışla birebir
# =================================================================================================
def _senaryo(seed, eski_index=False):
    """Rastgele, ÇAKIŞMASIZ korpus (her kanun_no tek kanun, kanunda her madde_no tek) + bacak skorları.
    Noktaların bir kısmının Qdrant payload'ında kanun_ad boştur (ad korpustan tamamlanır).

    eski_index: Qdrant index'i korpusun gerisinde (status.md açık konu 7) — noktaların bir kısmı eski id
    taşır ('MID-5' yerine 'MID-5-1'), bir kısmı korpusta artık yoktur (silinmiş '99', aynı madde no'lu sahte
    kopya). Eski (kanun_no, madde_no) anahtarı bunları birleştiriyordu; yeni anahtar da aynı sonucu vermeli."""
    rnd = random.Random(seed)
    kanunlar = []
    for i in range(rnd.randint(2, 6)):
        mid, kn, ad = str(1000 + i), str(5000 + i), f"ÖRNEK {i} KANUNU"
        kanunlar.append([_chunk(mid, kn, ad, no, MULGA if rnd.random() < 0.15 else YUR,
                                text=f"{ad} m.{no} metni {rnd.random():.12f}")
                         for no in [str(j) for j in range(1, rnd.randint(3, 9))] + ["Geçici 1", "Ek 2", "12/A"]])
    kanunlar[0][0]["metadata"]["yurutluk"] = YUR               # BM25 index'i boş kalmasın
    korpus = [r for kanun in kanunlar for r in kanun]
    noktalar = [dict(_qdrant_payload(r), kanun_ad="") if rnd.random() < 0.2 else _qdrant_payload(r)
                for r in korpus]
    if eski_index:
        # nokta başına (iki bacakta aynı payload): id'si embed anındaki halinde kalanlar ...
        noktalar = [dict(pl, madde_id=pl["madde_id"] + "-1") if rnd.random() < 0.3 else pl for pl in noktalar]
        for kanun in kanunlar:                                  # ... ve korpusta artık olmayanlar
            m = kanun[0]["metadata"]
            noktalar.append(_qdrant_payload(_chunk(m["mevzuat_id"], m["kanun_no"], m["kanun_ad"], "99")))
            kopya = rnd.choice(kanun)                           # aynı madde no'lu sahte kopya (bleed)
            noktalar.append(_qdrant_payload(kopya, madde_id=kopya["id"] + "-9"))
    dense = [(pl, rnd.random()) for pl in rnd.sample(noktalar, rnd.randint(0, len(noktalar)))]
    sparse = [(pl, rnd.uniform(0, 30)) for pl in rnd.sample(noktalar, rnd.randint(0, len(noktalar)))]
    bm25 = {r["id"]: rnd.choice([0.0, -1.0, rnd.uniform(0, 20), rnd.uniform(0, 20)]) for r in korpus}
    rerank = {r["text"]: rnd.uniform(-5, 5) for r in korpus}
    kw = {"aday_k": rnd.randint(1, 15),
          "agirliklar": rnd.choice([(0.33, 0.33, 0.34), (0.5, 0.2, 0.3), (0.2, 0.3, 0.5), (1.0, 0.0, 0.0)])}
    return korpus, dense, sparse, bm25, rerank, kw


def _beklenen_kimlik(korpus):
    """Beklenen aday kimliği: korpustaki id aynen; korpusta olmayan (eski index) id, aynı kanunda
    (mevzuat_id) o madde_no'lu TEK madde varsa onun id'si, yoksa kendisi. Eski çıktının madde_id'si
    (Qdrant payload'ından) bununla eşlenip karşılaştırılır."""
    idler = {r["id"] for r in korpus}
    kanun_madde = {}
    for r in korpus:
        kanun_madde.setdefault((r["metadata"]["mevzuat_id"], r["metadata"]["madde_no"]), []).append(r["id"])

    def kimlik(madde_id, madde_no):
        tek = kanun_madde.get((madde_id.split("-")[0], madde_no), [])
        return madde_id if madde_id in idler or len(tek) != 1 else tek[0]
    return kimlik


def _kayit(s, kimlik=None):
    mid = kimlik(s.madde_id, s.madde_no) if kimlik else s.madde_id
    return (mid, s.kanun_no, s.kanun_ad, s.madde_no, s.skor, s.rerank_skor)


def _gruplar(kayitlar, puan):
    """Sıralı liste → ardışık eşit-puan grupları; grup içi sıra önemsiz (eski sıra hash'e bağlıydı)."""
    gruplar = []
    for k in kayitlar:
        if gruplar and gruplar[-1][0] == puan(k):
            gruplar[-1][1].append(k)
        else:
            gruplar.append((puan(k), [k]))
    return [(p, sorted(g, key=repr)) for p, g in gruplar]


def _sinirlar(sirali):
    """Eşit-puan grubunu bölmeyen kesim noktaları (top_k / RERANK_ADAY bu noktalarda seçilir)."""
    puan = [p for _, p in sirali]
    return [i for i in range(1, len(puan) + 1) if i == len(puan) or puan[i - 1] != puan[i]]


def _cift(payload, k):
    return (str(payload[k]["kanun_no"]), str(payload[k]["madde_no"]))


@pytest.mark.parametrize("eski_index", [False, True], ids=["index-guncel", "index-eski"])
@pytest.mark.parametrize("seed", range(150))
def test_cakisma_yokken_eski_davranisla_birebir(tmp_path, seed, eski_index):
    korpus, dense, sparse, bm25, rerank, kw = _senaryo(seed, eski_index)
    kimlik = _beklenen_kimlik(korpus)
    yeni = _yeni(tmp_path, korpus, dense, sparse, bm25, **kw)
    eski = _eski(korpus, dense, sparse, bm25, **kw)
    assert yeni.bm25.maddeler == eski.maddeler                 # BM25 doküman hizası aynı

    for yururlukte_only in (True, False):
        # adaylar(): aynı aday kümesi, aynı puanlar, aynı sıra (eşit puan grupları içinde sırasız)
        y_sirali, y_payload, _ = yeni.adaylar("soru", yururlukte_only)
        e_sirali, e_payload = eski.adaylar("soru", yururlukte_only)
        assert _gruplar([(_cift(y_payload, k), p) for k, p in y_sirali], lambda x: x[1]) == \
            _gruplar(e_sirali, lambda x: x[1])
        for k, _ in y_sirali:                                   # payload aynı; anahtar = korpus kimliği
            pl, e_pl = y_payload[k], e_payload[_cift(y_payload, k)]
            assert pl["madde_id"] == e_pl["madde_id"] and k == kimlik(pl["madde_id"], pl["madde_no"])
            if "yurutluk" in e_pl:                              # eski sentetik BM25-only payload'ı hariç
                assert pl == e_pl

        sinirlar = _sinirlar(y_sirali) or [1]
        rnd = random.Random(seed)
        for rr in (False, True):
            aday = rnd.choice(sinirlar)
            top_k = rnd.choice([n for n in sinirlar if n > aday] + list(range(1, aday + 1))) if rr \
                else rnd.choice(sinirlar)
            rk = SahteReranker(rerank)
            y = HybridArama(_embedder, yeni.client, yeni.bm25, reranker=rk, rerank_aday=aday, **kw)
            e = _eski(korpus, dense, sparse, bm25, reranker=SahteReranker(rerank), rerank_aday=aday, **kw)
            y_son = [_kayit(s) for s in y.ara("soru", top_k=top_k, yururlukte_only=yururlukte_only, rerank=rr)]
            e_son = [_kayit(s, kimlik)
                     for s in e.ara("soru", top_k=top_k, yururlukte_only=yururlukte_only, rerank=rr)]
            assert _gruplar(y_son, lambda x: (x[5], x[4])) == _gruplar(e_son, lambda x: (x[5], x[4]))


@pytest.mark.parametrize("eski_index", [False, True], ids=["index-guncel", "index-eski"])
@pytest.mark.parametrize("seed", range(12))
def test_cakisma_yokken_ara_yaniti_eski_semayla_birebir(tmp_path, seed, eski_index):
    """/ara (mod=dogal, metin=true): alanlar ve metin eski yanıtla aynı (çakışma yok)."""
    korpus, dense, sparse, bm25, rerank, kw = _senaryo(seed, eski_index)
    kimlik = _beklenen_kimlik(korpus)
    yeni = _yeni(tmp_path, korpus, dense, sparse, bm25, **kw)
    eski = _eski(korpus, dense, sparse, bm25, **kw)
    sinirlar = [n for n in _sinirlar(yeni.adaylar("soru")[0]) if n <= 50] or [1]
    top_k = random.Random(seed).choice(sinirlar)
    with _istemci(yeni) as c:
        j = c.post("/ara", json={"sorgu": "soru", "top_k": top_k, "mod": "dogal", "metin": True}).json()
    assert [s["sira"] for s in j["sonuclar"]] == list(range(1, len(j["sonuclar"]) + 1))
    alanlar = ("madde_id", "kanun_no", "kanun_ad", "madde_no", "skor", "rerank_skor", "metin")
    y = [tuple(s[a] for a in alanlar) for s in j["sonuclar"]]
    e = [(kimlik(s.madde_id, s.madde_no),) + tuple(getattr(s, a) for a in alanlar[1:])
         for s in eski.ara("soru", top_k=top_k)]
    assert _gruplar(y, lambda x: x[4]) == _gruplar(e, lambda x: x[4])


# =================================================================================================
# 2. Çakışma — kanun_no tertip çakışması (6551 iki kanun) ve aynı kanunda tekrarlı madde no
# =================================================================================================
MAHALLI, ENERJI, TCK = "ÖRNEK MAHALLİ İDARELER KANUNU", "ÖRNEK ENERJİ PİYASASI KANUNU", "TÜRK CEZA KANUNU"
CAKISMA = [
    _chunk("400", "6551", MAHALLI, "5", text="mahalli idare birliği kurulur"),
    _chunk("400", "6551", MAHALLI, "6", text="birlik meclisi toplanır"),
    _chunk("401", "6551", ENERJI, "5", text="enerji piyasası lisansı verilir"),
    _chunk("100", "5237", TCK, "Geçici 1", ek=1, text="ilk geçici madde"),
    _chunk("100", "5237", TCK, "Geçici 1", ek=2, text="ikinci geçici madde"),
    _chunk("100", "5237", TCK, "141", text="hırsızlık suçu"),
]
R = {r["id"]: r for r in CAKISMA}


def _pl(cid, skor):
    return _qdrant_payload(R[cid]), skor


def test_cakisan_kanun_no_dense_adaylari_ayri(tmp_path):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("400-5", 0.9), _pl("401-5", 0.8), _pl("100-141", 0.1)])
    sonuc = [(s.madde_id, s.kanun_ad, s.madde_no, s.skor) for s in arama.ara("soru")]
    assert sonuc == [("400-5", MAHALLI, "5", pytest.approx(0.33)),
                     ("401-5", ENERJI, "5", pytest.approx(0.33 * 0.7 / 0.8)),
                     ("100-141", TCK, "141", 0.0)]


def test_cakisan_kanun_no_bm25_adaylari_ayri_ve_kanun_adi_dogru(tmp_path):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("100-141", 0.9), _pl("400-6", 0.2)],
                  bm25={"400-5": 3.0, "401-5": 2.0, "100-141": 1.0})
    sonuc = [(s.madde_id, s.kanun_no, s.kanun_ad, s.madde_no, s.skor) for s in arama.ara("soru")]
    assert sonuc == [("400-5", "6551", MAHALLI, "5", pytest.approx(0.34)),
                     ("100-141", "5237", TCK, "141", pytest.approx(0.33)),
                     ("401-5", "6551", ENERJI, "5", pytest.approx(0.17)),
                     ("400-6", "6551", MAHALLI, "6", 0.0)]


def test_ayni_kanunda_tekrarli_madde_no_ayri_aday(tmp_path):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("100-Gecici1-2", 0.7), _pl("100-141", 0.6)],
                  bm25={"100-Gecici1-1": 2.0, "100-Gecici1-2": 1.5, "100-141": 0.5})
    sonuc = {s.madde_id: s.skor for s in arama.ara("soru")}
    assert sonuc == {"100-Gecici1-2": pytest.approx(0.33 + 0.34 * 1.0 / 1.5),
                     "100-Gecici1-1": pytest.approx(0.34), "100-141": 0.0}


def test_cakisan_maddelerde_reranker_her_adayin_kendi_metnini_alir(tmp_path):
    rk = SahteReranker({R["400-5"]["text"]: 1.0, R["401-5"]["text"]: 2.0})
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("400-5", 0.9), _pl("401-5", 0.8)], reranker=rk)
    sonuc = [(s.madde_id, s.rerank_skor) for s in arama.ara("soru", rerank=True)]
    assert sonuc == [("401-5", 2.0), ("400-5", 1.0)]
    assert sorted(rk.gelen[0]) == sorted([R["400-5"]["text"], R["401-5"]["text"]])


def test_ara_cakisan_kanunlarda_metin_ve_kanun_adi_dogru_maddeden(tmp_path):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("400-5", 0.9), _pl("401-5", 0.8)],
                  bm25={"401-5": 1.0, "100-141": 0.5})
    with _istemci(arama) as c:
        j = c.post("/ara", json={"sorgu": "soru", "mod": "dogal", "metin": True}).json()
    sonuc = {s["madde_id"]: (s["kanun_no"], s["kanun_ad"], s["madde_no"], s["metin"]) for s in j["sonuclar"]}
    assert sonuc == {"400-5": ("6551", MAHALLI, "5", R["400-5"]["text"]),
                     "401-5": ("6551", ENERJI, "5", R["401-5"]["text"]),
                     "100-141": ("5237", TCK, "141", R["100-141"]["text"])}


def test_qdrant_payloadinda_bos_kanun_adi_kendi_maddesinin_korpus_adiyla_dolar(tmp_path):
    # eski kod adı (kanun_no, madde_no) haritasından alıyordu → 400-5'e korpusta son gelen ENERJİ adı düşerdi
    bos_ad = [(dict(_qdrant_payload(R[cid]), kanun_ad=""), skor) for cid, skor in (("400-5", 0.9), ("401-5", 0.8))]
    arama = _yeni(tmp_path, CAKISMA, dense=bos_ad)
    assert {s.madde_id: s.kanun_ad for s in arama.ara("soru")} == {"400-5": MAHALLI, "401-5": ENERJI}


def test_bm25_only_adayin_payloadi_korpustan_gercek_alanlar(tmp_path):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("100-141", 0.9)], bm25={"400-6": 2.0})
    _, payload, _ = arama.adaylar("soru")
    pl = next(p for p in payload.values() if p["madde_id"] == "400-6")   # anahtar türünden bağımsız
    assert pl == _qdrant_payload(R["400-6"])                   # Qdrant payload'ıyla aynı şema ve değerler
    assert pl["kanun_ad"] == MAHALLI and pl["yurutluk"] == YUR


# =================================================================================================
# 3. Ölçüm script'leri — gold eşleştirmesi (kanun_no, madde_no) değişmez, iç anahtardan etkilenmez
# =================================================================================================
_KOK = pathlib.Path(__file__).resolve().parent.parent.parent


def _script(ad):
    spec = importlib.util.spec_from_file_location(ad, str(_KOK / "scripts" / "kanun" / "retrieval" / f"{ad}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _aday_cikar(tmp_path, monkeypatch, arama):
    import kanun.retrieval.fabrika as fabrika
    m = _script("metrik_rerank_3bacak")
    monkeypatch.setattr(fabrika, "arama_kur", lambda ayar, reranker=None: arama)
    monkeypatch.setattr(m, "gold_sorgular", lambda n, yol: [("soru", ("6551", "5"))])
    monkeypatch.setattr(m, "OLCUM", str(tmp_path / "olcum"))
    m.aday_cikar(SimpleNamespace(embed="torch", n=1))
    with open(m.aday_dosya("torch"), encoding="utf-8") as f:
        return json.loads(f.readline())


@pytest.mark.parametrize("eski_index", [False, True], ids=["index-guncel", "index-eski"])
@pytest.mark.parametrize("seed", range(10))
def test_rerank_aday_dosyasi_cakisma_yokken_eski_ciktiyla_ayni(tmp_path, monkeypatch, seed, eski_index):
    korpus, dense, sparse, bm25, _, kw = _senaryo(seed, eski_index)
    yeni = _yeni(tmp_path, korpus, dense, sparse, bm25, **kw)
    satir = _aday_cikar(tmp_path, monkeypatch, yeni)
    y_sirali, y_payload, _ = yeni.adaylar("soru")
    e_sirali, _ = _eski(korpus, dense, sparse, bm25, **kw).adaylar("soru")
    puanlar = [p for _, p in y_sirali[:50]]
    # "adaylar" eski biçimde ([kanun_no, madde_no]) ve eski değerlerle (eşit puan grupları içinde sırasız)
    assert _gruplar([(tuple(a), p) for a, p in zip(satir["adaylar"], puanlar)], lambda x: x[1]) == \
        _gruplar([(k, p) for k, p in e_sirali[:50]], lambda x: x[1])
    assert satir["madde_idler"] == [k for k, _ in y_sirali[:50]]
    assert satir["adaylar"] == [list(_cift(y_payload, k)) for k in satir["madde_idler"]]


def test_rerank_aday_dosyasi_cakisan_maddeleri_ayri_yazar(tmp_path, monkeypatch):
    arama = _yeni(tmp_path, CAKISMA, dense=[_pl("400-5", 0.9), _pl("401-5", 0.8), _pl("100-141", 0.1)])
    satir = _aday_cikar(tmp_path, monkeypatch, arama)
    assert satir["madde_idler"] == ["400-5", "401-5", "100-141"]
    assert satir["adaylar"] == [["6551", "5"], ["6551", "5"], ["5237", "141"]]    # gold çifti (metrik tanımı)
    assert satir["dogru"] == ["6551", "5"]


def test_rerank_skorlama_metni_madde_idden_eski_dosyada_ciftten(tmp_path, monkeypatch):
    m = _script("metrik_rerank_3bacak")
    monkeypatch.setenv("KORPUS_YOL", _korpus_yaz(tmp_path, CAKISMA))
    monkeypatch.setattr(m, "OLCUM", str(tmp_path / "olcum"))
    os.makedirs(m.OLCUM)
    with open(m.aday_dosya("torch"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"sorgu": "q", "dogru": ["6551", "5"], "adaylar": [["6551", "5"], ["6551", "5"]],
                            "madde_idler": ["400-5", "401-5"]}) + "\n")
        f.write(json.dumps({"sorgu": "q", "dogru": ["5237", "141"], "adaylar": [["5237", "141"]]}) + "\n")

    class RR:                                   # skor = metin uzunluğu; gelen metinleri kaydeder
        def __init__(self):
            self.ciftler = []

        def skorla_ciftler(self, ciftler):
            self.ciftler += ciftler
            return [float(len(t)) for _, t in ciftler]

    rr = RR()
    monkeypatch.setattr(m, "_reranker", lambda *a, **k: rr)
    m.skorla(SimpleNamespace(embed="torch", backend="torch", max_len=512, aday=50, n=10, cihaz="cpu", batch=8))
    metinler = [R["400-5"]["text"], R["401-5"]["text"], R["100-141"]["text"]]
    assert [t for _, t in rr.ciftler] == metinler     # çakışan çiftte her aday kendi metni; eski satır çiftten
    with open(m.skor_dosya("torch", "torch", 512), encoding="utf-8") as f:
        assert [json.loads(l) for l in f] == [[len(metinler[0]), len(metinler[1])], [len(metinler[2])]]


P1, P2, P3 = ("1", "1"), ("1", "2"), ("1", "3")
_SINIF_PAYLOAD = {"A": {"kanun_no": "1", "madde_no": "1"}, "B": {"kanun_no": "1", "madde_no": "2"},
                  "C": {"kanun_no": "1", "madde_no": "3"},
                  "400-5": {"kanun_no": "6551", "madde_no": "5"}, "401-5": {"kanun_no": "6551", "madde_no": "5"}}


@pytest.mark.parametrize("eski, sirali, k, beklenen", [
    ([(P1, 0.9), (P2, 0.5)], [("A", 0.9), ("B", 0.5)], 10, "ayni"),
    # yalnız eşit puanlıların sırası farklı (eski set birleşimi bu sırayı hash'e bağlıyordu)
    ([(P1, 0.5), (P2, 0.5)], [("B", 0.5), ("A", 0.5)], 10, "esit_puan"),
    # eşit-puan grubu top-k sınırında bölünüyor: k içinde başka aday, adaylar ve puanlar aynı
    ([(P1, 0.9), (P2, 0.5), (P3, 0.5)], [("A", 0.9), ("C", 0.5), ("B", 0.5)], 2, "esit_puan"),
    # sıra aynı ama puan değişmiş
    ([(P1, 0.9), (P2, 0.5)], [("A", 0.9), ("B", 0.4)], 10, "fark"),
    # yeni yolda eşitlenen puan, sıra farkını eşit-puan farkı gibi gösteremez
    ([(P1, 0.6), (P2, 0.5)], [("B", 0.5), ("A", 0.5)], 10, "fark"),
    # eski aday yeni listede yok
    ([(P1, 0.9), (P2, 0.5), (P3, 0.1)], [("A", 0.9), ("B", 0.5)], 10, "fark"),
    # top-k birebir aynıysa k dışındaki fark sonucu değiştirmez
    ([(P1, 0.9), (P2, 0.5), (P3, 0.1)], [("A", 0.9), ("B", 0.5)], 2, "ayni"),
    # iki kanunun aynı numaralı maddesi artık iki aday — eski kod tek adaya çökertiyordu
    ([(("6551", "5"), 0.9)], [("400-5", 0.9), ("401-5", 0.8)], 10, "cakisma"),
])
def test_esdeger_kontrol_sinifi(eski, sirali, k, beklenen):
    """eski: eski algoritmanın tüm adayları [((kanun_no, madde_no), puan)]; sirali: yeni `adaylar()`."""
    assert _script("esdeger_kontrol").sinifla(eski, sirali, _SINIF_PAYLOAD, k=k) == beklenen


@pytest.mark.parametrize("korpus_madde_no, beklenen", [("12/A", "ayrisma"), ("12/ A", "fark")])
def test_esdeger_kontrol_index_korpus_ayrismasi(korpus_madde_no, beklenen):
    """Eski index payload'ı X'i (1, '12/ A') diye taşıyor. Korpus '12/A' diyorsa eski kod X'in dense puanını ve
    BM25 puanını iki ayrı adaya bölüyordu, yeni kod madde_id'de birleştirir (beklenen fark). Korpus da '12/ A'
    diyorsa ayrışma yok: fark açıklanamaz."""
    payload = {"X": {"kanun_no": "1", "madde_no": "12/ A"}, "A": {"kanun_no": "1", "madde_no": "1"}}
    korpus = {"X": {"kanun_no": "1", "madde_no": korpus_madde_no}, "A": {"kanun_no": "1", "madde_no": "1"}}
    eski = [(("1", "12/ A"), 0.6), (P1, 0.5), (("1", "12/A"), 0.3)]
    sirali = [("X", 0.9), ("A", 0.5)]
    assert _script("esdeger_kontrol").sinifla(eski, sirali, payload, korpus=korpus) == beklenen


# =================================================================================================
# 4. Eski index — Qdrant'taki madde_id korpusta yoksa korpus kimliğine bağlanır (yalnız tek aday varsa)
# =================================================================================================
def test_bm25index_kimlik(tmp_path):
    idx = bm25_kur(_korpus_yaz(tmp_path, CAKISMA))
    assert idx.kimlik("400-5", "5") == "400-5"                       # korpusta var → aynen
    assert idx.kimlik("400-5-1", "5") == "400-5"                     # eski id → kanunda tek '5'
    assert idx.kimlik("401-5-2", "5") == "401-5"                     # tertip çakışması: kendi kanunu
    assert idx.kimlik("100-Gecici1", "Geçici 1") == "100-Gecici1"    # kanunda iki 'Geçici 1' → belirsiz
    assert idx.kimlik("400-99", "99") == "400-99"                    # korpusta o madde yok
    assert idx.kimlik("400-5-1", None) == "400-5-1"                  # madde_no bilinmiyor → dokunulmaz


def test_eski_index_idsi_korpus_maddesiyle_birlesir_ve_metni_doner(tmp_path):
    eski_pl = _qdrant_payload(R["400-5"], madde_id="400-5-1")       # embed anındaki id
    arama = _yeni(tmp_path, CAKISMA, dense=[(eski_pl, 0.9), _pl("100-141", 0.1)],
                  bm25={"400-5": 2.0, "401-5": 1.0})
    sonuc = {s.madde_id: (s.kanun_ad, s.skor) for s in arama.ara("soru")}
    assert sonuc == {"400-5": (MAHALLI, pytest.approx(0.33 + 0.34)), "401-5": (ENERJI, 0.0),
                     "100-141": (TCK, 0.0)}                          # '400-5-1' ayrı aday değil
    with _istemci(arama) as c:
        j = c.post("/ara", json={"sorgu": "soru", "mod": "dogal", "metin": True}).json()
    assert {s["madde_id"]: s["metin"] for s in j["sonuclar"]}["400-5"] == R["400-5"]["text"]


def test_eski_index_idsi_belirsizse_ayri_aday_kalir(tmp_path):
    eski_pl = _qdrant_payload(R["100-Gecici1-1"], madde_id="100-Gecici1")   # iki 'Geçici 1'den hangisi?
    arama = _yeni(tmp_path, CAKISMA, dense=[(eski_pl, 0.9), _pl("100-141", 0.1)], bm25={"100-Gecici1-1": 1.0})
    assert {s.madde_id for s in arama.ara("soru")} == {"100-Gecici1", "100-Gecici1-1", "100-141"}
    assert arama.metin("100-Gecici1") == ""                         # korpusta yok → metin yok
