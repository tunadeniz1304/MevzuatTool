# FAZ 3 — Numaralı Asıl-Grup (B3) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam**
> **EN RİSKLİ FAZ** — 998 kenar-numaralı madde (TMK/TBK/TTK/FSEK/Anayasa) toplu bozma tuzağı.
> Dosya: `src/mevzuat_tool/fikra.py`.

## ✅ SONUÇ (tamamlandı)
- **B3** ([fikra.py](../../src/mevzuat_tool/fikra.py)): `_kes_iki_seviye` + `_harf_alt_bentler`; numaralı üst-grup (`1. 2.`) → `Bent`, altındaki harf (`a) b)`) → `AltBent`. Yeni alan yok (mevcut `alt_bentler` işaret-agnostik).
- **Tetik (4 AND koşulu):** (A) sıralı numara-koşu≥2, (B) bir dilimde harf var, (C) toplam harf≥2, (D) **ilk yapısal işaret NUMARA** (numara-üst).
- **Birim test:** +4 (hedef, 2 geriye-uyum, 1 harf-üst koruma) + TTK M4 kilidine açık assert. Tam paket **190 passed**.
- **916-kanun regresyon:** **164 madde** numaralı-üst-gruba döndü (Gümrük 4458=50, İYUK 2577=13, GVK 193=10, ÖTV/KDV...). E-tuzağı kapısı: **5 korumalı kanunda yapı değişimi 0** ✓. Status-flip **0**, text değişen **0**. Şüpheli (harf-ilk ama yapı-değişen): **0**. `103044-3` → 8 numaralı üst-bent + 33 harf alt-bent.

> 🔑 **DERS (TTK harf-üst yanlış-pozitifi):** İlk B3 (D koşulu YOK) TTK 6102'de **5 madde** ters çevirdi — `103039-55/181/960`'da hiyerarşi `a) ... 1. ... 2. ... b)` yani **harf ÜST, numara ALT** (Gümrük'ün TERSİ). B3 numara-üst varsaydığı için ters çözdü. **916-kanun E-tuzağı kapısı bunu yakaladı.** Çözüm: (D) "ilk yapısal işaret numara" şartı — `num_seq[0].start() < harf[0].start()`. İki hiyerarşi yönü (numara>harf vs harf>numara) artık doğru ayrışıyor.

## Sarkan-numara (9 madde) — ERTELENDİ
Ayrı kök (cümle-sonu `...edilir. 5.`), B3 kapsamı dışı. Sonraki küçük iş / kabul-edilen borç.

## Context

Bazı kanunlarda (Gümrük 4458, BİM 2576...) asıl yapı İKİ SEVİYELİ: numaralı üst-grup (`1. 2. 3.`)
+ her birinin altında harf-bent (`a) b) c)`). `_bentler` "ilk-stil-kazanır" ([fikra.py:114](../../src/mevzuat_tool/fikra.py#L114)) →
harf varsa numara koşusu yok sayılıyor → numaralı üst-grup kayboluyor, harf-bentler tek düz listeye eziliyor.

### Doğrulanmış gerçekler (bu oturumda korpustan)
- **Hedef küme: 64 madde / 30 kanun** (sıralı numara-koşu≥2 + tekrarlı harf-bent `a)`≥2). **E-tuzağı 5 kanunuyla çakışma = 0** ✓ (güçlü güvence).
- `103044-3` (Gümrük Tanımlar): `1. "Müsteşarlık"; 2. a)...; b)...; 9. a)...; 15. a)...h)` — mevcut: 1 fıkra, **33 düz bent** (numaralı üst-grup kayıp). Mevcut `alt_bentler`=0.
- **Üç-seviye** (numara>harf>paren-rakam `1)`) içeren: hedeften yalnız **8 madde** → veri modeli kararını etkiler.
- **Sarkan-numara** (`...edilir. N.` ile biten son bent): yalnız **9 madde** (FAZ 2 B1 çoğunu zaten çözmüş; eskiden ~60). Ayrı/küçük iş.

### Ayırt edici sinyal (kenar-numara tuzağından)
Numaralı-grup gerçek ise text-içinde HEM sıralı numara-koşu HEM tekrarlı harf-bent (`a)` ≥2) var.
Kenar-numarada (`1. Genel olarak` başlık) harf-bent **yok** → sinyal onları yakalamaz.

## Veri modeli kararı
Mevcut `AltBent`'i **işaret-agnostik** kullan, YENİ alan EKLEME:
- Numaralı üst-grup `1.` → `Bent(isaret="1.", alt_bentler=[...])`
- Altındaki harf `a)` → `AltBent(isaret="a)", ...)` (mevcut `1)` paren-rakam ile aynı tip; çelişmez)
- **Üç-seviye** (numara>harf>paren-rakam, 8 madde): bu fazda DÜZLEŞTİR — `a)`'nın içindeki `1)` paren-rakam `AltBent.text` içinde kalır (4. seviye eklenmez). RAG atfı "Gümrük 3/15 a bendi" iki seviyeyle çözülür.
- Serileştirme: `corpus.py` `asdict` otomatik akar, ek kod yok.

**RAG atıf yapısı:** `madde › fıkra › bent(isaret="15.") › alt_bent(isaret="a)")` → `bentler[isaret=="15."].alt_bentler[isaret=="a)"]` ile çözülür (mevcut düz 33-liste bunu imkânsız kılıyordu).

## Algoritma (`_bentler` iki-seviyeli dal)
1. `num_seq` (sıralı `1. 2.` koşusu) + `harf` (tüm `a)`) topla — mevcut mantık.
2. **İki-seviyeli mod tetiklenirse** (koşul ↓): üst seviyeyi `num_seq` ile dilimle; her dilim için harf alt-bentlerini çıkar → `Bent(isaret="1.", alt_bentler=[AltBent("a)"...)])`.
3. **Tetiklenmezse:** mevcut iki `return _kes(...)` satırı (114-117) **BİREBİR DEĞİŞMEZ** → geriye-uyum garanti.

Kod yeniden kullanım: `_alt_bentler`'i parametrik yap (`isaret_re`, sıralı-koşu opsiyonel); harf alt-bent için `_BENT_HARF_ISARET` geç (harfte sıralı-koşu şartı gevşek: ≥1 eşleşme).

## Tetikleme koşulu (KONSERVATİF, AND'li — 0 yanlış-pozitif)
```
(A) len(num_seq) >= 2                         # sıralı numara-koşu (1. 2. ardışık)
(B) en az bir num_seq diliminde harf >= 1     # üst-grubun ALTINDA harf var
(C) toplam harf eşleşmesi >= 2                # tek 'a)' gürültüsünü ele
```
**E-tuzağı neden GEÇMEZ:**
- Kenar-numara (`1. Genel olarak` başlık) → düz paragraf, harf-bent yok → (B) düşer.
- **TTK M4** (`(1)` paren-fıkra + `a)..f)`): gövdede sıralı `1. 2.` numara-**koşusu** YOK (tek `(1)` paren) → (A) düşer → mevcut `if harf` dalı → `a)..f)` korunur. ⭐ Koruma kalbi.
- **`_BENT_NUM_ISARET`=`\d+\.` (nokta) ≠ alt-bent `1)` (paren)** → `test_splits_alt_bentler_within_bent` (`1)` paren) (A)'yı geçmez, korunur.

## Sarkan-numara (9 madde)
**AYRI ele al, bu fazda DEĞİL.** Farklı kök (cümle-sonu sınırı `...edilir. 5.`). B3 ile karıştırmak tetik koşulunu kirletir. B3 stabil olunca ayrı küçük iş (FAZ 3.1 veya kabul-edilen borç).

## Risk altındaki testler (geriye-uyum — hepsi korunur)
| Test | Neden korunur |
|---|---|
| `test_splits_letter_bentler` | num_seq yok → (A) düşer → `if harf` dalı |
| `test_splits_numbered_bentler` | num var, harf yok → (B) düşer → `num_seq` dalı |
| `test_splits_alt_bentler_within_bent` | `1)` paren ≠ `1.` → (A) düşer, mevcut dal |
| `test_marginal_*` (998 kilit) | harf yok (B düşer) / TTK M4 (A düşer) |

## Regresyon stratejisi
- compare_corpus.py proxy `alt_bentler`'e inmiyor → B3'te üst-bent sayısı 33→~15 DÜŞER (iyileşme gibi görünür, aslında doğru yapı). İzleme için:
  - **E-tuzağı kapısı (yapı-bazlı):** 5 kanunda `[b.isaret for b in bentler]` + `alt_bentler` yapısı OLD==NEW (bit-bit aynı). B3 koşulu bu kanunlarda tetiklenmez → beklenen 0 değişim.
  - **Hedef 64 madde:** `bentler[].isaret` `['a)',...]` → `['1.','2.',...]` numaralı; `alt_bentler` dolu.
  - **Status-flip = 0** (yürürlük mantığı değişmiyor).
- Spot-check: `103044-3` → 15 numaralı üst-bent, her birinin altında harf alt-bent.

## Çıktılar (commit'ler)
- `fix(fikra): numaralı asıl-grubu iki-seviye çöz (1. > a)) — düz-ezilme (B3)`
- (Sarkan-numara ayrı, sonraki iş.)

