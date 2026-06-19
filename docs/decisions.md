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
- **Karar:** `saidsurucu/mevzuat-mcp` API'leri kullanılır (`search_mevzuat → get_mevzuat_article_tree → get_mevzuat_article_content`). Kendi scraper'ımız yazılmaz.
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

## ADR-0011 — Başlangıç korpusu = yapısal çeşitlilik içeren küçük set
- **Durum:** Kabul edildi
- **Bağlam:** Mevzuat tek tip değil: derin hiyerarşili kodifikasyonlar (kitap/kısım/bölüm), düz yönetmelik/tebliğler, ek/geçici maddeler, mülga hükümler, farklı madde numaralandırmaları (5/A, 5/1-a). Chunker tek bir kanuna göre yazılırsa farklı yapıdaki bir sonraki kanunda kırılır.
- **Karar:** Başlangıç korpusu tek kanun DEĞİL; yapısal çeşitliliği temsil eden **küçük bir örnek seti** (ör. 1 büyük kodifikasyon + 1 düz yönetmelik + 1 tebliğ + ek/geçici/mülga madde içeren örnek). "Önce çalıştır, sonra ölçekle" bozulmaz — az ama temsil edici.
- **Sonuç:** Chunker (ADR-0004) ve metadata (ADR-0005) çeşitliliğe karşı baştan test edilir; robustluk erken doğrulanır.

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
- **Durum:** Açık (opsiyonel)
- **Bağlam:** Precision artışı sağlar ama gecikme/komplekslik ekler.
- **Karar:** MVP'de opsiyonel; önce reranker'sız ölç, gerekirse ekle.

---

## Karar Şablonu (yeni ADR için kopyala)
```
## ADR-XXXX — <başlık>
- **Durum:** Önerildi | Kabul edildi | Açık | Reddedildi | Yerini aldı
- **Bağlam:** <neden bu karar gerekti>
- **Karar:** <ne kararlaştırıldı>
- **Sonuç:** <etkiler, ödünler>
```
