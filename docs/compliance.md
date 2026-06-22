# Kapsam Uygunluk Checklist'i (Compliance)

Bu dosya, yapılan her işin [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md) ile uyumunu **doğrular**.
İki yönlü kontrol eder:
1. **Kapsam İçi** maddeler eksiksiz/sadık yapılıyor mu? (yapılmalı ✅)
2. **Kapsam Dışı** maddeler yanlışlıkla projeye sızıyor mu? (yapılmamalı 🚫 — *scope creep guard*)

> Bir özellik eklemeden önce: aşağıdaki "Kapsam Dışı" listesine takılıyor mu diye bak. Takılıyorsa **yapma**.

İşaretler: ✅ uyumlu/yapıldı · 🟡 kısmen · ⬜ henüz değil · ❗ ihlal riski

---

## A. Kapsam İçi — sadakat kontrolü (YAPILMALI)

### 1. Veri Çekme
- [ ] Kaynak yalnızca `mevzuat-mcp` araçları (`search_mevzuat` / `get_mevzuat_madde_tree` / `get_mevzuat_content`), MCP client üzerinden
- [ ] Yalnızca **`KANUN`** türü çekiliyor (`mevzuat_tur=KANUN`); KHK/tüzük/yönetmelik/tebliğ ALINMIYOR
- [ ] Kendi web scraper'ımız **yok** (repo API'leri kullanılıyor)
- [ ] Yalnızca HTML/Markdown içerik alınıyor; PDF'ler atlanıyor
- [ ] Başlangıçta dar korpus (tüm mevzuat değil)

### 2. Yapısal Chunking
- [ ] Atomik birim = madde
- [ ] Uzun maddeler fıkra bazında bölünüyor
- [ ] `kanun → (kitap/kısım/bölüm) → madde → fıkra → bent` hiyerarşisi korunuyor
- [ ] Naive sabit-boy token chunking **yapılmıyor**

### 3. Metadata
- [ ] Zorunlu alanlar: mevzuat adı, no, tür, madde no, madde başlığı, fıkra, hiyerarşi path, kaynak, R.G. tarihi
- [ ] **Yürürlük durumu (yürürlükte / mülga)** her chunk'ta var
- [ ] Mülga hükümler işaretlenmiş/ayrılmış

### 4. Temiz Korpus Artifact
- [ ] Çıktı JSONL: `{id, text, metadata}`
- [ ] Bağımsız teslim edilebilir (modüler sınır korunuyor)
- [ ] Şema dokümante edilmiş

### 5. Embedding + Indexleme
- [ ] Türkçe'ye uygun embedding modeli
- [ ] Vektör store kuruldu (Qdrant veya pgvector)
- [ ] Hybrid arama: dense + BM25/sparse

### 6. Sorgu + Retrieval
- [ ] Atıf modu (metadata filtresiyle kesin getirme) çalışıyor
- [ ] Doğal dil modu (hybrid semantik) çalışıyor
- [ ] Çıktı: sıralı ilgili maddeler + metadata/atıf bilgisi

### 7. Dockerize
- [ ] `docker-compose` ile vektör DB + ingestion + retrieval/API
- [ ] Uçtan uca reproducible

---

## B. Kapsam Dışı — sızma kontrolü (YAPILMAMALI 🚫)

Aşağıdakilerden **herhangi biri** projede iş olarak yapılıyorsa, kapsam ihlali var demektir:

- [ ] 🚫 LLM ile **cevap üretme (generation)** kodlandı mı? → Pipeline retrieval'da bitmeli. (LLM yalnızca en sonda config'le takılan swap'lanabilir endpoint)
- [ ] 🚫 GraphRAG / **agentic RAG** / advanced RAG teknikleri (atıf grafı, bitemporal versiyonlama, multi-representation index, fine-tuned embedder, RAPTOR) eklendi mi? → Yaklaşım **vanilla RAG**'tır; bunlar future work.
- [ ] 🚫 Formal eval / benchmark harness kuruldu mu? → küçük sanity kontrolü hariç, future work
- [ ] 🚫 PDF / OCR işleme eklendi mi? → kapsam dışı
- [ ] 🚫 İçtihat / özelge (`yargi-mcp`: Yargıtay, Danıştay, GİB) işleniyor mu? → bu MVP dışı
- [ ] 🚫 Kanun dışı tür (KHK / tüzük / yönetmelik / tebliğ) işlendi mi? → bu MVP yalnız **KANUN** (ADR-0013)
- [ ] 🚫 Tüm mevzuatı baştan çekme denemesi mi yapılıyor? → önce dar korpus, sonra ölçekle

> Yukarıdaki kutulardan biri işaretlenirse: **dur, gözden geçir.** Gerçekten gerekliyse `decisions.md`'ye kapsam değişikliği olarak kaydet.

---

## C. Modüler Sınır Kontrolü
- [ ] Veri-hazırlama aşaması bağımsız bir **korpus artifact** üretiyor (söküp verilebilir)
- [ ] Retrieval pipeline bu artifact'i tüketiyor
- [ ] LLM/generation kararı build'den **bağımsız** (config'le swap'lanabilir endpoint)

## D. Definition of Done
- [ ] Atıf veya doğal dil sorgusu → **yürürlükteki ilgili mevzuat maddeleri** dönüyor
- [ ] Altında temiz, chunk'lanmış + indexlenmiş korpus var
- [ ] Tamamı dockerize, reproducible
