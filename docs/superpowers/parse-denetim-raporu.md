# Parse Doğruluğu Denetim Raporu — 10 Rastgele Kanun

**Tarih:** 2026-06-24
**Branch:** `phase-c/data-ingest`
**Yöntem:** 10 kanun (7 esas + 3 değişiklik paketi) için ham HTML ↔ pipeline çıktısı
(madde→fıkra→bent→alt-bent + metadata) yan yana denetlendi. 10 paralel denetçi + her kusur
iddiası adversaryal şüpheci tarafından çürütülmeye çalışıldı + sentez. **Tüm kritik bulgular
ayrıca ham veriye karşı `.venv` python'uyla tek tek teyit edildi (aşağıda "Kanıt" satırları).**

> Bu denetim, madde-seviyesi ölçümden ([916-korpus-raporu.md](916-korpus-raporu.md), recall 0.999)
> **daha derin bir katmanı** açar: madde-altı yapı (fıkra/bent) + yürürlük statüsü doğruluğu.
> İki katman çelişmez — madde keşfi isabetli, ama madde-altı yapı ve statüde sistematik hatalar var.

---

## Genel yargı

Parser madde keşfi ve sınır tespitinde çoğunlukla isabetli, ama **üç sistematik hata sınıfı**
madde-altı yapı ve statü güvenilirliğini zedeliyor. 10 kanundan: 1 temiz, 1 küçük-kusur,
8 ciddi-kusur. Toplam **5 doğrulanmış hata sınıfı** (her biri ham veriyle teyitli).

## Kanun bazlı tablo

| No | Kanun | Durum | Kusur sınıfı |
|---|---|---|---|
| 5637 | Kaldırılan Kanunlar | ✅ temiz | 0 |
| 4743 | Mali Sektör | 🟡 küçük | C1 (kısmi-mülga yayılması) |
| 3402 | Kadastro | 🔴 ciddi | C1 (M3 mülga) + gövde-taşma |
| 5651 | İnternet | 🔴 ciddi | C2 (M9 AYM iptali kaçmış) |
| 5564 | Kimyasal Silahlar | 🔴 ciddi | A (cetvel atıfları fıkra sanılmış) |
| 7326 | Bazı Alacaklar | 🔴 ciddi | A (M5 çapraz-atıf → 29 sahte fıkra) |
| 657 | Harita | 🔴 ciddi | C2 (Ek1/Ek2 mülga kaçmış) |
| 6756 | OHAL Tedbirler | 🔴 ciddi | B (gövde-taşma) + madde-11 kaybı |
| 2629 | Uçuş/Paraşüt | 🔴 ciddi | B (M1/M2 sonraki başlığı yutmuş) |
| 7080 | OHAL Personel | 🔴 ciddi | A ("Ekli (1)" → sahte fıkralar) |

---

## Üç hata sınıfı (hepsi ham veriyle DOĞRULANDI)

### A. Fıkra yanlış-bölme (en yaygın — en az 4 kanun)
Metin-içi `(n)` atıflarını fıkra başlangıcı sanıyor.

- **Kanıt 5564 M3:** Tek hüküm `"(1) Toksik kimyasal maddeler...bu Kanunun eki (1), (2) ve (3)
  sayılı cetvellerde gösterilmiştir."` → pipeline **3 fıkraya** bölmüş: `['(1)','(2)','(3)']`.
  `(2)` ve `(3)` aslında cetvel atfı, fıkra değil.
- **Kanıt 7326 M5:** → **29 "fıkra"** çıkmış: `['(1)','(2)','(1)','(11)','(13)','(2)','(5)',...]`.
  Tekrarlı ve sıra-dışı no'lar (`(11)`,`(13)`) = çapraz-atıflar fıkra sanılmış.

**Önemli nüans:** `7326 M5`'in **ilk `(1)` GERÇEK fıkra** (`(1) Mükellefler, bu fıkrada belirtilen
şartlar...`). Yani çözüm "tüm `(n)`'leri reddet" OLAMAZ — gerçek fıkraları kaçırır (yanlış-negatif).
Çözüm: sıralılık + konum (cümle-sonu sonrası, paragraf başı) kontrolü; "sayılı cetvelde",
"Ekli (n)", "(n) numaralı bendi" bağlamlarını dışla.

### B. Gövde-taşma (en az 2 kanun)
Bir maddenin gövdesi, bir sonraki maddenin **başlığını** yutuyor.

- **Kanıt 2629:** `M1` gövdesi `"...uygulanır. Amaç:"` ile bitiyor — "Amaç:" aslında M2'nin başlığı.
  `M2` gövdesi `"...düzenlenmesidir. Tanımlar:[3]"` ile bitiyor — "Tanımlar:" M3'ün başlığı.
- İçeriği yok etmiyor ama madde sınırını ve başlık ayrımını bozuyor.

### C. Mülga/iptal statü — iki zıt hata

**C1 — aşırı-genişletme:** Kısmi mülga, tüm maddeyi mülga sanıyor.
- **Kanıt 3402 M3:** pipeline statü = `mülga`, ama gövde baştan-mülga DEĞİL. Madde normal
  başlıyor (`"Kadastro ekibi; en az iki kadastro teknisyeni..."`), ortada `(Mülga **son fıkra**:
  11/10/2011-KHK-666/1 md.)` var. Yani sadece son fıkra mülga, madde yürürlükte — ama tüm madde
  mülga işaretlenmiş.

**C2 — kaçırma:** Gerçek mülga/iptal'i göremiyor. `extract_status` yalnız `(mülga` ile
**başlayan** deseni arıyor; parantez-ortası `; Mülga:` ve AYM `İptal:`'i görmüyor.
- **Kanıt (sentetik):** `extract_status("(Ek:...) hüküm; Mülga: ...md.)")` → `'yürürlükte'` (yanlış).
- **Kanıt (sentetik):** `extract_status("(İptal: Anayasa Mahkemesinin...)")` → `'yürürlükte'` (yanlış).
- **Kanıt gerçek 5651 M9:** statü = `yürürlükte`, ama gövdede `(İptal:Anayasa Mahkemesinin
  11/10/2023 tarihli...)` var → AYM iptali kaçmış.

---

## Ayrı kalem: madde-11 kaybı (6756) — DOĞRULANDI

İçeriksiz aralık satırları komşu maddeye sızıyor → bir madde tamamen kayboluyor.
- **Kanıt 6756:** madde no listesi `['1','2',...,'9','10','33','43',...]` → **madde 11 YOK**.
  M10 gövdesi `"...Personel Kanunu ile ilgili olup yerine işlenmiştir.)"` ile bitiyor (sızıntı).
- Kök neden: `MADDE 11-`/`MADDE 12 ila 20` gibi içeriksiz işlenmiş-aralık satırları chunker'ın
  madde sınırını şaşırtıyor. (Not: bu `aralik.py`'nin eval-metrik tespitinden FARKLI bir katman —
  burada chunker'ın gerçek sınır-tespit sorunu.)

---

## Sahte-alarm notu (önemli — kusur DEĞİL)

"Fazladan madde" gibi görünen Ek/Geçici/`X/A` girdileri **kusur değil** — HTML'de gerçek
maddeler; sorun bedesten ağacının onları içermemesi (önceki raporda "sahte-FP" olarak ayrıldı).
Bunları "uydurma madde" sanma. ([916-korpus-raporu.md](916-korpus-raporu.md) Bölüm 5c.)

---

## Öncelikli aksiyonlar (kanıtlı kusurlar) — HEPSİ DÜZELTİLDİ ✅

| Öncelik | Aksiyon | Durum | Commit | Sonuç |
|---|---|---|---|---|
| **P0a** | C2 statü-kaçırma genişlet (`; Mülga:` + AYM `İptal:`) | ✅ DÜZELTİLDİ | `e9cb766` | 5651 M9 + 657 Ek1/Ek2 artık mülga; 300-kanun +62 mülga |
| **P1** | C1 aşırı-mülga sınırla (nitelikli kısmi-mülga) | ✅ DÜZELTİLDİ | `e9cb766` | 3402 M3 artık yürürlükte; -32 yanlış-mülga |
| **P0b** | A fıkra-bölücü konum-duyarlı (cümle-sonu/baş) | ✅ DÜZELTİLDİ | `1a9ad2d` | 5564 M3: 3→1; 7326 M5: 29→13; esas kanun gerçek-fıkra kaybı 0 |
| **P2** | B gövde-taşma (sonraki başlık kuyruk-kırpma) | ✅ DÜZELTİLDİ | `b6e8521` | TAM 916: madde-sayı değişimi 0, gövde kırpılan 2849 madde/122 kanun |
| **P2b** | Gövde-başı içeriksiz-aralık not sızması (6756 M10) | ✅ DÜZELTİLDİ | `c7d4a62` | TAM 916: 333 madde temizlendi, yanlış-pozitif 0 |

**madde-11 (6756) — İKİ AYRI KATMAN:**
- *Madde 11'in ayrı chunk olmaması:* Düzeltme GEREKMEDİ — madde 11 zaten **içeriksiz işlenmiş
  madde** (`MADDE 10- 11- ...yerine işlenmiştir`), `aralik.py` onu içeriksiz-aralık sayıyor
  (`'11' in islenmis_aralik_maddeleri = True`). Eval'de "gerçek kayıp" değil; kendi chunk'ını
  hak etmiyor (yönlendirme notu, gerçek içeriği 211 sayılı kanunda).
- *M10 gövdesine sızma:* DÜZELTİLDİ (`c7d4a62`). M10 gövdesi `'11- (...işlenmiştir.) MADDE 12 ila
  20 - (...) MADDE 21 ila 32 - (...)'` ile kirleniyordu → RAG'da yanlış-chunk + embedding gürültüsü
  (M10 vektörü "Askeri Hakimler/TSK Personel" gibi alakasız terimlerle kirleniyordu). enrich artık
  gövde başına sızmış içeriksiz-aralık notunu kırpıyor. Güvenli kural: gövde RAKAM-tire-paren
  (`11- (`) ile başlar + `işlenmiş/ilgili olup` bağlamı → kırp (gerçek fıkra `(1)` parenle başlar,
  karışmaz). TAM 916: 333 madde temizlendi, **yanlış-pozitif 0** (gerçek içerik kesilmedi).

---

## Statü düzeltmesinde REGRESYON ve nihai çözüm (recheck workflow + kullanıcı yakaladı)

İlk statü düzeltmesi (`e9cb766`) **regresyon üretti**: `_TAM_MULGA` regex'i konum-duyarsızdı →
maddenin İÇERİĞİNDE (bir fıkrada) geçen AYM iptali/Mülga'yı **tüm maddeye yaydı**. Etki: 5651
M3/M5/M6 gibi maddeler (gerçek içerikle başlayıp ortasında fıkra-iptali olan) yanlışlıkla mülga
oldu — TAM 916'da **1525 madde** yanlış mülga. Bu, raporun "seviye-duyarsız statü atama"
teşhisiyle birebir örtüştü.

**Kök neden (kullanıcının ifadesiyle):** "madde contentinde iptal diyor, maddeye iptal demiyor."
Marker maddenin açılış künyesinde mi (→ tüm madde) yoksa bir fıkra içinde mi (→ o fıkra) ayrımı yok.

**Nihai çözüm (`2158ea7`) — fıkra-ağacından statü:** Madde yürürlüğü artık `parse_fikralar`
ağacından hesaplanıyor: numaralı fıkralar varsa **TÜMÜ mülga ise madde mülga**, en az biri
yürürlükte ise madde yürürlükte. Numaralı fıkra yoksa (künye-maddesi) konum-duyarlı metin
tespitine düşer. `extract_status`'a `konum_duyarli` parametresi eklendi (fıkra/bent/alt-bent
alt-birim çağrıları eski "içindeki Mülga o birime aittir" davranışında kaldı).

**6/6 gerçek vaka doğru:** 5651 M3/M5/M6 yürürlükte (kısmi iptal); 5651 M9 (künye-iptal),
7081 M10 (tüm fıkra mülga), 7071 M34 (tek fıkra iptal) → mülga. TAM 916: %9.5 mülga
(yörünge: konumsuz-regex 4567 → konum-duyarlı 3042 → fıkra-ağacı 3107).

**Öğrenme:** İlk "düzeltme tamam" değerlendirmesi dar bir spot-check'e dayanıyordu (sadece
düzelen 3 şeye bakıldı, yeni bozulan aranmadı). Regresyon her zaman bakılmayan yerdedir;
geniş recheck (10 kanun, yeni-bozulan dahil) bunu yakaladı.

---

## İkinci denetim turu (20 kanun) — kalan kusurlar bulundu ve düzeltildi

İlk turdan sonra 20-kanun geniş denetimi (Haiku) + Opus'un ham-veri teyidi, **ilk turun
kaçırdığı** kusurları ortaya çıkardı (önceki "3402 temiz" hükmü dump'ın baş/sonuna bakıp ortasını
taramadığı için eksikti — geniş tarama dar spot-check'ten fazlasını buldu). 4 açık kusur HTML'e
karşı tek tek teyit edilip TDD ile düzeltildi:

| Kusur | Commit | Sonuç | Yöntem-doğrulama |
|---|---|---|---|
| **B3 hayalet chunk** ('İŞLENEMEYEN madde eki') | `0618834` | 6183 Geçici 1: 5→1; 400 hayalet madde düştü (121 kanun) | madde-sayı kontrollü |
| **C 657 statü kaçırma** (tarih/'NNNN sayılı' künye) | `93b18b1` | 657 Ek2/Geçici1/Geçici2 → mülga; 220 madde | yanlış-pozitif 0 |
| **B P1a seviye-başlık bleed** ('X. BÖLÜM/KISIM') | `b54377d` | 2618 madde/307 kanun temizlendi | madde-sayı değişimi 0 |

**Hâlâ açık (bilinen-sınır):**
- **A' 5283 M5 numarasız çok-paragraf:** `(1)` ile başlamayan, düz paragraflı maddeler tek `None`
  fıkra kalıyor (4648 krk tek blok). Fıkra granülaritesi kayıp (içerik kayıp DEĞİL). Henüz açık.
- **Kolon-suz tek başlık bleed** ('Harcırah' gibi): güvenli ayırt-edici sinyal olmadığı için
  (gerçek cümle-sonu ile karışır) kapsanmadı. ~Az sayıda kanun.
- **Seviye-başlık kopuk-dizgi varyantları** (~56 madde): Roma rakamı 'III.', kopuk-harf 'N İKİNCİ'.
  Nadir; düzeltme regex'ini kırılgan büyütmemek için bırakıldı.

## Durum

Tüm iddialar ham veriyle teyit edildi (2026-06-24). **7 hata sınıfı** TDD ile düzeltildi
(C2, C1, A, B + gövde-başı sızma + statü-regresyon + hayalet-chunk + 657-statü + seviye-başlık),
her biri ayrı atomik commit + tam korpus regresyon + yanlış-pozitif kontrolü ile. madde-11
düzeltme gerektirmedi. pytest: 101 → 130 passed. Madde keşfi/sayısı tüm düzeltmelerde korundu
(916 kanunda madde-sayı değişimi 0). Kalan kusurlar düşük-RAG-etkili, bilinen-sınır.
