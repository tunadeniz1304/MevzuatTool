[Türkçe](README.tr.md) · **English**

<div align="center">

# ⚖️ MevzuatTool

**A structural RAG retrieval engine for Turkish laws**

Given a natural-language question or a legal citation, it returns the **relevant law articles that are currently in force**.
It chunks the laws from mevzuat.gov.tr at the article level, extracts rich metadata, and retrieves them with hybrid search.

[![Status](https://img.shields.io/badge/status-phase%201--7%20complete-brightgreen)](docs/status.md)
[![Scope](https://img.shields.io/badge/scope-laws%20only-blue)](docs/mevzuat-mvp-kapsam.md)
[![Approach](https://img.shields.io/badge/approach-vanilla%20RAG-orange)](CLAUDE.md)
[![Corpus](https://img.shields.io/badge/corpus-31.4k%20articles-informational)](#-corpus)
[![R@10](https://img.shields.io/badge/R%4010-0.689-success)](#-metrics)
[![License](https://img.shields.io/badge/license-LICENSE-lightgrey)](LICENSE)

</div>

---

## 📖 Table of contents

- [What it does](#-what-it-does)
- [Why?](#-why)
- [Architecture](#-architecture)
- [Metrics](#-metrics)
- [Corpus](#-corpus)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project structure](#-project-structure)
- [Roadmap](#-roadmap)
- [Scope](#-scope)
- [Documentation](#-documentation)
- [Contributing](#-contributing)

---

## 🎯 What it does

It takes a law/article citation or a natural-language question and returns a ranked list of the
**relevant articles currently in force** from a clean, chunked and indexed legislation corpus.

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

(Example query: "dismissal from the civil service as a disciplinary penalty for a civil servant"; results come from the Civil Servants Law — *Devlet Memurları Kanunu* — and the Turkish Radio and Television Law.)

> **🧭 Boundary:** The pipeline **ends at retrieval.** The LLM that writes the answer (generation) is **out of scope** —
> it is left as a swappable, OpenAI-compatible endpoint plugged in via config at the very end.
> This project is the **retrieval half** of vanilla RAG.

---

## 💡 Why?

Classic difficulties when searching Turkish legislation:

| Problem | MevzuatTool's solution |
|---|---|
| Naive fixed-size chunking splits context | **Article-level structural chunking** (long articles split by fıkra (paragraph)) |
| Mülga (repealed) provisions get mixed in | **In-force status as first-class metadata** → repealed provisions are filtered out |
| Semantic-only or keyword-only search is not enough | **3-leg hybrid** (dense + learned sparse + classic BM25) |
| The hierarchy (kitap (book) / kısım (part) / bölüm (chapter)) gets lost | `kanun → kitap → madde → fıkra → bent` (law → book → article → paragraph → sub-clause) is preserved |

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  mevzuat-mcp    │────▶│  Structural chunk│────▶│  Clean corpus JSONL │
│  (data fetch)   │     │  article + para  │     │  {id, text, meta}   │
└─────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                            │
                                            ┌───────────────▼───────────────┐
                                            │      BGE-M3 embed (Colab)      │
                                            │      dense + learned sparse    │
                                            └───────────────┬───────────────┘
                                                            │
     Query ──▶ BGE-M3 embed ──┐                 ┌───────────▼───────────┐
                              │                 │   Qdrant (dense +     │
                              ▼                 │   sparse + payload)   │
              ┌───────────────────────────┐    └───────────────────────┘
              │   3-leg WSUM fusion        │◀─── dense + BGE-sparse (Qdrant)
              │   dense + sparse + BM25    │◀─── classic BM25 (rank_bm25)
              │   + in-force filter        │
              └─────────────┬──────────────┘
                            ▼
                   Top-k in-force articles
```

**Stack:** Python · [`saidsurucu/mevzuat-mcp`](https://github.com/saidsurucu/mevzuat-mcp) ·
[BGE-M3](https://huggingface.co/BAAI/bge-m3) embeddings · [Qdrant](https://qdrant.tech) vector store ·
`rank_bm25` · hybrid search (dense + sparse + BM25) · ONNX Runtime int8 · FastAPI · Docker Compose.

---

## 📊 Metrics

Benchmark: the external **altınset** gold set (21,737 leakage-free queries; formal legal language), 2,000 queries.
Details: [`docs/retrieval-metrikleri.md`](docs/retrieval-metrikleri.md).

**Fusion evolution (article level):**

| Method | R@1 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| RRF hybrid (baseline) | 0.436 | 0.667 | 0.507 | 0.545 |
| WSUM_050 (2-leg) | 0.447 | 0.669 | 0.520 | 0.556 |
| **3-leg EQUAL + classic BM25 ← in use** (2026-07) | **0.491** | **0.700** | **0.562** | **0.596** |
| 3-leg, **current Qdrant index** (2026-09) ¹ | 0.481 | 0.689 | 0.552 | 0.585 |
| + reranker `bge-reranker-v2-m3`, 20 candidates (per request) | 0.465 | **0.711** | 0.550 | 0.589 |
| 3-leg, ONNX **int8** query embedding (CPU) | 0.480 | 0.688 | 0.551 | 0.584 |

With no fine-tuning and no GPU, using only **fusion + classic BM25**, the gain over the baseline is **R@1 +0.055, R@10 +0.033.**
¹ The Qdrant index (an older Colab embedding) has in-force status mismatches with the current corpus in 1,678 articles → −0.012.
The reranker is **integrated** but **off by default**: it raises R@10, lowers R@1 and takes ~15 s per query on CPU
(ADR-0015). The int8 query embedding keeps quality while cutting embedding latency ~3× (ADR-0016). Latency table:
[`docs/retrieval-metrikleri.md`](docs/retrieval-metrikleri.md).

**Recall vs. discrimination (bottleneck diagnosis):** R@100 = 0.809 >> R@10 = 0.700 → the correct article **is retrieved**, but
not ranked high enough. With same-**law** tolerance, R@10 = **0.889** → the system finds the right law; the bottleneck is
**distinguishing between articles** within the same law. (Next: re-embed the index, reranker score fusion, fine-tuning — future work.)

---

## 📚 Corpus

- **31,419 chunks / 916 laws** (`KANUN` type only — ADR-0013)
- Internal structure: **89,745 fıkra (paragraphs)**, **29,428 bent (sub-clauses)**; 1,718 repealed chunks (not removed but flagged — for historical queries)
- Each chunk: `{id, text, metadata}` — a standalone, deliverable JSONL
- Metadata: law number/name, article number/title, **in-force status (in force / repealed)**, hierarchy path, fıkra/bent tree, amendment history, footnotes, tables
- Atomic unit = **madde (article)** (long articles split by fıkra); **no** naive fixed-size token chunking
- Generated **deterministically** from the cache in ~75 s with `python scripts/kanun/build_corpus.py`

---

## 🚀 Installation

### Quick start — Docker Compose (Phase 7, ADR-0018)

Prerequisites (compose does not produce these; they must already exist on the host): `colab/outputs/` (the Colab corpus embedding:
`colab/bge_m3_embed.ipynb`), `models/onnx/` (`onnx_export.py hepsi` + `onnx_quantize.py hepsi`; `hepsi` = all),
`data/kanun/korpus.jsonl` (`build_corpus.py`).

```bash
docker compose build                                   # torch-free image (~630 MB)
docker compose up -d qdrant                            # Qdrant v1.18.0
docker compose --profile ingest run --rm ingest        # load the vectors (once, on first setup)
docker compose up -d api                               # retrieval service
curl -s localhost:8000/saglik
curl -s -X POST localhost:8000/ara -H 'Content-Type: application/json' -d '{"sorgu": "kira artışı", "top_k": 5}'
```

(`/saglik` = health check, `/ara` = search, `sorgu` = query; example query: "rent increase".)

If a port is already in use: `API_PORT=8001 QDRANT_PORT=6334 docker compose ...`. To skip loading the reranker: `RERANK_BACKEND=kapali` (off).

### Local development (venv)

```bash
# 1. Clone the repository
git clone https://github.com/tunadeniz1304/MevzuatTool.git && cd MevzuatTool

# 2. Virtual environment + dependencies
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt

# 3. Qdrant (Docker)
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 4. Load the corpus vectors into Qdrant
python scripts/kanun/retrieval/ingest_qdrant.py
```

> **Note:** BGE-M3 corpus embedding is heavy (GPU) — it is produced on Colab (`colab/bge_m3_embed.ipynb`)
> and the vectors are downloaded to the local machine. Query embedding is lightweight and runs on CPU.

---

## 🔍 Usage

```bash
# Single query
python scripts/kanun/retrieval/search_qdrant.py "kira artışı nasıl belirlenir"

# Interactive mode
python scripts/kanun/retrieval/search_qdrant.py
```

(Example query: "how is a rent increase determined".)

Output: the top-10 most relevant in-force articles, ranked by fusion score, with law/article information.

**HTTP service** (FastAPI, ADR-0017):

```bash
# Generate the int8 ONNX models once (models/onnx/, not committed)
python scripts/kanun/retrieval/onnx_export.py hepsi
python scripts/kanun/retrieval/onnx_quantize.py hepsi

# service (settings come from environment variables: EMBED_BACKEND, RERANK_BACKEND, RERANK_VARSAYILAN, QDRANT_URL ...)
EMBED_BACKEND=onnx-int8 RERANK_BACKEND=onnx-int8 uvicorn kanun.api.app:app --app-dir src --port 8000

curl localhost:8000/saglik
curl -X POST localhost:8000/ara -H 'Content-Type: application/json' -d '{"sorgu": "kira artışı nasıl belirlenir", "top_k": 10, "rerank": false}'
```

---

## 📂 Project structure

Each legislation type lives **in its own package, fully isolated.** There is no shared code — a change on the
kanun (law) side can never break another type. When adding a new type, the `src/kanun/` modules are **copied**,
not imported.

```
MevzuatTool/
├── src/
│   ├── kanun/                    # ✅ WORKING — 15 modules
│   │   ├── fetch.py              #   bedesten fetcher (429/Retry-After aware, cached)
│   │   ├── chunker.py fikra.py   #   article splitting · fıkra/bent tree
│   │   ├── enrich.py corpus.py   #   metadata merging · chunk generation
│   │   ├── retrieval/            #   search.py (HybridArama) · embed(_onnx).py · rerank.py · config.py
│   │   └── api/app.py            #   FastAPI: POST /ara, GET /saglik
│   ├── teblig/                   # ⏸ PARKED, not in the MVP — experimental fetcher + chunker (ADR-0020)
│   └── yonetmelik/               # ⬜ skeleton
├── scripts/
│   ├── kanun/
│   │   ├── build_corpus.py       # Corpus builder (main entry point)
│   │   ├── eval_*.py             # Parser accuracy measurements
│   │   └── retrieval/
│   │       ├── ingest_qdrant.py  #   Load corpus vectors into Qdrant
│   │       ├── search_qdrant.py  #   Search CLI (library wrapper)
│   │       ├── onnx_export.py · onnx_quantize.py  # ONNX FP32 export · dynamic int8
│   │       └── metrik_*.py       #   Retrieval evaluation measurements
│   ├── teblig/                   # ⏸ yapi_olc.py (structure measurement); no build script
│   └── yonetmelik/               # ⬜ empty
├── tests/
│   ├── kanun/                    # 22 files, 328 tests (+3 real-model: pytest -m model)
│   ├── teblig/                   # 2 files, 53 tests (lock the parked code)
│   └── yonetmelik/               # ⬜ empty
├── colab/
│   ├── bge_m3_embed.ipynb        # Corpus embedding (GPU)
│   └── rerank_olc.ipynb          # Reranker measurement (T4)
├── data/
│   ├── kanun/                    # raw/ (HTML cache) · korpus.jsonl
│   ├── teblig/ · yonetmelik/     # ⬜ no corpus
│   └── gold/                     # altınset gold set (type-agnostic)
├── docs/                         # All project documentation
├── CLAUDE.md                     # AI agent / contributor memory
└── README.md
```

(`teblig` = tebliğ (communiqué), `yonetmelik` = yönetmelik (regulation).)

---

## 🗺️ Roadmap

| Phase | Name | Status |
|---|---|---|
| 0 | Setup & Governance | ✅ |
| 1 | Data Fetching (mevzuat-mcp) | ✅ |
| 2 | Structural Chunking (madde/fıkra) | ✅ |
| 3 | Metadata (in-force status/hierarchy) | ✅ |
| 4 | Clean Corpus Artifact (JSONL) | ✅ |
| 5 | Embedding + Indexing (BGE-M3 + Qdrant) | ✅ |
| 6 | Query + Retrieval (3-leg hybrid) | ✅ |
| 7 | Dockerize (`docker compose up`) | ✅ |

Next improvements: citation mode, re-embedding the Qdrant index with the current corpus.
Details: [`docs/status.md`](docs/status.md) · [`docs/roadmap.md`](docs/roadmap.md).

---

## 🎯 Scope

**✅ In scope:** `KANUN` type only · data fetching (mevzuat-mcp) · structural chunking · rich metadata
(in force/repealed, hierarchy) · clean JSONL corpus · embedding + hybrid index · citation & natural-language retrieval · docker-compose.

**❌ Out of scope (future work):** Non-law types (KHK (decree-law) / tüzük (bylaw) / yönetmelik (regulation) / tebliğ (communiqué)) · LLM generation ·
GraphRAG / agentic / advanced RAG · embedding fine-tuning · PDF/OCR · içtihat (case law) / özelge (tax rulings).

Details: [`docs/mevzuat-mvp-kapsam.md`](docs/mevzuat-mvp-kapsam.md) · [`docs/compliance.md`](docs/compliance.md).

---

## 📄 Documentation

(The linked documents are in Turkish.)

| File | Contents |
|---|---|
| [`mevzuat-mvp-kapsam.md`](docs/mevzuat-mvp-kapsam.md) | Scope definition (source of truth) |
| [`status.md`](docs/status.md) | Current progress |
| [`roadmap.md`](docs/roadmap.md) | Phase plan |
| [`arch.md`](docs/arch.md) | Current architecture state |
| [`decisions.md`](docs/decisions.md) | Decision log (ADR) |
| [`retrieval-metrikleri.md`](docs/retrieval-metrikleri.md) | Measured retrieval metrics |
| [`compliance.md`](docs/compliance.md) | Scope compliance checklist |
| [`commit_discipline.md`](docs/commit_discipline.md) | Commit / branch rules |
| [`CLAUDE.md`](CLAUDE.md) | AI agent / contributor memory (at repo root) |

---

## 🤝 Contributing

Read [`docs/commit_discipline.md`](docs/commit_discipline.md) before starting work:

- 🚫 Pushing directly to `main` is **forbidden** — use `phase-N/feature-name` branches + PRs.
- 🚫 **No** AI co-author / "Generated with" lines in commit messages.
- ⚛️ **Atomic commits** — one logical change each; `type(scope): summary` format.

---

## 📜 License

See [`LICENSE`](LICENSE).
