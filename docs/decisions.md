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
- **Karar:** `saidsurucu/mevzuat-mcp` araçları kullanılır (`search_mevzuat → get_mevzuat_madde_tree → get_mevzuat_content`, bedesten birleşik ailesi). Kendi scraper'ımız yazılmaz. Erişim mekanizması (server/client): bkz. ADR-0012.
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
- **Bağlam:** Mevzuat tek tip değil ve yapısal fark yalnız **türler arası** (kanun/yönetmelik/tebliğ) değil, **tür içi**dir de: aynı türden iki belge hiyerarşi, geçici/ek madde, değişiklik şerhi, numaralandırma vb. açısından farklı olabilir. "Her türden bir tane" almak tür-içi varyasyonu kaçırır; chunker farklı yapıdaki ikinci belgede kırılır.
- **Karar:** Korpus türe göre DEĞİL, **yapısal eksen kapsamasına** göre seçilir. Önce chunker'ı zorlayan eksenler listelenir; sonra bu eksenlerin tümünü vuran **en küçük** belge seti alınır. Yeni bir eksen eklemeyen aday alınmaz. Bazı eksenler aynı türden 2 belge gerektirebilir (tür-içi varyasyon böyle karşılanır). Set küçük ve amaçlı kalır (~5-8 belge); "önce çalıştır, sonra ölçekle" korunur.
  - **Yapısal eksenler:** (1) hiyerarşi derinliği [düz ↔ kitap/kısım/bölüm], (2) madde içi yapı [paragraf ↔ fıkra ↔ bent listesi], (3) geçici/ek madde [var/yok], (4) mülga hüküm [var/yok], (5) değişiklik şerhleri [(Değişik/Ek/Mülga: …)], (6) numaralandırma [normal / 5/A / mükerrer], (7) tablo/EK/form [var/yok].
  - Her örneğin hangi eksenleri kapsadığı bir **işaret (coverage) tablosu**nda tutulur → kapsama ve boşluk (örneklenmemiş eksen) görünür olur.
- **Sonuç:** Chunker (ADR-0004) ve metadata (ADR-0005) yapısal çeşitliliğe karşı baştan, az ama temsil edici örnekle test edilir; robustluk ve kapsam boşlukları erken görülür.
- **Uygulama (2026-06-19):** Seçilen 5 belge — TCK 5237, VUK 213, KVKK 6698, bir tebliğ (ağaç yok), bir KKY yönetmeliği. Kapsama tablosu → status.md. **Yeni eksen keşfi:** bazı mevzuatın madde-ağacı YOK (kısa tebliğ) → o belgelerde `get_mevzuat_content`-only parse gerekir. Ayrıca mülga/ek/mükerrer işaretleri ağaçta değil **content metninde** taşınır (Faz 3 girdisi).

## ADR-0012 — mevzuat-mcp entegrasyonu: yerel MCP server + MCP client
- **Durum:** Kabul edildi
- **Bağlam:** mevzuat-mcp bir **kütüphane değil, MCP server**'dır (PyPI'de yok; git'ten `uvx` ile çalışır, Python 3.11+, FastMCP). Fonksiyonları doğrudan import edilemez; araçlar yalnız MCP protokolü üzerinden çağrılır. Uzak hosted bir endpoint de mevcut (`https://mevzuat.surucu.dev/mcp`).
- **Karar:** mevzuat-mcp **yerelde** (kendi docker-compose'umuzda) bir MCP server olarak koşulur; ingestion job ona **MCP client** olarak bağlanır. Uzak hosted endpoint'e (Seçenek C) bağımlı kalınmaz → reproducible + dockerize korunur. İç httpx kodunu import etmek (Seçenek B) reddedildi: undocumented + kırılgan.
- **Sonuç:** Pipeline tasarlanan arayüzü kullanır (iç yapı değişse de dayanıklı), self-contained kalır. Kullanılacak araçlar: `search_mevzuat`, `get_mevzuat_madde_tree`, `get_mevzuat_content` (bedesten ailesi). Bağımlılık: bir MCP client kütüphanesi (Python `mcp` SDK / FastMCP client) — `requirements.txt`'e Faz 1'de eklenir.

---

## Açık Kararlar (karar bekliyor)

## ADR-0007 — Embedding modeli
- **Durum:** Önerildi (aday: BGE-M3)
- **Bağlam:** Türkçe hukuki metinde iyi performans + hybrid/multilingual destek gerekiyor.
- **Seçenekler:** BGE-M3 (multilingual, dense+sparse+colbert), Türkçe fine-tuned alternatifler, OpenAI-uyumlu API embedding.
- **Karar:** Faz 5'te kesinleşecek. Şimdilik aday BGE-M3.

## ADR-0008 — Vektör store: Qdrant vs pgvector
- **Durum:** Açık (karar bekliyor)
- **Bağlam:** Hybrid arama + metadata filtreleme + dockerize kolaylığı gerekiyor.
- **Seçenekler:**
  - **Qdrant:** native hybrid/payload filtre, ayrı servis.
  - **pgvector:** tek Postgres, SQL filtre, sparse için ek iş.
- **Karar:** Faz 5 öncesi verilecek. (Etkilenen: arch.md, docker-compose.)

## ADR-0009 — Reranker kullanılacak mı?
- **Durum:** Açık (opsiyonel) — **metriğe bağlı**
- **Bağlam:** Reranker precision/sıralamayı (precision@k, nDCG, MRR) artırır ama recall'u artırmaz; gecikme + komplekslik ekler.
- **Karar:** MVP'de **opsiyonel kalır.** Önce reranker'sız (hybrid) ölç; precision metrikleri (precision@k / nDCG / MRR) hedefin altındaysa ekle, yeterliyse ekleme. Karar **metriklere göre** verilir.

---

## Karar Şablonu (yeni ADR için kopyala)
```
## ADR-XXXX — <başlık>
- **Durum:** Önerildi | Kabul edildi | Açık | Reddedildi | Yerini aldı
- **Bağlam:** <neden bu karar gerekti>
- **Karar:** <ne kararlaştırıldı>
- **Sonuç:** <etkiler, ödünler>
```
