# FAZ 2 — Fıkra/Bent Sınır (B1 + B2) — Alt-Plan

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam**
> Düşük-riskli, **E-tuzağına (998 kenar-numaralı madde) DOKUNMAZ**. Dosya: `src/mevzuat_tool/fikra.py`.
> B2, FAZ 3'ten ÖNCE olmalı (cetvel sahte-bentleri numaralı-grup mantığını kirletmesin).

## ✅ SONUÇ (tamamlandı)
- **B1** ([fikra.py](../../src/mevzuat_tool/fikra.py) `_FIKRA_BOL`): dipnot `]` + boşluk sonrası `(n)` + **BÜYÜK harf** → fıkra-başı. 189065-5'te gömülü `(2)` ayrıldı.
- **B2** ([fikra.py](../../src/mevzuat_tool/fikra.py) `_CETVEL_BAS` + `_parse_hukum`): `(N) SAYILI LİSTE/CETVEL/TARİFE` öncülünden sonrası cetvel; fıkra/bent bölünmez, içerik son fıkraya eklenir. 104030-5'in 862 sahte bent'i gitti.
- **Birim test:** +5 (B1×3, B2×2). Tam paket **186 passed**, 0 kırık.
- **916-kanun regresyon:** bent maks **864→130**, sahte-bent **21→19**, fıkra-ayrımı 565 madde; status-flip yalnız **2** (B1 fıkra-ayrımı kaynaklı, doğru), **text değişen 0**. YP taraması: B1 ile yeni ayrılan fıkraların **0'ı** küçük-harfle başlıyor (cümle-ortası yanlış-bölme yok). E-tuzağı: bent-yapısı/numara-bent değişimi **0**.

> 🔑 **DERS (B1 yanlış-pozitif):** İlk B1 lookbehind (`(?<=\]\s)\(\d+\)\s`, büyük-harf şartı YOK) `103569-28` (Tababet 1219) cümlesini `(…)[10] (1) zimmet...` ortadan böldü → 1 yanlış flip. **Büyük-harf şartı** (`(?=[A-ZÇĞİÖŞÜ])`) eklenince düzeldi. Gerçek fıkra metni büyük harfle başlar; küçük-harf = cümle devamı. 916-kanun compare bunu yakaladı → "0 yanlış-pozitif" disiplini iş başında.

> 🔧 **Kapı düzeltmesi:** FAZ 3 "etkilenen-madde=0" kapısı YANLIŞ — B1 dipnot-ayrımı korumalı kanunları meşru etkiler. Doğru kapı: **bent-işaret/numara-bent değişimi=0** (master plana işlendi).

## Context

İki yapısal sınır hatası: (B1) dipnot `]` fıkra-bölmeyi maskeliyor → fıkralar birleşiyor; (B2)
ekli cetvel `(N) SAYILI LİSTE` sahte fıkra+bent üretiyor. Her ikisi de `_FIKRA_BOL` / `_bentler`
([fikra.py:24-35](../../src/mevzuat_tool/fikra.py#L24-L35)) kaynaklı.

### Canlı doğrulanan gerçekler (bu oturumda)
- **B1:** `(1) yükümlüdür.[1] (2) Fona...` → fıkra listesi `['(1)','(3)']` — **`(2)` kayıp** (1)'e gömülmüş. Dipnotsuz aynı metin `[(1),(2),(3)]` doğru. Kök: `_FIKRA_BOL` lookbehind `[.:!?]\s|\n|)\s` — `]` yok ([fikra.py:25](../../src/mevzuat_tool/fikra.py#L25)).
- **B2:** `104030-5` (Büyükşehir 5747 Yürütme): gerçek hüküm `(1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür.` (58 krk), sonra `(1) SAYILI LİSTE ADANA...` cetvel. Fıkra no'ları `(1),(1),(16),(18),(20),(22),(23),(27)` (tekrar+atlama=bozuk), fıkra `(27)`'de **862 sahte bent**. Korpus geneli: `(N) SAYILI LİSTE/CETVEL/TARİFE` içeren **321 madde**, **25'i şüpheli sahte-yapı**.
- ⚠️ **B2 yanlış-pozitif yüzeyi:** `sayılı` kelimesi **6844 maddede** meşru fıkra metninde ("5237 sayılı Kanun"). B2 guard'ı bunları ETKİLEMEMELİ → ayırt edici desen `(N) SAYILI` + büyük-harf `LİSTE/CETVEL/TARİFE` (salt `sayılı` değil).

---

## B1 — Dipnot `]` fıkra-bölme lookbehind

**Mevcut** ([fikra.py:24-28](../../src/mevzuat_tool/fikra.py#L24-L28)):
```python
r"(?=(?:(?<=[.:!?]\s)|(?<=\n))\(\d+\)\s)"   # cümle-sonu/satır-sonu sonrası '(n)'
```
Cümle `.[1]` ile bitince `]` ile `(2)` arasındaki lookbehind `[.:!?]\s` tutmuyor.

**Çözüm:** Birinci dala dipnot-kapanışı sonrası varyant ekle. `.[1] (2)` deseninde `]`'den önce
zaten cümle-sonu noktalama var → lookbehind'ı `(?<=[.:!?]\][\s]?...)` yerine basit ve güvenli:
`(?:(?<=[.:!?]\s)|(?<=\n)|(?<=\]\s))\(\d+\)\s`. Yani `]` + boşluk sonrası `(n)` de fıkra-başı.

> Not: `]` öncesinde tipik olarak cümle-sonu vardır (`.[1]`), ama lookbehind sabit-genişlik
> ister; en temizi ayrı `(?<=\]\s)` dalı. Atıf riski düşük: `[n]` dipnot işaretidir, `(n)` atıf
> bağlamında `]`'den sonra gelmez.

**YP-riski (düşük):** `]` + `(n)` deseni atıfta nadir. Mevcut atıf testleri korunur.

**Test (TDD — kırmızı):** `parse_fikralar("(1) yükümlüdür.[1] (2) Fona... (3) Üçüncü.")` → `[(1),(2),(3)]`.

---

## B2 — Ekli cetvel `(N) SAYILI` sahte-bent/fıkra guard'ı

**Mevcut:** `(N)` işareti bağlam-kör bölünüyor; cetveldeki uzun numaralı liste sıralı-koşu sayılıp bente eziliyor.

**Çözüm (cetvel-bölge muafiyeti):** `parse_fikralar` girişinde, gövdede `(\d+)\s+SAYILI\s+(?:LİSTE|CETVEL|TARİFE)` (büyük-harf, ardışık) deseninin İLK konumunu bul. Varsa, gövdeyi ikiye ayır:
- **hüküm-bölgesi** (cetvel öncesi) → normal `parse_fikralar` mantığı.
- **cetvel-bölgesi** (cetvel başından sona) → fıkra/bent BÖLÜNMEZ; tek bir ek-blok olarak hüküm-bölgesinin son fıkrasının metnine eklenir VEYA ayrı işaretlenir (tasarım: en basit ve bilgi-koruyan = son fıkra metnine dahil ama bent üretmeden).

> İdealde ekli cetveller HTML tablo olarak `tablolar[]`'a gitmeli (FAZ 5/D kapsamı); B2 yalnız
> **sahte yapı üretimini durdurur** (fıkra-no tekrarı + 862 bent). İçerik text'te kalır (kayıp yok).

**Uygulama:**
```python
_CETVEL_BAS = re.compile(r"\(\d+\)\s+SAYILI\s+(?:LİSTE|CETVEL|TARİFE)")
# parse_fikralar başında:
mc = _CETVEL_BAS.search(body)
if mc:
    hukum, cetvel = body[:mc.start()].strip(), body[mc.start():].strip()
    fikralar = _parse_hukum(hukum)         # normal mantık (cetvelsiz)
    if fikralar and cetvel:
        fikralar[-1].text += " " + cetvel  # içerik korunur, bent üretilmez
    return fikralar
```
(`_parse_hukum` = mevcut `parse_fikralar` gövdesi refactor; cetvel yoksa aynen çalışır.)

**YP-riski (orta) + korumalar:**
- 🛡️ Desen `(N) SAYILI` + büyük-harf `LİSTE/CETVEL/TARİFE` AND → `sayılı Kanun` (6844 madde) ETKİLENMEZ.
- 🛡️ Cetvel-öncesi gerçek hüküm normal parse edilir (104030-5'te `(1) Bakanlar Kurulu yürütür.` korunur).
- 🛡️ Cetvelsiz madde davranışı birebir aynı (mevcut tüm fıkra/bent testleri yeşil).

**Test (TDD — kırmızı):**
- `104030-5` deseni: `Yürütme (1) ... yürütür. (1) SAYILI LİSTE ADANA ... (2) SAYILI LİSTE ...` → 1 fıkra `(1)`, **0 sahte bent**; cetvel metni son fıkrada korunur ("ADANA" text'te var).
- 🛡️ `(1) 5237 sayılı Kanuna göre işlem. (2) İkinci fıkra.` → cetvel değil, `[(1),(2)]` normal.

---

## Regresyon / Doğrulama (FAZ 2 sonu)

> ⚠️ Smoke build `data/corpus/korpus.jsonl`'i ezer → baseline al/geri yükle (FAZ 0 notu). Baseline = FAZ 1-sonrası korpus.

1. 🔴→🟢 TDD: B1 + B2 kırmızı testleri → düzeltme → yeşil.
2. 🛡️ True-negative: atıf testleri (`test_inline_paren_number_references_are_not_fikra`), kenar-numara koruma (`test_marginal_numbers.py`), `sayılı Kanun` örneği.
3. ♻️ Tam `pytest` (181 + yeni). 0 kırık.
4. 📊 916-kanun compare:
   - **Sahte-bent proxy** (>30 bent): OLD=21 → NEW belirgin düşmeli (104030-5'in 862'si gider).
   - **Bent maks:** 864 → çok düşmeli.
   - **Fıkra dağılımı:** B1 ile fıkra sayısı bazı maddelerde artar (birleşmiş fıkralar ayrılır).
   - **Etkilenen madde:** B1 ~605 sınır + B2 ~25 cetvel maddesi; başka beklenmeyen değişim = incele.
   - **E-tuzağı kapısı:** `--kanun 4721,6098,6102,5846,2709` → 0 etkilenen (B1/B2 onlara dokunmamalı).
   - Spot-check: `189065-5` fıkra `(2)` ayrıldı; `104030-5` 862 bent gitti.

---

## Çıktılar (commit'ler)
- `fix(fikra): dipnot ']' sonrası fıkra-başı tanı — birleşmiş fıkralar (B1)`
- `fix(fikra): ekli cetvel '(N) SAYILI' sahte-bent/fıkra guard'ı (B2)`

İkisi atomik ayrı commit. Branch: `bugfix/phase-0`.
