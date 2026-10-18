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
- **MVP kapsamı yalnız `KANUN` türü** (ADR-0013). Tebliğ/yönetmelik MVP'ye dahil **değil.** `src/yonetmelik/` boş iskelet; `src/teblig/`'de ise **deneysel, park edilmiş** kod var (çekici + chunker + yapı ölçümü, 53 test; build script'i ve korpusu YOK — ADR-0020): olduğu gibi kalır, geliştirilmez. Park edilmiş kodu geliştirmek ya da yeni tür eklemek MVP'yi genişletmektir; önce `decisions.md`'ye kapsam kararı yaz.
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
Python 3.10+ · bedesten API (saf `httpx` — ADR-0012 sapması, bkz. `docs/arch.md` §6) · **BGE-M3** embedding (ADR-0007) · **Qdrant** vektör store (ADR-0008) · 3-bacak hybrid arama: dense + BGE-sparse + klasik BM25, WSUM füzyon (ADR-0010) · reranker `bge-reranker-v2-m3` istek başına, varsayılan kapalı (ADR-0015) · ONNX Runtime dinamik int8 CPU çıkarımı (ADR-0016) · FastAPI servisi (ADR-0017) · atıf modu: deterministik ayrıştırıcı + bellek içi korpus indeksi, `POST /ara` `mod` alanı (ADR-0019) · docker-compose (qdrant + api + ingest profili, torch'suz imaj — ADR-0018) · CI: GitHub Actions `test` check'i (her PR + `main` push).

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

## Klasör yapısı — tür başına TAM İZOLASYON (2026-07-10)

Her mevzuat türü **kendi paketinde, sıfırdan** yazılır. **Ortak kod YOK, soyutlama YOK.**
Kanun tarafında bir kural değiştirmek başka türü **asla** bozamaz.

```
src/kanun/        ← ÇALIŞIYOR (15 modül + retrieval/ + api/)
src/kanun/retrieval/  search.py (HybridArama) · atif.py + atif_getir.py (atıf modu) · embed(_onnx) · rerank · config · fabrika · olcum
src/teblig/       ← PARK EDİLDİ, MVP dışı (ADR-0020): fetch.py · chunker.py — deneysel, geliştirilmez
src/yonetmelik/   ← iskelet (boş; sıfırdan yazılacak)

scripts/kanun/            build_corpus.py · eval_*.py · fetch_*.py
scripts/kanun/retrieval/  ingest_qdrant · search_qdrant · metrik_* · onnx_export/quantize · esdeger_kontrol
scripts/teblig/           yapi_olc.py (park; build script'i YOK) · scripts/yonetmelik/ (boş)

tests/kanun/      26 dosya, 1056 test (+3 `-m model`)
tests/teblig/     2 dosya, 53 test (park edilmiş kodu kilitler)    · tests/yonetmelik/ (boş)

data/kanun/       raw/ (cache) · korpus.jsonl · unique_atiflar.json
data/teblig/      korpus YOK (`fetch.py` yalnız raw/ cache'i yazar) · data/yonetmelik/ (boş)
data/gold/        altınset gold set (tür-bağımsız, retrieval ölçümü)
```

**Yeni tür eklerken:** `src/kanun/` modüllerini **oku ve KOPYALA** — `import` etme.
Çıktı şeması `{id, text, metadata}` kalsın (ileride tek Qdrant'ta birleşebilsin),
`metadata.mevzuat_tur` ekle (kanun korpusu `"KANUN"` yazar). Ayrıntı: `src/teblig/__init__.py` (park durumu + yönergeler);
tebliği yeniden açmanın ilk adımları: `decisions.md` ADR-0020.

## Bugünkü durum (2026-10-18)
**Faz 1-7 çalışıyor + atıf modu** (kütüphane + HTTP servisi + docker-compose, yalnız KANUN türü). Ayrıntı → [`docs/status.md`](docs/status.md).

- **Korpus:** `data/kanun/korpus.jsonl` — 31.611 chunk / 917 kanun (2026-10-18 yeniden çekim; 195'i yönlendirme chunk'ı — yeniden üretilen atıf setinden). `python scripts/kanun/build_corpus.py` ile cache'ten (`data/kanun/raw/`) ~75 sn'de **deterministik** üretilir. (89.986 fıkra, 29.621 bent, 1.718 mülga.) Metadata'da `mevzuat_tur` + `resmi_gazete_tarihi`/`resmi_gazete_sayisi` var (735/917 kanunda R.G. tarihi dolu).
- **Retrieval:** kütüphane `src/kanun/retrieval/search.py` (`HybridArama`), BGE-M3 + Qdrant, 3-bacak hybrid. Index güncel korpusla yeniden embed edildi (2026-10-18, 31.398 nokta). Eski altınset bu kopyada yok → **ölçüm seti v2** (442 soru, `data/gold/retrieval_v2/`, git dışı): güncel servis **R@10 0.871, MRR 0.718, R@1 0.643** (ADR-0022: BM25 Türkçe tokenizer + ilk 5 harf, WSUM 0.65/0.20/0.15; önceki servis 0.835 / 0.660 / 0.568). Eski altınset sayıları (R@10 0.6885, +reranker 0.711) karşılaştırılamaz. Reranker varsayılan kapalı; ONNX int8 sorgu embed'i embed gecikmesini ~3× düşürür. Aday kimliği `madde_id` (ADR-0021).
- **Atıf modu** (ADR-0019): `atif.py` (deterministik ayrıştırıcı) + `atif_getir.py` (korpus üzerinde bayt-ofsetli bellek içi indeks) — "TCK m. 141/2" → kesin madde/fıkra/bent; fıkra→bent toleransı, kanun_no çakışmasında `coklu_mevzuat`, eşleşme yoksa doğal dile düşüş. Gerçek korpusla doğrulanmadı.
- **Servis:** FastAPI `POST /ara` (`mod`: `otomatik` varsayılan | `atif` | `dogal`), `GET /saglik` (+ `atif_indeks`) (`src/kanun/api/app.py`); ayarlar ortam değişkeninden (`config.py`).
- **Testler:** 1109 test geçiyor (`pytest -q`: `tests/kanun/` 1056 + `tests/teblig/` 53); 3 gerçek-model parity testi ayrıca `pytest -m model`. CI: her PR'da ve `main`'e push'ta GitHub Actions `test` check'i aynı paketi koşar (ubuntu, Python 3.11).
- **Docker:** `docker compose up -d qdrant api` + `--profile ingest run --rm ingest` (ön koşul: `colab/outputs/`, `models/onnx/`, korpus).
- **Eksik:** atıf modunun gerçek korpusla doğrulanması (atıf seti 2026-10-18'de DeepSeek + Qwen + Clef ile yeniden üretildi, 15.672 adres; üretim script'leri henüz repoda değil) · ADR-0021 `esdeger_kontrol.py` koşusu · Clef reranker deneyi · eski altınset bulunursa ADR-0022 ağırlıklarının onunla doğrulanması · ONNX modellerinin (`models/onnx/`) bu kopyada üretilmesi.

### Build zincirine dokunacaksan — kritik invariant'lar
Bunlar bozulursa korpus **sessizce** bozulur (mevcut testler yakalamayabilir):
1. **`\x1f` paragraf sınırı:** `fetch.py strip_html` üretir → `normalize.py` korur → `fikra.py` numarasız fıkraları ondan böler. Zincirin bir halkası koparsa fıkra 89.745 → ~46.643'e çöker.
2. **Bent-listeli fıkra devam-koruması** (`fikra.py`): bozulursa rakamlı bent listeleri parçalanır (k193 m7: 7 → 0 bent).
3. **`'Ancak'` yeni-fıkra sinyali DEĞİLDİR** (bilinçli): bent-içi istisna cümlesi de "Ancak" ile başlar.
4. **Mülga maddeler korpusta KALIR** (işaretli), elenmez — tarihsel sorgu için.
5. **Chunk id `mevzuatId` tabanlıdır**, `kanun_no` değil (6551 gibi çakışan kanun no'ları var). Doğal dil araması da adayı bu id ile tanır (Qdrant payload `madde_id` = chunk id, ADR-0021): id şeması değişirse Qdrant yeniden embed/ingest edilmeli — köprü (`BM25Index.kimlik`) yalnız aynı kanundaki tek eş maddeyi bağlar.

**Doğrulama refleksi:** `python scripts/kanun/build_corpus.py` → 917 kanun / 31.611 chunk (atıf seti varken; yoksa 31.416); `k193 m7` = 2 fıkra, 7 bent.
Build ayrıca `[R.G.] X/Y kanunda R.G. tarihi var` ve `R.G. tarihi dolu chunk: N/M` satırlarını basar. Kaynak liste cache'i
`data/kanun/raw/_kanun_liste.json` (`PYTHONPATH=src python -m kanun.fetch` doldurur) `_kanun_ids.txt`'den **bağımsızdır**:
kanun seti ve sırası ids cache'inden gelir, liste cache'i yalnız alan ekler (yoksa alanlar null, build kırılmaz).
Yeni alanların yalnız eklemeli olduğunu doğrula (`ESKI.jsonl` = build öncesi korpusun kopyası; build ezer):
`python scripts/kanun/compare_corpus.py ESKI.jsonl YENI.jsonl --yoksay mevzuat_tur,resmi_gazete_tarihi,resmi_gazete_sayisi`
(chunk sayısı, id'ler ve kalan alanlar aynı kalmalı; "Metadata alanı: eklenen" satırı yalnız bu üç alanı göstermeli).

⚠️ **`build_corpus.py` çıktıyı SESSİZCE EZER** (`"w"` modu). `CORPUS_MID=...` ile tek kanun çalıştırırsan diskteki tam korpus 1 kanuna iner. Cache duruyorsa geri üretilebilir (deterministik). Tür-kapsamlı veri yolu sayesinde tebliğ/yönetmelik build'i kanun korpusunu **asla** ezemez.
