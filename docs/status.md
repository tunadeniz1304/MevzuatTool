# Proje Durumu (Status)

Fazlar: [`roadmap.md`](roadmap.md) · Kapsam uygunluğu: [`compliance.md`](compliance.md) · Mimari: [`arch.md`](arch.md)
Yapısal düzeltme fazları: [`yapisal-sadakat-master-plan.md`](yapisal-sadakat-master-plan.md) · Retrieval ölçümleri: [`retrieval-metrikleri.md`](retrieval-metrikleri.md)

**Son güncelleme:** 2026-09-28
**Genel durum:** 🟢 Faz 1-6 tamam. Korpus üretiliyor (31.419 chunk / 916 kanun), embed+index kurulu (BGE-M3 + Qdrant), arama kütüphanede (`HybridArama`) + FastAPI servisi (`/ara`, `/saglik`). 3-bacak taban R@10 = **0.6885** (index/korpus yürürlük uyuşmazlığı, bkz. ADR-0015); +reranker (istek başına, 20/512) 0.711 ama R@1 düşer → varsayılan kapalı. ONNX int8 sorgu embed'i kaliteyi korur (0.688), embed gecikmesini ~3× düşürür. Faz 7: docker-compose (qdrant + api + ingest profili) çalışıyor, torch'suz imaj. Kalan: atıf modu.

İşaretler: ✅ tamam · 🟡 devam ediyor · ⬜ başlamadı · ⛔ engelli

---

## Faz İlerlemesi (üst düzey)

| Faz | Ad | Durum | Kanıt |
|---|---|---|---|
| 0 | Kurulum & Yönetişim | ✅ | Yönetişim dokümanları + branch disiplini |
| 1 | Veri Çekme | ✅ | `fetch.py` — 916 kanun HTML+tree cache'li |
| 2 | Yapısal Chunking | ✅ | `chunker.py` + `fikra.py` — madde/fıkra/bent ağacı |
| 3 | Metadata | ✅ | `enrich.py` — hiyerarşi, yürürlük, künye, dipnot, tablo |
| 4 | Temiz Korpus Artifact | ✅ | `korpus.jsonl` — 31.419 chunk `{id,text,metadata}` |
| 5 | Embedding + Indexleme | ✅ | BGE-M3 (Colab) → Qdrant (dense+sparse) |
| 6 | Sorgu + Retrieval | ✅ | `HybridArama` + reranker (ops.) + ONNX int8 + FastAPI servisi (ADR-0015/16/17) |
| 7 | Dockerize | ✅ | `docker-compose.yml` + `Dockerfile` (ADR-0018); compose üzerinden `/ara` R@10 = in-process |

**Test durumu:** 381 test geçiyor (`pytest -q`); 3 gerçek-model parity testi `pytest -m model` ile ayrı (ağ/model indirmez varsayılan koşu).

---

## Korpus — üretilen artifact (doğrulanmış)

`data/kanun/korpus.jsonl` — `python scripts/kanun/build_corpus.py` ile cache'ten ~75 sn'de deterministik üretilir.

| Ölçü | Değer |
|---|---|
| Toplam chunk | **31.419** |
| Benzersiz kanun | 916 |
| `madde_tipi` | asil 25.564 · gecici 4.059 · ek 1.691 · mukerrer 57 · islenmistir_yonlendirme 48 |
| `yurutluk` | yürürlükte 29.701 · mülga 1.718 |
| Fıkra (metadata ağacı) | 89.745 |
| Bent | 29.428 |

> Yönlendirme chunk'ları (48) yalnız `unique_atiflar.json` varsa üretilir; dosya yoksa korpus 31.371 chunk olur ve başka hiçbir şey değişmez.

---

## Faz 0 — Kurulum & Yönetişim ✅
- [x] Yönetişim dokümanları: kapsam, roadmap, status, compliance, arch, decisions, commit_discipline
- [x] `README.md`, `.gitignore`, `CLAUDE.md`
- [x] Python iskeleti — venv + `src/kanun/` + `requirements.txt` + `pytest.ini`
- [x] Tür-izolasyonlu klasör yapısı (`src/{kanun,teblig,yonetmelik}/`) — 2026-07-10
- [ ] GitHub `main` branch protection ayarı (UI'dan — bkz. commit_discipline.md §5.2)

## Faz 1 — Veri Çekme ✅
- [x] `fetch.py` — bedesten API'sinden 429/Retry-After uyumlu, cache'li, devam-edilebilir çekim
- [x] 916 KANUN listesi + HTML + madde-ağacı cache'li (`data/kanun/raw/`)
- [x] Yalnız `KANUN` türü (ADR-0013); KHK/tüzük/yönetmelik/tebliğ kapsam dışı
- [x] Yalnız HTML içerik; PDF yok
- [x] Kendi scraper'ı yok — `saidsurucu/mevzuat-mcp` API sözleşmesi kullanılıyor

> **Not (ADR-0012 sapması, bilinçli):** MCP client yerine `fetch.py` saf `httpx` ile bedesten API'sine gidiyor. Sebep: mevzuat-mcp'nin bedesten client'ı HTTP 429'u ve `Retry-After` header'ını yutuyordu → throttle görünmez oluyordu. Aynı API, aynı sözleşme; yalnız transport katmanı bağımsız (bkz. `fetch.py` modül docstring'i).

## Faz 2 — Yapısal Chunking ✅
- [x] `normalize_text` — satır kırığı birleştir + tire tek tip (`\x1f` paragraf sınırı korunur)
- [x] `split_articles` — esnek madde regex + bleed-kırpma (0 yanlış-pozitif hedefi)
- [x] `parse_fikralar` — fıkra `(N)` / numarasız paragraf; bent `a)`/`1.`; alt-bent `1)`
- [x] `extract_status` — mülga/iptal tespiti (konum-duyarlı: madde vs fıkra seviyesi)
- [x] Hiyerarşi-path (Kitap/Kısım/Bölüm/Ayırım) — `tree.py` + `enrich.py`
- [x] Naive sabit-boy token chunking **yapılmadı**

## Faz 3 — Metadata ✅
- [x] Alanlar: `mevzuat_id`, `kanun_no`, `kanun_ad`, `madde_no`, `madde_baslik`, `madde_tipi`, hiyerarşi (kitap/kısım/bölüm/ayırım + `hiyerarsi_yolu`), `maddeId`
- [x] **Yürürlük durumu** her chunk'ta (`yurutluk`); mülga chunk'lar korpusta KALIR ve işaretlidir (tarihsel sorgu)
- [x] Fıkra/bent/alt-bent ağacı (`fikralar[]`) — her seviyenin kendi yürürlüğü
- [x] Değişiklik künyeleri yapısal (`degisiklik_gecmisi[]`), dipnotlar (`dipnotlar[]`), tablolar (`tablolar[]`)
- [ ] R.G. tarihi — chunk metadata'sında **yok** (bedesten liste yanıtında var, korpusa taşınmadı)

## Faz 4 — Temiz Korpus Artifact ✅
- [x] JSONL şeması `{id, text, metadata}` — `corpus.py`
- [x] `scripts/kanun/build_corpus.py` çıktıyı yazıyor (deterministik, cache'ten 75 sn)
- [x] Modüler sınır: `corpus.py` atıf listesini bilmez; atıf-farkındalık yalnız build katmanında
- [x] Şema dokümante: [`handoff/HANDOFF.md`](../handoff/HANDOFF.md) §1 (klasör ignore'lu, yerel)
- [x] Boş-gövde / işlenmiştir-notu / saf-artefakt maddeler eleniyor

## Faz 5 — Embedding + Indexleme ✅
- [x] Embedding: **BGE-M3** (ADR-0007), dense=CLS pooling; korpus embed'i Colab'da (`colab/bge_m3_embed.ipynb`)
- [x] Vektör store: **Qdrant** (ADR-0008) — dense + BGE-sparse + payload
- [x] Hybrid: dense + BGE-sparse + klasik BM25 (`rank_bm25`) — 3-bacak WSUM füzyon (ADR-0010)
- [x] `scripts/kanun/retrieval/ingest_qdrant.py` — vektörleri yükle

## Faz 6 — Sorgu + Retrieval ✅
- [x] Doğal dil modu: 3-bacak hybrid + yürürlük filtresi — kütüphane `src/kanun/retrieval/search.py` (`HybridArama`), eski script ile 50/50 birebir
- [x] Ölçüm altyapısı: altınset gold (21.737 sızıntısız sorgu), R@k/MRR/nDCG (`scripts/kanun/retrieval/metrik_*.py`, `src/kanun/retrieval/olcum.py`)
- [x] Reranker (`bge-reranker-v2-m3`) **entegre** (ADR-0015): 3-bacak üstünde yeniden ölçüldü; varsayılan kapalı, istek başına açık (önerilen 20 aday / 512 token)
- [x] ONNX Runtime + dinamik int8 (ADR-0016): parity + 2000 sorgu kalite + p50/p95/p99 gecikme tablosu
- [x] Servis katmanı: FastAPI `POST /ara`, `GET /saglik` (ADR-0017)
- [ ] **Atıf modu** (kanun/madde/fıkra/bent → metadata filtresiyle kesin getirme) — kod olarak YOK (bu fazın kapsamı dışı bırakıldı)

### Ölçülmüş retrieval performansı (2000 sorgu, altınset)
| Konfigürasyon | R@1 | R@10 | MRR |
|---|---|---|---|
| Hybrid (dense+sparse, RRF) | 0.436 | 0.667 | 0.507 |
| 3-bacak WSUM (eşit ağırlık) — 2026-07 ölçümü | 0.491 | 0.700 | 0.562 |
| 3-bacak WSUM — **bugünkü index** (2026-09) | 0.481 | **0.6885** | 0.5515 |
| + Reranker 20 aday / 512 (istek başına) | 0.4645 | **0.711** | 0.5501 |
| ONNX int8 sorgu embed (reranker yok) | 0.4795 | 0.688 | 0.5510 |

**Teşhis:** R@100 = 0.809 >> R@10 → doğru madde getiriliyor, **sıralama** zayıf. Aynı-KANUN toleransıyla R@10 = 0.889 → doğru kanun %89 bulunuyor, darboğaz **madde ayrımı**. Detay: [`retrieval-metrikleri.md`](retrieval-metrikleri.md).

## Faz 7 — Dockerize ✅
- [x] `docker-compose.yml`: `qdrant` (v1.18.0, healthcheck) + `api` (FastAPI, onnx-int8) + `ingest` (profil) — ADR-0018
- [x] `Dockerfile`: python:3.11-slim, non-root, `requirements-servis.txt` (**torch yok**), imaj 629 MB; modeller/korpus read-only volume
- [x] `docker compose up` ile uçtan uca: ingest 31.416 point, `/saglik` 200, `/ara` 200 sorguda R@10 0.610 = in-process
- [ ] Ön koşul artifact'leri (Colab embed, ONNX modelleri, korpus) compose dışında üretiliyor

---

## Yapısal sadakat fazları (Faz 0-22) — korpus kalite kampanyası

Roadmap fazlarına **paralel** yürüyen ayrı bir düzeltme serisi. Amaç: parser'ın kanun metnine
yapısal sadakati (bleed sızması, fıkra/bent sınırları, dipnot/tablo, yürürlük doğruluğu).
Plan: [`yapisal-sadakat-master-plan.md`](yapisal-sadakat-master-plan.md) · Faz dosyaları: [`faz-planlari/`](faz-planlari/)

**Tamamlanan 18 faz planı** (0,1,2,3,4,5,6,7,8,10,12,13,14,15,16,17-20,21,22). Son üçü:

| Faz | Konu | Kazanç |
|---|---|---|
| 21 | Cetvel + kolonsuz başlık bleed | Tablo-imzalı kanun-sonu ekleri kırpıldı |
| 22 | Numarasız fıkra paragraf-sınır (`\x1f`) | Fıkra 46.643 → **89.745** |
| 22b | Bent-listeli fıkrada devam-paragraf koruma | 122 maddede 567 bent kaybı geri geldi |
| 22f | Atıf-alan işlenmiş-madde → yönlendirme chunk | 48 boş-gövde yön kaydı |

### Atıf bulunabilirliği (unique_atiflar.json, 8.290 atıf)
Oturum başı ~%59.7 → **%75.3**. Kırılım: kanun %98 · madde %86 · fıkra/bent daha düşük.

> **Dürüstlük notu:** %75.3'ün bir kısmı korpus iyileşmesi (kalıcı, kodda — bağımsız `altınset`
> referansıyla ~%78 uyumlu, overfit değil), bir kısmı **ölçüm toleransı** (atıf "fıkra N" derken
> korpustaki "N." bent ile eşleştirme — Türk hukuk dilinde bent'e "fıkra" denir). Toleranslar
> **build kodunda değil**, ayrı karşılaştırma script'indeydi. Yani %75.3 bir **ölçüm üst-sınırıdır**;
> canlı retrieval'ın aynı toleransı uygulaması gerekir.

---

## Açık Konular / Engeller

1. **Atıf modu yok.** Roadmap Faz 6 "atıf modu (metadata filtreli kesin getirme)" diyor; korpus
   metadata'sı buna hazır (kanun_no + madde_no + fıkra/bent ağacı) ama **kod yazılmadı.**
2. **Reranker CPU'da yavaş + R@1'i düşürüyor** (ADR-0015): istek başına açık, varsayılan kapalı. Skor füzyonu / GPU servisi future.
3. **R.G. tarihi metadata'da yok** — kapsam listesinde var, chunk'a taşınmadı.
4. **Fıkra→bent terminoloji toleransı** retrieval tarafına taşınmalı (yukarıdaki dürüstlük notu).
5. **Dockerize ön koşulları compose dışında:** Colab embed + ONNX export/quantize elle.
6. **Çok-versiyonlu kanun artefaktı:** 6111/6736/7143/7326/7440 gibi yapılandırma kanunları aynı
   konuyu farklı no ile düzenliyor → gold "6111" derken sistem "7326" getirince haksız 0 alıyor.
7. **Qdrant index'i korpusun gerisinde:** eski Colab embed'i 1.678 maddede yürürlük uyuşmazlığı taşıyor → taban 0.700 → 0.6885. Yeniden embed gerekiyor.
