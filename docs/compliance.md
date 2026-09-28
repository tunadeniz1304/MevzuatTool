# Kapsam Uygunluk Checklist'i (Compliance)

Bu dosya, yapılan her işin [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md) ile uyumunu **doğrular**.
İki yönlü kontrol eder:
1. **Kapsam İçi** maddeler eksiksiz/sadık yapılıyor mu? (yapılmalı ✅)
2. **Kapsam Dışı** maddeler yanlışlıkla projeye sızıyor mu? (yapılmamalı 🚫 — *scope creep guard*)

> Bir özellik eklemeden önce: aşağıdaki "Kapsam Dışı" listesine takılıyor mu diye bak. Takılıyorsa **yapma**.

İşaretler: ✅ uyumlu/yapıldı · 🟡 kısmen · ⬜ henüz değil · ❗ ihlal riski

---

## A. Kapsam İçi — sadakat kontrolü (YAPILMALI)

> Son kontrol: 2026-09-28. Ayrıntılı durum: [`status.md`](status.md).

### 1. Veri Çekme
- [x] Kaynak yalnızca `mevzuat-mcp` **API sözleşmesi** (bedesten `searchDocuments` / `mevzuatMaddeTree` / `getDocumentContent`) — ⚠️ transport MCP client değil, saf `httpx` (ADR-0012 sapması; gerekçe: mevzuat-mcp client 429/`Retry-After`'ı yutuyordu — bkz. `arch.md` §6)
- [x] Yalnızca **`KANUN`** türü çekiliyor (`mevzuatTurList: ["KANUN"]`, `fetch.py`); KHK/tüzük/yönetmelik/tebliğ ALINMIYOR
- [x] Kendi web scraper'ımız **yok** (resmî API endpoint'leri kullanılıyor, HTML kazıma yok)
- [x] Yalnızca HTML içerik alınıyor; PDF'ler işlenmiyor
- [x] Başlangıçta dar korpus (3-5 kanun) → sonra 916 kanuna ölçeklendi (ADR-0011 sırası korundu)

### 2. Yapısal Chunking
- [x] Atomik birim = madde (`chunker.py split_articles`)
- [x] Uzun maddeler fıkra bazında bölünüyor (`fikra.py parse_fikralar` — 89.745 fıkra)
- [x] `kanun → (kitap/kısım/bölüm/ayırım) → madde → fıkra → bent → alt-bent` hiyerarşisi korunuyor
- [x] Naive sabit-boy token chunking **yapılmıyor**

### 3. Metadata
- [x] Alanlar: `kanun_ad`, `kanun_no`, `mevzuat_id`, `madde_no`, `madde_baslik`, `madde_tipi`, fıkra/bent ağacı, hiyerarşi path, `maddeId`
- [ ] ❗ **R.G. tarihi chunk metadata'sında YOK** (bedesten liste yanıtında mevcut, korpusa taşınmadı) — açık eksik
- [ ] ❗ `mevzuat_tur` alanı chunk'ta yok (korpus tek-tür olduğu için örtük; tebliğ vb. eklenirse gerekir)
- [x] **Yürürlük durumu (yürürlükte / mülga)** her chunk'ta (`yurutluk`) + fıkra/bent seviyesinde ayrı
- [x] Mülga hükümler işaretli ve **korpusta tutuluyor** (elenmiyor — tarihsel sorgu; 1.718 chunk)

### 4. Temiz Korpus Artifact
- [x] Çıktı JSONL: `{id, text, metadata}` — 31.419 chunk (`corpus.py`)
- [x] Bağımsız teslim edilebilir (modüler sınır korunuyor) — `handoff/` klasörü ana repodan bağımsız çalıştırılıp birebir aynı korpus üretildi
- [x] Şema dokümante edilmiş (`handoff/HANDOFF.md` §1)

### 5. Embedding + Indexleme
- [x] Türkçe'ye uygun embedding modeli: **BGE-M3** (ADR-0007), dense=CLS pooling
- [x] Vektör store kuruldu: **Qdrant** (ADR-0008), dense + sparse + payload filtre
- [x] Hybrid arama: 3-bacak (dense + BGE-sparse + klasik BM25), WSUM füzyon (ADR-0010)

### 6. Sorgu + Retrieval
- [ ] ❗ **Atıf modu (metadata filtresiyle kesin getirme) — KOD YOK.** Metadata hazır (kanun_no + madde_no + fıkra/bent ağacı) ama yazılmadı.
- [x] Doğal dil modu (hybrid semantik) çalışıyor — kütüphane `src/kanun/retrieval/search.py` (`HybridArama`), R@10 = 0.6885 (bugünkü index; ADR-0015)
- [x] Reranker entegre — istek başına, varsayılan kapalı (ADR-0015); ONNX int8 CPU çıkarımı (ADR-0016)
- [x] Çıktı: sıralı ilgili maddeler + metadata (yürürlük filtreli)
- [x] Servis/API katmanı — FastAPI `POST /ara`, `GET /saglik` (`src/kanun/api/app.py`, ADR-0017)

### 7. Dockerize
- [ ] `docker-compose` ile vektör DB + ingestion + retrieval/API — **başlamadı**
- [ ] Uçtan uca reproducible

---

## B. Kapsam Dışı — sızma kontrolü (YAPILMAMALI 🚫)

Aşağıdakilerden **herhangi biri** projede iş olarak yapılıyorsa, kapsam ihlali var demektir:

- [ ] 🚫 LLM ile **cevap üretme (generation)** kodlandı mı? → Pipeline retrieval'da bitmeli. (LLM yalnızca en sonda config'le takılan swap'lanabilir endpoint)
- [ ] 🚫 GraphRAG / **agentic RAG** / advanced RAG teknikleri (atıf grafı, bitemporal versiyonlama, multi-representation index, fine-tuned embedder, RAPTOR) eklendi mi? → Yaklaşım **vanilla RAG**'tır; bunlar future work.
- [ ] 🚫 Formal eval / benchmark harness kuruldu mu? → küçük sanity kontrolü hariç, future work
      *(Not: `metrik_gecikme.py` tek script + sabit protokol + tek tablo — harness değil; sınır ADR-0016 "Kapsam sınırı". Eşzamanlı yük testi, MTEB, genel çerçeve YOK.)*
- [ ] 🚫 PDF / OCR işleme eklendi mi? → kapsam dışı
- [ ] 🚫 İçtihat / özelge (`yargi-mcp`: Yargıtay, Danıştay, GİB) işleniyor mu? → bu MVP dışı
- [ ] 🚫 Kanun dışı tür (KHK / tüzük / yönetmelik / tebliğ) işlendi mi? → bu MVP yalnız **KANUN** (ADR-0013)
- [ ] 🚫 Tüm mevzuatı baştan çekme denemesi mi yapılıyor? → önce dar korpus, sonra ölçekle

> Yukarıdaki kutulardan biri işaretlenirse: **dur, gözden geçir.** Gerçekten gerekliyse `decisions.md`'ye kapsam değişikliği olarak kaydet.

---

## C. Modüler Sınır Kontrolü
- [x] Veri-hazırlama aşaması bağımsız bir **korpus artifact** üretiyor (söküp verilebilir)
      → *kanıt:* `handoff/` klasörü izole dizinde çalıştırıldı, ana repoya bağımsız aynı korpusu üretti
- [x] Retrieval pipeline bu artifact'i tüketiyor (`ingest_qdrant.py` yalnız `korpus.jsonl` okur)
- [x] LLM/generation kararı build'den **bağımsız** (generation kodu hiç yok)
- [x] `corpus.py` atıf listesini bilmez — atıf-farkındalık yalnız build katmanında (`build_corpus.py`)

## D. Definition of Done
- [x] Doğal dil sorgusu → **yürürlükteki ilgili mevzuat maddeleri** dönüyor (R@10 = 0.6885; HTTP `/ara` ile de)
- [ ] ❗ **Atıf sorgusu** → kesin madde getirme (atıf modu kodu yok)
- [x] Altında temiz, chunk'lanmış + indexlenmiş korpus var (31.419 chunk, Qdrant'ta)
- [ ] Tamamı dockerize, reproducible — **Faz 7 başlamadı**

> **MVP tamamlanma durumu: 2/4.** Kalan: atıf modu + dockerize.
