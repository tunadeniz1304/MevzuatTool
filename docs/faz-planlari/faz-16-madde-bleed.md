# FAZ 16 — Madde-bleed / yapışık başlık (BUG 2) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (confusion matrix FP=0)**
> Altınset karşılaştırması + fizibilite agent'ıyla bulundu; 0-FP kanıtlı 2 gerçek parser-bug'dan ikincisi (birincisi FAZ 15).
> Dosya: `src/mevzuat_tool/chunker.py`.
> Tasarım: [../superpowers/specs/2026-07-06-faz-16-madde-bleed-yapisik-baslik-design.md](../superpowers/specs/2026-07-06-faz-16-madde-bleed-yapisik-baslik-design.md)
> Plan: [../superpowers/plans/2026-07-06-faz-16-madde-bleed.md](../superpowers/plans/2026-07-06-faz-16-madde-bleed.md)

## Sorun

Kaynak metinde bir maddenin başlığı bir öncekinin gövde-sonuna **boşluksuz yapışık** geliyordu:
`"...şartlarıMADDE 132- (1) Karşı dava..."`. Ana madde deseni (`_MADDE`, chunker.py) `MADDE`'den önce `\b`
sözcük-sınırı bekliyor; ama Türkçe küçük harf (`ı`, `i`, `r`, `n`) + `M` **ikisi de word-char** → `\b`
OLUŞMAZ → başlık yakalanmaz → madde önceki gövdeye gömülür ve korpusa **ayrı chunk olarak hiç girmez**.

**Vakalar (kaynak-doğrulandı, hepsi 6100/HMK):**
- 6100:131 → 132 **ve** 133 gömülü (`...şartlarıMADDE 132-`, `...süresiMADDE 133-`)
- 6100:134 → 135 gömülü (`...hükümlerMADDE 135-`)
- 6100:164 → 165 gömülü (`...sorunMADDE 165-`)

Adversarial tarama (`<sözcük-karakteri>MADDE <no>- (<rakam>)` deseni, 916 kanun) korpus-genelinde **tam 4
eşleşme** buldu — **hepsi gerçek bug, 0 meşru/atıf**. Desen doğal olarak 0-FP.

## ✅ SONUÇ (commit `210370c` + `a48a02d` + `5af848f`)

- **`_YAPISIK_MADDE` + `_split_yapisik_madde`** ([chunker.py](../../src/mevzuat_tool/chunker.py)): Yaklaşım B
  (post-tespit). Ana `_MADDE` deseni DEĞİŞMEDİ. `split_articles`'ta madde bölündükten sonra her `body`
  içinde `(?<=[\wçğıöşüâîÇĞİÖŞÜ])MADDE\s+(no)-\s*(?=\()` yapışık imzası aranır (lookbehind sözcük-karakteri;
  tire + `(` fıkra imzası atıfları eler). Bulunursa gövde **gerçek cümle-sonundan** bölünüp gömülü madde
  ayrı `Article` olarak üretilir. `out.append(...)` → `out.extend(_split_yapisik_madde(no, body))`.
- **Gerçek cümle-sonu tespiti** (`_GERCEK_CUMLE_SONU = [.!?]\s+(?=[A-ZÇĞİÖŞÜ0-9])`): bölme noktası = gömülü
  `MADDE`'den geriye **en sağdaki gerçek cümle-sonu** (nokta + boşluk + büyük-harf/rakam ile başlayan yeni
  birim). Başlık İÇİNDEKİ sıra/kısaltma noktası (`5. fıkra`, `md.`) cümle-sonu SAYILMAZ → yanlış bölme yok.
- **0-FP KAPILARI (3):** (1) lookbehind sözcük-karakteri ŞART — boşluklu normal `MADDE 2- (1)` (ana desenin
  zaten yakaladığı) çift-bölünmez; (2) tire + `(` fıkra imzası — gövde-içi atıf (`MADDE 5'e göre`,
  `132 nci maddesi`) madde sayılmaz; (3) gerçek cümle-sonu yoksa bölme YAPILMAZ (başlık ayrılamaz → ertele).
- **Gömülü body BAŞLIKSIZ** (`5af848f`): sistem sözleşmesi = `Article.body` başlıksız; başlık ayrıca
  `node.baslik` (API madde-ağacı) → [corpus.py:112-113](../../src/mevzuat_tool/corpus.py) `text = madde_baslik
  + "\n" + govde` ile prepend edilir. Konteyner maddeler (131,134,164) bu sözleşmeye zaten uyuyordu; gömülü
  maddeler için başlık body'ye konulunca **çift-başlık** oluşuyordu (916-build sonrası bulundu). Fix: gömülü
  body başlıksız üretilir — başlık node.baslik'ten gelir (132/133/135/165 hepsi API'de dolu, doğrulandı).

## Confusion Matrix (kaynak-doğrulamalı, son build)

| Yeni bölme | Kanun:Madde | TP/FP | Başlık (API node.baslik) | Gövde |
|---|---|---|---|---|
| 132 | 6100:132 | **TP** | `Karşı dava açılabilmesinin şartları` | `(1)` ile başlıyor |
| 133 | 6100:133 | **TP** | `Karşı davanın açılması ve süresi` | `(1)` ile başlıyor |
| 135 | 6100:135 | **TP** | `Uygulanacak hükümler` | `(1)` ile başlıyor |
| 165 | 6100:165 | **TP** | `Bekletici sorun` | `(1)` ile başlıyor |

**FP = 0.** 4/4 gerçek gömülü madde. Adversarial tarama deseni yalnız bu 4 yerde buldu; her yeni madde
standart formatta (`<başlık>\n(1) ...`).

## Regresyon Kapısı (5-katman)

1. **TDD RED→GREEN:** 3 hedef test (131→131,132,133; 134→134,135; sıra-noktası doğru-cümle-sonu) + 3 FP-koruma
   test (boşluklu-MADDE çift-bölünmez / atıf madde sayılmaz / cümle-sonu-yok bölme yok). **230 passed.**
2. **Mevcut testler yeşil:** 224 baz test kırılmadı (+6 yeni = 230).
3. **916-kanun compare** (baseline FAZ 15 → NEW FAZ 16):
   - Etkilenen: **yalnız 6100** — değişen 131/134/164, eklenen 132/133/135/165 (**+4/-0**). 6100-dışı **0 değişim** (bağımsız teyit).
   - Status-flip **0** (bölme yürürlüğü değiştirmez). Mülga oranı %11.00→%11.00.
   - Fıkra dağılımı DEĞİŞMEDİ (ort 1.48, med 1.0, maks 42). Bent 0.93→0.93, sahte-bent 13→13.
   - **E-tuzağı** (TMK/TBK/TTK/FSEK/Anayasa): 6100 listede değil → yapı hiç değişmedi.
4. **Confusion matrix:** yukarıda — 4 TP, 0 FP (kaynak-doğrulamalı).
5. **Spot-check:** 7 hedef madde ayrı chunk VAR; 131 artık 132/133 sızıntısı içermiyor (`ileri sürülemez.`
   ile temiz bitiyor); çift-başlık yok (tüm maddeler standart `<başlık>\n(1)` formatı).

> NOT: `data/corpus/korpus.jsonl` git-ignored (FAZ 15'teki gibi) → korpus commit'lenmedi, regresyon kanıt-only.

## Etki

6100 (HMK): 3 chunk → 7 chunk (131→131+132+133, 134→134+135, 164→164+165). 4 komşu madde
(132/133/135/165) retrieval'a kazandırıldı. **0-FP.** Küçük ama net; her vaka 1-2 komşu maddeyi kurtarır.

## Ders (fizibilite disiplini)

916-build **çift-başlık** bug'ını ortaya çıkardı — birim testler (izole `split_articles`) yakalamamıştı,
çünkü sorun `split_articles` ↔ `corpus.py` **komponent sınırında** (body sözleşmesi). Systematic-debugging
ile kök neden (body başlıksız olmalı sözleşmesi) bulundu; symptom (çift metin) yerine sözleşme düzeltildi.
Master plan "build sonrası regresyon kapısı + spot-check" adımı olmasaydı çift-başlık korpusa sızardı.
