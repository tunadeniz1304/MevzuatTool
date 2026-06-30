# FAZ 13 — Ezilmiş liste (SINIF 2) + Kiril homoglyph (E2) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Kiril tamam; SINIF 2 ertelendi**
> Dosya: `src/mevzuat_tool/fikra.py`.

## ✅ E2 (Kiril homoglyph) — TAMAM (commit `0dba7c3`, 0 FP)

- Bent işareti Kiril homoglyph (`а)` U+0430 yerine Latin `a)`) → `_BENT_HARF_ISARET` tanımıyor, bent
  kayboluyordu (103907-8 fıkra (3)/(4): `а) Üç günlüğe...` bent a) kayıp).
- `_normalize_kiril_isaret`: YALNIZ işaret konumundaki (`<boşluk>Kiril)`) Kiril harfi Latin'e çevirir
  (асеорух→aceopyx). `parse_fikralar` girişinde. İçeriğe dokunmaz.
- **916-kanun:** etkilenen **TAM 1 madde** (103907-8), fıkra (3) `b)c)`→`a)b)c)`; status-flip 0;
  başka madde değişmedi (**0 FP**). Birim test +1. **216 passed**.

## ⏸️ SINIF 2 (ezilmiş liste / harf-restart) — ERTELENDİ (semantik, regex 0-FP veremez)

### Sorun
İki ayrı fıkra/liste tek fıkrada ezilmiş — harf-restart (`a)..e) a)..`) var ama gömülü `(N)` YOK
(E1 onu zaten ayırdı). Onaylanan bug: 103888-4A (3 liste), 103814-6, 103191-107, 103888-2.

### Neden ertelendi (KANIT)
**170 madde** harf-restart'lı AMA bug ile meşru-iki-liste **yüzeysel olarak AYNI desene** sahip:

| | restart-öncesi | restart sonrası |
|---|---|---|
| BUG 103888-4A | `...şunlardır:` | `a) İlgili mevzuat...` |
| MEŞRU 103758-Ek1 | `...görevleri şunlardır;` | `a) Yönetim kurulunun...` |
| BUG 103814-6 | `...yetkileri şunlardır:` | `a) Oyunlar ile...` |
| MEŞRU 103918-15 | `...yürütülür:` | `a) Ulusal kalkınma...` |

Denenen 2 kod-sinyali ikisi de FP/FN üretti:
- `:`-bitiş + restart: hem bug'da hem meşruda var (ayırmaz).
- "yeni-giriş cümlesi" (şunlardır:/görevleri): BUG'da 3 True/1 False (103191-107 KAÇAR);
  MEŞRU'da 1 True (103758-Ek1 → **FP**)/4 False. Güvenilir değil.

Ayrım tamamen **semantik** (ikinci liste GERÇEKTEN ayrı fıkra mı, aynı maddede meşru ikinci liste
mi). Adversarial denetim bile bunları ancak **kaynak HTML'e inerek** ayırabildi. Regex 0-FP veremez.
**Z2 (kapanış genişletme) ile aynı durum** — kapsamı bilerek daralt, 0-FP disiplinini koru.

### Çürütülen 9 meşru vaka (SINIF 2'nin neden riskli olduğunun kanıtı)
104329-105, 103918-15, 103758-Ek1, 102927-5, 103191-Gecici32, 104349-Gecici2, 103186-Gecici3,
103708-32, 104831-Gecici2 — hepsi harf-restart'lı ama MEŞRU (kaynak-doğrulandı). SINIF 2 fix'i
bunları bozardı.

## Çıktılar
- `fix(fikra): bent işaretindeki Kiril homoglyph'i Latin'e normalize et (E2)`
- (SINIF 2: fix yok — ertelendi)
