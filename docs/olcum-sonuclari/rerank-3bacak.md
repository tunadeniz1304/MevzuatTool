# Reranker — 3-bacak WSUM aday havuzu üzerinde (ADR-0015)

> Ölçüm: 2026-09-27/28 · Script: `scripts/kanun/retrieval/metrik_rerank_3bacak.py`
> Model: `BAAI/bge-reranker-v2-m3` (cross-encoder, FP32, torch; RTX 3050 Ti 4 GB — yalnız çevrimdışı kalite ölçümü, V-4)
> Protokol: `data/gold/altinset_temiz.jsonl`, `random.seed(4721)` + shuffle, doğru maddesi mülga/yok olan sorgu atlanır,
> N=2000 (256 taraması N=1000, aynı seed'in ilk 1000'i — eşleştirilmiş). MRR = MRR@10 (`metrik_bm25` tanımı).
> Aday havuzu: `HybridArama` 3-bacak WSUM (`ADAY_K=50` / bacak), fused listenin ilk 50'si. Madde metni reranker'a
> `RERANK_MAX_KRK=3000` karaktere kesilip verilir, tokenizer `max_len`'de keser.

## 1. Çapa — ADR-0009 ölçümü aynı girdiyle yeniden üretildi

`colab/rerank_input.jsonl` (2-bacak **RRF** top-50, metin 1500 krk), kütüphanedeki `TorchReranker` ile:

| Metrik | Hybrid (RRF) | +Reranker | Fark | ADR-0009 (Colab T4) |
|---|---|---|---|---|
| R@1 | 0.4325 | 0.4525 | +0.0200 | 0.4325 → 0.4525 |
| R@5 | 0.5980 | 0.6530 | +0.0550 | 0.5980 → 0.6530 |
| **R@10** | 0.6665 | **0.7060** | +0.0395 | 0.6665 → **0.7060** |
| MRR (tüm 50 aday) | 0.5099 | 0.5411 | +0.0312 | 0.5099 → 0.5411 |
| nDCG@10 | 0.5432 | 0.5784 | +0.0352 | 0.5432 → 0.5784 |

→ **Birebir aynı.** Entegre edilen kod ADR-0009'daki ölçümle aynı şeyi yapıyor (kabul: 0.7060 ± 0.005 ✓).

## 2. Taban — 3-bacak WSUM, reranker yok (bugünkü sistem)

| Kaynak | N | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|---|
| `metrik_bm25.py` (ÖLÇÜM 4, eşit 1/3 ağırlık) | 2000 | 0.4800 | 0.6445 | 0.6880 | 0.5508 | 0.5842 |
| `HybridArama` (.33/.33/.34) | 2000 | 0.4810 | 0.6455 | 0.6885 | 0.5515 | 0.5847 |

⚠️ Belgelenen 0.7000'dan **−0.012**. Teşhis: Qdrant index'i (Colab embed'i, `colab/outputs/meta.json`) güncel korpusla
(yapısal-sadakat fazları sonrası yeniden üretilen `korpus.jsonl`) **1.678 maddede yürürlük uyuşmazlığı** içeriyor;
2000 sorgunun **37'sinin** doğru maddesi Qdrant'ta "mülga" işaretli → dense/sparse bacağı yürürlük filtresiyle onu hiç
getiremez (≈ 0.018 tavan kaybı). Ayrıca uygun-sorgu kümesi 37 sorgu değişti (1963/2000 ortak). Qdrant 1.18.0 ve
payload index sonuçları değiştirmiyor (30/30 aynı). Korpus yeniden embed'i kapsam dışı → **yeni taban = 0.688**.

## 3. 3-bacak + reranker taraması (FP32)

| ADAY | max_len | N | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 | ΔR@10 | ΔMRR | ΔR@1 |
|---|---|---|---|---|---|---|---|---|---|---|
| — (taban) | — | 2000 | 0.4810 | 0.6455 | 0.6885 | 0.5515 | 0.5847 | | | |
| 10 | 512 | 2000 | 0.4705 | 0.6585 | 0.6885 | 0.5502 | 0.5842 | +0.0000 | −0.0013 | −0.0105 |
| **20** | **512** | 2000 | 0.4645 | **0.6635** | **0.7110** | 0.5501 | **0.5893** | **+0.0225** | −0.0014 | −0.0165 |
| 30 | 512 | 2000 | 0.4570 | 0.6585 | 0.7100 | 0.5442 | 0.5845 | +0.0215 | −0.0073 | −0.0240 |
| 50 | 512 | 2000 | 0.4485 | 0.6550 | 0.7035 | 0.5352 | 0.5761 | +0.0150 | −0.0163 | −0.0325 |

max_len 256 (N=1000; Δ'lar aynı 1000 sorgunun tabanına göre — taban R@1 0.4670 / R@10 0.6800 / MRR 0.5406):

| ADAY | 256: R@1 | 256: R@10 | 256: MRR@10 | 512 (aynı 1000): R@1 | 512: R@10 | 512: MRR@10 |
|---|---|---|---|---|---|---|
| 10 | 0.4280 | 0.6800 | 0.5096 | 0.4690 | 0.6800 | 0.5457 |
| 20 | 0.4290 | 0.7010 | 0.5132 | 0.4620 | 0.7100 | 0.5482 |
| 30 | 0.4170 | 0.6870 | 0.5024 | 0.4570 | 0.7100 | 0.5429 |
| 50 | 0.4050 | 0.6750 | 0.4910 | 0.4450 | 0.7060 | 0.5317 |

**Eşleştirilmiş kazanç/kayıp (N=2000, sorgu bazında; z = (kazanç − kayıp)/√(kazanç + kayıp)):**

| Konfig | Metrik | reranker kazandırdı | kaybettirdi | net | z |
|---|---|---|---|---|---|
| ADAY=20/512 | R@1 | 194 | 227 | −33 | −1.61 (anlamlı değil) |
| ADAY=20/512 | R@10 | 76 | 31 | +45 | **+4.35** |
| ADAY=50/512 | R@1 | 182 | 247 | −65 | **−3.14** |
| ADAY=50/512 | R@10 | 107 | 77 | +30 | +2.21 |

## 4. Yorum

- **Reranker ilk-10'a taşıyor, 1. sırayı bozuyor.** R@5/R@10/nDCG artıyor (ADAY=20: R@10 +0.0225, z=+4.35), ama R@1 ve
  MRR düşüyor. ADAY=10'da ilk 10'un kümesi aynı kalıyor (R@10 değişmez), yalnız sıra değişiyor → R@1 −0.0105: reranker
  aynı 10 aday içinde 1. sırayı WSUM'dan **daha kötü** seçiyor. Bu yüzden eski RRF tabanındaki R@1 kazancı (+0.020)
  3-bacak'ta tersine döndü: klasik BM25 bacağı üst sırayı zaten reranker'ın tek başına ulaşabildiği seviyenin
  (~0.45-0.47) üstüne (0.481) çıkarmıştı.
- **Aday sayısı arttıkça zarar büyüyor** (ADAY=50: R@1 −0.0325, anlamlı): reranker'a daha çok "yakın komşu madde"
  gösterildikçe (aynı kanunun komşu maddeleri, çok-versiyonlu kanunlar) yanlış olanı tepeye taşıma şansı artıyor.
- **max_len 256** her ADAY'da 512'den kötü (R@1 −0.03/−0.04): madde metninin ikinci yarısındaki bilgi (istisna/ceza
  fıkraları) ayrım için gerekli.

## 5. Karar (ADR-0015)

- **V-2 kuralı** (ADAY=50/512: ΔR@10 ≥ +0.02 **ve** ΔMRR ≥ +0.01 **ve** ΔR@1 ≥ 0): +0.0150 / −0.0163 / −0.0325 →
  **tutmadı** → reranker kodu kalır, **varsayılan KAPALI** (`RERANK_VARSAYILAN=0`); istek başına `rerank=true`.
- **Önerilen ADAY/max_len = 20 / 512.** Kural (ADAY=50/512 R@10'una göre en fazla 0.005 düşük olan en ucuz konfig)
  harfiyen 20/256'yı verirdi (N=1000'de R@10 0.7010 = 0.7060 − 0.005, tam sınırda); ama 20/256 aynı sorgularda
  20/512'den R@1 −0.033, MRR −0.035 kötü ve eşik sınırında (gürültü içinde) → **sapma: 20/512 seçildi** (R@10'da
  bütün taramanın en iyisi, R@1 kaybı anlamlı değil).
