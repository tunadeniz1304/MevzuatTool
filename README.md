# MevzuatTool

> Soru × Mevzuat MVP — mevzuat.gov.tr mevzuatını yapısal olarak çekip RAG'a uygun biçimde hazırlayan ve bir soruya/atıfa karşılık **ilgili mevzuat maddelerini getiren**, dockerize edilmiş bir retrieval pipeline'ı.

**Durum:** 🟡 Pre-MVP — kurulum/yönetişim fazı. Kod henüz yok. Bkz. [`status.md`](status.md).

---

## Ne yapar?
Bir kanun/madde atfını veya doğal dil sorusunu alır; altında temiz, chunk'lanmış ve indexlenmiş mevzuat korpusundan **yürürlükteki ilgili maddeleri** döndürür.

Akış:
```
mevzuat-mcp ile çek → madde chunk + metadata → temiz korpus (JSONL) → embed + index → sorgu/retrieve
```

> **Sınır:** Pipeline retrieval'da biter. Cevabı yazan LLM (generation) **kapsam dışıdır** — en sonda config'le takılan, swap'lanabilir bir endpoint olarak bırakılmıştır.

## Kapsam İçi
Veri çekme (mevzuat-mcp) · yapısal chunking (madde/fıkra) · zengin metadata (yürürlük/mülga, R.G., hiyerarşi) · temiz JSONL korpus · embedding + hybrid index · atıf & doğal dil retrieval · docker-compose.

## Kapsam Dışı (future work)
LLM generation · GraphRAG / ileri RAG · formal eval harness · PDF/OCR · içtihat/özelge (`yargi-mcp`).
Detay: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md).

---

## Dokümantasyon
| Dosya | İçerik |
|---|---|
| [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md) | Kapsam tanımı (kaynak doğruluk) |
| [`roadmap.md`](roadmap.md) | Faz planı |
| [`status.md`](status.md) | Güncel ilerleme |
| [`compliance.md`](compliance.md) | Kapsam uygunluk checklist'i |
| [`arch.md`](arch.md) | Güncel mimari durum |
| [`decisions.md`](decisions.md) | Karar kaydı (ADR) |
| [`commit_discipline.md`](commit_discipline.md) | Commit / branch kuralları |
| [`CLAUDE.md`](CLAUDE.md) | AI ajan / katkı sağlayıcı için proje hafızası |

## Teknoloji (planlanan)
Yaklaşım: **vanilla RAG** (graph/agentic değil), retrieval yarısı.
Python · `saidsurucu/mevzuat-mcp` · embedding (aday: BGE-M3) · vektör store (Qdrant veya pgvector) · hybrid arama (dense + BM25) · Docker Compose.

## Kurulum
> ⏳ Henüz yok. Dockerize hedefi Faz 7. Tamamlandığında: `docker compose up`.

## Katkı
Çalışmaya başlamadan önce [`commit_discipline.md`](commit_discipline.md) okunmalıdır:
- `main`'e doğrudan push **yasak** — `phase-N/feature-adi` branch'leri + PR.
- Commit mesajlarında AI co-author / "Generated with" satırı **yok**.
- Atomik commit.

## Lisans
Bkz. [`LICENSE`](LICENSE).
