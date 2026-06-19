# Yol Haritası (Roadmap)

Kaynak kapsam: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md).
Bu dosya kapsamı **fazlara** böler. İlerleme takibi: [`status.md`](status.md).

> **Temel ilke:** Pipeline yalnızca **retrieval'a kadar** kurulur. Generation (LLM) kapsam dışıdır; en sonda config'le takılan, swap'lanabilir bir endpoint'tir.
>
> **Yaklaşım:** vanilla RAG (graph/agentic/advanced değil) — MVP için en hızlı, debug'lanabilir ve temiz dockerize edilen yol. İleri teknikler future work. Doğru vanilla = madde-seviyesi chunking + hybrid (dense+BM25).

Akış:
`mevzuat-mcp ile çek → madde chunk + metadata → temiz korpus → embed + index → sorgu/retrieve` → (sonra LLM, kapsam dışı)

---

## Fazlar

### Faz 0 — Kurulum & Yönetişim
**Hedef:** Projeyi yönetilebilir kılacak iskelet ve disiplin.
- Yönetişim dokümanları (compliance, status, arch, roadmap, decisions, commit_discipline)
- `README.md`, `.gitignore`, `CLAUDE.md`
- Repo + branch disiplini devrede
**Çıktı:** Dokümante edilmiş, dallanma disiplinli repo.
**Bağımlılık:** —

### Faz 1 — Veri Çekme (data acquisition)
**Hedef:** `saidsurucu/mevzuat-mcp` API'leri üzerinden yapısal içerik çekme.
- `search_mevzuat → get_mevzuat_madde_tree → get_mevzuat_content` akışı (MCP client olarak; bkz. decisions.md ADR-0012)
- Dar başlangıç korpusu: türe göre değil **yapısal eksen kapsamasına göre** seçilen küçük set (tür-içi varyasyon dahil, ~5-8 belge) — chunker robustluğu için (bkz. decisions.md ADR-0011)
- Sadece HTML/Markdown içerik; PDF olanlar atlanır
- Web scraper **yazılmaz** — repo API'leri kullanılır
**Çıktı:** Ham, yapısal mevzuat içeriği (kaynak madde ağacı + Markdown).
**Bağımlılık:** Faz 0

### Faz 2 — Yapısal Chunking *(projenin ana işi)*
**Hedef:** Atomik birim = **madde**; uzun maddeler fıkra bazında bölünür.
- `kanun → (kitap/kısım/bölüm) → madde → fıkra → bent` hiyerarşisi korunur
- Naive sabit-boy token chunking **yapılmaz**
**Çıktı:** Hiyerarşi-bilinçli chunk'lar.
**Bağımlılık:** Faz 1

### Faz 3 — Metadata
**Hedef:** Her chunk için zengin, filtrelenebilir metadata.
- mevzuat adı/no/tür, madde no/başlık, fıkra, hiyerarşi path, kaynak, R.G. tarihi
- **Yürürlük durumu (yürürlükte / mülga)** — kritik; mülga hükümler işaretlenir/ayrılır
**Çıktı:** Metadata ile zenginleştirilmiş chunk'lar.
**Bağımlılık:** Faz 2

### Faz 4 — Temiz Korpus Artifact
**Hedef:** Bağımsız teslim edilebilir, dokümante korpus çıktısı.
- JSONL: `{id, text, metadata}`
- Modülün "söküp verilebilir" sınırı
**Çıktı:** Versiyonlanmış JSONL korpus + şema dokümanı.
**Bağımlılık:** Faz 3

### Faz 5 — Embedding + Indexleme
**Hedef:** Korpusu aranabilir hale getirme.
- Türkçe'ye uygun embedding (ör. `BGE-M3`)
- Vektör store: Qdrant **veya** pgvector *(karar açık — bkz. decisions.md)*
- Hybrid arama: dense + BM25/sparse
**Çıktı:** Doldurulmuş index + hybrid arama altyapısı.
**Bağımlılık:** Faz 4

### Faz 6 — Sorgu Formatı + Retrieval
**Hedef:** Soruya/atıfa karşılık ilgili maddeleri getirmek.
- **Atıf modu:** kanun/madde/fıkra/bent → metadata filtresiyle kesin getirme
- **Doğal dil modu:** serbest soru → hybrid semantik retrieval
- (Opsiyonel) reranker ile precision artırma
- Çıktı: sıralanmış ilgili maddeler (metadata + atıf bilgisiyle)
**Çıktı:** Çalışan retrieval API/servisi.
**Bağımlılık:** Faz 5

### Faz 7 — Dockerize
**Hedef:** Uçtan uca tekrar üretilebilir kurulum.
- `docker-compose`: vektör DB + ingestion job + retrieval/API servisi
**Çıktı:** `docker compose up` ile ayağa kalkan MVP.
**Bağımlılık:** Faz 6

---

## Kapsam Dışı (future work — bu roadmap'te YOK)
- LLM / cevap üretme (generation) — en sonda config'le takılan opsiyonel endpoint
- İleri RAG: GraphRAG, bitemporal versiyonlama, multi-representation index, fine-tuned embedder, RAPTOR
- Formal eval / benchmark harness (küçük sanity kontrolü hariç)
- PDF / OCR içerik
- İçtihat / özelge (`yargi-mcp` alanı)

## Definition of Done (MVP)
Bir sorguyu (atıf veya doğal dil) alıp **ilgili yürürlükteki mevzuat maddelerini** döndüren, dockerize edilmiş bir tool — altında temiz, chunk'lanmış + indexlenmiş korpus.
