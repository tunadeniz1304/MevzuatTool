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
| 2 | Yapısal Chunking | 🟡 |
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

## Faz 2 — Yapısal Chunking 🟡 (chunker parçaları kuruldu; birleştirme → Faz 4)
Plan: `docs/superpowers/plans/2026-06-19-structural-chunking.md` · branch `phase-2/structural-chunking` (lokal) · TDD, 5 task, 5/5 test ✓.
- [x] `normalize_text` — satır kırığı birleştir + tire tek tip
- [x] `split_articles` — esnek `Madde/MADDE N-` regex (madde bazlı chunk)
- [x] `split_fikralar` — `(N)` fıkra bölme
- [x] `extract_status` — `(Mülga: …)` → yürürlük durumu (ADR-0005)
- [x] `count_tree_articles` + `scripts/eval_chunker.py` — ağaca karşı ground-truth eval
- [ ] **Birleştirme (assembly):** `split_articles`→fıkra→status'u tek `{id,text,metadata}` chunk'ta toplama → **Faz 4** (parçalar henüz birbirini çağırmıyor)
- [ ] Hiyerarşi-path (Kitap/Kısım/Bölüm) — MVP'de yok (YAGNI)

### Eval sonucu (Task 6 fix sonrası — chunker vs ağaç ground-truth)
| Belge | chunker | unique | tree | dup |
|---|---|---|---|---|
| TCK | 348 | 347 | 345 | 1 |
| KKY | 22 | 22 | 22 | 0 ✓ |
| KVKK | 36 | 36 | 33 | 0 ✓ |
| VUK | 492 | 468 | 564 | 24 |

> **Düzeltildi (Task 6, commit f522f50):** prefix/suffix maddeler (Ek/Geçici/Mükerrer, `N/A`) artık benzersiz `no` alıyor (Türkçe i/İ-güvenli char-class regex). Ana çakışma bug'ı kapandı: **KVKK dup 3→0, VUK dup 104→24.**
> **Kalan dup'lar gerçek tekrar:** Türk mevzuatında her değişiklik kanununun kendi "Geçici Madde 1"i olur → "Geçici 1" meşru olarak defalarca geçer (VUK 7×). Kod defekti değil; tam benzersizlik için **değişiklik-bağlamı metadata'sı (Faz 3)** gerekir. VUK "215" ×4 anomalisi ayrı incelenecek.
> `fark` artık birincil metrik değil — chunker, geçici maddeleri ağacın atladığı yerde doğru yakalıyor.

### Faz 2 future-work (öncelik sırası)
1. ✅ Prefix/suffix madde desteği + benzersiz no (Task 6) — yapıldı.
2. Birleştirme + metadata → JSONL `{id,text,metadata}` (Faz 4 ile).
3. Geçici madde tekrarına değişiklik-bağlamı metadata'sı (Faz 3); VUK "215" ×4 anomalisi analizi.
4. Fıkra `(1)`boşluksuz; serbest-metin mülga tespiti; edge-case testleri; eval'e 5. belge.

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
