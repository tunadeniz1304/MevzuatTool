# Mimari Durum (Architecture)

**Son güncelleme:** 2026-07-10
**Olgunluk:** 🟢 Ingestion + indexing + retrieval çalışıyor (script seviyesinde). Korpus 31.419 chunk, hybrid R@10 = 0.700. Eksik: atıf modu, servis/API katmanı, docker-compose.

Bu dosya **güncel mimari durumu** tutar (bugün ne var, ne kararlaştırıldı, ne açık).
Kararların **gerekçesi/tarihçesi**: [`decisions.md`](decisions.md). Kapsam: [`mevzuat-mvp-kapsam.md`](mevzuat-mvp-kapsam.md). İlerleme: [`status.md`](status.md).

---

## 1. Gerçekleşen Mimari (uçtan uca, bugün)

```
┌──────────────────────── INGESTION (offline, çalışıyor) ─────────────────────────┐
│                                                                                 │
│  bedesten API ──► fetch.py ──────► data/raw/ cache (916 HTML + 912 tree)         │
│  (httpx, 429/Retry-After)          html_<mid>.html · treejson_<mid>.json         │
│                                          │                                       │
│                     strip_html (\x1f paragraf sınırı)                            │
│                                          ▼                                       │
│  normalize.py ─► chunker.py ─► tree.py ─► enrich.py ─► corpus.py                 │
│  (satır/tire)    (madde böl,   (hiyerarşi  (birleştir:  ({id,text,metadata})     │
│                   bleed-kırp)   index)      dipnot·künye·fıkra·id)               │
│                                          │                                       │
│                                          ▼                                       │
│                          data/corpus/korpus.jsonl  (31.419 chunk)               │
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │  ◄── MODÜLER SINIR (bağımsız teslim)
┌─────────────────────── INDEXING (offline, çalışıyor) ──────────┼─────────────────┐
│  colab/bge_m3_embed.ipynb ──► dense + BGE-sparse vektörler     │                 │
│  scripts/ingest_qdrant.py ──► Qdrant (dense + sparse + payload)                  │
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │
┌─────────────────────── RETRIEVAL (online, script) ─────────────┼─────────────────┐
│  sorgu ─► retrieval/embed.py (BGE-M3) ─┬─► dense       (Qdrant)                  │
│                                        ├─► BGE-sparse  (Qdrant)                  │
│                                        └─► klasik BM25 (rank_bm25, korpus text)  │
│                            └─► 3-bacak WSUM füzyon + yürürlük filtresi           │
│                                        ─► sıralı maddeler                        │
│                            (reranker: ölçüldü ✓, entegre ✗)                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                        ⋯⋯ KAPSAM DIŞI: LLM / generation ⋯⋯
                        (en sonda config'le takılan swap'lanabilir endpoint)
```

**Eksik oklar:** `atıf modu` (kanun/madde/fıkra/bent → metadata filtresiyle kesin getirme) ve
`servis/API` katmanı henüz yok — retrieval script seviyesinde (`scripts/search_qdrant.py`).

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
| **Sparse/BM25** | hybrid lexical bacak (BGE-sparse + klasik BM25) | ✅ 3-bacak WSUM (ADR-0010) | `search_qdrant.py` |
| **Retrieval — NL modu** | doğal dil → hybrid semantik + yürürlük filtresi | ✅ script | `search_qdrant.py` |
| **Retrieval — atıf modu** | kanun/madde/fıkra/bent → metadata filtresi | ⬜ **kod yok** | — |
| **Reranker** | precision artırma (`bge-reranker-v2-m3`) | 🟡 ölçüldü (+0.04 R@10), entegre değil | `metrik_rerank.py` |
| **Servis / API** | HTTP arayüzü | ⬜ yok | — |
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
| Reranker | `bge-reranker-v2-m3` (ADR-0009) | 🟡 ölçüldü, entegre değil |
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

**Doğrulama refleksi:** `python scripts/build_corpus.py` → 916 kanun / 31.419 chunk; `k193 m7` = 2 fıkra, 7 bent.

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
3. **Reranker entegre değil** — ölçüldü (R@10 0.667→0.706), GPU/servis çözümü bekliyor.
4. **Sıralama darboğazı:** R@100 = 0.809 >> R@10 = 0.700 → doğru madde getiriliyor, sıralanamıyor.
   Aynı-KANUN toleransıyla R@10 = 0.889 → darboğaz **madde ayrımı**, kanun ayrımı değil.
5. **Çok-versiyonlu kanun artefaktı:** 6111/6736/7143/7326/7440 aynı konuyu farklı no ile düzenler;
   gold "6111" derken sistem "7326" getirince haksız 0 alır.
6. **Fıkra↔bent terminoloji toleransı** yalnız ölçüm script'inde vardı; canlı retrieval'a taşınmadı
   (bkz. `status.md` dürüstlük notu).
