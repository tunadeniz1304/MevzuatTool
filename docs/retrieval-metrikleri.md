# Retrieval Metrikleri — Faz 5-6 Baseline

> Sistemin **ölçülmüş** durumu. Cetvel: dışarıdan gelen **altınset** gold set (21.737 sızıntısız
> sorgu; `ilgi`=sorgu, kanun_no+madde_no=doğru madde). Kapsam: retrieval'da biter (CLAUDE.md).
> Son güncelleme: 2026-07-02.

## Sistem mimarisi (ölçülen)

```
Korpus (31.416 madde) → BGE-M3 embed (Colab, dense+sparse) → Qdrant (dense+sparse+payload)
Sorgu → BGE-M3 embed (PC, transformers CLS) → Qdrant hybrid (dense+sparse) → RRF füzyon
        + yürürlük filtresi (yalnız yürürlükte maddeler)
```

- **Embedder:** BGE-M3 (ADR-0007). Dense=CLS pooling (FlagEmbedding ile birebir, 0.9998 aynı-metin).
- **Vektör store:** Qdrant (ADR-0008), RRF füzyon native.
- **Sparse:** BGE-M3 öğrenilmiş sparse (klasik BM25 değil; `sparse_linear.pt`). BM25 kıyası: future.

## Baseline: Hybrid (dense+sparse+RRF), 2000 sorgu

| Metrik | Değer |
|---|---|
| Recall@1 | 0.436 |
| Recall@5 | 0.598 |
| **Recall@10** | **0.667** |
| Recall@50 | 0.775 |
| Recall@100 | 0.809 |
| MRR | 0.507 |
| nDCG@10 | 0.545 |

- **Not:** **Hazır** BGE-M3 ile R@10 0.667 (fine-tune yok; çok-versiyonlu kanun cezası + gold katılığı
  skoru aşağı çeker).
- **Recall eğrisi teşhisi:** R@100 (0.809) >> R@10 (0.667) → doğru madde **getiriliyor** ama **sıralama kötü**
  → reranker adayı. (%19 top-100'de bile yok; bir kısmı çok-versiyonlu kanun artefaktı.)

## + Reranker (bge-reranker-v2-m3, top-50 aday), 2000 sorgu

| Metrik | Hybrid | +Reranker | Fark |
|---|---|---|---|
| Recall@1 | 0.4325 | 0.4525 | +0.020 |
| Recall@5 | 0.5980 | 0.6530 | +0.055 |
| Recall@10 | 0.6665 | 0.7060 | +0.040 |
| MRR | 0.5099 | 0.5411 | +0.031 |
| nDCG@10 | 0.5432 | 0.5784 | +0.035 |

- Reranker **işe yarıyor** (ADR-0009). Hybrid+reranker R@10=0.706.
- **Entegrasyon ertelendi** (yerel 4GB VRAM darboğazı); ölçüm-kanıtı + scriptler saklı.

## Bilinen sınırlar / gözlemler

1. **Çok-versiyonlu kanun:** Yapılandırma kanunları (6111/6736/7143/7326/7440 m.5) aynı konu, farklı no.
   Gold "6111" derken sistem "7326" getirir → haksız 0. Gerçek kalite ham sayıdan yüksek.
2. **Korpus-dışı sorgu:** "Hobi bahçesi" gibi kanunlarda geçmeyen konu → sistem en yakın çöpü getirir
   (yüksek RRF skoruyla bile). RRF skoru "alaka" değil "iki-bacak hemfikirliği" ölçer. → eşik/threshold future.
3. **Cetvel = altınset:** resmi-dilli (`ilgi`) sorgular + tek-doğru-madde. Vatandaş-dilli gold (bizim
   workflow, tamamlanmadı) farklı sayı verebilir.

## Araçlar

| Script | İş |
|---|---|
| `scripts/ingest_qdrant.py` | Colab vektörlerini Qdrant'a yükle |
| `scripts/search_qdrant.py` | Hybrid arama (dense+sparse+RRF+yürürlük) |
| `scripts/metrik_olc.py` | R@1/5/10 + MRR + nDCG (hybrid) |
| `scripts/metrik_egri.py` | Recall eğrisi R@1/5/10/50/100 |
| `scripts/metrik_rerank.py` | Reranker deneyi (yerel, 4GB'da yavaş) |
| `scripts/rerank_hazirla.py` + `colab/rerank_olc.ipynb` | Reranker ölçümü (Colab T4) |
| `src/mevzuat_tool/retrieval/embed.py` | BGE-M3 sorgu embed (dense+sparse) |
| `colab/bge_m3_embed.ipynb` | Korpus embed (Colab) |

## Sonraki adımlar (açık)

- Reranker'ı kalıcı entegre (Faz 6/7, GPU/servis çözümü sonrası).
- BM25 (klasik) ekle + hybrid'e kıyasla (metriğe bak).
- Ablasyon: dense-only vs hybrid (sparse'ın katkısını ölç).
- Çok-versiyonlu kanun toleransıyla "gerçek" R@10.
- (Future, kapsam-dışı) fine-tune Colab'da.
