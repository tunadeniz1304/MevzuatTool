# FAZ 22 — Numarasız Fıkra Sınır-Koruma (paragraf → fıkra) ✅

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (276 test yeşil, 0 sızıntı)**
> Branch: `faz-22/numarasiz-fikra-sinir-koruma`

## Kaynak: unique_atiflar.json atıf-kıyas ölçümü

`unique_atiflar.json` (8.290 benzersiz kanun/madde/fıkra/bent atıfı) ile korpusun **en katı mod**
karşılaştırması (atıfta belirtilen her seviye corpus'ta gerçekten bulunmalı → 1/0). İlk ölçüm
**%59.7** bulunma verdi; en büyük kayıp kalemi `fikra_yok = 1.083` (%13.1). Kök-neden kazısı bu
fazı doğurdu.

---

## Kök neden — paragraf sınırının pipeline'da ölmesi

**Gerçek:** Türk mevzuatında fıkralar **numarasızdır** — `(1)(2)` yazmaz, sadece **paragraf**
(ayrı `<p>`) ile ayrılır; "1. fıkra" = metindeki 1. paragraf. Ham HTML (`data/raw/html_*.html`,
916 kanun tam mevcut) bu `<p>` yapısını taşıyor.

**Kayıp iki katmanda:**
1. `fetch.py:strip_html` — `<p>`/`</p>` etiketlerini `<[^>]+>` deseniyle **boşluğa bile değil,
   bitişik** siliyordu → `<p>fıkra1</p><p>fıkra2</p>` → `fıkra1fıkra2`.
2. `normalize.py:15` — `re.sub(r"(?<!\n)\n(?!\n)", " ", ...)` tek satır kırığını boşluğa çeviriyor;
   `strip_html` zaten boş satırları atıp tek `\n` bıraktığı için fıkra sınırları hep tek `\n` →
   hepsi boşluğa dönüşüyordu.

**Sonuç:** 23.474 madde "tek blok" (tek numarasız fıkra); `fikra.py:_FIKRA_BOL` yalnız `(n)`
numarası aradığı için (kaynakta numara YOK) bunları hiç bölemiyordu.

## Çözüm — `\x1f` paragraf sınır işareti (3 katman, cerrahi)

Türk mevzuatında fıkra≠bent≠HTML-`<p>` ayrımını koruyan, mevcut 13-fazlık yanlış-pozitif
savunmasına dokunmayan bir sınır sinyali:

1. **`strip_html`** (`fetch.py`): `<p>/<div>/<li>` sınırlarını `\x1f` (Unit Separator — metinde
   asla geçmez) ile işaretle. `<br>` satır-içi kırıktır → `\n` kalır (davranış değişmez).
2. **`normalize_text`**: `\x1f`'e dokunmaz (yalnız `\n`/boşluk normalize eder) → sınır korunur.
3. **`fikra.py:_parse_hukum`**: numaralı `(n)` fıkra YOKKEN, `_numarasiz_fikra_bol` `\x1f`
   sınırından böler. **Bent işaretiyle (`a)` `1.` `1)`) başlayan paragraf yeni fıkra DEĞİL** →
   önceki fıkraya yapıştırılır (bent, fıkra değil — zehir koruması). 2+ fıkraya bölünürse
   **sıra no'su** atanır (`(1)(2)...` — Türk mevzuatında fıkra no'su = paragraf sırası → atıf
   `madde X fıkra N` eşleşir). Tek fıkrada `no=None` (mevcut sözleşme korunur).

**Cetvel sızıntı fix:** `_CETVEL_BAS` dalında cetvel gövdesine sızan `\x1f` düz metne indirildi
(9 madde → 0 sızıntı).

## 0-Sızıntı / regresyon kanıtı

- **276 test yeşil** (yeni 7 test: numarasız bölme, bent≠fıkra koruması, sıra-no, `\x1f`-çıktı-temiz).
- Zehir denetimi (tam korpus): **boş fıkra = 0, `\x1f` sızıntısı = 0.**
- 3 "boş bent" (492 Ek1, 488 Ek2, 4458 M227) — `b) i)` roman-alt-bent deseni; `_roman_i_idx`
  mantığı **FAZ 22 öncesinde de** aynı çıktıyı üretiyordu (git HEAD'de `_roman_i_idx` mevcut) →
  bu fazın regresyonu DEĞİL, bağımsız kenar durum.

## Etki — atıf bulunma oranı

| Metrik | Önce | Sonra |
|---|---|---|
| **Genel skor** (8.290 atıf, en katı) | 59.7% | **69.8%** (+10.1 puan, +832 atıf) |
| `fikra_yok` kaybı | 1.083 | **294** (−789, −%73) |
| **Fıkra-granülariteli atıf** | 34.4% | **77.6%** (+43 puan) |
| Tek-blok madde | 23.474 | 8.195 |
| Toplam fıkra | 46.643 | ~99.820 |

Projeksiyon %71.4 idi; gerçekleşen %69.8 (fark: bazı bölünmüş fıkra sırasının atıfın beklediği
numarayla birebir örtüşmemesi — beklenen tolerans).

## Kalan (bu fazın kapsamı dışı)
- `kanun_yok` (613) + `madde_yok` (593): eksik kanun/madde — korpus kapsamı işi, fıkra fazı değil.
- `bent_yok` (1.006): bent-seviyesi eşleşme — ayrı faz adayı.
- 3 boş bent (`b) i)` roman deseni): bağımsız mikro-fix adayı.
