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

## Teknoloji (uygulanan)
Python 3.10+ · bedesten API (saf `httpx` — ADR-0012 sapması, bkz. `docs/arch.md` §6) · **BGE-M3** embedding (ADR-0007) · **Qdrant** vektör store (ADR-0008) · 3-bacak hybrid arama: dense + BGE-sparse + klasik BM25, WSUM füzyon (ADR-0010) · docker-compose *(henüz yok)*.

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
| Metadata nasıl çıkarılıyor? | `docs/metadata-cikarim-raporu.md` |
| Yapısal-sadakat düzeltme fazları? | `docs/yapisal-sadakat-master-plan.md` |
| Retrieval ne kadar iyi (ölçüm)? | `docs/retrieval-metrikleri.md` |

## Bugünkü durum (2026-07-10)
**Faz 1-6 çalışıyor** (script seviyesinde). Ayrıntı → [`docs/status.md`](docs/status.md).

- **Korpus:** `data/corpus/korpus.jsonl` — 31.419 chunk / 916 kanun. `python scripts/build_corpus.py` ile cache'ten (`data/raw/`) ~75 sn'de **deterministik** üretilir. (89.745 fıkra, 29.428 bent, 1.718 mülga.)
- **Retrieval:** BGE-M3 + Qdrant, 3-bacak hybrid. **R@10 = 0.700**; +reranker 0.706 (ölçüldü, entegre değil).
- **Testler:** 285 test geçiyor (`pytest -q`).
- **Eksik:** atıf modu (metadata hazır, kod yok) · servis/API katmanı · docker-compose (Faz 7) · reranker entegrasyonu.

### Build zincirine dokunacaksan — kritik invariant'lar
Bunlar bozulursa korpus **sessizce** bozulur (mevcut testler yakalamayabilir):
1. **`\x1f` paragraf sınırı:** `fetch.py strip_html` üretir → `normalize.py` korur → `fikra.py` numarasız fıkraları ondan böler. Zincirin bir halkası koparsa fıkra 89.745 → ~46.643'e çöker.
2. **Bent-listeli fıkra devam-koruması** (`fikra.py`): bozulursa rakamlı bent listeleri parçalanır (k193 m7: 7 → 0 bent).
3. **`'Ancak'` yeni-fıkra sinyali DEĞİLDİR** (bilinçli): bent-içi istisna cümlesi de "Ancak" ile başlar.
4. **Mülga maddeler korpusta KALIR** (işaretli), elenmez — tarihsel sorgu için.
5. **Chunk id `mevzuatId` tabanlıdır**, `kanun_no` değil (6551 gibi çakışan kanun no'ları var).

**Doğrulama refleksi:** `python scripts/build_corpus.py` → 916 kanun / 31.419 chunk; `k193 m7` = 2 fıkra, 7 bent.

⚠️ **`build_corpus.py` çıktıyı SESSİZCE EZER** (`"w"` modu). `CORPUS_MID=...` ile tek kanun çalıştırırsan diskteki tam korpus 1 kanuna iner. Cache duruyorsa geri üretilebilir (deterministik).
