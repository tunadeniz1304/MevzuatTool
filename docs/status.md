# Proje Durumu (Status)

Fazlar: [`roadmap.md`](roadmap.md) · Kapsam uygunluğu: [`compliance.md`](compliance.md) · Mimari: [`arch.md`](arch.md)

**Son güncelleme:** 2026-06-18
**Genel durum:** 🟡 Faz 0 (kurulum) devam ediyor — kod yazımı henüz başlamadı.

İşaretler: ✅ tamam · 🟡 devam ediyor · ⬜ başlamadı · ⛔ engelli

---

## Faz İlerlemesi (üst düzey)

| Faz | Ad | Durum |
|---|---|---|
| 0 | Kurulum & Yönetişim | 🟡 |
| 1 | Veri Çekme (data acquisition) | ⬜ |
| 2 | Yapısal Chunking | ⬜ |
| 3 | Metadata | ⬜ |
| 4 | Temiz Korpus Artifact | ⬜ |
| 5 | Embedding + Indexleme | ⬜ |
| 6 | Sorgu + Retrieval | ⬜ |
| 7 | Dockerize | ⬜ |

---

## Faz 0 — Kurulum & Yönetişim 🟡

- [x] Repo'ya bağlanıldı (`origin/main` takip ediliyor)
- [x] `mevzuat-mvp-kapsam.md` (kapsam) mevcut
- [x] `commit_discipline.md` — commit/branch kuralları
- [x] `roadmap.md` — faz planı
- [x] `status.md` — bu dosya
- [x] `compliance.md` — kapsam uygunluk checklist'i
- [x] `arch.md` — mimari durum
- [x] `decisions.md` — karar kaydı
- [x] `README.md` — proje tanıtımı
- [x] `.gitignore` — Python/RAG
- [x] `CLAUDE.md` — proje hafızası
- [ ] GitHub `main` branch protection ayarı (UI'dan — bkz. commit_discipline.md §5.2)
- [ ] Python proje iskeleti (paket yapısı, bağımlılık yönetimi) — *Faz 1 öncesi*

## Faz 1 — Veri Çekme ⬜
- [ ] `mevzuat-mcp` entegrasyonu / istemci
- [ ] Yapısal eksenler listelendi + örnek başına kapsama (coverage) işaret tablosu oluşturuldu
- [ ] Başlangıç korpusu seçildi: **yapısal eksen kapsamasına göre** küçük set (~5-8, tür-içi varyasyon dahil) (bkz. decisions.md ADR-0011)
- [ ] `search_mevzuat → article_tree → article_content` akışı çalışıyor
- [ ] PDF içerik atlama mantığı
- [ ] Ham çıktı kaydı

## Faz 2 — Yapısal Chunking ⬜
- [ ] Madde bazlı atomik chunk üretimi
- [ ] Uzun madde → fıkra bölme
- [ ] Hiyerarşi (`kanun→...→madde→fıkra→bent`) korunuyor

## Faz 3 — Metadata ⬜
- [ ] Temel metadata alanları (ad/no/tür/madde/başlık/fıkra/path/kaynak/R.G.)
- [ ] Yürürlük durumu (yürürlükte/mülga) işaretleme
- [ ] Mülga hükümlerin ayrımı

## Faz 4 — Temiz Korpus Artifact ⬜
- [ ] JSONL şeması `{id, text, metadata}` tanımlı
- [ ] Korpus üretici çıktıyı yazıyor
- [ ] Şema dokümante edildi

## Faz 5 — Embedding + Indexleme ⬜
- [ ] Embedding modeli seçildi/entegre (ör. BGE-M3)
- [ ] Vektör store kararı (Qdrant↔pgvector) verildi
- [ ] Hybrid (dense + BM25/sparse) arama kuruldu

## Faz 6 — Sorgu + Retrieval ⬜
- [ ] Atıf modu (metadata filtreli kesin getirme)
- [ ] Doğal dil modu (hybrid semantik)
- [ ] (Opsiyonel) reranker
- [ ] Sıralı sonuç çıktısı (metadata + atıf)

## Faz 7 — Dockerize ⬜
- [ ] `docker-compose` (vektör DB + ingestion + retrieval/API)
- [ ] `docker compose up` ile uçtan uca çalışıyor

---

## Açık Konular / Engeller
- Vektör store seçimi açık (Qdrant ↔ pgvector) — bkz. `decisions.md`
- Başlangıç korpusu hangi alan/kanun seti olacak? — Faz 1'de netleşmeli
