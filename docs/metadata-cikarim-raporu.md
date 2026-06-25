# Metadata Çıkarım Algoritması — Madde / Fıkra / Bent Nasıl Ayrıştırılıyor?

> **Amaç:** Bu rapor, ham mevzuat metnini RAG'a uygun yapısal `{id, text, metadata}` chunk'lara
> dönüştüren pipeline'ın **nasıl karar verdiğini** açıklar. Gerçek bir madde (KVKK 6698 — Madde 11)
> üzerinden, her aşamanın gerçek çıktısıyla gösterilir.
>
> **Kapsam notu:** Bu pipeline retrieval'ın **ilk yarısıdır** (temiz korpus üretimi). Embedding +
> vektör index + arama sonraki fazdır.

---

## 1. En Kritik Soru: Hangi Sinyalleri Kullanıyoruz? (font? kalınlık? boşluk?)

Bu sık sorulan ve **yanlış varsayılan** bir noktadır. Net cevap:

| Sinyal | Kullanıyor muyuz? | Neden |
|---|---|---|
| **Font kalınlığı (bold)** | ❌ HAYIR | Kaynaktan silinir (aşağıda kanıt) |
| **Font boyutu (pt)** | ❌ HAYIR | Silinir |
| **Girinti / boşluk** | ❌ HAYIR | Kaynak metin tutarsız (cümle ortası satır kırıkları var) |
| **Resmî işaret konvansiyonu** | ✅ EVET | Türk mevzuatının standart kuralı |
| **Pozisyon (cümle/satır sonu)** | ✅ EVET | İşaretin atıf mı yapısal mı olduğunu ayırt eder |
| **Bedesten ağacı (otorite)** | ✅ EVET | Hiyerarşi (kitap/kısım/bölüm) için resmî kaynak |

### Neden font/kalınlık kullanmıyoruz? — Kanıt

Ham HTML'de görsel bilgi **vardır**:
```html
line-height:124%;color:black'>MADDE 11-</span></b><span style='font-size:12.0pt;...'>(1) Herkes...
```
`<b>` (bold), `font-size:12.0pt` görünüyor. Ama pipeline'ın ilk adımı (`strip_html`) **bütün görsel
formatlamayı atar** ve düz metin bırakır:
```
İlgili kişinin hakları
MADDE 11- (1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili;
a) Kişisel veri işlenip işlenmediğini öğrenme,
```

**Neden bilinçli olarak atıyoruz?** Üç sebep:
1. **Tutarsızlık:** Mevzuat HTML'leri farklı dönemlerde farklı araçlarla üretilmiş — bold/font
   belgeden belgeye değişir, güvenilir sinyal değil.
2. **Dayanıksızlık:** Görsel formata bağlı bir parser, kaynak formatı değişince kırılır.
3. **Gereksizlik:** Türk mevzuatının **resmî yapısal konvansiyonu** zaten metinde kodlanmış —
   görsele ihtiyaç yok.

### Kullandığımız asıl sinyal: Resmî İşaret Konvansiyonu

Türk mevzuat yazım kuralları her yapısal seviyeyi **belirli bir işaretle** kodlar:

| Seviye | İşaret | Örnek |
|---|---|---|
| **Madde** | `MADDE N-` veya `Madde N -` | `MADDE 11-` |
| **Fıkra** | `(1)` `(2)` `(3)` | `(1) Herkes, veri sorumlusuna...` |
| **Bent** | `a)` `b)` `c)` (harf) veya `1.` `2.` (numara) | `a) Kişisel veri işlenip...` |
| **Alt-bent** | `1)` `2)` (parantez-rakam) | `1) birinci alt bent` |

Parser bu işaretleri **pozisyona duyarlı** şekilde tespit eder (sadece "var mı" değil, "doğru yerde mi").

---

## 2. Pipeline — 6 Aşama (gerçek KVKK M11 çıktılarıyla)

Ham HTML → temiz `{id, text, metadata}` chunk dönüşümü:

```
HTML ──▶ strip_html ──▶ normalize ──▶ split_articles ──▶ parse_tree ──▶ enrich ──▶ corpus
 (0)        (1)            (2)            (3)               (4)          (5)        (6)
```

### Aşama 1 — `strip_html`: HTML → düz metin
Görsel formatlamayı (bold/font/renk) atar. Base64-kodlu HTML çözülür, etiketler temizlenir.
```
Çıktı:  ...MADDE 11- (1) Herkes, veri sorumlusuna\nbaşvurarak kendisiyle ilgili;\na) Kişisel...
```

### Aşama 2 — `normalize_text`: metin temizleme
**Sorun:** Mevzuat metni "kirli" — cümle ortasında satır kırıkları var (`Madde\n11`, `sorumlusuna\nbaşvurarak`),
tire türleri karışık (`-` vs `–` vs `—`).
**Çözüm:** Satır kırıklarını birleştirir, tüm tire/çizgi varyantlarını tek tipe çevirir.
```
Çıktı:  ...MADDE 11- (1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili; a) Kişisel...
```

### Aşama 3 — `split_articles`: madde sınırı tespiti
`MADDE N-` / `Madde N -` desenini (büyük/küçük harf, tire varyantı toleranslı) tespit edip metni
**madde sınırlarından** böler. Bir sonraki `MADDE` işaretine kadar olan metin o maddenin gövdesidir.
```
Çıktı:  no="11"
        body="(1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili; a) Kişisel veri işlenip..."
```
> **Atomik birim = madde.** Sabit-boy (her 500 token) chunking YAPILMAZ — bir hukuki soruya cevap
> "Madde 11'in tamamı" olmalı, "ortasından rastgele 500 karakter" değil.

### Aşama 4 — `parse_tree`: hiyerarşi otoritesi (bedesten ağacı)
Madde **metni** sadece madde numarasını ve gövdeyi verir; **hiyerarşi** (hangi bölümün altında,
başlığı ne) için ayrı bir resmî kaynak kullanırız: bedesten API'sinin **madde ağacı**. Bu ağaç,
mevzuatın resmî içindekiler yapısıdır. Metinden tahmin etmek yerine **otoriteden** alırız.
```
Çıktı:  baslik          = "İlgili kişinin hakları"
        bolum_no        = "ÜÇÜNCÜ BÖLÜM"
        bolum_baslik    = "Haklar ve Yükümlülükler"
        hiyerarsi_yolu  = "ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler › Madde 11"
        maddeId         = "1643063"
```
> **Neden ağaç + metin birlikte?** Madde başlığı (`İlgili kişinin hakları`) metinde maddeden ÖNCEKİ
> satırda durur ve görsel olarak ayırt edilir — ama biz görsele güvenmiyoruz. Ağaç bunu kesin verir.

### Aşama 5 — `enrich`: fıkra/bent ağacı + yürürlük + birleştirme
İşin kalbi. Madde gövdesini resmî işaret konvansiyonuyla **iç içe ağaca** böler:

**Fıkra tespiti** (`parse_fikralar`): `(1)` işareti fıkra başıdır — AMA sadece **cümle sonu (`.` `:` `!`
`?`) veya satır sonundan sonra** geliyorsa. Cümle ortasındaki `(1)` bir **atıftır**, fıkra değil
(örn. "eki (1), (2) sayılı cetveller"). Bu pozisyon kontrolü yanlış-pozitifi önler.

**Bent tespiti** (`_bentler`): fıkra içinde `a) b) c)` (harf) veya `1. 2. 3.` (numara). Harf-stili
öncelikli. Sıralı koşu şartı (`a,b,c` ardışık) yıl/madde atıflarını eler.

**Yürürlük** (`extract_status`): `(Mülga:...)` / `(İptal:...)` künyeleri yürürlük durumunu belirler.
Madde yürürlüğü **fıkra ağacından** hesaplanır: tüm numaralı fıkralar mülga ise madde mülga, en az
biri yürürlükte ise madde yürürlükte.
```
Çıktı:  madde_baslik  = "İlgili kişinin hakları"
        yurutluk      = "yürürlükte"
        fıkralar      = 1 fıkra
          └─ fıkra (1): 9 bent
             bent işaretleri: a) b) c) ç) d) e) f) g) ğ)
             bent[0]: "a) Kişisel veri işlenip işlenmediğini öğrenme,"
```

### Aşama 6 — `corpus`: RAG chunk üretimi
Zenginleştirilmiş maddeyi son `{id, text, metadata}` JSONL satırına çevirir:
- **`text`** = başlık + temiz gövde → embedding'e gidecek (anlamsal arama bunun üzerinde)
- **`metadata`** = hiyerarşi + yürürlük + fıkra/bent ağacı + değişiklik künyeleri (filtreleme/atıf için)
- Boş/içeriksiz/saf-artefakt maddeler filtrelenir; tablolar text'ten çıkarılıp metadata'da tutulur

---

## 3. Gerçek Örnek — KVKK 6698, Madde 11 (uçtan uca)

### Girdi (ham, strip sonrası düz metin):
```
İlgili kişinin hakları
MADDE 11- (1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili;
a) Kişisel veri işlenip işlenmediğini öğrenme,
b) Kişisel verileri işlenmişse buna ilişkin bilgi talep etme,
c) Kişisel verilerin işlenme amacını ve bunların amacına uygun kullanılıp kullanılmadığını öğrenme,
ç) Yurt içinde veya yurt dışında kişisel verilerin aktarıldığı üçüncü kişileri bilme,
d) Kişisel verilerin eksik veya yanlış işlenmiş olması hâlinde bunların düzeltilmesini isteme,
e) 7 nci maddede öngörülen şartlar çerçevesinde kişisel verilerin silinmesini/yok edilmesini isteme,
f) (d) ve (e) bentleri uyarınca yapılan işlemlerin üçüncü kişilere bildirilmesini isteme,
g) İşlenen verilerin münhasıran otomatik sistemlerle analizi suretiyle aleyhe sonuca itiraz etme,
ğ) Kanuna aykırı işleme sebebiyle zarara uğraması hâlinde zararın giderilmesini talep etme,
haklarına sahiptir.
```

### Çıktı (üretilen korpus chunk'ı — `id: 104383-11`):
```json
{
  "id": "104383-11",
  "text": "İlgili kişinin hakları\n(1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili; a) Kişisel veri işlenip işlenmediğini öğrenme, b) ... haklarına sahiptir.",
  "metadata": {
    "kanun_no": "6698",
    "kanun_ad": "KİŞİSEL VERİLERİN KORUNMASI KANUNU",
    "madde_no": "11",
    "madde_baslik": "İlgili kişinin hakları",
    "madde_tipi": "asil",
    "yurutluk": "yürürlükte",
    "maddeId": "1643063",
    "kitap_no": null, "kitap_baslik": null,
    "kisim_no": null, "kisim_baslik": null,
    "bolum_no": "ÜÇÜNCÜ BÖLÜM",
    "bolum_baslik": "Haklar ve Yükümlülükler",
    "ayirim_no": null, "ayirim_baslik": null,
    "hiyerarsi_yolu": "ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler › Madde 11",
    "fikralar": [
      {
        "no": "(1)",
        "yurutluk": "yürürlükte",
        "bentler": [
          { "isaret": "a)", "text": "a) Kişisel veri işlenip işlenmediğini öğrenme,", "yurutluk": "yürürlükte", "alt_bentler": [] },
          { "isaret": "b)", "text": "b) Kişisel verileri işlenmişse buna ilişkin bilgi talep etme,", "yurutluk": "yürürlükte", "alt_bentler": [] },
          { "isaret": "c)", "...": "..." },
          { "isaret": "ç)", "...": "..." },
          { "isaret": "d)", "...": "..." },
          { "isaret": "e)", "...": "..." },
          { "isaret": "f)", "...": "..." },
          { "isaret": "g)", "...": "..." },
          { "isaret": "ğ)", "text": "ğ) ...zararın giderilmesini talep etme,", "yurutluk": "yürürlükte", "alt_bentler": [] }
        ]
      }
    ],
    "degisiklik_gecmisi": [],
    "dipnotlar": [],
    "tablolar": []
  }
}
```

### Neden `kitap_no`, `kisim_no`, `ayirim_no` boş (null)?
KVKK görece **düz yapılı** bir kanundur — sadece **bölüm** seviyesine kadar hiyerarşisi vardır
(`ÜÇÜNCÜ BÖLÜM`). KİTAP / KISIM / AYIRIM seviyeleri bu kanunda **yoktur**, o yüzden `null`. Bu bir
eksiklik değil, kaynağın gerçek yapısının doğru yansımasıdır.

Daha derin yapılı bir kanunda bu alanlar dolar. Örnek — **Medeni Kanun 4721, Madde 118** (tüm 4
hiyerarşi seviyesi dolu):
```
kitap_no  = "İKİNCİ KİTAP"
kisim_no  = "BİRİNCİ KISIM"
bolum_no  = "BİRİNCİ BÖLÜM"
ayirim_no = "BİRİNCİ AYIRIM"
hiyerarsi_yolu = "İKİNCİ KİTAP › BİRİNCİ KISIM › BİRİNCİ BÖLÜM › BİRİNCİ AYIRIM › Madde 118"
```
> Yani metadata şeması **sabittir** (her chunk aynı alanları taşır), ama her alan kanunun gerçek
> yapısı kadar dolar. Bu, filtreleme tutarlılığı için önemlidir (alan her zaman vardır, değeri
> bazen null).

### Bu örnek ne gösteriyor?
- **Madde → fıkra → bent** üç seviye doğru ayrıştırıldı: 1 fıkra `(1)`, içinde 9 bent (`a` → `ğ`,
  Türkçe alfabe sırasıyla)
- **Hiyerarşi** metinden değil **ağaçtan** alındı: `ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler`
- **`text`** (embedding girdisi) ile **`metadata`** (filtreleme/atıf) ayrı: arama text üzerinde,
  "yürürlükte mi", "6698 Madde 11" gibi sorgular metadata üzerinde
- **Yürürlük** her seviyede ayrı: madde, fıkra ve her bent kendi durumunu taşır

---

## 4. Zor Durumları Nasıl Çözüyoruz? (sağlamlık örnekleri)

Gerçek mevzuatta her madde M11 kadar temiz değil. Pipeline şu zorlukları çözer:

| Zorluk | Örnek | Nasıl çözülür |
|---|---|---|
| **Atıf vs fıkra** | "eki (1), (2) sayılı cetveller" | Cümle-ortası `(n)` fıkra sayılmaz (pozisyon kontrolü) |
| **Künye-lider fıkra** | `(Değişik:...) (1) ... (2) ...` | Lider künye fıkra bölmeyi çökertmez (preamble olarak ayrılır) |
| **Mülga fıkra** | KVKK M6: `(2) (Mülga:...)` | Fıkra mülga işaretlenir ama madde yürürlükte kalır |
| **AYM iptali** | `(İptal fıkra: Anayasa Mahkemesi...)` | Yürürlük tespitinde iptal sinyali sayılır |
| **Değişiklik geçmişi** | `(Değişik: 2/3/2024-7499/33 md.)` | Yapısal `degisiklik_gecmisi` kaydına çıkarılır |
| **Tablo/ek cetvel** | "I SAYILI LİSTE..." | text'ten çıkarılır, `tablolar` metadata'sında tutulur |
| **Geçici/Ek madde** | `Geçici Madde 1` | Ayrı tip (`madde_tipi`), benzersiz id, doğru hiyerarşi |

Her biri TDD ile (önce başarısız test, sonra düzeltme) ve **0 yanlış-pozitif** disipliniyle yazıldı —
yani bir düzeltme başka maddeleri bozmuyor, 916 kanunda gerçek-veri regresyonuyla doğrulandı.

---

## 5. Metadatanın Doğru Olduğunu Nasıl Biliyoruz? (Doğrulama)

Parser doğru çalışıyor demek yetmez — **kanıtlamak** gerekir. Dört bağımsız katman kullandık:

**1. Bedesten ground-truth karşılaştırması.** Bedesten API'sinin resmî madde ağacı bağımsız bir
referanstır. Pipeline'ın bulduğu maddeleri bu ağaca karşı saydık: **~%95 madde uyumu** (fark =
ağacın atladığı Ek/Geçici maddeler — biz onları metinden ek olarak yakalıyoruz, yani ağaçtan
*fazla* doğru). Madde başlığı, maddeId, hiyerarşi bu ağaçtan doğrulanır.

**2. Bağımsız gold-set denetimi.** Elimizdeki bağımsız bir mevzuat atıf listesi (6.055 kanun-madde-
fıkra-bent adresi, vergi/mali hukuk ağırlıklı) ile korpusu karşılaştırdık: gold-set'in işaret ettiği
maddelerin **%80'i dolu içerikle** korpusta, kalanı ya mülga (içerik gerçekten yok) ya kapsam-dışı.
Bu, dışarıdan bir gözün "şu maddeler önemli" dediği listeyi bizim kapsadığımızı gösterdi.

**3. Adversarial (çürütücü) denetim.** Beş bağımsız denetçi korpusu/kodu **kırmaya** çalıştı (kusur
aramak için, övgü için değil). Bulunan her yüksek-ciddiyet kusur, ayrı bir skeptik tarafından
*çürütülmeye* çalışıldı (yanlış-alarmları elemek için). Sonuç: bulunan gerçek kusurlar düzeltildi,
yanlış-alarmlar elendi. Örnek: bir denetçi "parser bent'i yanlış etiketliyor" dedi; başka denetçi
çürüttü (Türkçede bent harfle gösterilir, parser doğruydu).

**4. TDD + 0 yanlış-pozitif disiplini.** Her parser kuralı **önce başarısız test** yazılarak, sonra
düzeltilerek eklendi (170 birim test). Kritik olarak: her düzeltme sonrası **916 kanunluk gerçek
korpusta regresyon** çalıştırıldı — bir düzeltmenin başka maddeleri bozmadığı (yanlış-pozitif
üretmediği) doğrulandı. Örneğin "(İptal fıkra:) mülga sinyali" eklenince, ilk 200 kanunda 80
iptal-fıkra maddesinden sadece 16'sı mülga oldu (içeriksiz olanlar), 64'ü yürürlükte kaldı (içerikli
olanlar) — yani kural konum-duyarlı, körü körüne uygulanmıyor.

> **Özet:** Metadata doğruluğu tek bir yönteme değil, **dört bağımsız doğrulama katmanına** dayanır:
> resmî ağaç (otorite), bağımsız gold-set (dış göz), adversarial denetim (kırma denemesi), TDD +
> gerçek-veri regresyonu (her değişiklikte).

---

## 6. Korpus Kalitesi (916 kanun)

| Metrik | Değer |
|---|---|
| Toplam chunk (madde) | 31.416 |
| Benzersiz kanun | 902 |
| ID çakışması | 0 |
| Boş-text | 0 |
| Yürürlükte / Mülga | 27.951 / 3.465 (mülga işaretli, ayrılabilir) |
| Bedesten ground-truth ile uyum | ~%95 (fark = ağacın atladığı Ek/Geçici maddeler) |
| Birim test | 170 passed |

---

## 7. Özet — Algoritma Ne Üzerine Kurulu?

> **Görsel değil, yapısal.** Font/kalınlık/boşluk değil — Türk mevzuatının **resmî işaret
> konvansiyonu** (`MADDE N-`, `(1)`, `a)`) + **pozisyon duyarlılığı** (atıf mı yapısal mı) +
> **bedesten ağacı otoritesi** (hiyerarşi için resmî kaynak) üzerine kurulu.
>
> Bu yaklaşım dayanıklıdır: kaynak HTML formatı değişse de işaret konvansiyonu değişmez; ve
> hiyerarşiyi tahmin etmek yerine resmî ağaçtan alır.
