# Soru × Mevzuat MVP — Proje Kapsamı

## Amaç
mevzuat.gov.tr'deki mevzuatı (kanun, KHK, tüzük, yönetmelik, tebliğ) yapısal olarak çekip RAG'a uygun biçimde hazırlayan ve bir soruya/atıfa karşılık **ilgili mevzuat maddelerini getiren**, dockerize edilmiş bir MVP.

Pipeline yalnızca **retrieval'a kadar** kurulur. Cevabı üreten LLM (generation) bu kapsamın dışındadır — bkz. *Kapsam Dışı*.

Akış (özet):
`mevzuat-mcp ile çek → madde chunk + metadata → temiz korpus → embed + index → sorgu/retrieve` → (sonra LLM, kapsam dışı)

---

## Kapsam İçi (yapılacaklar)

**1. Veri çekme (data acquisition)**
- Kaynak: mevzuat.gov.tr, `saidsurucu/mevzuat-mcp` API üzerinden (`search_mevzuat` → `get_mevzuat_article_tree` → `get_mevzuat_article_content`, Markdown çıktı).
- Web scraper yazılmaz — repo'nun API'leri kullanılır.
- Sadece HTML/Markdown gelen içerik. PDF olanlar (ör. çoğu Cumhurbaşkanı kararı) atlanır.
- Başlangıçta dar bir korpus (seçilmiş tek bir alan / sınırlı kanun seti), tüm mevzuat değil. Önce çalıştır, sonra ölçekle.

**2. Yapısal chunking — projenin ana işi**
- Atomik birim = **madde**. Uzun maddeler fıkra bazında bölünür.
- `kanun → (kitap/kısım/bölüm) → madde → fıkra → bent` hiyerarşisi korunur.
- Naive sabit-boy token chunking yapılmaz.

**3. Metadata**
- Her chunk için: mevzuat adı, no, tür, madde no, madde başlığı, fıkra, **yürürlük durumu (yürürlükte / mülga)**, R.G. tarihi, hiyerarşi path, kaynak.
- Yürürlük durumu kritik — mülga (yürürlükten kalkmış) hükümler işaretlenir/ayrılır.

**4. Temiz korpus çıktısı (artifact)**
- Net, dokümante bir çıktı: JSONL → `{id, text, metadata}`.
- Bu, modülün "söküp verilebilir" sınırı; bağımsız teslim edilebilir.

**5. Embedding + indexleme**
- Türkçe'ye uygun embedding modeli (ör. `BGE-M3`) ile chunk'lar gömülür.
- Vektör store: Qdrant ya da pgvector.
- Hybrid arama: dense + BM25/sparse.

**6. Sorgu formatı + retrieval**
- İki mod:
  - **Atıf modu:** kanun/madde/fıkra/bent → metadata filtresiyle kesin getirme.
  - **Doğal dil modu:** serbest soru → hybrid semantik retrieval.
- (Opsiyonel) reranker ile precision artırma.
- Çıktı: soruya karşılık **sıralanmış ilgili maddeler** (metadata + atıf bilgisiyle).

**7. Dockerize**
- `docker-compose`: vektör DB + ingestion job + retrieval/API servisi.
- Uçtan uca tekrar üretilebilir (reproducible) kurulum.

---

## Kapsam Dışı (şimdilik)

- **LLM / cevap üretme (generation):** Getirilen maddeleri yazılı cevaba dönüştürme. Bu kısım ekibin Qwen'ine bırakılır ya da en sonda config'le bağlanan, OpenAI-uyumlu, swap'lanabilir bir endpoint olarak eklenir. **Pipeline retrieval'da biter.**
- **İleri RAG teknikleri:** atıf grafı (GraphRAG), bitemporal versiyonlama, multi-representation index, fine-tuned embedder, RAPTOR → future work.
- **Formal eval / benchmark harness** (küçük bir sanity kontrolü dışında) → future work.
- **PDF / OCR** içerik → dışında.
- **İçtihat / özelge** (`yargi-mcp` alanı: Yargıtay, Danıştay, GİB vb.) → bu MVP'nin dışında.

---

## Teslim Edilebilir (definition of done)
Bir sorguyu (atıf veya doğal dil) alıp **ilgili yürürlükteki mevzuat maddelerini** döndüren, dockerize edilmiş bir tool — ve altında temiz, chunk'lanmış + indexlenmiş korpus. LLM/generation kuyruğu en sonda config'le takılır.

## Temel İlke — modüler sınır
Veri-hazırlama aşaması bağımsız bir korpus artifact üretir; retrieval pipeline onu tüketir; LLM, retrieval'dan sonra gelen ve config'le değiştirilebilen bir endpoint'tir. Böylece build, LLM kararından (onların Qwen'i / kendi modelin / herhangi bir API key) **bağımsız** kalır.

---

> Not: Faz planı (phase phase yürütme) bir sonraki adımda ayrıca çıkarılacak. Bu dosya yalnızca kapsamı tanımlar.
