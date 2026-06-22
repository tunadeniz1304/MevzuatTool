# Proje Durumu (Status)

Fazlar: [`roadmap.md`](roadmap.md) · Kapsam uygunluğu: [`compliance.md`](compliance.md) · Mimari: [`arch.md`](arch.md)

**Son güncelleme:** 2026-06-19
**Genel durum:** 🟡 Faz 1 (veri çekme) başladı — Python iskeleti kuruldu, mevzuat-mcp MCP client smoke test çalışıyor.

İşaretler: ✅ tamam · 🟡 devam ediyor · ⬜ başlamadı · ⛔ engelli

---

## Faz İlerlemesi (üst düzey)

| Faz | Ad | Durum |
|---|---|---|
| 0 | Kurulum & Yönetişim | 🟡 |
| 1 | Veri Çekme (data acquisition) | 🟡 |
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
- [x] Python proje iskeleti — venv + `src/mevzuat_tool/` + `requirements.txt`

## Faz 1 — Veri Çekme 🟡
- [x] `mevzuat-mcp` entegrasyonu: yerel server + MCP client (ADR-0012) — smoke test ✓
- [x] Yapısal eksenler listelendi + kapsama (coverage) işaret tablosu oluşturuldu ↓
- [x] Başlangıç korpusu seçildi: 5 belgelik yapısal-çeşitlilik seti (bkz. decisions.md ADR-0011)
- [x] `search_mevzuat` ✓ → `get_mevzuat_madde_tree` ✓ → `get_mevzuat_content` ✓ — tam zincir MCP client ile çalışıyor

### Başlangıç korpusu — seçilen set + kapsama tablosu (2026-06-19)
| Belge | mevzuatId | Yapı / kapsanan eksen | Düğüm |
|---|---|---|---|
| Türk Ceza Kanunu 5237 | 103228 | Derin hiyerarşi (Kitap/Kısım/Bölüm) | 397 |
| Vergi Usul Kanunu 213 | 103006 | Karışık + dev + çok-değişiklikli (serbest madde + Kitap) | 691 |
| KVKK 6698 | 104383 | Düz kanun (sadece Bölüm) | 41 |
| İthalatta Gözetim Tebliği | 350781 | **Ağaç YOK** → content-only edge-case | 0 |
| Kültür Bak. Yayın Yönetmeliği | 352791 | Düz yönetmelik (KKY) | 26 |

> **Doğrulandı (2026-06-19, content):** mülga/değişik/ek/mükerrer/geçici işaretleri content'te; VUK çok yoğun (mükerrer 290, değişik 272, mülga 91, ek 76, geçici 73), tebliğ/yönetmelik tertemiz.
>
> **Adım 12 chunking bulguları (Faz 2 girdisi):** content metni "kirli" — cümle ortası satır kırıkları (`Madde\n1`); madde işareti belgeden belgeye değişir (`Madde 1-` / `MADDE 1-` / `MADDE 1 –`, tire↔en-dash); fıkra = `(N)`; madde başlığı maddeden ÖNCEki satırda; değişiklik/mülga şerhi (`(Değişik: …)`/`(Mülga: …)`) madde no'sundan hemen sonra; tablolar düz metne yayılmış. → chunker **normalize + esnek madde-regex** gerektirir; ağaç olan/olmayan için iki yol denenecek.
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
