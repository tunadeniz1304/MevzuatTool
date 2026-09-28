# Karar Kaydı (Architecture Decision Records — ADR)

Hafif ADR formatı. Her karar: bağlam → karar → durum → sonuç.
Güncel mimari görünümü: [`arch.md`](arch.md). Kapsam: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md).

**Durum etiketleri:** `Kabul edildi` · `Önerildi` · `Açık (karar bekliyor)` · `Reddedildi` · `Yerini aldı`

---

## ADR-0001 — Pipeline retrieval'da biter, generation kapsam dışı
- **Durum:** Kabul edildi
- **Bağlam:** Soruya cevap üreten LLM ile retrieval'ı aynı build'e bağlamak, projeyi ekip modeli kararına (Qwen vs.) bağımlı kılar.
- **Karar:** Pipeline yalnızca retrieval'a kadar kurulur. Generation, en sonda config'le takılan, OpenAI-uyumlu, swap'lanabilir bir endpoint olarak bırakılır.
- **Sonuç:** Build, LLM kararından bağımsız kalır; modüler sınır korunur.

## ADR-0010 — RAG tipi: vanilla RAG (graph/agentic/advanced değil)
- **Durum:** Kabul edildi
- **Bağlam:** RAG'ın birçok varyantı var (graph RAG, agentic RAG, advanced RAG). MVP için en hızlı, en debug'lanabilir ve dockerize'ı en temiz yaklaşım gerekiyor.
- **Karar:** **Vanilla RAG** kullanılır; graph/agentic/advanced RAG **yapılmaz** (future work). Bu MVP, vanilla RAG'ın yalnız **retrieval yarısını** kapsar.
- **Sonuç:** "Vanilla'yı doğru yapmak" iki şeyi şart koşar (ikisi de zaten kapsamda): madde-seviyesi yapısal chunking (ADR-0004) ve hybrid retrieval dense+BM25 (ADR-0006). Bunlar advanced RAG değil, vanilla'nın doğru kurulmuş hâlidir.

## ADR-0002 — Veri kaynağı: mevzuat-mcp API (scraper yok)
- **Durum:** Kabul edildi
- **Bağlam:** mevzuat.gov.tr içeriğine erişim için ya scraper yazılır ya hazır API kullanılır.
- **Karar:** `saidsurucu/mevzuat-mcp` araçları kullanılır (`search_mevzuat → get_mevzuat_madde_tree → get_mevzuat_content`, bedesten birleşik ailesi). Kendi scraper'ımız yazılmaz. Yalnız `KANUN` türü çekilir (bkz. ADR-0013). Erişim mekanizması (server/client): bkz. ADR-0012.
- **Sonuç:** Bakım yükü azalır, yapısal madde ağacı + Markdown hazır gelir. PDF içerik (çoğu Cumhurbaşkanı kararı) atlanır.

## ADR-0003 — Korpus çıktısı: JSONL `{id, text, metadata}`
- **Durum:** Kabul edildi
- **Bağlam:** Ingestion ile retrieval arasında net, bağımsız teslim edilebilir bir sınır gerekiyor.
- **Karar:** Temiz korpus, satır başına bir chunk olacak şekilde JSONL: `{id, text, metadata}`.
- **Sonuç:** Modül "söküp verilebilir"; retrieval bu artifact'i tüketir.

## ADR-0004 — Atomik birim = madde, hiyerarşi korunur
- **Durum:** Kabul edildi
- **Bağlam:** Naive sabit-boy token chunking, hukuki yapıyı (madde/fıkra/bent) bozar ve atıf doğruluğunu düşürür.
- **Karar:** Chunking'in atomik birimi madde; uzun maddeler fıkra bazında bölünür; `kanun→...→madde→fıkra→bent` hiyerarşisi metadata'da korunur.
- **Sonuç:** Atıf modu ve metadata filtreleri güvenilir olur.

## ADR-0005 — Yürürlük durumu birinci sınıf metadata
- **Durum:** Kabul edildi
- **Bağlam:** Mülga (yürürlükten kalkmış) hükümlerin yürürlüktekilerle karışması yanlış sonuç doğurur.
- **Karar:** Her chunk'ta yürürlük durumu (yürürlükte/mülga) taşınır; filtrelenebilir/ayrılabilir.
- **Sonuç:** Retrieval varsayılan olarak yürürlükteki hükümleri döndürebilir.

## ADR-0006 — Hybrid arama (dense + BM25/sparse)
- **Durum:** Kabul edildi
- **Bağlam:** Hukuki sorgularda hem semantik benzerlik hem birebir terim/atıf eşleşmesi önemli.
- **Karar:** Dense (embedding) + sparse (BM25) hybrid retrieval kullanılır.
- **Sonuç:** Hem doğal dil hem atıf-ağırlıklı sorgularda recall/precision dengesi.

## ADR-0011 — Başlangıç korpusu: kapsama-odaklı, yapısal eksenlere göre örnekleme
- **Durum:** Kabul edildi
- **Bağlam:** Kanunlar tek tip değil; aynı **KANUN** türü içinde bile yapısal fark var: iki kanun hiyerarşi (kitap/kısım/bölüm derinliği), geçici/ek/mükerrer madde, değişiklik şerhi, fıkra stili (`(1)` vs `1.`), numaralandırma açısından farklı olabilir. Tek kanuna göre yazılan chunker, farklı yapıdaki ikinci kanunda kırılır.
- **Karar:** Korpus türe göre DEĞİL, **yapısal eksen kapsamasına** göre seçilir. Önce chunker'ı zorlayan eksenler listelenir; sonra bu eksenlerin tümünü vuran **en küçük** belge seti alınır. Yeni bir eksen eklemeyen aday alınmaz. Bazı eksenler aynı türden 2 belge gerektirebilir (tür-içi varyasyon böyle karşılanır). Set küçük ve amaçlı kalır (~5-8 belge); "önce çalıştır, sonra ölçekle" korunur.
  - **Yapısal eksenler:** (1) hiyerarşi derinliği [düz ↔ kitap/kısım/bölüm], (2) madde içi yapı [paragraf ↔ fıkra ↔ bent listesi], (3) geçici/ek madde [var/yok], (4) mülga hüküm [var/yok], (5) değişiklik şerhleri [(Değişik/Ek/Mülga: …)], (6) numaralandırma [normal / 5/A / mükerrer], (7) tablo/EK/form [var/yok].
  - Her örneğin hangi eksenleri kapsadığı bir **işaret (coverage) tablosu**nda tutulur → kapsama ve boşluk (örneklenmemiş eksen) görünür olur.
- **Sonuç:** Chunker (ADR-0004) ve metadata (ADR-0005) yapısal çeşitliliğe karşı baştan, az ama temsil edici örnekle test edilir; robustluk ve kapsam boşlukları erken görülür.
- **Uygulama (2026-06-19):** Kapsam **kanun-only** (ADR-0013) olduğundan aktif set yalnız **KANUN**: TCK 5237, VUK 213, KVKK 6698 (aday: GVK 193). _İlk keşifte alınan tebliğ 350781 + KKY yönetmeliği 352791 artık **kapsam dışı** — geçmiş kayıt._ Kapsama tablosu → status.md. Bulgu: mülga/ek/mükerrer işaretleri ağaçta değil **content metninde** (Faz 3 girdisi); ayrıca eski kanunlarda (GVK) fıkra `(1)` yerine `1.` stili çıkabilir.

## ADR-0012 — mevzuat-mcp entegrasyonu: yerel MCP server + MCP client
- **Durum:** Kabul edildi
- **Bağlam:** mevzuat-mcp bir **kütüphane değil, MCP server**'dır (PyPI'de yok; git'ten `uvx` ile çalışır, Python 3.11+, FastMCP). Fonksiyonları doğrudan import edilemez; araçlar yalnız MCP protokolü üzerinden çağrılır. Uzak hosted bir endpoint de mevcut (`https://mevzuat.surucu.dev/mcp`).
- **Karar:** mevzuat-mcp **yerelde** (kendi docker-compose'umuzda) bir MCP server olarak koşulur; ingestion job ona **MCP client** olarak bağlanır. Uzak hosted endpoint'e (Seçenek C) bağımlı kalınmaz → reproducible + dockerize korunur. İç httpx kodunu import etmek (Seçenek B) reddedildi: undocumented + kırılgan.
- **Sonuç:** Pipeline tasarlanan arayüzü kullanır (iç yapı değişse de dayanıklı), self-contained kalır. Kullanılacak araçlar: `search_mevzuat`, `get_mevzuat_madde_tree`, `get_mevzuat_content` (bedesten ailesi). Bağımlılık: bir MCP client kütüphanesi (Python `mcp` SDK / FastMCP client) — `requirements.txt`'e Faz 1'de eklenir.

## ADR-0013 — Kapsam yalnız KANUN türü
- **Durum:** Kabul edildi (2026-06-19)
- **Bağlam:** mevzuat-mcp birçok tür sunar (KANUN, KHK, TÜZÜK, YÖNETMELİK, TEBLİĞ…). Hepsini birden işlemek yapısal çeşitliliği ve test yükünü çoğaltır; türlerin yapısı/önceliği farklı.
- **Karar:** MVP **yalnız `KANUN` türünü** kapsar (`mevzuat_tur=KANUN`). KHK, tüzük, yönetmelik, tebliğ — **kapsam dışı**, future work. (KHK dahil **değil**.)
- **Sonuç:** Daha dar, daha tutarlı korpus; chunker tek tür ailesine (kanunlar) odaklanır. Önceki örnek setindeki tebliğ (350781) + yönetmelik (352791) düşer (bkz. ADR-0011 Uygulama).

---

## Faz 5-6 Kararları

## ADR-0007 — Embedding modeli
- **Durum:** ✅ Kabul edildi — **BGE-M3** (2026-07-01)
- **Bağlam:** Türkçe hukuki metinde iyi performans + hybrid + uzun-madde bağlamı gerekiyor.
- **Seçenekler (hazır modeller incelendi):**
  - **BGE-M3** (BAAI): XLM-RoBERTa-large, 1024 boyut, **8192 token bağlam**, dense+sparse tek model.
  - **YTÜ COSMOS turkish-e5-large:** TR-MTEB retrieval 77.0 (en yüksek Türkçe) AMA **512 token** (uzun madde kesilir), yalnız dense.
  - **EmbeddingGemma-300m:** 2048 bağlam, Matryoshka, verimli AMA yalnız dense.
  - **Mursit/Mecellem** (ModernBERT-large): hukuk-özel AMA sözleşmede güçlü, **kanun/regülasyonda orta** (56.87 genel); yalnız dense.
- **Karar:** **BGE-M3.** Gerekçe (projeye özgü):
  1. **Hybrid native** — dense+sparse tek modelden çıkar → Qdrant'a ikisi birden verilir (CLAUDE.md
     hybrid=MVP tanımı). Diğer adaylar yalnız dense → BM25 ayrı kurulurdu.
  2. **8192 bağlam** — korpusta uzun maddeler (p90≈1754 krk, bazıları 100k+). COSMOS'un 512 sınırı
     uzun maddenin sonunu (ceza/istisna/yürürlük fıkraları) keser → retrieval kör noktası. BGE-M3'te tam sığar.
  3. **Fine-tune yolu** — ileride BGE-M3 fine-tune edilirse "hazır vs fine-tuned" A/B testi aynı
     aile içinde adil yapılır.
- **Sonuç:** COSMOS Türkçe skoru (77.0) daha yüksek AMA 512-bağlam + dense-only bizim uzun-madde +
  hybrid ihtiyacında elenir. Kesin doğrulama Faz 6'da **kendi gold setiyle A/B** (benchmark değil, öz-veri).
- **Not (kapsam):** Hazır BGE-M3'ü *kullanmak* retrieval → kapsam-içi. Fine-tune *etmek* kapsam-dışı (gelecek).

## ADR-0008 — Vektör store: Qdrant vs pgvector
- **Durum:** ✅ Kabul edildi — **Qdrant** (2026-07-01)
- **Bağlam:** Hybrid arama + metadata filtreleme + dockerize kolaylığı gerekiyor.
- **Seçenekler:**
  - **Qdrant:** native hybrid/payload filtre, ayrı servis.
  - **pgvector:** tek Postgres, SQL filtre, sparse için ek iş.
- **Karar:** **Qdrant.** Gerekçe (projeye özgü):
  1. **Hybrid native** — CLAUDE.md'nin çekirdek gereksinimi (dense+BM25) MVP'nin *tanımı*, opsiyon değil.
     Qdrant dense+sparse vektörü tek "point"te tutar, füzyonu (RRF) Query API'de dahili yapar.
     pgvector yalnız dense; BM25 + füzyon elle kurulurdu (ekstra faz + kendi RRF debug'ı).
  2. **Yürürlük filtresi = MVP-kritik** — payload filtre arama *sırasında* çalışır (mülga maddeler
     HNSW'de hiç değerlendirmeye alınmaz; "önce getir sonra ele → 10'dan az kalır" sorunu yok).
  3. **Dockerize** — tek servis hazır image (CLAUDE.md docker-compose hedefi).
  4. **Ölçek/hız** — HNSW (approx. nearest neighbor); 31k'da anlık, milyonlara logaritmik ölçeklenir.
  5. **Öğrenme** — hybrid API füzyon mantığını açıkça gösterir (kavramsal şeffaflık).
- **Sonuç:** docker-compose'a Qdrant servisi; ingestion korpus.jsonl → dense+sparse+payload point.
  pgvector "zaten Postgres olan sistem" senaryosu için reddedildi (bizde bağımsız retrieval servisi).
- **Not (kapsam):** Qdrant'ı *kullanmak* retrieval'ın parçası → kapsam-içi. Embedder *eğitmek* değil.

## ADR-0009 — Reranker kullanılacak mı?
- **Durum:** ✅ Kabul (değerli) — **entegrasyon ertelendi** (2026-07-02) → **entegrasyon ADR-0015'te** (2026-09-28):
  kod kütüphanede, 3-bacak üstünde yeniden ölçüldü, varsayılan kapalı / istek başına açık.
  ⚠️ Aşağıdaki ölçümün aday havuzu **2-bacak RRF**'tir (bugünkü 3-bacak WSUM değil).
- **Bağlam:** Reranker precision/sıralamayı (nDCG, MRR, R@k) artırır ama recall'u artırmaz; gecikme + komplekslik ekler.
- **Ölçüm (2000 sorgu, altınset gold, bge-reranker-v2-m3, Colab T4):**

  | Metrik | Hybrid | +Reranker | Fark |
  |---|---|---|---|
  | Recall@1 | 0.4325 | 0.4525 | +0.020 |
  | Recall@5 | 0.5980 | 0.6530 | **+0.055** |
  | Recall@10 | 0.6665 | 0.7060 | +0.040 |
  | MRR | 0.5099 | 0.5411 | +0.031 |
  | nDCG@10 | 0.5432 | 0.5784 | +0.035 |

- **Karar:** Reranker **işe yarıyor** (tüm metrikler pozitif, R@5 +0.055, R@10 +0.040 → literatür tipik +0.03-0.08
  aralığında). Hybrid+reranker R@10=0.706. **Kalıcı kullanılacak
  AMA entegrasyon ERTELENDİ:** yerel 4GB VRAM'de embed(BGE-M3)+reranker sığmıyor → PC'de yavaş/kırılgan.
  Entegrasyon Faz 6/7'de (Colab-üretimi veya reranker'ı ayrı servis/GPU'da). Şimdilik ölçüm-kanıtı + scriptler saklı.
- **Not:** Reranker'ın R@50 tavanı (0.775) tam yakalanmadı (+0.04/0.11) — çok-versiyonlu kanun (6111 vs 7326)
  reranker'ı da yanıltıyor. Yol: gold'da aynı-konu toleransı VEYA fine-tune (future).
- **Araçlar:** `scripts/metrik_rerank.py` (yerel deney), `scripts/rerank_hazirla.py` + `colab/rerank_olc.ipynb`
  (Colab ölçüm: PC top-50 aday çıkarır → Colab T4 reranker'lar). Ağır iş bulutta, retriever PC'de.

---

## ADR-0010 — Füzyon: 3-bacak WSUM (dense + BGE-sparse + klasik BM25)
- **Durum:** ✅ Kabul + **uygulandı** (2026-07-03)
- **Bağlam:** ADR-0006 hybrid = dense + BGE-M3 öğrenilmiş sparse (`sparse_linear.pt`). Klasik BM25 (istatistiksel
  TF-IDF) hiç denenmemişti. Darboğaz teşhisi: sistem doğru KANUNU %89, doğru MADDEYİ %67 buluyor → madde-ayrımı
  zayıf. Klasik BM25 nadir/ayırt-edici terimlere IDF ile yüksek ağırlık verir → tam bu darboğaza aday.
- **Ölçüm (2000 sorgu, altınset gold, korpus `text` üzerine rank_bm25, metadata YOK → sızıntısız):**
  - **ÖLÇÜM 4:** klasik BM25 tek başına R@10=0.588 → BGE-sparse'ı (0.526) geçti. 3-bacak (eşit) her metrikte
    +0.03/+0.05.
  - **ÖLÇÜM 5 (ağırlık taraması):** EŞİT (.33/.33/.34) R@1=0.491/MRR=0.562 en iyi; DENSE_AĞIR (.50/.20/.30)
    R@10=0.710 en iyi. DENSE_BM25 (BGE-sparse=0) en zayıf → **üç bacak da katkı yapıyor.**
- **Karar:** 3-bacak WSUM füzyon, **EŞİT ağırlık** (0.33/0.33/0.34). EŞİT seçildi çünkü R@1/R@5/MRR
  (üst-sıra kalitesi) en iyi + ağırlık-ayarı yok → altınsete overfit yok. Farklar küçük (~0.01), ağırlığa
  tolerant. Yolculuk: RRF 0.667 → WSUM_050 0.685 → 3-bacak 0.700 (R@10), R@1 0.436→0.491.
- **Sonuç:** `search_qdrant.py` başlangıçta korpus `text`'ten BM25 index kurar (27954 yürürlükte madde, ~3sn),
  her sorguda 3 bacağı normalize + eşit ağırlıkla toplar. GPU/fine-tune YOK. rank_bm25 saf-Python bağımlılık.
  BGE-sparse atılamaz (ölçümle kanıtlı). Reranker (ADR-0009) hâlâ üstüne eklenebilir (ayrık kazanç).
- **Araçlar:** `scripts/kanun/retrieval/metrik_bm25.py` (ÖLÇÜM 4), `.../metrik_bm25_agirlik.py` (ÖLÇÜM 5).

---

## Faz 6 Kapanışı — Servis Kararları

## ADR-0015 — Reranker entegrasyonu: 3-bacak üstünde cross-encoder
- **Durum:** ✅ Kabul + uygulandı (2026-09-28) — ADR-0009'un "entegrasyon ertelendi" durumunu kapatır.
- **Bağlam:** ADR-0009 reranker'ı (`BAAI/bge-reranker-v2-m3`) ölçtü (R@10 0.6665 → 0.7060) ama o ölçümün aday
  havuzu **2-bacak RRF**'ti (`rerank_hazirla.py` / `metrik_rerank.py`: `FusionQuery(RRF)`). Sonra füzyon 3-bacak
  WSUM'a geçti (ADR-0010) ve "R@10 = 0.700; +reranker 0.706" yan yana yazıldı — yanıltıcı: 0.706 RRF tabanının
  üstündeydi, **3-bacak + reranker hiç ölçülmemişti.** Klasik BM25 bacağı üst sırayı zaten iyileştirdiği için
  reranker'ın ek katkısı küçülebilirdi → yeniden ölçmek şarttı.
- **Ne yapıldı:**
  1. Arama mantığı 9 script'teki kopyalardan kütüphaneye çıkarıldı (`src/kanun/retrieval/search.py`,
     `HybridArama`); eski `search_qdrant.ara` ile 50/50 birebir aynı (`esdeger_kontrol.py`).
  2. `rerank.py`: `TorchReranker` / `OnnxReranker`, arayüz `skorla(sorgu, metinler)`. `HybridArama.ara(rerank=...)`
     WSUM sırasının ilk `RERANK_ADAY` adayını kararlı yeniden sıralar; gerisine dokunmaz.
  3. **Çapa:** ADR-0009 girdisi (`colab/rerank_input.jsonl`) kütüphane koduyla yeniden puanlandı → R@1 0.4525,
     R@5 0.6530, **R@10 0.7060**, nDCG@10 0.5784, MRR(50) 0.5411 — **birebir aynı.**
  4. **Asıl ölçüm** (2000 sorgu, FP32, 3-bacak top-50 aday): `docs/olcum-sonuclari/rerank-3bacak.md`.
- **Ölçüm (N=2000, max_len 512; taban 3-bacak R@1 0.4810 / R@10 0.6885 / MRR@10 0.5515):**

  | ADAY | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 | ΔR@10 | ΔMRR | ΔR@1 |
  |---|---|---|---|---|---|---|---|---|
  | 10 | 0.4705 | 0.6585 | 0.6885 | 0.5502 | 0.5842 | +0.0000 | −0.0013 | −0.0105 |
  | **20** | 0.4645 | 0.6635 | **0.7110** | 0.5501 | 0.5893 | **+0.0225** | −0.0014 | −0.0165 |
  | 30 | 0.4570 | 0.6585 | 0.7100 | 0.5442 | 0.5845 | +0.0215 | −0.0073 | −0.0240 |
  | 50 | 0.4485 | 0.6550 | 0.7035 | 0.5352 | 0.5761 | +0.0150 | −0.0163 | −0.0325 |

  max_len 256 (N=1000 eşleştirilmiş) her ADAY'da 512'den kötü (R@1 −0.03/−0.04). Sorgu bazında: ADAY=20'de R@10
  kazancı 76'ya 31 (z=+4.35, anlamlı), R@1 kaybı 194'e 227 (z=−1.61, anlamlı değil); ADAY=50'de R@1 kaybı z=−3.14.
- **Karar:**
  - **V-2 kuralı** (3-bacak üstünde ADAY=50/512: ΔR@10 ≥ +0.02, ΔMRR ≥ +0.01, ΔR@1 ≥ 0) → +0.0150 / −0.0163 /
    −0.0325: **tutmadı.** Reranker kodu kalır, **varsayılan KAPALI** (`RERANK_VARSAYILAN=0`); servis istek başına
    `rerank=true` ile açar (reranker `RERANK_BACKEND` ile yüklüyse).
  - **Önerilen ADAY/max_len = 20/512** (istek başına açıldığında kullanılan). Kural harfiyen 20/256'yı verirdi
    (N=1000'de R@10 0.7010 = referans 0.7060 − 0.005, tam sınırda); 20/256 aynı sorgularda R@1 −0.033, MRR −0.035
    daha kötü ve sınır değeri gürültü içinde → **sapma: 20/512** (taramanın en iyi R@10'u, R@1 kaybı anlamlı değil).
  - **p95 bütçesi (V-3, 1500 ms) ekı:** reranker-açık satırların CPU gecikmesi (ADR-0016 tablosu): int8 E (20/512)
    p95 **16 121 ms** (reranker aşaması tek başına 15 965 ms); F (50/512) ve torch FP32 D **ölçülmedi** (makine bellek
    sıkışması, bkz. `retrieval-metrikleri.md`) — F'in çift sayısı 2.5× olduğundan daha yavaş olacağı açık → **bütçeye sığmıyor** ve kalite
    kuralını da geçen konfig yok → servis varsayılanı `rerank` kapalı kalır; istek başına açma "yavaş ama daha
    yüksek R@10" seçeneği olarak belgelenir.
- **Sonuç:**
  - ✅ Reranker artık kütüphanede + serviste (istek başına); ADR-0009'daki "entegre değil" kapandı.
  - ✅ "R@10 0.700; +reranker 0.706" yanıltıcı yan yanalığı düzeltildi: bugünkü taban 0.6885, +reranker (20/512)
    0.7110, ama R@1/MRR düşüyor.
  - ❌ Reranker 1. sırayı WSUM'dan kötü seçiyor (ADAY=10'da ilk 10 kümesi aynı, R@1 yine −0.0105) → skor füzyonu
    (reranker skoru + WSUM puanı) ya da alan-içi fine-tune ile düzelebilir — ikisi de ölçüm/ağırlık ayarı ya da
    kapsam dışı (fine-tune) gerektirdiği için bu hedefte **yapılmadı** (future work).
  - Taban sapması: belgelenen 0.7000 yerine ölçülen **0.6885** — Qdrant index'i (eski Colab embed'i) güncel
    korpusla 1.678 maddede yürürlük uyuşmazlığı taşıyor; 2000 sorgunun 37'sinin doğru maddesi Qdrant'ta "mülga"
    işaretli (dense/sparse filtresi getiremez). Korpus yeniden embed'i kapsam dışı; not düşüldü.
- **Öğrenme notu:**
  - **NASIL:** adaylar bir kez çıkarılıp dosyaya yazıldı (`--aday-cikar`), reranker ayrı aşamada top-50'yi puanladı
    (`--skorla`); bir çiftin skoru diğer adaylardan bağımsız olduğu için ADAY ∈ {10,20,30,50} aynı skorlardan türetildi.
  - **NEYE GÖRE:** V-2 kuralı (2000 sorguda R@10 standart hatası ≈ √(0.7·0.3/2000) ≈ 0.010 → +0.02 gürültü değil),
    ayrıca eşleştirilmiş kazanç/kayıp sayımı (aynı sorguda iki sistemi karşılaştırmak, iki bağımsız ortalamayı
    karşılaştırmaktan çok daha hassas).
  - **NEDEN (alternatif):** "reranker'ı hep aç" — R@10 artar ama kullanıcının gördüğü 1. sonuç daha sık yanlış olur
    ve CPU'da saniyeler sürer; "reranker'ı kaldır" — R@10'da anlamlı +0.02'lik kazanç çöpe gider. Orta yol: kod +
    istek başına bayrak.
  - **MANTIK:** **bi-encoder** (BGE-M3) sorgu ve maddeyi ayrı ayrı vektöre çevirir → maddeler önceden gömülebilir,
    arama milisaniye. **cross-encoder** (reranker) sorgu+maddeyi tek girdi olarak birlikte okur → kelime kelime
    etkileşim görür, daha isabetli ama her aday için ayrı model geçişi gerekir → yalnız ilk N adaya uygulanır
    ("getir, sonra yeniden sırala" = iki aşamalı retrieval).

## ADR-0016 — ONNX Runtime + dinamik int8 çıkarım (CPU); gecikme ölçümünün kapsam sınırı
- **Durum:** ✅ Kabul + uygulandı (2026-09-28)
- **Bağlam:** Servis CPU'da koşacak (V-4: i5-11300H 4 çekirdek/8 thread; 4 GB VRAM embed+reranker'ı birlikte
  taşımıyor — ADR-0009). İstek yolunda iki XLM-R-large modeli var (BGE-M3 sorgu embedder'ı, bge-reranker-v2-m3).
  FP32 torch ile gecikme ve bellek yüksek; servis imajı torch taşırsa GB'larca büyür (ADR-0018). Hiç gecikme ölçümü yoktu.
- **Seçenekler:**
  - **ORT dinamik int8** (`quantize_dynamic`, QInt8, per-channel) — kalibrasyon verisi gerekmez.
  - **Optimum `ORTQuantizer`** — aynı ORT quantization'ın sarmalayıcısı; ek bağımlılık, bizim özel embed
    sarmalayıcımız (dense + sparse_w çıktısı) için yine elle export gerekir → katma değer yok.
  - **Statik (kalibrasyonlu) int8** — aktivasyon ölçekleri önceden sabit; kalibrasyon seti seçimi + transformer'da
    doğruluk riski; kapsam dışı (V-6).
  - **fp16** — bu CPU'da hızlandırmaz (GPU işi). **GPU/CUDA EP** — servis CPU (V-4).
  - **Yalnız thread ayarı (torch FP32)** — A satırı bunu ölçer; model boyutu/bellek aynı kalır.
- **Karar:** Sorgu embedder'ı ve reranker ONNX'e export edilir (`onnx_export.py`, opset 17, dinamik batch/seq, FP32
  > 2 GB → tek dosya external data), ORT dinamik int8'e çevrilir (`onnx_quantize.py`, QInt8 per-channel,
  `MatMulConstBOnly`); çıkarım `CPUExecutionProvider`, `intra_op_num_threads=4`. **Karma hassasiyet:** tam int8
  BGE-M3'te dense kosinüsü 0.985'e düşürdü (< 0.99 eşiği) → deney (40 sorgu): embedding/Gather hariç 0.985
  (etkisiz), FFN çıkışları hariç 0.990, ilk 4 katman hariç 0.985, **son 4 katman hariç 0.991 (0.72 GB)**, son 6
  hariç 0.994 (0.80 GB). Hata son katmanlarda birikiyor (CLS vektörü doğrudan son katmandan çıkar) → embed'de son 4
  transformer katmanı FP32. Reranker tam int8. Korpus vektörleri **değişmez** (Colab FP32); yalnız **sorgu tarafı**.
- **Sorgu/korpus asimetrisi:** korpus FP32, sorgu int8 BGE-M3 ile gömülür. İkisi aynı uzayda kalır (int8 ağırlıklar
  FP32'nin yaklaşığı); hata sorgu vektörüne küçük gürültü olarak biner. Etkisi kosinüsle değil doğrudan R@10/MRR ile ölçüldü.
- **Ölçüm — doğruluk (parity, `tests/kanun/test_onnx_parity.py`, `pytest -m model`, N=200):**

  | Kontrol | Eşik | Sonuç |
  |---|---|---|
  | ONNX-FP32 vs torch dense kosinüs (ort) | ≥ 0.9999 | **1.000000** (sparse maks fark 1.3e-5) |
  | ONNX-int8 vs torch dense (ort / min) | ≥ 0.99 / ≥ 0.97 | **0.99116 / 0.98600** |
  | reranker int8 vs FP32 top-10 kesişimi (50 liste × 20 aday) | ort ≥ 0.9 | **0.950** (min 0.90) |

- **Ölçüm — kalite (2000 sorgu, 3-bacak, reranker kapalı):** torch R@10 0.6885 / MRR 0.5515; ONNX-FP32 0.6885 /
  0.5515 (birebir); **ONNX-int8 0.6880 / 0.5510** (−0.0005 / −0.0005; eşik −0.01 ✓). int8 embed + int8 reranker:
  ilk 200 sorguda (eşleştirilmiş) R@1 0.425 / R@10 0.645 / MRR 0.504; aynı 200 sorguda torch FP32 + torch reranker
  0.400 / 0.650 / 0.487 → ΔR@10 −0.005 (eşik −0.01 ✓). 2000 sorguda **ölçülmedi** (CPU'da ≈0.7 sn/çift → 2000×20
  çift ≈ 7-8 saat; GPU'daki FP32 ölçümü + parity + bu 200'lük eşleştirme yeterli kanıt sayıldı).
- **Ölçüm — gecikme (CPU, N=200, p95 ms):** A torch FP32 708 · B ONNX FP32 511 · **C ONNX int8 253**
  (embed p95 672 → 215 ms, 0.32×; V-3 ≤ 400 ms ✓) · E int8 + int8 reranker 20/512 16 121 · D, F, C-http **ölçülmedi**
  (bellek sıkışması: F 20/100 sorguda Qdrant zaman aşımıyla düştü, D/C-http durduruldu). Tepe RSS: A 3076 / C 2325 /
  E 3806 MB. Tam tablo + protokol + ortam: `docs/retrieval-metrikleri.md`, ham JSON
  `docs/olcum-sonuclari/gecikme-2026-09-28.json`.
- **Kapsam sınırı (V-5):** compliance B "Formal eval / benchmark harness 🚫". Gecikme ölçümü **tek script**
  (`metrik_gecikme.py`), **sabit protokol** (N=200, 10 ısınma, sıralı tek istek, 4 thread, model yükleme ölçüm
  dışı), **tek tablo** (`docs/retrieval-metrikleri.md`). Genel çerçeve, MTEB, eşzamanlı yük testi yok.
- **Sonuç:**
  - ✅ Servis torch'suz koşabilir (ORT ~20 MB vs torch GB'lar); model 2.27 GB → 0.72 GB (embed) / 0.57 GB (reranker).
  - ✅ Reranker'sız yol (C) bütçede; embed aşaması 3× hızlandı.
  - ❌ Cross-encoder CPU'da int8 ile bile istek başına saniyeler (≈0.7 sn/çift; E satırında 20 çift ≈ 14.4 sn p50) → reranker CPU'da etkileşimli
    kullanım için pahalı (ADR-0015).
  - ⚠️ i5-11300H AVX-512 VNNI destekler; ORT'nin VNNI çekirdeklerini kullandığı **doğrulanmadı** (ORT profilleme
    yapılmadı) — hızlanma ölçüldü, mekanizması varsayım.
- **Öğrenme notu:**
  - **NASIL:** `torch.onnx.export` modeli örnek girdiyle bir kez çalıştırıp hesap grafiğini (MatMul, Add, Softmax…)
    ONNX dosyasına yazar; `quantize_dynamic` bu grafikteki MatMul ağırlıklarını int8'e çevirir; ORT grafiği CPU için
    optimize edip koşturur.
  - **NEYE GÖRE:** parity eşikleri (export doğruluğu), 2000 sorguluk R@10/MRR (asıl kalite), p95 (asıl hız).
  - **NEDEN (alternatif):** statik int8 daha hızlı olabilirdi ama kalibrasyon seti = altınsete ayar riski ve kapsam
    dışı; fp16 bu CPU'da hız getirmez.
  - **MANTIK:** **quantization** = sayıları daha az bitle saklamak. **Dinamik** int8'de ağırlıklar önceden int8,
    ara çıktıların (aktivasyon) ölçeği her çağrıda o anki min/max'tan hesaplanır → veri gerekmez ama her çağrıda
    küçük bir ölçek hesabı maliyeti var. **per-channel** = matrisin her satırı kendi ölçeğini alır. **Execution
    provider** = ORT'nin grafiği hangi donanım arka ucunda koşturduğu (burada CPU). **intra-op thread** = tek bir
    MatMul'ın kaç çekirdeğe bölündüğü (4 fiziksel çekirdek; hyper-thread'ler aynı FPU'yu paylaştığı için 8 genelde
    kazandırmaz). **p95** = sorguların %95'inin bu sürenin altında bittiği değer (ortalama "tipik"i, p95 "kötü günü"
    anlatır; p99 N=200'de ≈ en yavaş 2 sorgu → güvenilirliği düşük).


## ADR-0017 — Retrieval servis katmanı: FastAPI
- **Durum:** ✅ Kabul + uygulandı (2026-09-28)
- **Bağlam:** Roadmap Faz 6 çıktısı "çalışan retrieval API/servisi"; status/compliance "servis/API katmanı yok"
  diyordu. Arama script seviyesindeydi (`search_qdrant.py`) ve model her süreçte yeniden yükleniyordu
  (BGE-M3 ~2.3 GB, yükleme ~20-60 sn). Servis, modeli **bir kez** yükleyip her isteğe aynı bellekten cevap verir.
- **Seçenekler:**
  - **FastAPI** — pydantic ile girdi doğrulama (boş/uzun sorgu, `top_k` sınırı → otomatik 422), OpenAPI şeması
    (`/docs`), `TestClient` ile ağsız test, `uvicorn` zaten kurulu.
  - **Flask** — olgun ama doğrulama/şema elle; tip ipuçlarından şema üretmez.
  - **stdlib `http.server`** — bağımlılık yok ama JSON doğrulama, hata kodları, eşzamanlılık hepsi elle.
  - **gRPC** — hızlı ikili protokol, ama `.proto` derleme + istemci stub'ı gerekir; tek istemci/insan-okur
    JSON ihtiyacı için aşırı.
- **Karar:** FastAPI + uvicorn, **tek worker**. `src/kanun/api/app.py`:
  - `GET /saglik` → `{durum, qdrant, embed_backend, rerank_backend, rerank_aday, rerank_varsayilan, madde_sayisi}`
  - `POST /ara` → `{sorgu (1..2000 krk, boşluk-only reddedilir), top_k (1..50), rerank (null = sunucu
    varsayılanı), yururlukte_only, metin}` → `{sonuclar[{sira, madde_id, kanun_no, kanun_ad, madde_no, skor,
    rerank_skor, metin?}], sure_ms, config}`. `rerank=true` ama reranker yüklü değilse **400**.
  - Modeller + BM25 + Qdrant client `lifespan`'da bir kez kurulur (`fabrika.arama_kur`). Endpoint'ler `def`
    (async değil) → CPU-bağlı çıkarım FastAPI'nin thread havuzunda koşar, event loop bloklanmaz.
  - **Generation/LLM endpoint'i yok** (ADR-0001); test bunu da doğrular.
- **Sonuç:**
  - ⚠️ Servis in-process kütüphaneyle aynı `HybridArama.ara` çağrısını kullanır (servis
    yalnız ince sarmalayıcı); 200 sorguluk HTTP eşdeğerlik + C-http gecikme koşusu (`metrik_gecikme.py --satir C-http
    --esdeger`) hazır ama **koşulamadı** (makine bellek sıkışması) → servis ek yükü ölçülmedi. Servis varsayılanı
    reranker kapalı olduğundan HTTP satırı C üzerinden planlandı (E-http değil).
  - ✅ İstek yolu hızlandırmaları (sonuç değiştirmeyen): `HizliBM25` (rank_bm25 ile bit-bit aynı skor, posting
    list üzerinden → BM25 bacağı ~100 ms → ~10 ms) ve Qdrant `yurutluk` keyword payload index'i (filtreli sorguda
    p95 208 → 15 ms, 30/30 sonuç aynı; `ingest_qdrant.py` artık index'i kendisi kurar).
  - ✅ `tests/kanun/test_api.py` — sahte `HybridArama` ile şema, sınırlar, 422/400, `rerank=null` varsayılanı.
  - ❌ Tek worker = modeller süreç başına bellekte; çoklu worker her biri modeli ayrı yükler (int8 embed +
    reranker ≈ 1.2 GB/worker). Kimlik doğrulama, rate-limit, yatay ölçek **kapsam dışı** (bu fazın hedefi değil).
- **Öğrenme notu:**
  - **NASIL:** pydantic `BaseModel` istek şemasını tanımlar; FastAPI gelen JSON'u buna göre doğrular, uymazsa
    handler'a hiç girmeden 422 döner. `lifespan` = uygulama açılırken/kapanırken bir kez çalışan kod.
  - **NEYE GÖRE:** roadmap Faz 6 çıktısı + compliance A.6 "servis yok" + gecikme bütçesi (model yüklemesi
    istek yolunda olmamalı).
  - **NEDEN (alternatif):** Flask'ta aynı doğrulama elle yazılırdı; gRPC tek bir JSON istemcisi için gereksiz
    derleme adımı ekler.
  - **MANTIK:** worker = istekleri işleyen süreç. Tek süreç + thread havuzu: modeller tek kopya, ama aynı
    anda gelen iki istek CPU çekirdeklerini paylaşır (eşzamanlı yük testi kapsam dışı).

## ADR-0018 — docker-compose topolojisi (qdrant + api + ingest profili, modeller volume)
- **Durum:** ✅ Kabul + uygulandı (2026-09-28)
- **Bağlam:** Roadmap Faz 7 + MVP Definition of Done: "tamamı dockerize, reproducible". Faz 6'da retrieval
  servisi (ADR-0017) ve torch'suz ONNX int8 çıkarım (ADR-0016) hazır → servis imajı torch'suz kurulabilir.
- **Karar:**
  - **3 servis:** `qdrant` (sabit tag `qdrant/qdrant:v1.18.0` — `qdrant-client 1.18.0` ile eşleşik; `qdrant_storage`
    named volume; healthcheck imajda curl olmadığı için `bash /dev/tcp`), `api` (`depends_on: qdrant (healthy)`,
    `QDRANT_URL=http://qdrant:6333`, healthcheck `/saglik`), `ingest` (**profil `ingest`** → `docker compose up`
    ile kalkmaz; `docker compose --profile ingest run --rm ingest` ile bir kez koşar).
  - **Tek imaj** (`Dockerfile`, `python:3.11-slim`, non-root `mevzuat` kullanıcısı): `requirements-servis.txt`
    (onnxruntime, transformers yalnız tokenizer, qdrant-client, rank-bm25, numpy, fastapi, uvicorn) — **torch yok**.
    api ve ingest aynı imajı kullanır (ingest için numpy + qdrant-client yeter).
  - **Modeller ve korpus imaja gömülmez:** `./models/onnx` ve `./data/kanun/korpus.jsonl` **read-only volume**;
    `colab/outputs` yalnız ingest'e ro mount. `.dockerignore` `.env*`, `data/`, `models/`, `colab/`, `.venv/`,
    `docs/`, `tests/` dışarıda bırakır → build context küçük, secret sızmaz.
  - Varsayılan `EMBED_BACKEND=onnx-int8`, reranker ayarları ADR-0015 kararından (`RERANK_*` ortam değişkenleri,
    compose'da `${VAR:-varsayılan}` ile override edilebilir). Host portları `API_PORT`/`QDRANT_PORT` ile değişir.
  - `ingest_qdrant.py`'deki `QDRANT_URL` sabiti ortam değişkeni varsayılanına çevrildi (davranış aynı).
- **Sonuç / neden:**
  - **Neden modeller volume?** int8 embed + reranker ~1.2 GB, FP32 ~4.5 GB: imaja gömmek imajı GB'larca şişirir,
    her model değişikliğinde yeniden build ister ve repo'ya/registry'ye büyük artifact taşır (>5 MB commit yasağı,
    `docs/commit_discipline.md`). Volume ile imaj yalnız kod + kütüphane.
  - **Neden ingest ayrı profil?** Korpus vektörlerinin Qdrant'a yüklenmesi tek seferlik iş (collection'ı silip
    yeniden kurar); her `up`'ta koşsa servis açılışını dakikalarca geciktirir ve veriyi gereksiz yeniden yazar.
  - **Neden torch'suz?** torch CPU wheel'i ~200 MB+, CUDA'lı ~2.5 GB; ONNX Runtime ~20 MB. Servis zaten int8 ONNX
    kullanıyor → torch gereksiz ağırlık. Kanıt: `docker compose run --rm api python -c "import torch"` →
    ModuleNotFoundError.
  - **Doğrulama (2026-09-28):** `docker compose build` 67 sn; imaj **629 MB** (sıkıştırılmış 147 MB), `import torch` →
    ModuleNotFoundError, kullanıcı uid 10001. `QDRANT_PORT=6334 API_PORT=8001`: `up -d qdrant` → `--profile ingest run
    --rm ingest` (31.416 point, 45 sn) → `up -d api` → healthy, `/saglik` 200. `/ara` üzerinden 200 sorgu: R@10
    **0.610** = in-process C satırı 0.610 (±0.005 ✓; R@1 0.425 vs 0.430, MRR 0.484 vs 0.488 — ayrı Qdrant
    örneğinde HNSW bağ sırası farkı). İstemci duvar saati p50/p95/p99 178/334/502 ms (Docker port yönlendirmesi dahil,
    ısınma yok — protokol satırı değil, gösterge). api konteyneri 1.73 GB bellek (reranker kapalı).
  - ⚠️ Doğrulama `RERANK_BACKEND=kapali` ile yapıldı (makine bellek sıkışması; servis varsayılanı zaten reranker kapalı).
    Compose varsayılanı `onnx-int8` reranker'ı da yükler (+~0.6-1.5 GB) — bu haliyle konteynerde koşturulmadı.
  - ❌ Ön koşullar compose'un işi değil: `colab/outputs/` (Colab korpus embed'i), `models/onnx/` (`onnx_export.py` +
    `onnx_quantize.py`), `data/kanun/korpus.jsonl` (`build_corpus.py`) host'ta hazır olmalı.
- **Öğrenme notu:**
  - **NASIL:** `docker compose up -d qdrant api` → qdrant sağlıklı olunca api kalkar; api `lifespan`'da modelleri
    volume'dan yükler; `curl localhost:8000/saglik`.
  - **NEYE GÖRE:** roadmap Faz 7 çıktısı + DoD "reproducible"; imaj boyutu; commit yasağı.
  - **NEDEN (alternatif):** (a) modelleri build sırasında HF'den indirmek → build ağ bağımlı ve yavaş, ONNX
    export'u torch ister; (b) ingest'i api başlangıcına gömmek → her restart'ta yeniden yükleme.
  - **MANTIK:** `depends_on: condition: service_healthy` yalnız "konteyner başladı" değil "healthcheck geçti"yi
    bekler → api, Qdrant portu açılmadan bağlanmaya çalışmaz.

---

## Yapı Kararları

## ADR-0014 — Mevzuat türleri arasında sıfır kod paylaşımı (tür izolasyonu)
- **Durum:** Kabul edildi (2026-07-10)
- **Bağlam:** MVP yalnız KANUN'u kapsıyor (ADR-0013) ama ileride tebliğ ve yönetmelik de
  işlenecek. Klasik yaklaşım: ortak bir `chunker`/`fetch` yazıp tür farkını `if tur == "KANUN"`
  dallarıyla taşımak. Ancak türler parser'ın **özünde** farklı:
  - Tebliğlerin `mevzuatMaddeTree`'si çoğu zaman **boş** döner; kanun parser'ı ağaca dayanıyor
    (hiyerarşi, madde başlıkları, bleed-marker'ları buradan geliyor).
  - Kanunun bleed-kırpma kuralları (`"...yürütür"` anchor'ı, kanun-sonu cetvel eki, E-tuzağı
    guard'ı) tebliğde anlamsız — hatta zararlı.
  - Bu parser'da hatalar **sessizdir**: yanlış bir kırpma testleri geçer ama korpusu zehirler
    (bkz. `arch.md` §5 invariant tablosu). Ortak koda dokunmak diğer türü sessizce bozabilir.
- **Karar:** Her mevzuat türü **kendi paketinde, sıfırdan** yazılır. Ortak modül, ortak
  soyutlama, tür dalı **yoktur**. Yeni tür eklerken `src/kanun/` modülleri **kopyalanır**,
  import edilmez.
  ```
  src/kanun/  src/teblig/  src/yonetmelik/          ← paketler
  scripts/<tur>/   tests/<tur>/   data/<tur>/       ← simetrik
  ```
  **Tek sözleşme:** çıktı şeması `{id, text, metadata}` aynı kalır (+ `metadata.mevzuat_tur`),
  böylece üç korpus ileride tek Qdrant'ta birleşebilir. Kod değil, **veri formatı** paylaşılır.
- **Sonuç:**
  - ✅ Bir türe dokunmak diğerini **asla** bozamaz; her tür kendi test setiyle doğrulanır.
  - ✅ Tür-kapsamlı veri yolları (`data/<tur>/`) sayesinde `build_corpus.py`'nin "sessizce ezme"
    davranışı tür içinde kalır — tebliğ build'i kanun korpusunu ezemez.
  - ❌ **Bedel:** ortak bir bug 3 yerde düzeltilir. Kod tekrarı bilinçli olarak kabul edildi;
    gerekçe: bu alanda *yanlış birleştirmenin* maliyeti, tekrarın maliyetinden yüksek.
  - Reddedilen alternatifler: (a) ortak `chunker` + tür dalları, (b) ortak saf-metin yardımcıları
    (`normalize`, `ids`) — ikincisi cazipti ama "sıfır ortak" sınırını bulanıklaştırırdı.

---

## Karar Şablonu (yeni ADR için kopyala)
```
## ADR-XXXX — <başlık>
- **Durum:** Önerildi | Kabul edildi | Açık | Reddedildi | Yerini aldı
- **Bağlam:** <neden bu karar gerekti>
- **Karar:** <ne kararlaştırıldı>
- **Sonuç:** <etkiler, ödünler>
```
