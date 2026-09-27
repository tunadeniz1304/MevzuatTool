# -*- coding: utf-8 -*-
"""FastAPI retrieval servisi — `POST /ara`, `GET /saglik` (ADR-0017).

Modeller, BM25 index'i ve Qdrant client'ı `lifespan`'da BİR KEZ kurulur (süreç başına bellekte;
tek worker). Ayarlar `kanun.retrieval.config` ortam değişkenlerinden (EMBED_BACKEND, RERANK_BACKEND, ...).
Endpoint'ler `def` (async değil): model çıkarımı CPU-bağlı, FastAPI bunları thread havuzunda koşturur.

Generation/LLM endpoint'i YOK — pipeline retrieval'da biter (ADR-0001).
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from kanun.retrieval.config import ayarlar_oku


class AraIstek(BaseModel):
    sorgu: str = Field(..., min_length=1, max_length=2000, description="Doğal dil soru ya da atıf")
    top_k: int = Field(10, ge=1, le=50)
    rerank: Optional[bool] = Field(None, description="null = sunucu varsayılanı (RERANK_VARSAYILAN)")
    yururlukte_only: bool = True
    metin: bool = Field(False, description="true ise madde metni de döner")

    @field_validator("sorgu")
    @classmethod
    def bos_olmasin(cls, v):
        if not v.strip():
            raise ValueError("sorgu boş olamaz")
        return v


class SonucModel(BaseModel):
    sira: int
    madde_id: str
    kanun_no: str
    kanun_ad: str
    madde_no: str
    skor: float
    rerank_skor: Optional[float] = None
    metin: Optional[str] = None


class AraYanit(BaseModel):
    sonuclar: list[SonucModel]
    sure_ms: dict[str, float]
    config: dict


def _config(ayar, arama, rerank):
    return {"embed_backend": ayar.embed_backend, "rerank_backend": ayar.rerank_backend,
            "rerank": rerank, "rerank_aday": arama.rerank_aday, "rerank_max_len": ayar.rerank_max_len,
            "aday_k": arama.aday_k, "agirliklar": list(arama.agirliklar),
            "rerank_varsayilan": arama.rerank_varsayilan}


def uygulama_olustur(arama_fabrika=None, ayar=None):
    """arama_fabrika: () -> HybridArama. Testler sahte arama verir (ağ/model yok)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ayar = ayar or ayarlar_oku()
        if arama_fabrika is None:
            from kanun.retrieval.fabrika import arama_kur
            app.state.arama = arama_kur(app.state.ayar)
        else:
            app.state.arama = arama_fabrika()
        yield

    app = FastAPI(title="MevzuatTool retrieval", version="0.6.0", lifespan=lifespan,
                  description="Türk kanunları için 3-bacak hybrid (+ops. reranker) madde getirme. "
                              "Generation yok.")

    def arama_al(request: Request):
        return request.app.state.arama

    def ayar_al(request: Request):
        return request.app.state.ayar

    @app.get("/saglik")
    def saglik(arama=Depends(arama_al), ayar=Depends(ayar_al)):
        try:
            qdrant = bool(arama.client.collection_exists(arama.collection))
        except Exception:
            qdrant = False
        return {"durum": "ok" if qdrant else "qdrant-yok", "qdrant": qdrant,
                "embed_backend": ayar.embed_backend, "rerank_backend": ayar.rerank_backend,
                "rerank_aday": arama.rerank_aday, "rerank_varsayilan": arama.rerank_varsayilan,
                "madde_sayisi": len(arama.bm25)}

    @app.post("/ara", response_model=AraYanit)
    def ara(istek: AraIstek, arama=Depends(arama_al), ayar=Depends(ayar_al)):
        try:
            sonuc = arama.ara(istek.sorgu, top_k=istek.top_k, yururlukte_only=istek.yururlukte_only,
                              rerank=istek.rerank)
        except ValueError as e:          # ör. rerank=true ama RERANK_BACKEND=kapali
            raise HTTPException(status_code=400, detail=str(e))
        sonuclar = [SonucModel(sira=i, madde_id=s.madde_id, kanun_no=s.kanun_no, kanun_ad=s.kanun_ad,
                               madde_no=s.madde_no, skor=s.skor, rerank_skor=s.rerank_skor,
                               metin=arama.bm25.metinler.get(s.anahtar) if istek.metin else None)
                    for i, s in enumerate(sonuc, 1)]
        return AraYanit(sonuclar=sonuclar, sure_ms=sonuc.sure_ms, config=_config(ayar, arama, sonuc.rerank))

    return app


app = uygulama_olustur()
