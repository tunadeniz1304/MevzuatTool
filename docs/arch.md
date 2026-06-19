# Mimari Durum (Architecture)

**Son güncelleme:** 2026-06-18
**Olgunluk:** 🟡 Tasarım netleşiyor — kod henüz yok (yalnız yönetişim dokümanları + LICENSE).

Bu dosya **güncel mimari durumu** tutar (bugün ne var, ne kararlaştırıldı, ne açık).
Kararların **gerekçesi/tarihçesi**: [`decisions.md`](decisions.md). Kapsam: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md).

---

## 1. Hedef Mimari (uçtan uca)

```
                 ┌─────────────────────────── INGESTION (offline) ───────────────────────────┐
mevzuat.gov.tr → mevzuat-mcp API → [yapısal chunker] → [metadata zenginleştirme] → korpus.jsonl
                 (search/tree/content)   (madde/fıkra)     (yürürlük/mülga, R.G.)   {id,text,metadata}
                                                                                          │
                 ┌────────────────────────── INDEXING ──────────────────────────┐         │
                 │  [embedder (BGE-M3?)] → [vektör store: Qdrant|pgvector]  ◄──── korpus.jsonl
                 │                          + BM25/sparse (hybrid)           │
                 └───────────────────────────────────────────────────────────┘
                                                                                          │
                 ┌────────────────────────── RETRIEVAL (online) ────────────────┐         │
   sorgu ──────► │ atıf modu ─► metadata filtre ─┐                              │ ◄───── index
   (atıf/NL)     │ NL modu  ─► hybrid semantik ──┴─► (opsiyonel reranker) ─► sıralı maddeler
                 └───────────────────────────────────────────────────────────────┘
                                                                                          │
                                                          ⋯⋯ KAPSAM DIŞI: LLM/generation ⋯⋯
                                                          (en sonda config'le takılan swap'lanabilir endpoint)
```

---

## 2. Bileşenler ve Durum

| Bileşen | Sorumluluk | Durum |
|---|---|---|
| **mevzuat-mcp istemci** | API'den madde ağacı + Markdown çekme | ⬜ planlandı |
| **Yapısal chunker** | madde/fıkra bazlı, hiyerarşi-bilinçli chunk | ⬜ planlandı (ana iş) |
| **Metadata zenginleştirici** | yürürlük/mülga, R.G., path, kaynak | ⬜ planlandı |
| **Korpus artifact** | JSONL `{id, text, metadata}` (modüler sınır) | ⬜ planlandı |
| **Embedder** | Türkçe-uyumlu gömme (ör. BGE-M3) | ⬜ planlandı |
| **Vektör store** | dense index + filtre | ⬜ karar açık (Qdrant↔pgvector) |
| **Sparse/BM25** | hybrid arama lexical bacağı | ⬜ planlandı |
| **Retrieval servisi** | atıf + NL modu, (ops.) reranker, API | ⬜ planlandı |
| **Reranker** | precision artırma | ⬜ opsiyonel / karar açık |
| **Docker compose** | DB + ingestion + retrieval orkestrasyonu | ⬜ planlandı |
| **LLM/generation** | cevap üretimi | ⛔ **kapsam dışı** (config endpoint) |

---

## 3. Mimari İlkeler (değişmez)
1. **Retrieval'da biter.** Generation kapsam dışı; yalnızca config'le takılan, OpenAI-uyumlu, swap'lanabilir endpoint.
2. **Modüler sınır.** Korpus artifact bağımsız teslim edilebilir; ingestion ↔ retrieval gevşek bağlı.
3. **Yürürlük durumu birinci sınıf.** Mülga/yürürlükte ayrımı metadata'da taşınır ve filtrelenebilir.
4. **Yapı korunur.** Madde/fıkra hiyerarşisi chunk ve metadata boyunca kaybolmaz; naive chunking yok.
5. **Önce çalıştır, sonra ölçekle.** Dar korpusla uçtan uca çalış, sonra genişlet.
6. **Vanilla RAG.** Yaklaşım kasıtlı olarak vanilla RAG'tır; graph/agentic/advanced değil. İleri teknikler future work.

---

## 4. Teknoloji Kararları (özet)

| Konu | Seçim | Durum |
|---|---|---|
| Yaklaşım (RAG tipi) | vanilla RAG (graph/agentic değil) | ✅ karar |
| Veri kaynağı | `saidsurucu/mevzuat-mcp` API | ✅ karar |
| Dil/runtime | Python (varsayılan) | 🟡 örtük varsayım |
| Embedding | BGE-M3 (aday) | 🟡 öneri |
| Vektör store | Qdrant **veya** pgvector | ⬜ açık |
| Arama | Hybrid (dense + BM25/sparse) | ✅ karar |
| Reranker | — | ⬜ opsiyonel |
| Korpus formatı | JSONL `{id, text, metadata}` | ✅ karar |
| Paketleme | docker-compose | ✅ karar |

> Detaylı gerekçeler ve açık kararlar: [`decisions.md`](decisions.md).

---

## 5. Bugünkü Gerçek Durum
- Repo'da yalnız `LICENSE` + bu yönetişim dokümanları + kapsam dosyası var.
- **Henüz kod, paket iskeleti, bağımlılık tanımı veya docker yapılandırması yok.**
- Bir sonraki somut adım: Faz 1 öncesi Python proje iskeleti + Faz 1 (mevzuat-mcp entegrasyonu).
