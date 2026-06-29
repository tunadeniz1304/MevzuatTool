# FAZ 5 — Dipnot/Tablo (D1) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam** (yalnız D1; D2/D3 ertelendi)
> **KOZMETİK** (embedding gürültüsü, retrieval'ı az etkiler). Dosya: `src/mevzuat_tool/corpus.py`.
> **Kapsam kararı (kullanıcı): YALNIZ D1.** D2/D3 ertelendi (gerekçe ↓).

## ✅ SONUÇ (tamamlandı)
- **D1** ([corpus.py](../../src/mevzuat_tool/corpus.py)): `_strip_dipnot_isaret` + `_fikra_dict_temiz` — `text` (başlık+gövde) ve `fikralar[].bentler[].text` (recursive) içinden `[n]` temizlenir. `metadata.dipnotlar[]`/`degisiklik_gecmisi[]` DOKUNULMAZ.
- **Birim test:** +2 (text/bent temizleme + dipnotlar[] korunma). Tam paket **195 passed**.
- **916-kanun regresyon:** text'te `[n]` **5801→0**, bent'te `[n]` **1863→0**; `dipnotlar[]` dolu **5596→5596** (korundu); status-flip **0**; şüpheli (text değişti ama `[n]` yok) **0**.

> 🔑 **DERS:** İlk D1'de (1) başlıktaki `[n]` (`_text` başlığı temizlemeden ekliyordu → 419 kaldı) ve (2) boşluk-normalize'in `[n]` içermeyen maddelere yan etkisi (90 gereksiz fark) vardı. 916-kanun regresyon yakaladı → `_strip_dipnot_isaret` "yalnız işaret VARSA dokun" + başlık da temizleniyor. Tertemiz (5801→0, şüpheli 0).

## Context

`[n]` dipnot işaretleri (`[1]`, `[27]`) `text` ve bent metinlerinde gürültü olarak kalıyor — embedding/BM25 sinyalini hafif kirletir.

### Doğrulanmış gerçekler (bu oturumda)
- **D1:** `[n]` kalan — **text 5801 chunk, bent text 1863 kayıt.** Örnek `328134-3`.
- **D1 GÜVENLİ:** dipnot bağı `baglanan_dipnotlar(m.body, ...)` ([enrich.py:222](../../src/mevzuat_tool/enrich.py#L222)) **`m.body`** üzerinde kurulur — `text`/bent üretiminden (`_text` → `body_temiz`, `corpus.py`) tamamen AYRI. Yani chunk üretiminde `[n]` silmek `metadata.dipnotlar[]` bağını BOZMAZ.

### Ertelenenler (gerekçe)
- **D2** (`_ESIK` 3→2, 661 chunk): `dipnot.py` apendiks-eşiği çok sayıda over-split korumasıyla (`_MAX_ORT_ARALIK`, `_MAX_SON_ISARET_KUYRUK`, `_MIN_ONCE_METIN`) hassas dengelenmiş; gerçek-veri bug'ları (7174 M8, 5335 M30, 102939 M11). Eşiği düşürmek bu dengeyi riske atar — **yüksek risk / düşük getiri** → ertelendi.
- **D3** (tablo duplike, ~42 chunk): `_tablo_duz` eşleşmesi bent-gömülü tabloları kaçırıyor (`102935-51`). Orta karmaşıklık, düşük frekans → ertelendi.

## D1 — `[n]` işaret temizleme

**Yer:** `corpus.py` chunk üretimi (`madde_to_chunk`) — hem `text` hem serialize edilen `fikralar[].bentler[].text` (ve fıkra/alt-bent text'leri). Tek yardımcı `_strip_dipnot_isaret(s)` = `re.sub(r"\[\d+\]", "", s)`, sonra boşluk normalize.

- `text` üretiminde (`_text` sonrası veya içinde) uygula.
- `fikralar` ağacında (`asdict` sonrası) recursive uygula: fıkra.text, bent.text, alt_bent.text.
- `metadata.dipnotlar[]` ve `degisiklik_gecmisi[]` DOKUNULMAZ (dipnot içeriği orada yapısal durur).

**YP-riski (düşük):** `[n]` yalnız dipnot işareti; `[` `]` mevzuat metninde başka yapısal anlam taşımaz. Künye `[...]` yok (künye `(...)` paren). Tablo markdown `|` farklı.

## Regresyon / Doğrulama
1. 🔴→🟢 TDD: `text`/bent'te `[n]` temizleme + `dipnotlar[]` korunma testi.
2. ♻️ Tam `pytest`.
3. 📊 916-kanun compare: `[n]` kalan chunk 5801→~0; `dipnotlar[]` dolu chunk SAYISI değişmez (5596); text uzunluğu hafif kısalır; status-flip 0.
   > ⚠️ Smoke build korpusu ezer → baseline al/geri yükle.

## Çıktılar (commit'ler)
- `fix(corpus): [n] dipnot işaretlerini text/bent metninden temizle (D1)`
- `docs(faz-5): dipnot temizleme — D2/D3 ertelendi`
