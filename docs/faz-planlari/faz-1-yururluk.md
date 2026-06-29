# FAZ 1 — Yürürlük/Mülga (A1+A2+A3) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam**
> **MVP-KRİTİK** — yürürlük birinci-sınıf metadata (ADR-0005); yanlış yürürlük retrieval'ı doğrudan yanıltır.
> Dosyalar: `src/mevzuat_tool/chunker.py` (A1, A3), `src/mevzuat_tool/fikra.py` (A2). enrich.py'ye dokunulmadı.

## ✅ SONUÇ (tamamlandı)
- **A1+A3** ([chunker.py](../../src/mevzuat_tool/chunker.py)): `_MULGA_MARKER` `fıkra` → `(?:fıkra|bent|madde)`. `(İptal bent:)` + `(İptal madde:)` artık iptal sinyali.
- **A2** ([fikra.py](../../src/mevzuat_tool/fikra.py)): `_fikra_yurutluk` — fıkra statüsü bent ağacından türetiliyor; gömülü tek `(Mülga:)` bendi fıkrayı mülga YAPMIYOR. Bentsiz fıkrada davranış birebir aynı.
- **Birim test:** +6 yeni (3 chunker, 3 fikra). Tam paket **181 passed**, 0 kırık (5651/7081 korumaları dahil).
- **916-kanun regresyon (compare_corpus.py):**
  - **20 madde → mülga** (hepsi `İptal madde/bent` — 0 beklenmeyen). 103326-1..9 (K221 AYM tam iptal zinciri), Ek/Geçici iptal maddeleri.
  - **23 madde → yürürlükte** (hepsi gömülü-mülga düzeldi, en az 1 canlı bent — 0 beklenmeyen). Ağırlıkla **Tanımlar** maddeleri (104051-2, 103932-2, 104010-2...).
  - **489 madde etkilendi** (fıkra/bent `yurutluk` alanı) — **0'ında text değişmedi** (içerik birebir korundu).
  - Mülga oranı %11.03 → %11.02.
  - Spot-check: `103326-1` mülga ✓, `104051-2` yürürlükte ✓.

## Context

Üç yürürlük hatası canlı maddeyi "mülga"/mülgayı "canlı" gösteriyor. Hepsi FAZ 0'da kurulan
`compare_corpus.py` **status-flip tablosuyla** ölçülecek. Geçmiş desen: commit `2158ea7`
(yürürlük regresyonu fıkra-ağacıyla çözüldü).

### Canlı doğrulanan gerçekler (bu oturumda korpustan)
- **A2 / `103829-3`** (Nüfus K. 5490 Tanımlar): madde=**mülga** ❌; fıkra `(1)` içinde **29 bent, yalnız `ç)` mülga**, 28 canlı. Kök: fıkra statüsü `extract_status(p)` ile TÜM fıkra metninden alınıyor ([fikra.py:126](../../src/mevzuat_tool/fikra.py#L126)) → tek gömülü `ç) (Mülga:)` fıkrayı mülga yapıyor → [enrich.py:181-182](../../src/mevzuat_tool/enrich.py#L181-L182) tek numaralı fıkra mülga → madde mülga.
- **A1 / `(İptal bent:)`**: korpusta **22 madde** (103795-38, 102948-5/6, 104178-6, 103348-6, 103242-2...). `extract_status("...İptal bent...")` = "yürürlükte" → ilgili bent **mülga işaretlenmiyor** (asimetri: `_MULGA_MARKER`'da `fıkra` var, `bent` yok).
- **A3 / `(İptal madde:)`**: korpusta **11 madde** (103326-1..5 zinciri). "yürürlükte" ❌ — boş iptal maddesi canlı görünüyor. Kök: `\(\s*iptal\s*:` `iptal`+`:` bekliyor, `iptal madde:` araya `madde` girince eşleşmiyor.
- **Asimetri kanıtı:** `extract_status("(İptal bent: ...)")="yürürlükte"` ama `extract_status("(Mülga: ...)")="mülga"`.

---

## A1 + A3 — `_MULGA_MARKER` bent/madde simetrisi (tek atomik commit)

**Mevcut** ([chunker.py:133-135](../../src/mevzuat_tool/chunker.py#L133-L135)):
```python
_MULGA_MARKER = re.compile(
    r"(?i)\(\s*mülga|;\s*mülga|\(\s*iptal\s*:|;\s*iptal\s*:"
    r"|\(\s*iptal\s+(?:\w+\s+)?fıkra\s*:|;\s*iptal\s+(?:\w+\s+)?fıkra\s*:")
```

**Çözüm:** `iptal ... fıkra:` dalındaki `fıkra`'yı `(?:fıkra|bent|madde)` yap → `(İptal bent:)`, `(İptal birinci bent:)`, `(İptal madde:)` de yakalanır.
```python
    r"|\(\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:|;\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:"
```

**YP-riski (düşük) + korumalar:**
- `(İptal bent:)` bent-seviyesinde (`extract_status` konum_duyarli=False) → o bent mülga. DOĞRU.
- Madde seviyesinde (`konum_duyarli=True`): `_madde_basi_iptal` ile içerikte gelen iptal-bent fıkra/bent iptali sayılır, madde yürürlükte kalır → **5651 mantığı korunur**.
- `(İptal madde:)` açılış künyesinde → tüm madde mülga (doğru).

**Test (TDD — önce kırmızı):**
- A1: `extract_status("a) x (İptal bent: AYM 1/1/2020 kararı)") == "mülga"` (bent birimi).
- A3: `extract_status("(İptal madde: AYM ...)", konum_duyarli=True) == "mülga"`.
- 🛡️ Güvenlik: `extract_status("(1) içerik. (İptal bent: AYM...)", konum_duyarli=True) == "yürürlükte"` (madde, içerik-sonrası iptal).
- 🛡️ Mevcut `test_iptal_inside_content_keeps_madde_yururlukte` (5651) korunur.

---

## A2 — Fıkra statüsünü bent ağacından türet (gömülü-mülga kaskadı)

**Mevcut** ([fikra.py:120-126](../../src/mevzuat_tool/fikra.py#L120-L126)): fıkra statüsü `extract_status(p)` / `extract_status(body)` ile **tüm fıkra metninden** alınıyor → bent-içi tek `(Mülga:)` fıkrayı mülga yapıyor.

**Çözüm:** Fıkranın `bentler`'i varsa, statüsü bentlerden türetilsin:
- Tüm bentler mülga → fıkra mülga; en az biri yürürlükte → fıkra yürürlükte.
- Bent YOKSA (düz fıkra) → mevcut `extract_status` davranışı **aynen** kalır (değişiklik yok).

Bu, [enrich.py:181-182](../../src/mevzuat_tool/enrich.py#L181-L182)'deki madde-mantığının fıkra-içi analoğu (aynı desen, bir seviye aşağıda). enrich.py'ye **dokunulmaz** — fıkra statüsü düzelince madde statüsü kendiliğinden düzelir.

**Uygulama yeri:** `parse_fikralar` içinde Fikra üretilirken `yurutluk` hesabı; `_bentler(p)` zaten çağrılıyor, sonucu kullan:
```python
bentler = _bentler(p)
yur = ("mülga" if bentler and all(b.yurutluk == "mülga" for b in bentler)
       else "yürürlükte" if bentler
       else extract_status(p))
```
(Hem numarasız tek fıkra [satır 120] hem numaralı fıkralar [satır 126] için.)

**YP-riski (orta) + korumalar:**
- 🛡️ `test_bent_level_yurutluk` ([test_fikra.py:32](../../tests/test_fikra.py#L32)) korunur (bent statüsü değişmiyor, sadece fıkra türetimi).
- 🛡️ Tüm-bent-mülga fıkra hâlâ mülga (gerçek tam-mülga korunur).
- 🛡️ Bentsiz fıkrada davranış birebir aynı.

**Test (TDD — önce kırmızı):**
- A2: `103829-3` deseni — `a) tanım b) tanım ç) (Mülga: tarih) d) tanım ...` (29 bent, 1 mülga) → fıkra **yürürlükte**, sadece `ç)` mülga.
- 🛡️ `a) (Mülga:..) b) (Mülga:..)` (tüm bent mülga) → fıkra **mülga**.

---

## Regresyon / Doğrulama (FAZ 1 sonu)

> ⚠️ Smoke build `data/corpus/korpus.jsonl`'i ezer → önce baseline al, sonra geri yükle (FAZ 0 notu).

1. 🔴→🟢 TDD: A1/A3 (chunker), A2 (fikra) kırmızı testleri → düzeltme → yeşil.
2. 🛡️ True-negative: 5651 M3/M5/M6 yürürlükte; 7081 M10 mülga; `test_bent_level_yurutluk` yeşil.
3. ♻️ Tam `pytest` (175 + yeni). 0 kırık.
4. 📊 916-kanun compare:
   ```
   cp data/corpus/korpus.jsonl data/gold/korpus_baseline.jsonl   # FAZ 0 baseline (zaten var)
   .venv/Scripts/python.exe scripts/build_corpus.py              # NEW üret
   .venv/Scripts/python.exe scripts/compare_corpus.py data/gold/korpus_baseline.jsonl data/corpus/korpus.jsonl --flips
   ```
   **Beklenen status-flip:** ~49 madde + ~129 bent → **yürürlüğe döner** (A2); ~10 bent + 11 madde → **mülga olur** (A1+A3). Bu yönlerin DIŞINDA flip = regresyon → incele.
   - Spot-check: `103829-3` artık yürürlükte; `103326-1` artık mülga.
   - Sonra baseline'dan geri yükle.

---

## Çıktılar (commit'ler)
- `fix(chunker): (İptal bent:)/(İptal madde:) mülga sinyali — marker simetrisi (A1+A3)`
- `fix(fikra): fıkra statüsünü bent ağacından türet — gömülü-mülga kaskadı (A2)`

İkisi atomik ayrı commit. Branch: mevcut `bugfix/phase-0` (veya FAZ-1'e yeni branch — kullanıcı kararı).
