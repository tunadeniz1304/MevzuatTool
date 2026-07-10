<div align="center">

# ⚖️ MevzuatTool

**Türk kanunları için yapısal RAG retrieval motoru**

Bir doğal dil sorusuna ya da atfa karşılık, **yürürlükteki ilgili kanun maddelerini** getirir.
mevzuat.gov.tr kanunlarını madde-seviyesinde chunk'lar, zengin metadata çıkarır, hybrid arama ile getirir.

[![Durum](https://img.shields.io/badge/durum-Faz%205--6%20çalışır-brightgreen)](docs/status.md)
[![Kapsam](https://img.shields.io/badge/kapsam-yalnız%20KANUN-blue)](docs/mevzuat-mvp-kapsam.md)
[![Yaklaşım](https://img.shields.io/badge/yaklaşım-vanilla%20RAG-orange)](CLAUDE.md)
[![Korpus](https://img.shields.io/badge/korpus-31.4k%20madde-informational)](#-korpus)
[![R@10](https://img.shields.io/badge/R%4010-0.700-success)](#-metrikler)
[![Lisans](https://img.shields.io/badge/lisans-LICENSE-lightgrey)](LICENSE)

</div>

---

## 📖 İçindekiler

- [Ne yapar?](#-ne-yapar)
- [Neden?](#-neden)
- [Mimari](#-mimari)
- [Metrikler](#-metrikler)
- [Korpus](#-korpus)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [Proje yapısı](#-proje-yapısı)
- [Yol haritası](#-yol-haritası)
- [Kapsam](#-kapsam)
- [Dokümantasyon](#-dokümantasyon)
- [Katkı](#-katkı)

---

## 🎯 Ne yapar?

Bir kanun/madde atfını veya doğal dil sorusunu alır; temiz, chunk'lanmış ve indexlenmiş
mevzuat korpusundan **yürürlükteki ilgili maddeleri** sıralayarak döndürür.

```
"memurun disiplin cezası olarak devlet memurluğundan çıkarılması"
        │
        ▼
 1. [0.77] Devlet Memurları Kanunu m.126
 2. [0.67] Devlet Memurları Kanunu m.133
 3. [0.66] Türkiye Radyo ve Televizyon Kanunu m.56/C
 4. [0.63] Devlet Memurları Kanunu m.132
 ...
```

> **🧭 Sınır:** Pipeline **retrieval'da biter.** Cevabı yazan LLM (generation) **kapsam dışıdır** —
> en sonda config'le takılan, OpenAI-uyumlu, swap'lanabilir bir endpoint olarak bırakılmıştır.
> Bu proje, vanilla RAG'ın **retrieval yarısıdır.**

---

## 💡 Neden?

Türk mevzuatı aranırken klasik zorluklar:

| Sorun | MevzuatTool çözümü |
|---|---|
| Naive sabit-boy chunking bağlamı böler | **Madde-seviyesi yapısal chunking** (uzun maddeler fıkra bazında) |
| Mülga (yürürlükten kalkmış) hükümler karışır | **Yürürlük durumu birinci sınıf metadata** → mülga filtrelenir |
| Sadece anlam ya da sadece kelime yetmez | **3-bacak hybrid** (dense + öğrenilmiş sparse + klasik BM25) |
| Hiyerarşi (kitap/kısım/bölüm) kaybolur | `kanun → kitap → madde → fıkra → bent` korunur |

---

## 🏗️ Mimari

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  mevzuat-mcp    │────▶│  Yapısal chunk   │────▶│  Temiz korpus JSONL │
│  (veri çekme)   │     │  madde + fıkra   │     │  {id, text, meta}   │
└─────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                            │
                                            ┌───────────────▼───────────────┐
                                            │      BGE-M3 embed (Colab)      │
                                            │      dense + öğrenilmiş sparse │
                                            └───────────────┬───────────────┘
                                                            │
     Sorgu ──▶ BGE-M3 embed ──┐                 ┌───────────▼───────────┐
                              │                 │   Qdrant (dense +     │
                              ▼                 │   sparse + payload)   │
              ┌───────────────────────────┐    └───────────────────────┘
              │   3-bacak WSUM füzyon      │◀─── dense + BGE-sparse (Qdrant)
              │   dense + sparse + BM25    │◀─── klasik BM25 (rank_bm25)
              │   + yürürlük filtresi      │
              └─────────────┬──────────────┘
                            ▼
                   Top-k yürürlükteki madde
```

**Teknoloji:** Python · [`saidsurucu/mevzuat-mcp`](https://github.com/saidsurucu/mevzuat-mcp) ·
[BGE-M3](https://huggingface.co/BAAI/bge-m3) embedding · [Qdrant](https://qdrant.tech) vektör store ·
`rank_bm25` · hybrid arama (dense + sparse + BM25) · Docker Compose (hedef).

---

## 📊 Metrikler

Cetvel: dışarıdan gelen **altınset** gold set (21.737 sızıntısız sorgu; resmi-dilli), 2000 sorgu.
Detay: [`docs/retrieval-metrikleri.md`](docs/retrieval-metrikleri.md).

**Füzyon evrimi (madde-seviyesi):**

| Yöntem | R@1 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| RRF hybrid (baseline) | 0.436 | 0.667 | 0.507 | 0.545 |
| WSUM_050 (2-bacak) | 0.447 | 0.669 | 0.520 | 0.556 |
| **3-bacak EŞİT + klasik BM25 ← uygulanan** | **0.491** | **0.700** | **0.562** | **0.596** |
| + reranker (`bge-reranker-v2-m3`, ölçüldü) | – | 0.706 | – | – |
| _(supervisor fine-tuned, kıyas)_ | – | _0.76_ | – | – |

Fine-tune / GPU olmadan, yalnızca **füzyon + klasik BM25** ile baseline'dan **R@1 +0.055, R@10 +0.033.**
Reranker ölçüldü ama henüz kalıcı entegre değil.

**Erişim vs ayrım (darboğaz teşhisi):** R@100 = 0.809 >> R@10 = 0.700 → doğru madde **getiriliyor**, ama
sıralanamıyor. Aynı-**kanun** toleransıyla R@10 = **0.889** → sistem doğru kanunu buluyor; darboğaz aynı
kanun içinde **madde ayrımı**. (Sıradaki: reranker entegrasyonu / fine-tune.)

---

## 📚 Korpus

- **31.419 chunk / 916 kanun** (yalnız `KANUN` türü — ADR-0013)
- İç yapı: **89.745 fıkra**, **29.428 bent**; 1.718 mülga chunk (elenmez, işaretlenir — tarihsel sorgu)
- Her chunk: `{id, text, metadata}` — bağımsız teslim edilebilir JSONL
- Metadata: kanun_no/ad, madde_no/başlık, **yürürlük (yürürlükte/mülga)**, hiyerarşi yolu, fıkra/bent ağacı, değişiklik geçmişi, dipnotlar, tablolar
- Atomik birim = **madde** (uzun maddeler fıkra bazında); naive sabit-boy token chunking **yok**
- `python scripts/kanun/build_corpus.py` ile cache'ten ~75 sn'de **deterministik** üretilir

---

## 🚀 Kurulum

> ⏳ Tam dockerize hedefi **Faz 7.** Şu an bileşenler ayrı çalışır.

```bash
# 1. Depoyu klonla
git clone <repo-url> && cd MevzuatTool

# 2. Sanal ortam + bağımlılıklar
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt

# 3. Qdrant (Docker)
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 4. Korpus vektörlerini Qdrant'a yükle
python scripts/kanun/retrieval/ingest_qdrant.py
```

> **Not:** BGE-M3 korpus embed'i ağır (GPU) — Colab'da üretilir (`colab/bge_m3_embed.ipynb`),
> vektörler PC'ye indirilir. Sorgu embed'i hafif, CPU'da çalışır.

---

## 🔍 Kullanım

```bash
# Tek sorgu
python scripts/kanun/retrieval/search_qdrant.py "kira artışı nasıl belirlenir"

# İnteraktif mod
python scripts/kanun/retrieval/search_qdrant.py
```

Çıktı: yürürlükteki en ilgili top-10 madde, füzyon skoru + kanun/madde bilgisiyle sıralı.

---

## 📂 Proje yapısı

Her mevzuat türü **kendi paketinde, tam izole.** Ortak kod yok — kanun tarafındaki bir
değişiklik başka türü asla bozamaz. Yeni tür eklerken `src/kanun/` modülleri **kopyalanır**,
import edilmez.

```
MevzuatTool/
├── src/
│   ├── kanun/                    # ✅ ÇALIŞIYOR — 15 modül
│   │   ├── fetch.py              #   bedesten çekici (429/Retry-After uyumlu, cache'li)
│   │   ├── chunker.py fikra.py   #   madde bölme · fıkra/bent ağacı
│   │   ├── enrich.py corpus.py   #   metadata birleştirme · chunk üretimi
│   │   └── retrieval/embed.py    #   BGE-M3 sorgu embed (dense + sparse)
│   ├── teblig/                   # ⬜ iskelet (sıfırdan yazılacak)
│   └── yonetmelik/               # ⬜ iskelet
├── scripts/
│   ├── kanun/
│   │   ├── build_corpus.py       # Korpus üretici (ana giriş)
│   │   ├── eval_*.py             # Parser doğruluk ölçümleri
│   │   └── retrieval/
│   │       ├── ingest_qdrant.py  #   Korpus vektörlerini Qdrant'a yükle
│   │       ├── search_qdrant.py  #   3-bacak hybrid arama (ana giriş)
│   │       └── metrik_*.py       #   Retrieval değerlendirme ölçümleri
│   ├── teblig/ · yonetmelik/     # ⬜ boş
├── tests/kanun/                  # 17 dosya, 285 test
├── colab/
│   ├── bge_m3_embed.ipynb        # Korpus embed (GPU)
│   └── rerank_olc.ipynb          # Reranker ölçümü (T4)
├── data/
│   ├── kanun/                    # raw/ (HTML cache) · korpus.jsonl
│   ├── teblig/ · yonetmelik/     # ⬜ boş
│   └── gold/                     # altınset gold set (tür-bağımsız)
├── docs/                         # Tüm proje dokümanları
├── CLAUDE.md                     # AI ajan / katkı sağlayıcı hafızası
└── README.md
```

---

## 🗺️ Yol haritası

| Faz | Ad | Durum |
|---|---|---|
| 0 | Kurulum & Yönetişim | ✅ |
| 1 | Veri Çekme (mevzuat-mcp) | ✅ |
| 2 | Yapısal Chunking (madde/fıkra) | ✅ |
| 3 | Metadata (yürürlük/hiyerarşi) | ✅ |
| 4 | Temiz Korpus Artifact (JSONL) | ✅ |
| 5 | Embedding + Indexleme (BGE-M3 + Qdrant) | ✅ |
| 6 | Sorgu + Retrieval (3-bacak hybrid) | ✅ |
| 7 | Dockerize (`docker compose up`) | ⬜ |

Sıradaki iyileştirmeler: reranker entegrasyonu (kanıtlı +0.04), yapısal-sadakat düzeltmeleri.
Detay: [`docs/status.md`](docs/status.md) · [`docs/roadmap.md`](docs/roadmap.md).

---

## 🎯 Kapsam

**✅ Kapsam içi:** Yalnız `KANUN` türü · veri çekme (mevzuat-mcp) · yapısal chunking · zengin metadata
(yürürlük/mülga, hiyerarşi) · temiz JSONL korpus · embedding + hybrid index · atıf & doğal dil retrieval · docker-compose.

**❌ Kapsam dışı (future work):** Kanun dışı türler (KHK/tüzük/yönetmelik/tebliğ) · LLM generation ·
GraphRAG / agentic / ileri RAG · embedding fine-tune · PDF/OCR · içtihat/özelge.

Detay: [`docs/mevzuat-mvp-kapsam.md`](docs/mevzuat-mvp-kapsam.md) · [`docs/compliance.md`](docs/compliance.md).

---

## 📄 Dokümantasyon

| Dosya | İçerik |
|---|---|
| [`mevzuat-mvp-kapsam.md`](docs/mevzuat-mvp-kapsam.md) | Kapsam tanımı (kaynak doğruluk) |
| [`status.md`](docs/status.md) | Güncel ilerleme |
| [`roadmap.md`](docs/roadmap.md) | Faz planı |
| [`arch.md`](docs/arch.md) | Güncel mimari durum |
| [`decisions.md`](docs/decisions.md) | Karar kaydı (ADR) |
| [`retrieval-metrikleri.md`](docs/retrieval-metrikleri.md) | Ölçülmüş retrieval metrikleri |
| [`compliance.md`](docs/compliance.md) | Kapsam uygunluk checklist'i |
| [`commit_discipline.md`](docs/commit_discipline.md) | Commit / branch kuralları |
| [`CLAUDE.md`](CLAUDE.md) | AI ajan / katkı sağlayıcı hafızası (kökte) |

---

## 🤝 Katkı

Çalışmaya başlamadan önce [`docs/commit_discipline.md`](docs/commit_discipline.md) okunmalıdır:

- 🚫 `main`'e doğrudan push **yasak** — `phase-N/feature-adi` branch'leri + PR.
- 🚫 Commit mesajlarında AI co-author / "Generated with" satırı **yok**.
- ⚛️ **Atomik commit** — tek mantıksal değişiklik; `type(scope): özet` formatı.

---

## 📜 Lisans

Bkz. [`LICENSE`](LICENSE).
