# -*- coding: utf-8 -*-
"""3-bacak hybrid arama kütüphanesi — dense + BGE-sparse + klasik BM25 → WSUM → (ops.) reranker.

Eskiden aynı mantık `scripts/kanun/retrieval/search_qdrant.py` ve 8 ölçüm script'inde kopya halindeydi.
Bu modül tek kaynak: CLI, FastAPI servisi, gecikme ölçümü ve reranker ölçümü buradan arar.
Davranış `search_qdrant.ara` (main, 2026-07) ile birebir aynıdır — `esdeger_kontrol.py` 50/50 doğrular —
tek bilinçli fark: aday kimliği madde_id'dir (korpus chunk id'si, mevzuatId tabanlı), (kanun_no, madde_no)
değil. kanun_no globalde benzersiz değil (tertip çakışması, ör. 6551 iki kanun) ve aynı kanunda iki 'Geçici 1'
olabilir (ids.py -1/-2); bu maddeler artık tek adaya çökmez. Çakışmasız korpusta sonuçlar birebir aynı
(tests/kanun/test_madde_kimligi.py, eski davranışın dondurulmuş kopyasına karşı).

Akış (`HybridArama.ara`):
  1. embed    : sorgu → (dense 1024, sparse {token-id: ağırlık})   [enjekte edilen embedder]
  2. dense    : Qdrant `query_points(using="dense")`  top-ADAY_K, yürürlük filtresi arama SIRASINDA
  3. sparse   : Qdrant `query_points(using="sparse")` top-ADAY_K, aynı filtre
  4. bm25     : rank_bm25 korpus `text` (yalnız yürürlükte), top-ADAY_K, skor ≤ 0 atılır
  5. fuzyon   : her bacak min-max normalize → ağırlıklı toplam (WSUM) → azalan sıra; bacaklar madde_id'de birleşir
  6. rerank   : (ops.) WSUM sırasının ilk RERANK_ADAY adayı cross-encoder ile yeniden sıralanır
Her aşamanın süresi `sure_ms`'e yazılır (time.perf_counter, ms).

Bu modül torch İMPORT ETMEZ — embedder/reranker dışarıdan verilir (servis imajı torch'suz kalabilsin).
"""
import functools
import json
import re
import time
from dataclasses import dataclass, field

import numpy as np

_TOKEN = re.compile(r"[0-9a-zçğıöşü]+", re.UNICODE)
YURURLUKTE = "yürürlükte"
SURE_ANAHTARLARI = ("embed", "dense", "sparse", "bm25", "fuzyon", "rerank", "toplam")


def tokenize(metin):
    """BM25 klasik: lower + kelime ayır (Türkçe harfler dahil)."""
    return _TOKEN.findall(metin.lower())


def norm(skor):
    """min-max normalize (0-1). Bacakların skoru farklı ölçekte → toplamadan önce şart.
    Boş sözlük → {}; tüm skorlar eşitse aralık 0 → 1.0'a bölünür (0'a bölme yok, hepsi 0 olur)."""
    if not skor:
        return {}
    vals = list(skor.values())
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return {k: (v - lo) / rng for k, v in skor.items()}


def wsum_puan(skorlar, agirliklar):
    """Bacak skor sözlüklerini normalize edip ağırlıklı topla → {anahtar: puan}.
    Bir bacakta olmayan anahtar o bacaktan 0 alır. Anahtarlar İLK GÖRÜNDÜKLERİ sırayla birleşir (bacak
    sırası, bacak içinde sözlük sırası = o bacağın sıralaması) → kararlı sıralamada eşit puanlılar bu sırada
    kalır, süreçten sürece aynı. Eski `set(d) | set(s) | set(b)` birleşimi eşitlerin sırasını anahtar
    hash'ine (PYTHONHASHSEED) bağlıyordu; eşit olmayan puanların sırası ve puanlar aynıdır."""
    if len(skorlar) != len(agirliklar):
        raise ValueError("skorlar ve agirliklar aynı uzunlukta olmalı")
    normler = [norm(s) for s in skorlar]
    tum = dict.fromkeys(k for n in normler for k in n)
    puan = {}
    for k in tum:
        puan[k] = sum(w * n.get(k, 0.0) for w, n in zip(agirliklar, normler))
    return puan


def wsum(skorlar, agirliklar):
    """WSUM füzyon → anahtarların azalan puan sırası (metrik_iki_asama.py tanımı); eşitlerde ilk görünme."""
    puan = wsum_puan(skorlar, agirliklar)
    return [k for k, _ in sorted(puan.items(), key=lambda x: -x[1])]


class HizliBM25:
    """rank_bm25 `BM25Okapi.get_scores`'un posting-listeli, BİT-BİT AYNI sonuçlu hali.

    Orijinal her sorgu token'ı için 28k dokümanlık bir Python list-comprehension'ı kurar
    (`[doc.get(q) or 0 for doc in doc_freqs]`) → token başına ~5-10 ms, sorgu başına yüzlerce ms.
    Burada her terimin (doküman indeksi, frekans) posting listesi bir kez çıkarılır; sorguda aynı
    int64 frekans dizisi np.zeros + indeksli atama ile kurulur ve orijinal formül AYNI sırayla
    uygulanır → skorlar birebir eşit (test_search.py doğrular), token başına ~0.1 ms.
    """

    def __init__(self, okapi):
        self.okapi = okapi
        self.doc_len = np.array(okapi.doc_len)
        n = len(okapi.doc_freqs)
        postings = {}
        for i, doc in enumerate(okapi.doc_freqs):
            for terim, frek in doc.items():
                postings.setdefault(terim, ([], []))
                postings[terim][0].append(i)
                postings[terim][1].append(frek)
        self.postings = {t: (np.array(ix, dtype=np.int64), np.array(fr, dtype=np.int64))
                         for t, (ix, fr) in postings.items()}
        self.n = n

    def get_scores(self, query):
        o = self.okapi
        score = np.zeros(self.n)
        for q in query:
            q_freq = np.zeros(self.n, dtype=np.int64)
            p = self.postings.get(q)
            if p is not None:
                q_freq[p[0]] = p[1]
            score += (o.idf.get(q) or 0) * (q_freq * (o.k1 + 1) /
                                             (q_freq + o.k1 * (1 - o.b + o.b * self.doc_len / o.avgdl)))
        return score


# Qdrant point payload'ı = `madde_id` (ingest_qdrant.py) + bu alanlar (colab/bge_m3_embed.ipynb `payloadlar`).
# BM25-only aday aynı şemayı korpustan alır → adayın payload'ı hangi bacaktan geldiğine göre değişmez.
PAYLOAD_ALANLARI = ("kanun_no", "kanun_ad", "madde_no", "yurutluk", "mevzuat_tur",
                    "resmi_gazete_tarihi", "resmi_gazete_sayisi")


def korpus_payload(r):
    """Korpus satırı → Qdrant point payload'ıyla aynı şemada sözlük (eksik alan None)."""
    m = r["metadata"]
    return {"madde_id": str(r["id"]), **{a: m.get(a) for a in PAYLOAD_ALANLARI}}


@dataclass
class BM25Index:
    """Klasik BM25 index'i + korpus haritaları (reranker metni, servis `metin`i, BM25-only aday payload'ı).

    Haritaların anahtarı madde_id (korpus chunk id'si — globalde benzersiz). (kanun_no, madde_no) anahtar
    olamaz: tertip çakışan iki kanunun (6551) ya da aynı kanundaki iki 'Geçici 1'in değeri birbirini ezer.
    maddeler[i] = (kanun_no, madde_no, madde_id) — BM25 doküman i ile hizalı (yalnız yürürlükte).
    metinler   : TÜM korpus (mülga dahil) madde_id → text
    payloadlar : TÜM korpus (mülga dahil) madde_id → `korpus_payload` (Qdrant payload şeması)
    """
    bm25: object                # get_scores(tokenler) sunan nesne (HizliBM25 ya da BM25Okapi)
    maddeler: list
    metinler: dict = field(default_factory=dict)
    payloadlar: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.maddeler)

    def payload(self, i):
        """BM25 doküman i'nin payload'ı: korpustan gerçek alanlar. Harita yoksa (sahte index) yalnız kimlik."""
        kn, mn, mid = self.maddeler[i]
        return self.payloadlar.get(mid) or {"madde_id": mid, "kanun_no": kn, "madde_no": mn}

    def kimlik(self, madde_id, madde_no=None):
        """Qdrant payload'ındaki madde_id → korpus madde_id'si (aday anahtarı).

        Index bu korpustan üretildiyse id korpusta vardır, aynen döner. Index korpusun gerisindeyse (eski
        Colab embed'i, status.md açık konu 7) yeniden üretilen korpusta id değişmiş olabilir — ör. bleed
        temizliği sahte bir '5'i silince 'MID-5-1' → 'MID-5'. Eski (kanun_no, madde_no) anahtarı bunları
        birleştiriyordu; burada aynı kanunda (mevzuat_id = id öneki) o madde_no'lu TEK korpus maddesi varsa
        ona bağlanır. Birden çoksa (aynı kanunda iki 'Geçici 1') ya da hiç yoksa id olduğu gibi kalır:
        belirsizlik sessizce çözülmez (aday ayrı durur, korpus metni yoktur)."""
        if madde_id in self.payloadlar or madde_no is None:
            return madde_id
        eslesen = self._kanun_maddeleri.get((madde_id.split("-")[0], str(madde_no)), ())
        return eslesen[0] if len(eslesen) == 1 else madde_id

    @functools.cached_property
    def _kanun_maddeleri(self):
        """(mevzuat_id, madde_no) → [madde_id]; yalnız korpusta olmayan bir index id'si görülünce kurulur."""
        ters = {}
        for mid, pl in self.payloadlar.items():
            ters.setdefault((mid.split("-")[0], str(pl.get("madde_no"))), []).append(mid)
        return ters


def bm25_kur(korpus_yol="data/kanun/korpus.jsonl"):
    """Korpus 'text' üzerine BM25 index (yalnız yürürlükte maddeler), ~3-5 sn."""
    from rank_bm25 import BM25Okapi   # geç import: testler sahte index verebilsin

    maddeler, dokumanlar, metinler, payloadlar = [], [], {}, {}
    with open(korpus_yol, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            mid = str(r["id"])
            metinler[mid] = r.get("text") or ""
            payloadlar[mid] = korpus_payload(r)
            if m["yurutluk"] != YURURLUKTE:
                continue
            maddeler.append((str(m["kanun_no"]), str(m["madde_no"]), mid))
            dokumanlar.append(tokenize(r["text"]))
    return BM25Index(HizliBM25(BM25Okapi(dokumanlar)), maddeler, metinler, payloadlar)


@dataclass
class Sonuc:
    madde_id: str
    kanun_no: str
    kanun_ad: str
    madde_no: str
    skor: float                 # WSUM füzyon puanı
    rerank_skor: float = None   # reranker çalıştıysa cross-encoder logit'i, yoksa None

    @property
    def anahtar(self):
        """(kanun_no, madde_no) — gold/ölçüm eşleştirme çifti. Benzersiz DEĞİL (tertip çakışması, tekrarlı
        madde no): adayın kimliği `madde_id`'dir; madde metni ve aday birleştirme madde_id ile yapılır."""
        return (self.kanun_no, self.madde_no)


class AramaSonucu(list):
    """list[Sonuc] + çağrıya ait aşama süreleri (`sure_ms`) ve reranker'ın çalışıp çalışmadığı."""

    def __init__(self, sonuclar=(), sure_ms=None, rerank=False):
        super().__init__(sonuclar)
        self.sure_ms = sure_ms or {}
        self.rerank = rerank


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


class HybridArama:
    """3-bacak WSUM hybrid arama (+ ops. reranker). Bağımlılıklar enjekte edilir → sahte nesnelerle test edilir.

    embedder : callable(str) -> (dense: list[float], sparse: dict[str, float])
    client   : qdrant_client.QdrantClient (ya da `query_points` sunan sahte nesne)
    bm25     : BM25Index
    reranker : `skorla(sorgu, metinler) -> list[float]` sunan nesne ya da None
    """

    def __init__(self, embedder, client, bm25, collection="mevzuat", aday_k=50,
                 agirliklar=(0.33, 0.33, 0.34), reranker=None, rerank_aday=20,
                 rerank_varsayilan=False, rerank_max_krk=3000):
        self.embedder = embedder
        self.client = client
        self.bm25 = bm25
        self.collection = collection
        self.aday_k = aday_k
        self.agirliklar = tuple(agirliklar)
        self.reranker = reranker
        self.rerank_aday = rerank_aday
        self.rerank_varsayilan = rerank_varsayilan
        self.rerank_max_krk = rerank_max_krk

    # -- yardımcılar --------------------------------------------------------
    def _filtre(self, yururlukte_only):
        if not yururlukte_only:
            return None
        from qdrant_client import models
        return models.Filter(must=[models.FieldCondition(
            key="yurutluk", match=models.MatchValue(value=YURURLUKTE))])

    def _sparse_vektor(self, sparse):
        from qdrant_client import models
        return models.SparseVector(indices=[int(k) for k in sparse.keys()],
                                   values=list(sparse.values()))

    def metin(self, madde_id):
        """Reranker'a giden madde metni (RERANK_MAX_KRK karaktere kesili)."""
        return (self.bm25.metinler.get(madde_id) or "")[: self.rerank_max_krk]

    def rerank_acik_mi(self, rerank):
        """İstek değeri None ise ayar varsayılanı; True ama reranker yüklü değilse hata."""
        acik = self.rerank_varsayilan if rerank is None else bool(rerank)
        if acik and self.reranker is None:
            raise ValueError("rerank istendi ama reranker yüklü değil (RERANK_BACKEND=kapali)")
        return acik

    # -- ana akış -----------------------------------------------------------
    def adaylar(self, sorgu, yururlukte_only=True):
        """Reranker ÖNCESİ tüm WSUM adayları (azalan puan) + payload haritası + süreler.
        → (sirali [(madde_id, puan)], payload {madde_id: payload}, sure_ms).

        Aday anahtarı madde_id: BM25'te korpus id'si, Qdrant noktasında payload `madde_id`'si — korpusta yoksa
        (index korpusun gerisinde) `BM25Index.kimlik` ile korpus id'sine bağlanır; payload Qdrant'ın döndürdüğü
        haliyle kalır. Ölçüm script'leri adayları bir kez çıkarıp reranker'ı ayrı aşamada koşmak için
        kullanır; gold eşleştirmesi için (kanun_no, madde_no) payload'dan okunur."""
        sure = {}
        t0 = time.perf_counter()
        dense, sparse = self.embedder(sorgu)
        sure["embed"] = _ms(t0)

        flt = self._filtre(yururlukte_only)

        t = time.perf_counter()
        dres = self.client.query_points(collection_name=self.collection, query=dense, using="dense",
                                        limit=self.aday_k, query_filter=flt, with_payload=True)
        sure["dense"] = _ms(t)
        t = time.perf_counter()
        sres = self.client.query_points(collection_name=self.collection,
                                        query=self._sparse_vektor(sparse), using="sparse",
                                        limit=self.aday_k, query_filter=flt, with_payload=True)
        sure["sparse"] = _ms(t)

        def anahtar(p):
            return self.bm25.kimlik(str(p.payload["madde_id"]), p.payload.get("madde_no"))

        d_skor = {anahtar(p): p.score for p in dres.points}
        s_skor = {anahtar(p): p.score for p in sres.points}
        payload = {anahtar(p): p.payload for p in dres.points}
        for p in sres.points:
            payload.setdefault(anahtar(p), p.payload)

        # klasik BM25 — yalnız yürürlükteki maddeler index'te (yururlukte_only'den bağımsız, eski davranış)
        t = time.perf_counter()
        bm_skorlar = np.asarray(self.bm25.bm25.get_scores(tokenize(sorgu)))
        # kararlı argsort(-skor) == sorted(range, key=-skor) → eşitlerde index sırası aynı
        en_iyi = np.argsort(-bm_skorlar, kind="stable")[: self.aday_k]
        b_skor = {}
        for i in en_iyi:
            if bm_skorlar[i] <= 0:
                continue
            mid = str(self.bm25.maddeler[i][2])
            b_skor[mid] = float(bm_skorlar[i])
            payload.setdefault(mid, self.bm25.payload(i))   # yalnız BM25'te: korpustan gerçek alanlar
        sure["bm25"] = _ms(t)

        t = time.perf_counter()
        puan = wsum_puan([d_skor, s_skor, b_skor], self.agirliklar)
        sirali = sorted(puan.items(), key=lambda x: -x[1])
        sure["fuzyon"] = _ms(t)
        return sirali, payload, sure

    def _sonuc(self, madde_id, payload, skor, rerank_skor=None):
        pl = payload.get(madde_id) or {}
        korpus = self.bm25.payloadlar.get(madde_id) or {}   # Qdrant payload'ında kanun_ad boşsa korpustan
        return Sonuc(madde_id=madde_id, kanun_no=str(pl.get("kanun_no", "")),
                     kanun_ad=pl.get("kanun_ad") or korpus.get("kanun_ad") or "",
                     madde_no=str(pl.get("madde_no", "")), skor=float(skor),
                     rerank_skor=None if rerank_skor is None else float(rerank_skor))

    def ara(self, sorgu, top_k=10, yururlukte_only=True, rerank=None):
        """Sorgu → top_k madde (AramaSonucu). rerank: None=ayar varsayılanı, True/False=zorla."""
        t_bas = time.perf_counter()
        acik = self.rerank_acik_mi(rerank)
        sirali, payload, sure = self.adaylar(sorgu, yururlukte_only)

        rerank_skor = {}
        t = time.perf_counter()
        if acik and sirali:
            bas = sirali[: self.rerank_aday]
            skorlar = self.reranker.skorla(sorgu, [self.metin(k) for k, _ in bas])
            rerank_skor = {k: s for (k, _), s in zip(bas, skorlar)}
            # kararlı sıralama: eşit rerank skorunda WSUM sırası korunur; RERANK_ADAY sonrası dokunulmaz
            bas = sorted(bas, key=lambda x: -rerank_skor[x[0]])
            sirali = bas + sirali[self.rerank_aday:]
        sure["rerank"] = _ms(t) if acik else 0.0

        sonuclar = [self._sonuc(k, payload, sk, rerank_skor.get(k)) for k, sk in sirali[:top_k]]
        sure["toplam"] = _ms(t_bas)
        return AramaSonucu(sonuclar, sure_ms=sure, rerank=acik)
