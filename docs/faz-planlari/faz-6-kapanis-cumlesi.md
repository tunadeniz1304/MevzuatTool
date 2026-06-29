# FAZ 6 — Liste-kapanış cümlesi (B4) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (0 FP)**
> Bu, projenin EN BAŞINDA fark edilen orijinal bug'dır (GVK m.2). İlk "son cümleyi kes" denemesi
> **46 yanlış-pozitifliydi** (FAZ 0'da geri alındı). Bu faz onu **dar imzayla** yeniden tasarlar.
> Dosya: `src/mevzuat_tool/fikra.py`.

## ✅ SONUÇ (commit edildi — etkilenen-madde=3, 0 FP)

- **B4** ([fikra.py](../../src/mevzuat_tool/fikra.py) `_kapanis_ayir` + `_kisa_enum_bent` +
  `_KAPANIS_GERI_ATIF`): liste-açan fıkrada son bende yapışmış geri-atıflı kapanış cümlesi son
  bentten ayrılır. `_parse_hukum`'da her fıkra için `_bentler` sonrası uygulanır.
- **Birim test:** +4 (hedef GVK m.2 + 3 FP-koruma: `Ancak` istisnası, çok-cümle bent, geri-atıfsız
  başlık). Tam paket **199 passed**.
- **916-kanun regresyon:** etkilenen-madde **TAM 3** (`103111-2`, `103111-Gecici56`, `103003-9`);
  status-flip 0; sahte-bent 0; fıkra dağılımı sabit; **text (embedding) değişimi 0** (yalnız
  `bentler[]` yapısı düzeldi).

> 🔑 **DERS:** İlk denemenin 46 FP'sinin kaynağı ölçülerek bulundu: naif "son bentte ekstra cümle"
> proxy'si korpusta **2008 aday** veriyor, çoğu `a) ... kaldırılır. Ancak ...` = bende MEŞRU 2.
> cümle. Kademe kademe daralt: +liste-açan `:` → 19, **+geri-atıf → 3 (0 FP)**. Geri-atıf öncülü
> (`Bu Kanunda`/`yukarıda`/`Şu kadar ki`) FP-tuzaklarını (`Ancak` istisnaları) ve bleed başlıklarını
> eler. `fikra.text` dokunulmadığı için embedding girdisi bit-bit korunur.

## Kapsam kararı (kullanıcı)
**EN DAR — geri-atıflı kapanış.** Orta/geniş kapsam (tam-cümle / `Ancak` dahil) FP riski taşıdığı
için reddedildi.

## DAR imza (3 koşul AND)
1. **Liste-açan fıkra:** giriş cümlesi `:` ile biter (`...şunlardır:`).
2. **Kısa-enum bentler:** son-bent HARİÇ hepsi `<70` krk, virgül/`;` sonu, tek cümle.
3. **Geri-atıflı kapanış:** son bent `<öğe>. <KAPANIŞ>` ve KAPANIŞ şununla başlar:
   `Bu Kanunda` / `Bu kanunda` / `Yukarıda` / `yukarıda` / `Bunlar` / `Şu kadar ki` /
   `Söz konusu` / `Bu fıkra(da)`.

İmza tutarsa `bentler[-1].text` = `<işaret> <öğe>.` (kapanıştan önce); kapanış cümlesi
`fikra.text`'te KALIR (kayıp yok).

## FN analizi (adversarial workflow, 9 ajan)
Genişletme bölgesi sınıflandırıldı (kapsam genişletme borcu için):

| Kademe | Toplam | TP (kaçırılan gerçek bug) | FP | BLEED (C1'in işi) |
|---|---|---|---|---|
| K1 (uygulanan) | 3 | 3 | **0** | 0 |
| FN_orta (K2\K1) | 16 | 7 | 4 | 5 |
| FN_geniş (K3\K2) | 73 | 11 | 3 | **59** |

- **18 gerçek TP** genişletme borcu (master "Kalan Zehir" Z2). Geri-atıfı gevşetmek FP getirir
  (orta 4 + geniş 3); genişletmenin asıl bedeli BLEED (59, FAZ 4 C1 alanı, yanlış mekanizma).

## Bilinen sınır (commit'i bloke etmez)
`103003-9` (YMM şartları): fix `c) ...almış olmak, Şartları aranır.` bıraktı — `Şu kadar ki...`
kesildi ama ondan önceki `Şartları aranır.` kapanışı hâlâ `c)`'de. Yine de iyileşme (devasa
paragraf çıktı, `text` korundu); FP değil, "tam temiz değil". Z2 genişletmesinde ele alınabilir.

## Çıktılar (commit'ler)
- `fix(fikra): liste-kapanış cümlesini son bentten ayır (B4)`
- `docs(faz-6): kapanış cümlesi tamamlandı + kalan zehir kalemleri (Z1-Z5)`
