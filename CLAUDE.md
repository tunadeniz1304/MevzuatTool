# CLAUDE.md — Proje Hafızası

Bu dosya, projede çalışan her AI ajanın (ve insanın) **önce okuması gereken** kalıcı bağlamdır.
Tek doğruluk kaynakları: kapsam → [`mevzuat-mvp-kapsam.md`](docs/mevzuat-mvp-kapsam.md), kurallar → bu dosya + [`commit_discipline.md`](docs/commit_discipline.md).

> Not: Proje dokümanları `docs/` altındadır. `README.md` ve bu `CLAUDE.md` kökte kalır (GitHub ana sayfa + Claude Code otomatik yükleme için).

---

## Proje nedir
mevzuat.gov.tr **kanunlarını** (yalnız `KANUN` türü) `mevzuat-mcp` ile çekip RAG'a uygun yapısal chunk + metadata'ya dönüştüren ve bir soruya/atıfa karşılık **ilgili yürürlükteki kanun maddelerini getiren**, dockerize MVP.

## En kritik sınır — UNUTMA
- **Pipeline retrieval'da BİTER.** LLM / cevap üretme (generation) **KAPSAM DIŞI.** Generation, en sonda config'le takılan, OpenAI-uyumlu, swap'lanabilir bir endpoint olarak bırakılır — build buna bağımlı değildir.
- **Yaklaşım = vanilla RAG.** Graph/agentic/advanced RAG **YAPMA** (future work). Bu MVP, vanilla RAG'ın retrieval yarısı. Doğru vanilla = madde-seviyesi yapısal chunking + hybrid (dense+BM25); bunlar "advanced" değil.
- **Yalnız `KANUN` türü.** KHK/tüzük/yönetmelik/tebliğ **YAPMA** — kapsam dışı (ADR-0013). `mevzuat_tur=KANUN`.
- Yeni bir özellik eklemeden önce **mutlaka** [`compliance.md`](docs/compliance.md) "Kapsam Dışı" listesine bak. Listeye takılıyorsa **yapma**.

## Değişmez mimari ilkeler
1. Veri kaynağı yalnızca `saidsurucu/mevzuat-mcp` API'leri — **kendi scraper'ını yazma**.
2. Sadece HTML/Markdown içerik; **PDF/OCR yok**.
3. Atomik chunk birimi = **madde** (uzun maddeler fıkra bazında); naive sabit-boy token chunking **yapma**.
4. `kanun → (kitap/kısım/bölüm) → madde → fıkra → bent` hiyerarşisini koru.
5. **Yürürlük durumu (yürürlükte/mülga)** her chunk'ta birinci sınıf metadata; mülga ayrılabilir olmalı.
6. Korpus çıktısı bağımsız teslim edilebilir JSONL `{id, text, metadata}` — modüler sınır.
7. Önce dar korpusla çalıştır, sonra ölçekle. Başlangıç korpusu tek kanun değil, **yapısal çeşitlilik içeren küçük set** (bkz. docs/decisions.md ADR-0011). Tüm mevzuatı baştan çekme.

## Commit & branch disiplini (özet — tam metin docs/commit_discipline.md)
- Commit mesajlarında **AI co-author / "Generated with" satırı YASAK.** (Bu, Claude'un varsayılan davranışını bilinçli olarak ezer.)
- `main`'e **doğrudan push YASAK.** Çalışma branch'lerde + PR.
- Branch adı: **`phase-N/feature-adi`** (ör. `phase-2/structural-chunking`).
- **Atomik commit** — tek mantıksal değişiklik; `type(scope): özet` formatı.

## Teknoloji (planlanan)
Python · mevzuat-mcp · embedding (aday: BGE-M3) · vektör store **açık karar: Qdrant↔pgvector** · hybrid arama (dense + BM25) · docker-compose.

## Doküman haritası
| Soru | Dosya |
|---|---|
| Kapsam nedir? | `docs/mevzuat-mvp-kapsam.md` |
| Hangi fazdayız / ne kaldı? | `docs/status.md` |
| Faz planı? | `docs/roadmap.md` |
| Kapsama uygun muyum? | `docs/compliance.md` |
| Mimari bugün ne durumda? | `docs/arch.md` |
| Bu karar neden böyle? | `docs/decisions.md` |
| Commit/branch nasıl? | `docs/commit_discipline.md` |

## Bugünkü durum (2026-06-18)
Faz 0 (kurulum/yönetişim). Repo'da yalnız LICENSE + yönetişim dokümanları var; **kod henüz yok.** Sıradaki: Python iskeleti + Faz 1 (mevzuat-mcp entegrasyonu).
