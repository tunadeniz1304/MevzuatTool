# Mimari Durum (Architecture)

**Son güncelleme:** 2026-09-28
**Olgunluk:** 🟢 Ingestion + indexing + retrieval kütüphanesi + HTTP servisi çalışıyor. Korpus 31.419 chunk, 3-bacak R@10 = 0.6885 (bugünkü index). Eksik: atıf modu, docker-compose.

Bu dosya **güncel mimari durumu** tutar (bugün ne var, ne kararlaştırıldı, ne açık).
Kararların **gerekçesi/tarihçesi**: [`decisions.md`](decisions.md). Kapsam: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md). İlerleme: [`status.md`](status.md).

---

## 1. Gerçekleşen Mimari (uçtan uca, bugün)

> **Tür izolasyonu:** Aşağıdaki zincir `src/kanun/` içindir. Tebliğ/yönetmelik eklenirse
> **kendi kopyalarını** alır (`src/teblig/`, `src/yonetmelik/`) — kod paylaşımı YOK. §7'ye bak.

```
┌────────────────────── INGESTION (offline, çalışıyor) ───────────────────────┐
│                                                                             │
│  bedesten API ──► fetch.py ──────► data/kanun/raw/ (916 HTML + 912 tree)     │
│  (httpx, 429/Retry-After)          html_<mid>.html · treejson_<mid>.json     │
│                                     │                                        │
│                strip_html (\x1f paragraf sınırı)                             │
│                                     ▼                                        │
│  normalize.py ─► chunker.py ─► tree.py ─► enrich.py ─► corpus.py             │
│  (satır/tire)    (madde böl,   (hiyerarşi  (birleştir:  ({id,text,metadata}) │
│                   bleed-kırp)   index)      dipnot·künye·fıkra·id)           │
│                                     │                                        │
│                                     ▼                                        │
│                    data/kanun/korpus.jsonl  (31.419 chunk)                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │  ◄── MODÜLER SINIR (bağımsız teslim)
┌───────────────────── INDEXING (offline, çalışıyor) ──┼──────────────────────┐
│  colab/bge_m3_embed.ipynb ──► dense + BGE-sparse vektörler                   │
│  ingest_qdrant.py ──► Qdrant (dense + sparse + payload)                      │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌──────────── RETRIEVAL (online: src/kanun/retrieval/search.py) ┼─────────────┐
│  HTTP ─► api/app.py (FastAPI: POST /ara, GET /saglik)  ✓ ADR-0017            │
│           │                                                                  │
│  sorgu ─► embed (BGE-M3: torch FP32 | ONNX FP32 | ONNX int8 ✓ ADR-0016)      │
│           ├─► dense       (Qdrant)                                           │
│           ├─► BGE-sparse  (Qdrant)                                           │
│           └─► klasik BM25 (HizliBM25, korpus text)                           │
│                    └─► 3-bacak WSUM füzyon + yürürlük filtresi               │
│                    └─► (ops., istek başına) reranker ilk 20 aday  ✓ ADR-0015  │
│                               ─► sıralı maddeler                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                     ⋯⋯ KAPSAM DIŞI: LLM / generation ⋯⋯
                     (en sonda config'le takılan swap'lanabilir endpoint)
```

**Eksik ok:** `atıf modu` (kanun/madde/fıkra/bent → metadata filtresiyle kesin getirme) henüz yok.
Arama tek yerde (`HybridArama`); `search_qdrant.py` CLI'ı, ölçüm script'leri ve servis onu çağırır.

---

## 2. Bileşenler ve Durum

| Bileşen | Sorumluluk | Durum | Nerede |
|---|---|---|---|
| **Veri çekici** | bedesten API'den HTML + madde ağacı; 429/Retry-After uyumlu, cache'li | ✅ çalışıyor | `fetch.py` |
| **Yapısal chunker** | madde bölme + bleed-kırpma + yürürlük tespiti | ✅ çalışıyor | `chunker.py` |
| **Hiyerarşi index** | ağaç → kitap/kısım/bölüm/ayırım konumu | ✅ çalışıyor | `tree.py` |
| **Fıkra/bent parser** | fıkra→bent→alt-bent ağacı + seviye yürürlüğü | ✅ çalışıyor | `fikra.py` |
| **Metadata zenginleştirici** | dipnot, değişiklik künyesi, tablo, id birleştirme | ✅ çalışıyor | `enrich.py` |
| **Korpus artifact** | JSONL `{id, text, metadata}` (modüler sınır) | ✅ 31.419 chunk | `corpus.py` |
| **Embedder** | BGE-M3 dense (CLS pooling) + sparse | ✅ çalışıyor | `colab/`, `retrieval/embed.py` |
| **Vektör store** | dense+sparse index + payload filtre | ✅ Qdrant (ADR-0008) | `ingest_qdrant.py` |
| **Sparse/BM25** | hybrid lexical bacak (BGE-sparse + klasik BM25) | ✅ 3-bacak WSUM (ADR-0010) | `retrieval/search.py` |
| **Retrieval — NL modu** | doğal dil → hybrid semantik + yürürlük filtresi | ✅ kütüphane | `retrieval/search.py` (`HybridArama`) |
| **Çıkarım backend'i** | sorgu embed + reranker: torch / ONNX FP32 / ONNX int8 | ✅ ADR-0016 | `retrieval/embed_onnx.py`, `fabrika.py` |
| **Retrieval — atıf modu** | kanun/madde/fıkra/bent → metadata filtresi | ⬜ **kod yok** | — |
| **Reranker** | ilk 20 adayı yeniden sıralama (`bge-reranker-v2-m3`) | ✅ entegre, varsayılan kapalı (ADR-0015) | `retrieval/rerank.py` |
| **Servis / API** | HTTP arayüzü (`/ara`, `/saglik`) | ✅ FastAPI (ADR-0017) | `src/kanun/api/app.py` |
| **Docker compose** | Qdrant + ingestion + retrieval orkestrasyonu | ⬜ yok | — |
| **LLM/generation** | cevap üretimi | ⛔ **kapsam dışı** (config endpoint) | — |

---

## 3. Mimari İlkeler (değişmez)
1. **Retrieval'da biter.** Generation kapsam dışı; yalnızca config'le takılan, OpenAI-uyumlu, swap'lanabilir endpoint.
2. **Modüler sınır.** Korpus artifact bağımsız teslim edilebilir; ingestion ↔ retrieval gevşek bağlı.
   *(Kanıt: `handoff/` klasörü — build zinciri ana repodan bağımsız çalıştırıldı, birebir aynı korpusu üretti.)*
3. **Yürürlük durumu birinci sınıf.** Mülga/yürürlükte ayrımı metadata'da taşınır ve filtrelenebilir. Mülga chunk'lar korpusta KALIR (tarihsel sorgu), retrieval'da filtrelenir.
4. **Yapı korunur.** Madde/fıkra hiyerarşisi chunk ve metadata boyunca kaybolmaz; naive chunking yok.
5. **Önce çalıştır, sonra ölçekle.** Dar korpusla uçtan uca çalış, sonra genişlet. *(3 kanun → 916 kanun)*
6. **Vanilla RAG.** Yaklaşım kasıtlı olarak vanilla RAG'tır; graph/agentic/advanced değil. İleri teknikler future work.

---

## 4. Teknoloji Kararları (özet)

| Konu | Seçim | Durum |
|---|---|---|
| Yaklaşım (RAG tipi) | vanilla RAG (graph/agentic değil) | ✅ karar |
| Veri kaynağı | bedesten API (mevzuat-mcp sözleşmesi) | ✅ karar |
| Kapsam (tür) | yalnız `KANUN` (ADR-0013) | ✅ karar |
| bedesten erişimi | saf `httpx` (ADR-0012 sapması, aşağıda §6) | ✅ uygulandı |
| Dil/runtime | Python 3.10+ | ✅ uygulandı |
| Embedding | **BGE-M3** (ADR-0007), dense=CLS pooling | ✅ uygulandı |
| Vektör store | **Qdrant** (ADR-0008) | ✅ uygulandı |
| Arama | 3-bacak hybrid: dense + BGE-sparse + klasik BM25, WSUM (ADR-0010) | ✅ uygulandı |
| Reranker | `bge-reranker-v2-m3` (ADR-0009/0015) | ✅ istek başına, varsayılan kapalı |
| Çıkarım | ONNX Runtime CPU, dinamik int8 (ADR-0016) | ✅ uygulandı |
| Servis | FastAPI + uvicorn (ADR-0017) | ✅ uygulandı |
| Korpus formatı | JSONL `{id, text, metadata}` | ✅ uygulandı |
| Paketleme | docker-compose | ⬜ yapılmadı |

> Detaylı gerekçeler ve açık kararlar: [`decisions.md`](decisions.md).

---

## 5. Kritik yapısal invariant'lar (build zinciri)

Bunlar bozulursa korpus sessizce bozulur — değişiklik sonrası mutlaka doğrula.

| Invariant | Nerede | Bozulursa |
|---|---|---|
| `\x1f` paragraf sınırı üretilir ve korunur | `fetch.py` (strip_html) → `normalize.py` → `fikra.py` | Numarasız fıkralar tek bloğa çöker (89.745 → ~46.643) |
| Bent-listeli fıkrada devam-paragraf koruması | `fikra.py` (`_bent_listeli_fikra`) | Rakamlı bent listeleri parçalanır (k193 m7: 7 → 0 bent) |
| `'Ancak'` yeni-fıkra sinyali **değildir** | `fikra.py` (`_YENI_FIKRA_SINYALI`) | Bent-içi istisna cümlesi yeni fıkra sanılır, bent kopar |
| Bleed-kırpma 0 yanlış-pozitif | `chunker.py` + `enrich.py` | Ya çöp sızar ya gerçek içerik kırpılır |
| E-tuzağı guard'ı (`gercek_kanun_no`) | `enrich.py` (`_ETUZAK`) | TMK/TBK/TTK/FSEK/Anayasa madde başlıkları kırpılır |
| Mülga maddeyi eleme | `corpus.py` | Tarihsel sorgu için gerekli maddeler kaybolur |
| Chunk id = `mid` tabanlı (kanun_no değil) | `ids.py`, `build_corpus.py` | Aynı kanun_no'lu iki kanun çakışır (ör. 6551) |

**Doğrulama refleksi:** `python scripts/kanun/build_corpus.py` → 916 kanun / 31.419 chunk; `k193 m7` = 2 fıkra, 7 bent.

---

## 6. Bilinçli sapmalar ve bilinen sınırlar

**ADR-0012 sapması (transport).** Karar "yerel mevzuat-mcp MCP server + MCP client" diyordu.
Gerçekte `fetch.py` saf `httpx` ile doğrudan bedesten API'sine gidiyor. **Sebep:** mevzuat-mcp'nin
bedesten client'ı HTTP 429'u ve `Retry-After` header'ını yutuyordu → throttle görünmez oluyor, kör
backoff başarısız oluyordu. Aynı API, aynı sözleşme, aynı veri; yalnız transport bağımsız ve
pydantic/ABI kırılganlığından muaf. (Kaynak: `fetch.py` modül docstring'i.)

**Bilinen sınırlar:**
1. **Atıf modu yok** — metadata hazır (kanun_no + madde_no + fıkra/bent ağacı), kod yazılmadı.
2. **R.G. tarihi** chunk metadata'sında taşınmıyor (bedesten liste yanıtında var).
3. **Reranker CPU'da pahalı ve R@1'i düşürüyor** (ADR-0015) — istek başına açık, varsayılan kapalı.
   **Qdrant index'i korpusun gerisinde** (1.678 maddede yürürlük uyuşmazlığı) → taban 0.700 → 0.6885.
4. **Sıralama darboğazı:** R@100 = 0.809 >> R@10 = 0.700 → doğru madde getiriliyor, sıralanamıyor.
   Aynı-KANUN toleransıyla R@10 = 0.889 → darboğaz **madde ayrımı**, kanun ayrımı değil.
5. **Çok-versiyonlu kanun artefaktı:** 6111/6736/7143/7326/7440 aynı konuyu farklı no ile düzenler;
   gold "6111" derken sistem "7326" getirince haksız 0 alır.
6. **Fıkra↔bent terminoloji toleransı** yalnız ölçüm script'inde vardı; canlı retrieval'a taşınmadı
   (bkz. `status.md` dürüstlük notu).

---

## 7. Tür izolasyonu — mevzuat türleri arasında SIFIR kod paylaşımı

**Karar (2026-07-10):** Her mevzuat türü kendi paketinde, **sıfırdan** yazılır. Ortak modül,
ortak soyutlama, `if tur == "KANUN"` dalı **yoktur.**

```
src/kanun/       ✅ 15 modül + retrieval/     scripts/kanun/ + kanun/retrieval/   tests/kanun/
src/teblig/      ⬜ iskelet                   scripts/teblig/                     tests/teblig/
src/yonetmelik/  ⬜ iskelet                   scripts/yonetmelik/                 tests/yonetmelik/

data/kanun/{raw/, korpus.jsonl}   data/teblig/{...}   data/yonetmelik/{...}
data/gold/                        altınset gold set (tür-bağımsız ölçüm verisi)
```

**Neden ortak soyutlama değil?** Türler yapısal olarak farklı ve bu fark parser'ın *özünde*:
- Tebliğlerin `mevzuatMaddeTree`'si çoğu zaman **boş** döner; kanun parser'ı ağaca dayanıyor
  (hiyerarşi, madde başlıkları, bleed-marker'ları).
- Kanunun bleed-kırpma kuralları (`"...yürütür"` anchor'ı, kanun-sonu cetvel eki, E-tuzağı
  guard'ı) tebliğde **anlamsız — hatta zararlı.**
- Ortak bir `chunker` bu farkları `if/else` ile taşısaydı, bir türde yapılan düzeltme diğerini
  sessizce bozardı. Bu parser'da sessiz bozulma = korpus zehri (bkz. §5 invariant tablosu).

**Bedeli kabul edildi:** bir bug 3 yerde düzeltilir. Karşılığında: bir türe dokunmak diğerini
**asla** bozamaz; her tür kendi test setiyle bağımsız doğrulanır.

**Yeni tür eklerken:**
1. **Önce ölç, sonra yaz.** Birkaç örnek çek (`mevzuatTurList: ["TEBLIGLER"]`), yapısını incele:
   madde ağacı geliyor mu? Madde işareti nasıl? Fıkra/bent var mı?
2. `src/kanun/` modüllerini **oku ve KOPYALA** — `import` etme. Kopyayı türe özgü hale getir.
3. Çıktı şeması `{id, text, metadata}` **aynı kalsın** — tek "sözleşme" budur; ileride üç korpus
   tek Qdrant'ta birleşebilir. `metadata.mevzuat_tur` ekle (kanun korpusunda bu alan yok, tek-tür
   olduğu için örtük).
4. Veri yolun **kendi tür klasörün** olsun. `build_corpus.py` çıktıyı `"w"` modunda ezer —
   tür-kapsamlı yol sayesinde tebliğ build'i kanun korpusunu asla ezemez.

Ayrıntı: `src/teblig/__init__.py`, `src/yonetmelik/__init__.py` (iskelet docstring'leri).
