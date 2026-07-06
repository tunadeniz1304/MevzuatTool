# FAZ 15-16 — Kanun-sonu bleed + Madde-bleed — Tasarım (Design Spec)

> Master plan: [../../yapisal-sadakat-master-plan.md](../../yapisal-sadakat-master-plan.md)
> Branch: `bugfix/phase-15-corpus-fixes` · Tarih: 2026-07-06
> Parser: `src/mevzuat_tool/chunker.py`

## Bağlam

Altınset (dış gold set) ile korpus karşılaştırması + 3 paralel fizibilite agent'ı, 9 aday bug'dan
**yalnız 2'sinin** gerçek parser-bug'ı VE 0-yanlış-pozitif (0-FP) çözülebilir olduğunu ölçtü. Diğer 7:
- **BUG 1** (nokta-stili fıkra): YANLIŞ TEŞHİS — `1. 2. 3.` dizileri fıkra değil **bent**, zaten doğru
  bölünmüş (kanunların kendi dili "bent" diyor: 193:23 "Bu bentte"). Düzeltmek regresyon olurdu. → ERTELE.
- **BUG 3** (başlık None %42): gerçek kayıp ~0; başlıksızlık meşru (torba/değişiklik kanunları). Başlık
  API node'undan gelir, text'te yok → parser çıkaramaz. → PARSER-DIŞI/ertele.
- **BUG 6** (gövde kaybı): 32 gerçek vaka ama gövde korpusa hiç çekilmemiş (fetch eksik). → PARSER-DIŞI (fetch).
- **BUG 7** (hizalama): altınsetin kendi artefaktı (variant'ı madde_no'ya yazmış). Bizim parser doğru. → KAPSAM-DIŞI.

Bu spec, **0-FP kanıtlı 2 bug'ı** iki faz olarak ele alır. FAZ 1-14 disiplini korunur: `text` (embedding)
bozulmaz, yalnız yapı düzelir; her faz 0-FP; 5-katmanlı regresyon kapısı.

---

## FAZ 15 — Son-madde kanun-sonu ek bleed (BUG 9)

### Sorun
Bir kanunun **son maddesi** genelde "Yürütme" ("Bu Kanunu Bakanlar Kurulu/Cumhurbaşkanı yürütür") —
kısa, tek cümle. Ama `split_articles`'ta son maddede `end=len(text)` olduğu için, o maddenin ardından
gelen **kanun-sonu ekleri** gövdeye giriyor:
- Değişiklik-listesi tablosu ("X SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUAT LİSTESİ")
- Kadro/tarife cetvelleri ("N SAYILI CETVEL/LİSTE")
- Yürürlüğe-giriş tabloları, toplu AYM iptal şerhleri

Sonuç: "Bakanlar Kurulu yürütür" + devasa cetvel tek chunk (5996:50 = 5791 kar, 657:239, 5651:14...).

### Çözüm (0-FP, agent ölçümüyle doğrulanmış)
`chunker.py`'de mevcut `_SEVIYE_BASLIK_BLEED` / `_ISLENEMEYEN_EKI` **kardeşi** yeni `_KANUN_SONU_EK_BLEED`.
Gövde-kuyruğu kırpma — ağaç değişmez, `text` içindeki meşru içerik korunur.

**Desen — ANCHOR + tümü-büyük belge başlığı:**
1. **ANCHOR:** `(Bakanlar Kurulu|Cumhurbaşkanı)\s+yürütür` — kesim YALNIZ bu cümleden sonra.
2. Anchor sonrası `<~60 kar` içinde **tümü-büyük** belge başlığı görülürse, oradan madde sonuna kadar kes:
   - `(N|Roman) SAYILI (CETVEL|LİSTE|ÇİZELGE|TARİFE|KADRO|TABLO|EK GÖSTERGE)`
   - `SAYILI KANUN[A]? (EK VE)? DEĞİŞİKLİK GETİREN` (142/154 vaka — en güçlü)
   - `Değiştiren Kanunun ... | İptal Eden Anayasa Mahkemesi Kararının Numarası` (tablo başlığı)
   - `GÖSTERİR (TABLO|LİSTE)`

**Güvenlik kapıları (0-FP için ZORUNLU):**
- **Anchor şart** — anchorsuz "salt sınır" ölçümde **299 tüm-madde-kaybı** (felaket) üretti. Anchor bunu eler.
- **Küçük-harf → KESME:** kesilecek ilk karakter küçük-harfse (hüküm cümlesi devamı) kesme.
- **Tümü-büyük belge başlığı şart** — meşru gövde-içi "NNNN sayılı Kanun" atfı küçük-harf, karışmaz.

### Ölçülen sonuç (fizibilite agent, korpus 31.416)
| Tasarım | Kesim | FP (meşru kayıp) | Kaçan bleed |
|---|---|---|---|
| ANCHOR (yürütür + tümü-büyük çöp) | **441** | **0** | 25 |
| Salt-sınır (anchorsuz) | 593 | **299 (felaket)** | — |

- Meşru "Yürürlük" maddeleri (yürürlüğe-giriş tablosu) "yürütür" içermez → anchor dokunmaz.
- "Ekli 2 sayılı listede..." madde-başı meşru atıf → anchor eler (0 kesim).
- Meşru "yürütür + gerçek hüküm devamı" korpusta HİÇ yok → güvenli.

### ERTELE (bu fazın DIŞI, semantik — Z2/SINIF2 gerekçesi)
"yürütür" sonrası **küçük-harf düz cümleyle** akan çöp (tümü-büyük başlık YOK): 7326:18 (CB Kararı düz
metin), 6552:146, 3986:21 (AYM şerhi düz metin). Regex meşru hüküm cümlesinden ayıramaz. ~3-5 madde.

### Etki
~441 madde temizlenir (0-FP ölçüldü), ~3-5 semantik vaka ertelenir.

---

## FAZ 16 — Madde-bleed / yapışık başlık (BUG 2)

### Sorun
Kaynak metinde bir maddenin başlığı bir öncekinin gövde-sonuna **boşluksuz yapışık**:
`"...şartlarıMADDE 132- (1)..."`. Parser'ın madde deseni (`_MADDE`, chunker.py:31-34) `MADDE`'den önce
`\b` sözcük-sınırı bekliyor; ama Türkçe küçük `ı` + `M` **ikisi de word-char** → `\b` oluşmaz → başlık
yakalanmaz → madde chunk'ı sonraki maddeye kadar akar. Sonuç: 132/133. madde 131'in içine gömülür.

**Vakalar (3, hepsi 6100/HMK):** 6100:131 (→132,133), 6100:134 (→135), 6100:164 (→165).

### Çözüm (0-FP, dar imza)
Madde deseninde `MADDE` öncesi ayracı, sözcük-karakteri-sonrası-toleranslı yap. Ayırt edici imza çok dar:
`MADDE <no>- (<fıkra>)` — no ≠ kendi madde_no. Atıflar ("MADDE 5'e göre") bu desende yakalanmaz (fıkra
`(1)` takibi zorunlu, karışık-case atıf zaten elenir). Ölçümde imza tam 3 madde, 0 şüpheli FP.

**Yaklaşım seçeneği (plan aşamasında netleşir):** ya (a) `_MADDE` deseninin `\b`'sini gevşet + FP-guard,
ya (b) split sonrası "yapışık MADDE N-(1)" post-tespiti. Hangisi 0-FP + minimum-regresyon → planda karar.

### Etki
3 madde (HMK), 0-FP. Her vaka 2-3 komşu maddeyi kurtarır (131/132/133 ayrı chunk olur).

---

## Ortak: Regresyon Stratejisi (5-katmanlı kapı — her iki faz)

Master plan FAZ 1-14 disiplininin aynısı. **"Eskiden çalışan yerleri bozmama" merkezî hedef.**

1. **TDD RED→GREEN** — gerçek bug id'leriyle hedef testleri (5996:50 bleed kesilir, 6100:131 132-ayrılır)
   + FP-koruma testleri (meşru "yürütür+hüküm" kesilmez, "MADDE 5'e göre" atfı madde sayılmaz).
2. **Mevcut 217 testin TAMAMI yeşil** — özellikle B1/B2/B3/A2/E-tuzağı/`_SEVIYE_BASLIK_BLEED`/E1-E3.
   Bir tek kırılırsa fix yanlış.
3. **916-kanun baseline diff** (`compare_corpus.py --gate`):
   - Baseline al → build → compare. Etkilenen-madde beklenen kümede mi (FAZ 15: ~441 yürütme/son-madde;
     FAZ 16: 6100 HMK 3 madde + komşuları).
   - Status-flip 0 (bleed kırpma yürürlüğü değiştirmemeli).
   - Fıkra/bent dağılımı: FAZ 16'da 131/132/133 ayrılınca fıkra-sayısı değişir (beklenen).
   - **E-tuzağı 5-kanun** (TMK/TBK/TTK/FSEK/Anayasa) **bent/fıkra YAPISI DEĞİŞMEZ** (sert kapı). NOT
     (FAZ 15 kararı): kanun-sonu bleed bu kanunların da SON maddesinde olabilir (FSEK 5846:91, TTK
     6102:1535 "yürütür"+değişiklik-listesi çöpü) — bu maddelerde çöp-temizliği (text kısalması) MEŞRUDUR,
     yapı (fıkra/bent) korunduğu sürece E-tuzağı ihlali sayılmaz. Sert kapı = yapısal-sadakat, salt text-eşitlik değil.
   - Çürütülen-meşru vakalar (Ekli-sayılı-liste madde-başı) DEĞİŞMEZ (sert kapı).
4. **Confusion matrix** (FAZ 15 — FP-riskli): yeni her kesimi TP(gerçek çöp)/FP(meşru içerik) sınıflandır
   (adversarial agent, kaynak-doğrulamalı). FP=0 → commit; FP>0 → daralt veya ERTELE.
5. **Spot-check** — hedef id'ler (5996:50 kesildi mi, 6100:131→132 çıktı mı) + rastgele 5 değişmemiş-
   olması-gereken madde elle kontrol.

> ⚠️ Smoke build korpusu ezer → her faz: baseline al → build → compare → (kötüyse) baseline geri yükle.

**KARAR KURALI (her faz):** FP=0 ve E-tuzağı+çürütülen değişmemiş → commit. Aksi halde daralt/ertele.

---

## Sıralama + Bağımlılık

```
FAZ 15 (son-madde bleed, BUG 9)  ◄── ÖNCE, en büyük (~441), en yüksek değer
   │   (kanun-sonu ek gövdeden ayrılır)
FAZ 16 (madde-bleed, BUG 2)      ◄── SONRA, küçük (3 madde HMK), bağımsız
```
Bağımsız fazlar; FAZ 15 önce (büyük etki). FAZ 16 ayrı desen (madde-başı yakalama), çakışmaz.

## Disiplin
TDD, 0-FP, atomik commit, **AI co-author YASAK**, `bugfix/phase-15-corpus-fixes` üstüne. Her faz master
tablo + `docs/faz-planlari/faz-15-*.md` / `faz-16-*.md`. Geçici: `.parser_buglari_gecici.txt` +
`.tmp_analiz/` sonra sil.

## Kapsam DIŞI (bu spec'te değil)
BUG 1 (ertele, yanlış-teşhis), BUG 3/6 (parser-dışı, fetch fazı), BUG 7 (altınset temizliği). Bunlar
gelecek işler; bu spec yalnız 0-FP-kanıtlı parser düzeltmelerini kapsar.
