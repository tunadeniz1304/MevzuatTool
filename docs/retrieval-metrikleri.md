# Retrieval Metrikleri — Faz 5-6 Baseline

> Sistemin **ölçülmüş** durumu. Cetvel: dışarıdan gelen **altınset** gold set (21.737 sızıntısız
> sorgu; `ilgi`=sorgu, kanun_no+madde_no=doğru madde). Kapsam: retrieval'da biter (CLAUDE.md).
> Son güncelleme: 2026-09-28 (Faz 6 kapanışı: reranker entegrasyonu, ONNX int8, servis, gecikme tablosu).

## Sistem mimarisi (ölçülen)

```
Korpus (31.416 madde) → BGE-M3 embed (Colab, dense+sparse) → Qdrant (dense+sparse+payload)
Sorgu → BGE-M3 embed (PC; torch FP32 ya da ONNX int8) → dense + BGE-sparse (Qdrant) + klasik-BM25
        → 3-bacak WSUM füzyon (EŞİT) + yürürlük filtresi (yalnız yürürlükte)
        → (ops., istek başına) bge-reranker-v2-m3 ilk 20 adayı yeniden sıralar     [ADR-0015]
Kütüphane: src/kanun/retrieval/search.py (HybridArama) · Servis: src/kanun/api/app.py (FastAPI)
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

## + Reranker (bge-reranker-v2-m3, top-50 aday), 2000 sorgu — ⚠️ 2-bacak RRF tabanı üzerinde

> Bu tablonun aday havuzu **2-bacak RRF**'tir (bugünkü 3-bacak WSUM değil). 3-bacak üstündeki ölçüm:
> aşağıda "3-bacak + reranker (ADR-0015)". Bu ölçüm 2026-09-28'de kütüphane koduyla **birebir** tekrarlandı (çapa).

| Metrik | Hybrid | +Reranker | Fark |
|---|---|---|---|
| Recall@1 | 0.4325 | 0.4525 | +0.020 |
| Recall@5 | 0.5980 | 0.6530 | +0.055 |
| Recall@10 | 0.6665 | 0.7060 | +0.040 |
| MRR | 0.5099 | 0.5411 | +0.031 |
| nDCG@10 | 0.5432 | 0.5784 | +0.035 |

- Reranker RRF tabanında **işe yarıyordu** (ADR-0009). Entegrasyon ADR-0015'te yapıldı; 3-bacak üstünde tablo aşağıda.

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

**3-bacak EŞİT tam profil (2000 sorgu, ADAY=200) vs WSUM_050 (2-bacak):**

| Metrik | WSUM_050 | 3-BACAK EŞİT | Fark |
|---|---|---|---|
| R@1 | 0.4605 | 0.4900 | +0.030 |
| R@5 | 0.6285 | 0.6680 | +0.040 |
| R@10 | 0.6855 | 0.7155 | +0.030 |
| R@20 | 0.7335 | 0.7550 | +0.022 |
| R@50 | 0.7810 | 0.7925 | +0.012 |
| R@75 | 0.7995 | 0.8120 | +0.013 |
| R@100 | 0.8110 | 0.8220 | +0.011 |
| MRR | 0.5387 | 0.5708 | +0.032 |
| nDCG@10 | 0.5700 | 0.6025 | +0.033 |

- Kazanç **üst-sıralarda yoğun** (R@1/5/10 +0.03/+0.04), geniş recall'da küçülür (R@100 +0.01). BM25 doğru
  maddeyi **tepeye taşıyor** (sıralama iyileştirmesi), korpus tavanını değil.

## Madde-seviyesi vs Kanun-seviyesi (3-bacak EŞİT, 2000 sorgu)

Aynı sıralama iki hedef tanımıyla puanlandı: **MADDE** = (kanun_no, madde_no) tam eşleşme (üretim katılığı);
**KANUN** = yalnız kanun_no eşleşme (doğru mevzuata ulaşıldı mı — madde-ince-ayrımı affedilir).

| Metrik | MADDE | KANUN | Fark |
|---|---|---|---|
| R@1 | 0.4900 | 0.7280 | +0.238 |
| R@5 | 0.6680 | 0.8735 | +0.206 |
| **R@10** | 0.7155 | **0.9110** | +0.196 |
| R@20 | 0.7550 | 0.9370 | +0.182 |
| R@50 | 0.7925 | 0.9590 | +0.167 |
| R@75 | 0.8120 | 0.9655 | +0.154 |
| R@100 | 0.8220 | **0.9665** | +0.145 |
| MRR | 0.5708 | 0.7953 | +0.225 |
| nDCG@10 | 0.6025 | 0.8214 | +0.219 |

- **Darboğaz nicelenmiş:** sistem doğru **KANUNU** R@10=%91 (R@100=%97) buluyor ama doğru **MADDEYİ** %72.
  Fark ~%20 = "madde-ayrımı darboğazı". "Düşük" görünen madde-R@50/75/100 aslında **erişim başarısızlığı
  DEĞİL** — doğru mevzuata ulaşılıyor, aynı kanun içinde komşu maddeler ayrıştırılamıyor.
- **Gerçek erişim tavanı** = KANUN R@100 (0.967), madde 0.822 değil. Kalan %3.3: korpus-dışı + çok-versiyonlu
  kanun artefaktı.
- **İyileştirme yönü:** darboğaz erişimde değil sıralamada → **reranker** (top-50 aday içinde metin-bazlı
  ince madde-kıyası) ve **fine-tune** (dense'i madde-ayırt edecek şekilde) tam bu boşluğu hedefler. Madde
  R@10 teorik tavanı = KANUN eğrisi 0.91. Query expansion GEREKSİZ (kapsama zaten yüksek).

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

## 3-bacak + reranker (ADR-0015) — 2000 sorgu, FP32

Ayrıntı + eşleştirilmiş testler: [`olcum-sonuclari/rerank-3bacak.md`](olcum-sonuclari/rerank-3bacak.md).

| Konfig | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|
| Taban (3-bacak WSUM, reranker yok) | **0.4810** | 0.6455 | 0.6885 | **0.5515** | 0.5847 |
| + reranker ADAY=10 / 512 | 0.4705 | 0.6585 | 0.6885 | 0.5502 | 0.5842 |
| + reranker **ADAY=20 / 512** (önerilen) | 0.4645 | **0.6635** | **0.7110** | 0.5501 | **0.5893** |
| + reranker ADAY=30 / 512 | 0.4570 | 0.6585 | 0.7100 | 0.5442 | 0.5845 |
| + reranker ADAY=50 / 512 | 0.4485 | 0.6550 | 0.7035 | 0.5352 | 0.5761 |

- ⚠️ **Taban 0.700 değil 0.688:** Qdrant index'i (eski Colab `meta.json`) güncel korpusla 1.678 maddede yürürlük
  uyuşmazlığı taşıyor → 2000 sorgunun 37'sinin doğru maddesi dense/sparse'ta "mülga" filtreleniyor. Korpus
  yeniden embed'i bu fazın kapsamı dışı; yeni taban 0.688 (sayılar değil, index verisi değişti).
- Reranker 3-bacak üstünde **R@10'u artırıyor** (+0.0225, z=+4.35) ama **R@1/MRR'yi düşürüyor** (klasik BM25 bacağı
  üst sırayı reranker'ın ulaşabildiğinin üstüne çıkarmış). V-2 kuralı tutmadı → **varsayılan kapalı**, istek başına
  `rerank=true`. max_len 256 her ADAY'da 512'den kötü (N=1000).

## ONNX + dinamik int8 (ADR-0016) — kalite

| Embed backend | N | R@1 | R@10 | MRR@10 | Dense kosinüs (torch'a) | Model |
|---|---|---|---|---|---|---|
| torch FP32 (taban) | 2000 | 0.4810 | 0.6885 | 0.5515 | 1 | 2.27 GB |
| ONNX FP32 | 2000 | 0.4810 | 0.6885 | 0.5515 | 1.000000 (N=200) | 2.27 GB |
| ONNX int8 (son 4 katman FP32) | 2000 | 0.4795 | 0.6880 | 0.5510 | 0.99116 ort. / 0.986 min (N=200) | 0.72 GB |

- Reranker int8 (tam int8, 0.57 GB): FP32'ye top-10 kesişimi ort. **0.950** (min 0.90; 50 liste × 20 aday).
- int8 embed + int8 reranker (20/512), ilk 200 sorgu (eşleştirilmiş): R@1 0.425 / R@10 0.645 / MRR 0.504 —
  aynı 200 sorguda torch FP32 + torch reranker: 0.400 / 0.650 / 0.487 (ΔR@10 −0.005, eşik −0.01 içinde).
  2000 sorguluk int8-reranker kalitesi **ölçülmedi** (CPU'da ~0.7 sn/çift → 2000×20 çift ≈ 7-8 saat).

## Gecikme × kalite — FP32 vs int8, reranker açık/kapalı (CPU, ADR-0016)

Ham veri: [`olcum-sonuclari/gecikme-2026-09-28.json`](olcum-sonuclari/gecikme-2026-09-28.json) · Script: `scripts/kanun/retrieval/metrik_gecikme.py`.
Ortam: i5-11300H (4 çekirdek / 8 thread), 15.8 GB RAM, Windows 11, Python 3.11, onnxruntime 1.30.0 CPUExecutionProvider,
torch 2.5.1 (CPU'da), Qdrant v1.18.0 yerel Docker. Protokol: gold SEED 4721 ilk N=200 uygun sorgu, 10 ısınma sorgusu ölçüm
dışı, sıralı tek istek, 4 thread, model yükleme + BM25 kurulumu ölçüm dışı; her satır ayrı süreçte. Süreler ms (toplam =
embed + 3 bacak + füzyon + reranker). Kalite sütunları **2000 sorgu** (`rerank_3bacak_rapor.json`).

| # | Embed | Reranker | p50 | p95 | p99 | p95 embed | p95 rerank | R@1 | R@10 | MRR@10 | nDCG@10 | Tepe RSS (MB) | N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | torch FP32 | kapalı | 412 | 708 | 831 | 672 | – | 0.481 | 0.689 | 0.551 | 0.585 | 3076 | 200 |
| B | ONNX FP32 | kapalı | 253 | 511 | 559 | 474 | – | 0.481 | 0.689 | 0.552 | 0.585 | 2597 | 200 |
| **C** | **ONNX int8** | kapalı | **132** | **253** | 382 | 215 | – | 0.480 | 0.688 | 0.551 | 0.584 | 2325 | 200 |
| D | torch FP32 | torch FP32 (20/512) | ölçülmedi ¹ | | | | | 0.465 ² | 0.711 ² | 0.550 ² | 0.589 ² | | |
| E | ONNX int8 | ONNX int8 (20/512) | 14622 | 16121 | 17860 | 286 | 15965 | ölçülmedi ³ | ölçülmedi ³ | ölçülmedi ³ | ölçülmedi ³ | 3806 | 200 |
| F | ONNX int8 | ONNX int8 (50/512) | ölçülmedi ¹ | | | | | | | | | | |
| C-http | ONNX int8, FastAPI | kapalı | ölçülmedi ¹ | | | | | | | | | | |

¹ **Ölçülmedi — bellek:** F koşusu 20/100 sorguda Qdrant zaman aşımıyla düştü, D ve C-http başlayamadan durduruldu; makine
  (15.8 GB, WSL VM'i ~8 GB tutuyor) kritik bellek sıkışmasına girdi ve ağır işlerin yeniden başlatılmaması gerekti.
  Tahmin (ölçüm değil, tabloya yazılmadı): F ≈ 50 çift × ~0.72 sn ≈ 36 sn/sorgu; D, E ile aynı mertebede (saniyeler).
² D'nin kalitesi = FP32 reranker taramasının ADAY=20/512 satırı (2000 sorgu, GPU'da çevrimdışı ölçüldü; kalite
  donanımdan bağımsız).
³ int8 embed + int8 reranker 2000 sorguda ölçülmedi (CPU'da ≈ 7-8 saat). İlk 200 sorguda (eşleştirilmiş): R@1 0.425 /
  R@10 0.645 / MRR 0.504; aynı 200'de torch FP32 + torch reranker 0.400 / 0.650 / 0.487, taban 0.420 / 0.615 / 0.486.

**Okuma:**
- **int8 embed işe yarıyor:** embed p95 672 → 215 ms (0.32×), toplam p95 708 → 253 ms, bellek −750 MB, kalite farkı
  R@10 −0.0005. V-3 bütçesi (reranker-kapalı int8 p95 ≤ 400 ms) **✓**. ONNX'in quantization'sız katkısı (B) ~1.4×.
- **Reranker CPU'da bütçeye sığmıyor:** E p95 16.1 sn (bütçe 1.5 sn, ~10×); süre neredeyse tamamen reranker
  (20 çift × ~0.7 sn — cross-encoder her çift için 512 token'lık tam XLM-R-large geçişi). Bu, ADR-0015'in
  "varsayılan kapalı" kararını kalite kuralından bağımsız olarak da destekliyor.
- p99 N=200'de ≈ en yavaş 2 sorgu → düşük güvenilirlik; bacak süreleri (dense/sparse/BM25) her satırda ~10-25 ms.
- Servis ek yükü (C-http − C) ölçülmedi; servis doğruluğu `tests/kanun/test_api.py` ile (sahte arama) test edildi.

## Araçlar

Tüm script'ler `scripts/kanun/retrieval/` altında; kütüphane `src/kanun/retrieval/`, servis `src/kanun/api/`.

| Yol | İş |
|---|---|
| `src/kanun/retrieval/search.py` | `HybridArama`: 3-bacak WSUM + yürürlük filtresi + ops. reranker (kütüphane) |
| `src/kanun/retrieval/config.py` · `fabrika.py` | Ortam değişkeni ayarları · backend seçimi (torch / onnx-fp32 / onnx-int8) |
| `src/kanun/retrieval/embed.py` · `embed_onnx.py` | BGE-M3 sorgu embed (torch) · ONNX Runtime karşılığı |
| `src/kanun/retrieval/rerank.py` | `TorchReranker` / `OnnxReranker` (bge-reranker-v2-m3) |
| `src/kanun/retrieval/olcum.py` | Ortak gold örnekleme (SEED 4721) + R@k/MRR/nDCG |
| `src/kanun/api/app.py` | FastAPI `/ara`, `/saglik` (ADR-0017) |
| `ingest_qdrant.py` | Colab vektörlerini Qdrant'a yükle (+ `yurutluk` payload index) |
| `search_qdrant.py` | Arama CLI (kütüphanenin ince sarmalayıcısı) |
| `esdeger_kontrol.py` | Kütüphane = eski script (50 sorgu, birebir) |
| `metrik_bm25.py` · `metrik_bm25_agirlik.py` | ÖLÇÜM 4 (3. bacak) · ÖLÇÜM 5 (ağırlık taraması) |
| `metrik_olc.py` · `metrik_egri.py` · `metrik_ablasyon.py` | R@k/MRR/nDCG · recall eğrisi · ablasyon (eski 2-bacak) |
| `metrik_rerank_3bacak.py` | Reranker çapa + ADAY×max_len taraması (ADR-0015) |
| `onnx_export.py` · `onnx_quantize.py` | FP32 ONNX export · dinamik int8 (ADR-0016) |
| `metrik_gecikme.py` | p50/p95/p99 × kalite tablosu (A–F + HTTP) |
| `metrik_rerank.py` · `rerank_hazirla.py` + `colab/rerank_olc.ipynb` | Eski RRF-tabanlı reranker ölçümü (ADR-0009) |
| `colab/bge_m3_embed.ipynb` | Korpus embed (Colab) |

## Sonraki adımlar (açık)

- **Qdrant index'ini güncel korpusla yeniden embed et** (1.678 maddelik yürürlük uyuşmazlığı → taban 0.688 → ~0.70).
- Reranker'ı R@1'i bozmadan kullanmak: WSUM skoruyla reranker skorunu **birleştirmek** (şimdi saf yer değiştirme).
- Reranker'ı GPU'lu ayrı bir serviste koşmak (CPU'da ~15 sn/sorgu, bütçe 1.5 sn).
- 2000 sorguluk int8-reranker kalitesi (GPU'da ya da gece koşusu).
- Çok-versiyonlu kanun toleransıyla "gerçek" R@10.
- (Future, kapsam-dışı) fine-tune; statik int8; atıf modu.
