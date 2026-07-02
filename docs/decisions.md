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
  3. **Supervisor uyumu** — elindeki kanun-embedder-v1 zaten BGE-M3 fine-tune → ileride "hazır vs
     fine-tuned" A/B testi aynı aile içinde adil yapılır.
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
- **Durum:** ✅ Kabul (değerli) — **entegrasyon ertelendi** (2026-07-02)
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
  aralığında). Hybrid+reranker R@10=0.706 → supervisor fine-tuned 0.76'ya 5 puan yaklaşır. **Kalıcı kullanılacak
  AMA entegrasyon ERTELENDİ:** yerel 4GB VRAM'de embed(BGE-M3)+reranker sığmıyor → PC'de yavaş/kırılgan.
  Entegrasyon Faz 6/7'de (Colab-üretimi veya reranker'ı ayrı servis/GPU'da). Şimdilik ölçüm-kanıtı + scriptler saklı.
- **Not:** Reranker'ın R@50 tavanı (0.775) tam yakalanmadı (+0.04/0.11) — çok-versiyonlu kanun (6111 vs 7326)
  reranker'ı da yanıltıyor. Yol: gold'da aynı-konu toleransı VEYA fine-tune (future).
- **Araçlar:** `scripts/metrik_rerank.py` (yerel deney), `scripts/rerank_hazirla.py` + `colab/rerank_olc.ipynb`
  (Colab ölçüm: PC top-50 aday çıkarır → Colab T4 reranker'lar). Ağır iş bulutta, retriever PC'de.

---

## Karar Şablonu (yeni ADR için kopyala)
```
## ADR-XXXX — <başlık>
- **Durum:** Önerildi | Kabul edildi | Açık | Reddedildi | Yerini aldı
- **Bağlam:** <neden bu karar gerekti>
- **Karar:** <ne kararlaştırıldı>
- **Sonuç:** <etkiler, ödünler>
```
