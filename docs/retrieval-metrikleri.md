# Retrieval Metrikleri — Faz 5-6 Baseline

> Sistemin **ölçülmüş** durumu. Cetvel: dışarıdan gelen **altınset** gold set (21.737 sızıntısız
> sorgu; `ilgi`=sorgu, kanun_no+madde_no=doğru madde). Kapsam: retrieval'da biter (CLAUDE.md).
> Son güncelleme: 2026-07-02.

## Sistem mimarisi (ölçülen)

```
Korpus (31.416 madde) → BGE-M3 embed (Colab, dense+sparse) → Qdrant (dense+sparse+payload)
Sorgu → BGE-M3 embed (PC) → dense + BGE-sparse (Qdrant) + klasik-BM25 (rank_bm25)
        → 3-bacak WSUM füzyon (EŞİT) + yürürlük filtresi (yalnız yürürlükte)
```

- **Embedder:** BGE-M3 (ADR-0007). Dense=CLS pooling (FlagEmbedding ile birebir, 0.9998 aynı-metin).
- **Vektör store:** Qdrant (ADR-0008), dense + BGE-sparse.
- **Füzyon:** 3-bacak WSUM (dense + BGE-sparse + klasik-BM25), min-max normalize ağırlıklı toplam.
  Evrim: RRF → WSUM_050 (2-bacak) → 3-bacak EŞİT (ÖLÇÜM 4-5). Klasik BM25 = rank_bm25, korpus text.

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

## Füzyon: WSUM_050 (RRF yerine) — UYGULANDI

RRF sadece sırayı kullanır, gerçek skoru atar. WSUM_050 = skorları min-max normalize edip
0.5*dense + 0.5*sparse topla → skor-büyüklüğü bilgisi korunur. `search_qdrant.py` bunu kullanır.

| Metrik | RRF | WSUM_050 | Fark |
|---|---|---|---|
| R@1 | 0.4215 | 0.4595 | **+0.038** |
| R@5 | 0.6080 | 0.6285 | +0.021 |
| R@10 | 0.6790 | 0.6855 | +0.007 |
| R@20 | 0.7320 | 0.7335 | +0.002 |
| R@50 | 0.7830 | 0.7810 | -0.002 |
| R@100 | 0.8095 | 0.8110 | +0.002 |
| MRR | 0.5094 | 0.5382 | **+0.029** |
| nDCG@10 | 0.5456 | 0.5696 | **+0.024** |

Kazanç **üst sıralarda** yoğun (R@1/MRR/nDCG), geniş recall değişmez → WSUM sıralamayı iyileştirir,
recall tavanını değil. **Sıfır maliyet** (füzyon yöntemi, aynı model/retriever). → kalıcı uygulandı.

## 3-bacak: + klasik BM25 (ÖLÇÜM 4-5) — UYGULANDI

Şu ana kadarki "sparse" = BGE-M3 **öğrenilmiş** sparse. Klasik **BM25** (rank_bm25, TF-IDF+doc-len)
korpus `text` üzerine ayrı bir üçüncü bacak olarak eklendi (metadata YOK → sızıntı yok). Klasik BM25
nadir/ayırt-edici terimlere IDF ile yüksek ağırlık verir → **madde-ayrımı darboğazına** keskin.

**ÖLÇÜM 4 (eşit ağırlık, 2000 sorgu):**

| Yöntem | R@1 | R@5 | R@10 | MRR | nDCG |
|---|---|---|---|---|---|
| WSUM_050 (2-bacak, önceki) | 0.4450 | 0.6120 | 0.6690 | 0.5185 | 0.5548 |
| **3-BACAK (+BM25)** | **0.4910** | **0.6560** | **0.7000** | **0.5626** | **0.5959** |
| BM25_ONLY | 0.3705 | 0.5305 | 0.5880 | 0.4394 | 0.4750 |

- Klasik BM25 tek başına R@10=0.588 → BGE-sparse ablasyonunu (0.526) **geçti.** Klasik BM25 daha güçlü
  sparse bacak. 3-bacak her metrikte +0.03/+0.05.

**ÖLÇÜM 5 (ağırlık taraması, 2000 sorgu; d=dense s=BGE-sparse b=BM25):**

| Yöntem | (d,s,b) | R@1 | R@5 | R@10 | MRR | nDCG |
|---|---|---|---|---|---|---|
| WSUM_050 (2-bacak) | (.50,.50,0) | 0.4465 | 0.6120 | 0.6690 | 0.5196 | 0.5556 |
| **EŞİT ← uygulandı** | (.33,.33,.34) | **0.4905** | **0.6545** | 0.6995 | **0.5622** | 0.5955 |
| DENSE_AĞIR | (.50,.20,.30) | 0.4885 | 0.6525 | **0.7095** | 0.5597 | **0.5957** |
| BM25_AĞIR | (.35,.15,.50) | 0.4715 | 0.6410 | 0.6960 | 0.5439 | 0.5804 |
| SPARSE_KIS | (.45,.10,.45) | 0.4870 | 0.6445 | 0.7005 | 0.5570 | 0.5916 |
| DENSE_BM25 (s yok) | (.50,0,.50) | 0.4660 | 0.6340 | 0.6905 | 0.5419 | 0.5778 |

- **EŞİT seçildi:** R@1/R@5/MRR (üst-sıra kalitesi) en iyi; ağırlık-ayarı yok → altınsete overfit yok.
  DENSE_AĞIR R@10'da +0.01 önde ama R@1/MRR gerisinde — üst-sıra tercih edildi. Farklar küçük (~0.01),
  ağırlığa tolerant. `search_qdrant.py` 3-bacak EŞİT kullanır.
- **BGE-sparse atılamaz:** DENSE_BM25 (s=0) en zayıf üçlü → üç bacak da katkı yapıyor (eş-anlam sinyali
  az ama gerçek). Ölçmeden atsaydık kaybederdik.
- **Yolculuk:** RRF 0.667 → WSUM_050 0.685 → 3-bacak 0.700 (R@10), R@1 0.436 → 0.491.
  GPU/fine-tune YOK, sadece füzyon + klasik BM25.

## Ablasyon: dense vs sparse vs hybrid (2000 sorgu)

| Yöntem | R@1 | R@5 | R@10 | MRR | nDCG |
|---|---|---|---|---|---|
| DENSE_ONLY | 0.4030 | 0.5665 | 0.6375 | 0.4747 | 0.5136 |
| SPARSE_ONLY | 0.2555 | 0.4470 | 0.5260 | 0.3382 | 0.3830 |
| HYBRID_RRF | 0.4225 | 0.6105 | 0.6690 | 0.5026 | 0.5427 |

- **Hybrid en iyi:** dense-only'dan +0.032, sparse-only'dan +0.143 → CLAUDE.md "hybrid=doğru vanilla" ispatı.
- **Dense baskın bacak:** anlam (0.637) >> kelime (0.526). Hukuk-resmi-dilde embedding belirleyici.
  İleride iyileştirme → dense'i güçlendir (fine-tune) en çok kazandırır.
- **Çok-versiyon toleransı (ölçüm 1):** KATI 0.667 ≈ AYNI_AD 0.667 (artefakt değil). AMA aynı-KANUN
  toleransı R@10=0.889 → sistem doğru KANUNU %89 buluyor, doğru MADDEYİ %67. Darboğaz = madde ayrımı.

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
| `scripts/search_qdrant.py` | 3-bacak arama (dense+BGE-sparse+klasik-BM25 WSUM+yürürlük) |
| `scripts/metrik_bm25.py` | ÖLÇÜM 4: klasik BM25 üçüncü bacak katkısı |
| `scripts/metrik_bm25_agirlik.py` | ÖLÇÜM 5: 3-bacak ağırlık taraması |
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
