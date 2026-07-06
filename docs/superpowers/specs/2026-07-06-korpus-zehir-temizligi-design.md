# Korpus Zehir Temizliği — Tasarım (Design Spec)

> Master plan: [../../yapisal-sadakat-master-plan.md](../../yapisal-sadakat-master-plan.md)
> Branch: `bugfix/korpus-zehir-temizligi` (FAZ 16 üstüne) · Tarih: 2026-07-06
> Kaynak: 3-kaynaklı analiz (altınset karşılaştırma + cowork HTML-denetimi + ham-korpus çapraz-doğrulama)

## Bağlam

Altınset (dış gold) karşılaştırması + cowork'ün HTML-vs-JSONL denetimi + ham-korpus çapraz-doğrulama, korpusta
**4 gerçek zehir** ortaya çıkardı. Halüsinasyon-eleme yapıldı: her bulgu ham korpus verisiyle doğrulandı;
kaynaklar çeliştiğinde ham veri hakem oldu (ör. cowork "269 temiz" dedi, ham veri "bleed" dedi → A haklı).

**Genel durum: korpus altınsetten iyi** — kanun coverage %100, madde coverage %97.4, içerik-farkların %19.8'inde
biz haklı (altınset şişkin). Bu spec, kalan 4 gerçek zehri **doğru katmanda** (parser / retrieval / fetch) çözer.

**Değişmez disiplin:** `text` (embedding) bozulmaz, yalnız YAPI/anahtar düzelir; her fix 0-FP (veremezse ERTELE);
5-katmanlı regresyon kapısı; `analiz/` (cowork) dosyalarına DOKUNULMAZ.

---

## Zehir Envanteri (ham-doğrulanmış)

| # | Zehir | Katman | 0-FP? | Boyut | Faz |
|---|---|---|---|---|---|
| 3 | Anchor kör noktası ("X Bakanı yürütür") | Parser | ✅ NET | 6 madde | FAZ 17 |
| 2 | Madde-arası bleed (kolonlu başlık) | Parser | ✅ ölçüldü | 316 madde | FAZ 18a |
| 2 | Madde-arası bleed (kolonsuz/roma/bent) | Parser | ⚠️ riskli | ~250 | FAZ 18b (ayrı ölç) |
| 1 | Tertip-çakışması (kanun_no benzersiz değil) | Retrieval | — | 14 kanun / 891 chunk | FAZ 19 |
| 4 | Gövde-kaybı (213:93) | Fetch | — | ~14-54 | FAZ 20 |

---

## FAZ 17 — Anchor kör noktası (Zehir 3)

### Sorun
FAZ 15 `_KANUN_SONU_ANCHOR` = `(Bakanlar Kurulu|Cumhurbaşkanı) yürütür`. Eski kanunlarda yürütme cümlesi
`<Bakanlık> Bakanı/Bakanları yürütür` biçiminde (ör. "Millî Savunma ve Maliye Bakanları yürütür"). Bu anchor'a
UYMADIĞI için 6 madde hâlâ kanun-sonu ek bleed içeriyor.

### Vakalar (ham-doğrulandı, 6 madde — hepsi tümü-büyük kanun-sonu ek)
- 269:6 ("...Savunma ve Maliye Bakanları yürütür. 269 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN...LİSTE")
- 1473:8, 1264:12, 1053:12, 439:17, 168:7 — hepsi `bleed-ek-var=True` (ham teyit).

### Çözüm (0-FP, dar)
`_KANUN_SONU_ANCHOR` desenine yeni dal: `\w+(\s+ve\s+\w+)?\s+[Bb]akan(ı|ları)\s+yürütür`. Mevcut FAZ 15 guard'ları
AYNEN geçerli: (1) kuyruk tümü-büyük OLMALI (`_buyuk_oran_kunyesiz > 0.85`); (2) küçük-harf kuyruk → KESME;
(3) anchor yoksa dokunma. Yeni dal yalnız anchor eşleşmesini genişletir, kesim mantığı değişmez.

### 0-FP gerekçesi
"X Bakanı yürütür" + ardından tümü-büyük kanun-sonu ek = yalnız kanun-sonu yürütme maddesinde görülür. Meşru
gövde-içi "Bakanı yürütür" + gerçek hüküm devamı korpusta YOK (FAZ 15'teki "yürütür+hüküm" analizi bunu kanıtladı).

### Etki
6 madde temizlenir, 0-FP. FAZ 15'in birebir kardeşi.

---

## FAZ 18a — Madde-arası bleed, kolonlu başlık (Zehir 2, güvenli kısım)

### Sorun
Bir maddenin sonuna, **bir sonraki maddenin başlığı** boşluksuz/kolonlu yapışık giriyor (kanun-sonu değil,
madde-arası): `"...memurluktan çekilebilirler. Müracaat, şikayet ve dava açma:"`. Mevcut `_BLEED_BASLIK`
(chunker.py:59) bunu kırpmaya çalışıyor ama DAR:
- Kelime sınırı `{0,4}` (max 5 kelime) → uzun başlıklar (7201:53 = 8 kelime) kaçıyor.
- Virgül kapsanmıyor → `Müracaat, şikayet...` (657:20) kaçıyor.

### Çözüm (0-FP ölçüldü)
`_BLEED_BASLIK` desenini genişlet:
- Karakter sınıfına virgül ekle: `[\wçğıöşüâî,]`
- Kelime sınırını `{0,4}` → `{0,9}` (max 10 kelime)
- **Liste-başı guard ekle:** yutulan başlık öncesi metin liste-başı sözcüğüyle bitiyorsa (`şunlar|aşağıdaki|
  belirtilen|sayılanlar|hususlar|kimseler|olanlar|halinde`) KIRPMA — çünkü `...şunlardır: a) b)` gerçek liste-başı.

**Mevcut `if not son_madde` koşulu KORUNUR** (son maddede yutacak başlık yok).

### Ölçülen sonuç (ham korpus, 31420 madde)
| | Yakalanan |
|---|---|
| Mevcut `_BLEED_BASLIK` | 419 |
| Genişletilmiş | 736 |
| **EK yakalanan** | **317** (316 gerçek-bleed + 1 FP-şüphe: 633:37) |

Liste-başı guard 633:37'yi eler → **316 madde, 0-FP.**

### Etki
316 madde: sonraki maddenin başlığı gövde-kuyruğundan kırpılır. `text` (embedding) temizlenir.

---

## FAZ 18b — Madde-arası bleed, kolonsuz/roma/bent (Zehir 2, riskli kısım — ayrı ölç)

### Sorun (farklı imzalar, daha riskli)
- **Kolonsuz başlık:** `2559:4` → `"...kullanılamaz. Durdurma ve kimlik sorma"` (`:` YOK). Kolon olmadan
  meşru cümle-sonundan ayırmak çok zor → 0-FP riskli.
- **Roma-madde:** `926:100` → `"...uygulanır. II - Esir astsubaylar:"` (roma rakamlı alt-başlık).
- **Bent-harf:** `6102:1073` → `"...zorundadır. bb) Defter tutma..."` (bent harfi).

### Karar: ÖNCE ÖLÇ, 0-FP verirse uygula, VEREMEZSE ERTELE
FAZ 18a bittikten sonra her imza için ayrı FP-ölçümü + (gerekirse) agent-kalibrasyon. Roma ve bent-harf imzaları
dar olabilir (0-FP mümkün); kolonsuz başlık büyük olasılıkla ERTELE (HTML-tabanlı çözüm gerekir). Bu faz
**koşullu** — ölçüm sonucu master plan "0-FP veremezse ertele" kuralına göre karar.

---

## FAZ 19 — Tertip-çakışması (Zehir 1, RETRIEVAL katmanı)

### Sorun
Türkiye'de kanun numaraları tertip'e göre tekrar kullanılmış. 14 `kanun_no` altında 2 farklı kanun var
(657 = Devlet Memurları + Harita GM; 3201 = Emniyet Teşkilat + Yurt Dışı Sosyal Güvenlik). 891 chunk, 156
duplicate madde-no.

### Kritik: içerik GÜVENDE, kod bunu zaten biliyor
`corpus.py:121` yorumu: *"kanun_no globalde benzersiz DEĞİL (6551 iki kanun)"*. Chunk `id` alanı `mevzuat_id`
tabanlı → benzersiz (104484 vs 103124). İçerik EZİLMİYOR, iki kanun ayrı chunk'larda. **Bu bir parser bug'ı DEĞİL.**

### Sorun yalnız retrieval-filtrede
`metadata.kanun_no` ile filtreleme ("657 sayılı kanunun 5. maddesi") iki farklı kanunu karıştırır.

### Çözüm (retrieval katmanı — korpus değişmez)
Retrieval kodunda kanun-bazlı filtre/arama `kanun_no` yerine `mevzuat_id` (benzersiz) kullanmalı. Tasarım
retrieval kodu incelendikten sonra netleşir (retrieval modülü henüz bu spec'te haritalanmadı — plan aşamasında
retrieval'daki kanun_no kullanımları taranıp mevzuat_id'ye taşınır). Korpus üretimi (chunker/enrich) DEĞİŞMEZ.

### Etki
14 kanun_no'da retrieval doğruluğu düzelir. Korpus içeriği değişmez → regresyon yüzeyi retrieval testleriyle sınırlı.

---

## FAZ 20 — Gövde-kaybı 213:93 (Zehir 4, FETCH katmanı)

### Sorun
VUK madde 93 "Tebliğ esasları" kaynakta tam var, komşu 92/94 korpusta var, **93 korpusta YOK**. Metin hiç
çekilmemiş → chunker regex'iyle kurtarılamaz.

### Çözüm (fetch/madde-ağacı — önce teşhis)
1. **Teşhis:** 213'ü `fetch.py` / `get_mevzuat_madde_tree` ile yeniden çek; 93'ün neden atlandığını bul (madde
   ağacı node'u eksik mi, parse mi atlıyor, tek madde mi sistematik mi).
2. **Kapsam ölç:** Bu tek 213:93 mü, yoksa benzer atlama başka kanunlarda da var mı (altınset-eksik 406'nın
   gerçek-eksik alt kümesi ~14-54 madde tahmini). Sistematik ise kök-neden fix, değilse hedefli yeniden-çekme.
3. **Fix:** Kök nedene göre. Bu faz **teşhis-önce** — kör fix yok.

### Etki
Belirsiz (teşhise bağlı). En az 213:93; muhtemelen birkaç düzine madde kurtarılır.

---

## Ortak: Regresyon Stratejisi (5-katmanlı kapı — her parser fazı)

Master plan FAZ 1-16 disiplini. **"Çalışan şeyleri bozma" merkezî hedef.**

1. **TDD RED→GREEN** — her faz gerçek bug id'leriyle hedef test + FP-koruma testi.
2. **Mevcut 230 testin TAMAMI yeşil** — hiçbiri kırılmaz. FAZ 18a özellikle: mevcut `_BLEED_BASLIK` testleri
   (`test_body_does_not_swallow_next_article_title`, `test_real_body_ending_with_colon_kept_when_last`) yeşil kalmalı.
3. **916-kanun baseline diff** (`compare_corpus.py`): etkilenen-madde beklenen kümede mi (FAZ 17: 6 madde;
   FAZ 18a: ~316 madde). Status-flip 0. Fıkra/bent dağılımı: bleed-kırpma yapıyı bozmamalı (yalnız text-kuyruk kısalır).
   **E-tuzağı** (TMK/TBK/TTK/FSEK/Anayasa): yapı (fıkra/bent) DEĞİŞMEZ — text-kuyruk kısalması meşru (bleed çöpü).
4. **Confusion matrix** — FAZ 18a FP-riskli: 316 yeni kırpımın her biri TP (gerçek sonraki-başlık) mi FP (meşru
   içerik) mi (adversarial agent, kaynak-doğrulamalı). FP=0 → commit; FP>0 → guard daralt veya ERTELE.
5. **Spot-check** — hedef id'ler + rastgele 5 değişmemiş-olması-gereken madde.

> ⚠️ Retrieval (FAZ 19) ve fetch (FAZ 20) parser dışı → farklı regresyon: retrieval testleri / fetch doğrulama.

**KARAR KURALI (her parser fazı):** FP=0 ve E-tuzağı+değişmemiş → commit. Aksi halde daralt/ertele.

---

## Sıralama + Bağımlılık

```
FAZ 17 (anchor, 6 madde)         ◄── ÖNCE (en kolay, FAZ 15 kardeşi)
FAZ 18a (kolonlu bleed, 316)     ◄── SONRA (0-FP ölçüldü, en büyük parser etkisi)
FAZ 18b (kolonsuz/roma/bent)     ◄── KOŞULLU (ölç → 0-FP ise uygula, değilse ertele)
FAZ 19 (tertip, retrieval)       ◄── retrieval katmanı (korpus değişmez)
FAZ 20 (213:93, fetch)           ◄── teşhis-önce (fetch katmanı)
```
Parser fazları (17, 18a, 18b) bağımsız desenler, çakışmaz. 19-20 ayrı katman.

## Disiplin
TDD, 0-FP, atomik commit, **AI co-author YASAK**, `bugfix/korpus-zehir-temizligi` üstüne. `analiz/` (cowork)
dosyalarına DOKUNULMAZ (yalnız okundu). Kritik review'lar Opus 4.8.

## Kapsam DIŞI
BUG 1/3/7 (önceki fazlarda ertelendi), FAZ 15.1 (~97 Title-Case, HTML-tablo işi), tablo-format (BUG 8).
