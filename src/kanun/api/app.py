# -*- coding: utf-8 -*-
"""FastAPI retrieval servisi — `POST /ara`, `GET /saglik` (ADR-0017; atıf modu ADR-0019).

Modeller, BM25 index'i, Qdrant client'ı ve atıf indeksi `lifespan`'da BİR KEZ kurulur (süreç başına
bellekte; tek worker). Ayarlar `kanun.retrieval.config` ortam değişkenlerinden (EMBED_BACKEND, ...).
Endpoint'ler `def` (async değil): model çıkarımı CPU-bağlı, FastAPI bunları thread havuzunda koşturur.

`POST /ara` isteğinin `mod` alanı: 'otomatik' (varsayılan — sorgu atıf olarak ayrıştırılıp korpusta
çözülürse atıf modu, değilse doğal dil) | 'atif' | 'dogal'. Kullanılan mod `config.mod`'da döner. Doğal
dil yanıtı ESKİ ŞEMAYLA birebir aynıdır; atıfa ait alanlar yalnız atıf denendiğinde görünür:
  - sonuclar[].atif : atıf modunda her sonuçta — mevzuat_id, madde_tipi, madde_baslik, yurutluk,
                      atif_sira, alt_parca {fikra, bent, metin, yurutluk, tolerans}, tasindigi_kanun, uyarilar
  - atif            : atıf denendiyse (atıf modu ya da doğal dile düşüş) — durum, dusus, aciklama,
                      atiflar [{ham, kanun_nolari, madde_no, fikra, bent, durum, coklu_mevzuat, ...}]
Atıf modunda skor = 1.0 (kesin eşleşme, sıra = atıfların sorgudaki sırası), reranker ve yürürlük filtresi
uygulanmaz (mülga madde `yurutluk` ile döner); `metin` belirtilmezse atıf modunda madde metni döner.

Generation/LLM endpoint'i YOK — pipeline retrieval'da biter (ADR-0001).
"""
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_serializer

from kanun.retrieval.atif_getir import KorpusDegisti, modlu_ara
from kanun.retrieval.config import ayarlar_oku


class AraIstek(BaseModel):
    sorgu: str = Field(..., min_length=1, max_length=2000, description="Doğal dil soru ya da atıf")
    top_k: int = Field(10, ge=1, le=50)
    rerank: Optional[bool] = Field(None, description="null = sunucu varsayılanı (RERANK_VARSAYILAN)")
    yururlukte_only: bool = True
    metin: Optional[bool] = Field(None, description="madde metni dönsün mü; null = mod varsayılanı "
                                                    "(doğal dil: false, atıf: true)")
    mod: Literal["otomatik", "atif", "dogal"] = Field(
        "otomatik", description="otomatik: atıf ayrıştırılıp çözülürse atıf modu, değilse doğal dil; "
                                "atif: atıf olarak dene (olmazsa doğal dile düşer); dogal: yalnız doğal dil")

    @field_validator("sorgu")
    @classmethod
    def bos_olmasin(cls, v):
        if not v.strip():
            raise ValueError("sorgu boş olamaz")
        return v


def _bos_atifi_gizle(d):
    """Doğal dil yanıtı eski şemayla birebir kalsın: `atif` yoksa anahtar hiç yazılmaz."""
    if d.get("atif") is None:
        d.pop("atif", None)
    return d


class AltParcaModel(BaseModel):
    fikra: Optional[str] = None             # '(2)'; numarasız tek fıkrada null
    bent: Optional[str] = None              # 'a)' / '1.'; fıkra düzeyinde null
    metin: str
    yurutluk: str
    tolerans: Optional[str] = None          # 'fikra->bent': 'fıkra N' atfı 'N.' bendine çözüldü


class AtifSonucModel(BaseModel):
    mevzuat_id: str
    madde_tipi: str
    madde_baslik: Optional[str] = None
    yurutluk: str
    atif_sira: int                          # sorgudaki kaçıncı atfa ait (1-tabanlı)
    alt_parca: Optional[AltParcaModel] = None
    tasindigi_kanun: Optional[str] = None   # yönlendirme kaydı: hüküm bu kanuna işlenmiş
    uyarilar: list[str] = []


class SonucModel(BaseModel):
    sira: int
    madde_id: str
    kanun_no: str
    kanun_ad: str
    madde_no: str
    skor: float
    rerank_skor: Optional[float] = None
    metin: Optional[str] = None
    atif: Optional[AtifSonucModel] = Field(None, description="yalnız atıf modunda")

    @model_serializer(mode="wrap")
    def _serilestir(self, handler):
        return _bos_atifi_gizle(handler(self))


class AtifModel(BaseModel):
    ham: str
    kanun_nolari: list[str]
    kanun_kaynak: str                       # numara | kisaltma | ad | korpus_adi
    madde_no: str
    fikra: Optional[int] = None             # -1 = son fıkra
    bent: Optional[str] = None
    durum: Optional[str] = None             # eslesti | kanun_yok | madde_yok (null: çözülmedi)
    cozulen_madde_no: Optional[str] = None
    yorum: Optional[str] = None             # alternatif yorumla çözüldüyse: 'harf->bent' | 'roma->fikra'
    coklu_mevzuat: bool = False             # kanun_no çakışması: birden çok kanun döndü
    aciklama: Optional[str] = None


class AtifBilgiModel(BaseModel):
    durum: str                              # eslesti | kismi | eslesme_yok | ayristirilamadi | indeks_yok
    dusus: bool                             # atıf denendi ama doğal dile düşüldü
    aciklama: Optional[str] = None
    atiflar: list[AtifModel] = []


class AraYanit(BaseModel):
    sonuclar: list[SonucModel]
    sure_ms: dict[str, float]
    config: dict
    atif: Optional[AtifBilgiModel] = Field(None, description="atıf denendiyse (atıf modu ya da düşüş)")

    @model_serializer(mode="wrap")
    def _serilestir(self, handler):
        return _bos_atifi_gizle(handler(self))


def _config(ayar, arama, rerank):
    return {"embed_backend": ayar.embed_backend, "rerank_backend": ayar.rerank_backend,
            "rerank": rerank, "rerank_aday": arama.rerank_aday, "rerank_max_len": ayar.rerank_max_len,
            "aday_k": arama.aday_k, "agirliklar": list(arama.agirliklar),
            "rerank_varsayilan": arama.rerank_varsayilan}


def _atif_sonucu(sira, atif_sira, e, metin):
    md = e.metadata
    return SonucModel(
        sira=sira, madde_id=e.kayit.madde_id, kanun_no=e.kayit.kanun_no, kanun_ad=e.kayit.kanun_ad,
        madde_no=e.kayit.madde_no, skor=1.0, rerank_skor=None, metin=e.metin if metin else None,
        atif=AtifSonucModel(
            mevzuat_id=e.kayit.mevzuat_id, madde_tipi=md.get("madde_tipi") or e.kayit.madde_tipi,
            madde_baslik=md.get("madde_baslik"), yurutluk=md.get("yurutluk") or e.kayit.yurutluk,
            atif_sira=atif_sira, alt_parca=AltParcaModel(**asdict(e.alt_parca)) if e.alt_parca else None,
            tasindigi_kanun=md.get("tasindigi_kanun"), uyarilar=list(e.uyarilar)))


def _atif_bilgisi(sonuc):
    if sonuc.durum is None:
        return None
    cozumler = sonuc.cozumler or [None] * len(sonuc.atiflar)
    atiflar = [AtifModel(ham=a.ham, kanun_nolari=list(a.kanun_nolari), kanun_kaynak=a.kanun_kaynak,
                         madde_no=a.madde_no, fikra=a.fikra, bent=a.bent,
                         durum=c.durum if c else None,
                         cozulen_madde_no=c.yorum.madde_no if c and c.yorum else None,
                         yorum=c.yorum.aciklama if c and c.yorum else None,
                         coklu_mevzuat=bool(c and c.coklu_mevzuat), aciklama=c.aciklama if c else None)
               for a, c in zip(sonuc.atiflar, cozumler)]
    return AtifBilgiModel(durum=sonuc.durum, dusus=sonuc.dusus, aciklama=sonuc.aciklama, atiflar=atiflar)


def uygulama_olustur(arama_fabrika=None, ayar=None, atif_fabrika=None):
    """arama_fabrika: () -> HybridArama; atif_fabrika: () -> AtifIndeks. Testler sahte nesne verir
    (ağ/model yok). arama_fabrika verilip atif_fabrika verilmezse atıf indeksi yoktur (atıf denemesi
    doğal dile düşer); ikisi de verilmezse ikisi de ayarlardaki korpustan kurulur."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ayar = ayar or ayarlar_oku()
        if arama_fabrika is None:
            from kanun.retrieval.fabrika import arama_kur
            app.state.arama = arama_kur(app.state.ayar)
        else:
            app.state.arama = arama_fabrika()
        if atif_fabrika is not None:
            app.state.atif = atif_fabrika()
        elif arama_fabrika is None:
            from kanun.retrieval.atif_getir import atif_indeks_kur
            app.state.atif = atif_indeks_kur(app.state.ayar.korpus_yol)
        else:
            app.state.atif = None
        yield

    app = FastAPI(title="MevzuatTool retrieval", version="0.6.0", lifespan=lifespan,
                  description="Türk kanunları için madde getirme: atıf modu (kanun/madde/fıkra/bent → "
                              "kesin getirme) + doğal dil modu (3-bacak hybrid, ops. reranker). "
                              "Generation yok.")

    def arama_al(request: Request):
        return request.app.state.arama

    def atif_al(request: Request):
        return request.app.state.atif

    def ayar_al(request: Request):
        return request.app.state.ayar

    @app.get("/saglik")
    def saglik(arama=Depends(arama_al), atif=Depends(atif_al), ayar=Depends(ayar_al)):
        try:
            qdrant = bool(arama.client.collection_exists(arama.collection))
        except Exception:
            qdrant = False
        return {"durum": "ok" if qdrant else "qdrant-yok", "qdrant": qdrant,
                "embed_backend": ayar.embed_backend, "rerank_backend": ayar.rerank_backend,
                "rerank_aday": arama.rerank_aday, "rerank_varsayilan": arama.rerank_varsayilan,
                "madde_sayisi": len(arama.bm25), "atif_indeks": len(atif) if atif is not None else 0}

    @app.post("/ara", response_model=AraYanit)
    def ara(istek: AraIstek, arama=Depends(arama_al), atif=Depends(atif_al), ayar=Depends(ayar_al)):
        try:
            sonuc = modlu_ara(arama, atif, istek.sorgu, mod=istek.mod, top_k=istek.top_k,
                              yururlukte_only=istek.yururlukte_only, rerank=istek.rerank)
        except ValueError as e:          # ör. rerank=true ama RERANK_BACKEND=kapali
            raise HTTPException(status_code=400, detail=str(e))
        except KorpusDegisti as e:       # korpus dosyası servis açıkken değişmiş
            raise HTTPException(status_code=503, detail=str(e))
        metin = istek.metin if istek.metin is not None else sonuc.mod == "atif"
        if sonuc.mod == "atif":
            sonuclar = [_atif_sonucu(i, atif_sira, e, metin)
                        for i, (atif_sira, e) in enumerate(sonuc.satirlar, 1)]
            rerank, sure_ms = False, sonuc.sure_ms
        else:
            dogal = sonuc.dogal
            # metin madde_id ile (benzersiz): (kanun_no, madde_no) çakışan kanunlarda başka maddeyi verirdi
            sonuclar = [SonucModel(sira=i, madde_id=s.madde_id, kanun_no=s.kanun_no, kanun_ad=s.kanun_ad,
                                   madde_no=s.madde_no, skor=s.skor, rerank_skor=s.rerank_skor,
                                   metin=arama.bm25.metinler.get(s.madde_id) if metin else None)
                        for i, s in enumerate(dogal, 1)]
            rerank, sure_ms = dogal.rerank, dogal.sure_ms
        config = {**_config(ayar, arama, rerank), "mod": sonuc.mod, "istenen_mod": istek.mod}
        return AraYanit(sonuclar=sonuclar, sure_ms=sure_ms, config=config, atif=_atif_bilgisi(sonuc))

    return app


app = uygulama_olustur()
