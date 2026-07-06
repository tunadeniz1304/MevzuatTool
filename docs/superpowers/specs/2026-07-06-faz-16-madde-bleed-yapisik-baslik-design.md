# FAZ 16 — Madde-bleed / yapışık başlık (BUG 2) — Tasarım (Design Spec)

> Master plan: [../../yapisal-sadakat-master-plan.md](../../yapisal-sadakat-master-plan.md)
> Önceki spec (FAZ 15-16 birlikte): [2026-07-06-faz-15-16-kanun-sonu-bleed-madde-bleed-design.md](2026-07-06-faz-15-16-kanun-sonu-bleed-madde-bleed-design.md)
> Branch: `bugfix/phase-16-madde-bleed` (main'den, FAZ 15 dahil) · Tarih: 2026-07-06
> Parser: `src/mevzuat_tool/chunker.py`

## Bağlam

FAZ 15 (son-madde kanun-sonu bleed, BUG 9) bitti ve main'e merge edildi (PR #21, ~424 kesim, 0 FP).
Fizibilite tablosu (bkz. önceki spec + `.parser_buglari_gecici.txt`) 9 aday bug'dan **yalnız 2'sinin**
gerçek parser-bug'ı VE 0-FP çözülebilir olduğunu ölçtü: **BUG 9 (FAZ 15, bitti)** ve **BUG 2 (bu faz)**.

Bu spec FAZ 16'yı (BUG 2, madde-bleed) tek başına, uygulanabilir ayrıntıyla ele alır. FAZ 1-15 disiplini
korunur: `text` (embedding) bozulmaz, yalnız YAPI düzelir; 0-FP; 5-katmanlı regresyon kapısı.

---

## Sorun

Kaynak metinde bir maddenin başlığı bir öncekinin gövde-sonuna **boşluksuz yapışık** gelebiliyor:
`"...şartlarıMADDE 132- (1) Karşı dava..."`. Parser'ın madde deseni (`_MADDE`, chunker.py:31-34)
`MADDE`'den önce `\b` sözcük-sınırı bekliyor. Ama Türkçe küçük harf (`ı`, `i`, `r`, `n`) + `M` **ikisi de
word-char** → aralarında `\b` OLUŞMAZ → başlık yakalanmaz → madde chunk'ı sonraki maddeye kadar akar.
Sonuç: gömülü madde önceki maddenin gövdesine yutulur; korpusa **ayrı chunk olarak hiç girmez**.

### Doğrulanmış vakalar (kaynak veri: `data/corpus/korpus.jsonl`)

Adversarial tarama (`<sözcük-karakteri>MADDE <no>- (<rakam>)` deseni, 916 kanun) korpus-genelinde **tam 4
eşleşme** buldu — **hepsi gerçek bug, 0 meşru/atıf**:

| Korpustaki chunk | Yapışık dizgi | Yutulan madde |
|---|---|---|
| 6100:131 (len=980) | `...şartlarıMADDE 132- (1) Karşı dava...` | 132 |
| 6100:131 (aynı chunk) | `...süresiMADDE 133- (1) Karşı dava...` | 133 |
| 6100:134 (len=285) | `...hükümlerMADDE 135- (1) Bu Kanunun...` | 135 |
| 6100:164 (len=1096) | `...sorunMADDE 165- (1) Bir davada...` | 165 |

Hepsi HMK (6100). 132/133/135/165 korpusta **ayrı chunk olarak YOK** (yutulmuş).

---

## Çözüm — Yapışık-Madde Post-Tespiti (Yaklaşım B)

**Karar:** Ana `_MADDE` deseni **DEĞİŞMEZ**. Bunun yerine `split_articles`'ta madde bölündükten sonra, her
`body` içinde yapışık gömülü madde ara → varsa böl → yeni Article(ler) ekle. Mevcut bleed-kırpma zincirinin
(`_SEVIYE_BASLIK_BLEED` → `_strip_kanun_sonu_ek` → `_BLEED_BASLIK`) **kardeşi** — aynı "gövde-üzerinde
post-işlem, ana desene dokunma" mimarisi.

**Neden B (regex-gevşetme A DEĞİL):** `_MADDE.finditer` madde-bölmenin kalbi; her maddenin yakalanması bu
desene bağlı. `\b`'yi gevşetmek 916 kanunda geniş regresyon yüzeyi açar. Post-tespit yalnız yeni bir
fonksiyon ekler → ana desen + mevcut 224 test dokunulmaz kalır. 0-FP kanıtı B için doğrudan (desen 4/4 gerçek).

### Desen

```python
_YAPISIK_MADDE = re.compile(
    r"(?<=[\wçğıöşüâîÇĞİÖŞÜ])"                        # ÖNÜNDE sözcük-karakteri (asıl bug: \b yok)
    r"MADDE\s+(\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?)-\s*(?=\()"  # MADDE <no>- ( → fıkra imzası
)
```

- **Lookbehind `(?<=[\w…])`**: YALNIZ sözcük-karakterine yapışıksa yakala. Boşluk/newline öncesi (yani `\b`'nin
  normalde çalıştığı yer) → mevcut `_MADDE` zaten yakalamış, tekrar bölmeye gerek yok → çift-bölme önlenir.
- **`MADDE` tam-büyük + `-` tire + `(` lookahead**: Dar imza. Atıflar (`132 nci maddesi`, `MADDE 5'e göre`)
  bu biçimde değil → 0-FP.

### Bölme algoritması

Her `body` için `_YAPISIK_MADDE.finditer` ile TÜM yapışık maddeleri bul (131 → 132 VE 133, iki tane). Sonra
`body`'yi sırayla parçala. Her yapışık-MADDE için başlık sınırı = `MADDE`'den geriye **en yakın cümle-sonu**
(`[.!?]`):

```
"...ileri sürülemez. Karşı dava açılabilmesinin şartlarıMADDE 132- (1)..."
 └─ 131 gövde sonu ──┘└──────── 132 başlığı ─────────┘└─ 132 gövde
```

- **131 gövdesi** = son cümle-sonuna kadar (`...ileri sürülemez.`)
- **132 başlığı** = o cümle-sonundan `MADDE`'ye kadar (`Karşı dava açılabilmesinin şartları`)
- **132 gövdesi** = `MADDE 132-` sonrası
- Yeni Article: `no` = gömülü no (grup 1), `body` = `<başlık>\n<gövde>` (mevcut chunk formatı `başlık\ngövde`).

Bu, mevcut `_BLEED_BASLIK` (chunker.py:59) ile **birebir aynı sezgi**: "cümle-sonu (`[.!?]`) = başlık sınırı".

### Edge-case & güvenlik kapıları (0-FP için)

- **Cümle-sonu bulunamazsa** (`MADDE`'den geriye `[.!?]` yok): başlığı önceki gövdeden ayıramayız → o vakada
  **bölme YAPMA** (0-FP korunur, vaka ertelenir). Ölçüm: 4 vakanın 4'ünde de `. ` sınırı var → hiçbiri
  ertelenmez.
- **Çift-bölme yok:** lookbehind sözcük-karakteri şartı, `_MADDE`'nin zaten yakaladığı boşluk-önlü maddeleri
  eler → aynı madde iki kez üretilmez.
- **Recursion yok:** `finditer` bir gövdedeki tüm gömülü maddeleri tek geçişte bulur.
- **`no` çarpışması yok:** gömülü no (132) ≠ konteyner no (131); atıf değil gerçek başlık.

---

## Regresyon Stratejisi (5-katmanlı kapı)

Master plan FAZ 1-15 disiplininin aynısı. **"Eskiden çalışan yerleri bozmama" merkezî hedef.**

1. **TDD RED→GREEN** — hedef testleri:
   - `6100:131` → 131, 132, 133 **ayrı** Article; 132 başlık=`Karşı dava açılabilmesinin şartları`, 133 başlık
     doğru.
   - `6100:134` → 134, 135 ayrı.
   - `6100:164` → 164, 165 ayrı.
   - FP-koruma: boşluklu normal `MADDE 5- (1)` **çift-bölünmez**; gövde-içi atıf `MADDE 5'e göre` /
     `132 nci maddesi` madde SAYILMAZ; cümle-sonu-yok senaryosunda bölme yapılmaz.
2. **Mevcut 224 testin TAMAMI yeşil** — özellikle E-tuzağı (TMK/TBK/TTK/FSEK/Anayasa yapı değişmez),
   `_BLEED_BASLIK`/`_SEVIYE_BASLIK_BLEED`/`_strip_kanun_sonu_ek` (FAZ 15). Bir tek kırılırsa fix yanlış.
3. **916-kanun baseline diff** (`compare_corpus.py --gate`):
   - Baseline al → build → compare. Etkilenen-madde beklenen kümede mi: **yalnız 6100**, 3 konteyner madde
     (131,134,164) + 4 yeni doğan madde (132,133,135,165). Başka kanun/madde değişmemeli.
   - Status-flip 0 (bölme yürürlüğü değiştirmez).
   - Fıkra/bent dağılımı: 132/133/135/165 ayrılınca fıkra-sayısı değişir (beklenen, yalnız 6100'de).
   - **E-tuzağı 5-kanun** (TMK/TBK/TTK/FSEK/Anayasa) **bent/fıkra YAPISI DEĞİŞMEZ** (sert kapı). 6100 bu
     listede değil → 6100 dışı hiçbir yapı değişmemeli.
4. **Confusion matrix** — yeni her bölme TP mi (gerçek gömülü madde) / FP mi (yanlış bölme)? Ölçüm: desen 4/4
     gerçek. FP=0 → commit; FP>0 → daralt veya ERTELE.
5. **Spot-check** — hedef id'ler (6100:132 çıktı mı, başlığı doğru mu, gövdesi 133'e sızmıyor mu) + rastgele 5
     değişmemiş-olması-gereken madde elle kontrol.

> ⚠️ Smoke build korpusu ezer → baseline al → build → compare → (kötüyse) baseline geri yükle.

**KARAR KURALI:** FP=0 ve E-tuzağı+6100-dışı değişmemiş → commit. Aksi halde daralt/ertele.

---

## Etki

6100 (HMK): 3 chunk → 7 chunk (131→131+132+133, 134→134+135, 164→164+165). 4 komşu madde (132,133,135,165)
retrieval'a kazandırılır. 0-FP. Küçük ama net; her vaka 1-2 komşu maddeyi kurtarır.

## Disiplin

TDD, 0-FP, atomik commit, **AI co-author YASAK**, `bugfix/phase-16-madde-bleed` üstüne (sonunda PR). Kritik
review'lar (final + fix) **Opus 4.8**. Build tek süreçte (segfault kuralı).

## Kapsam DIŞI (bu spec'te değil)

BUG 1 (ertele, yanlış-teşhis: `1. 2. 3.` = bent, doğru), BUG 3 (başlık None, parser-dışı/API), BUG 6 (gövde
kaybı, parser-dışı/fetch), BUG 7 (hizalama, altınset artefaktı), BUG 8 (tablo format, düşük öncelik), FAZ
15.1 (~97 Title-Case kanun-sonu, HTML-tablo işi). Bunlar gelecek işler.
