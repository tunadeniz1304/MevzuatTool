# FAZ 17-20 — Korpus Zehir Temizliği ✅

> Master: [../yapisal-sadakat-master-plan.md](../yapisal-sadakat-master-plan.md) · Durum: ✅ **Tamam (0-FP, tam regresyon)**
> Tasarım: [../superpowers/specs/2026-07-06-korpus-zehir-temizligi-design.md](../superpowers/specs/2026-07-06-korpus-zehir-temizligi-design.md)
> Plan: [../superpowers/plans/2026-07-06-korpus-zehir-temizligi.md](../superpowers/plans/2026-07-06-korpus-zehir-temizligi.md)
> Branch: `bugfix/korpus-zehir-temizligi` (FAZ 16 üstüne)

## Kaynak: 3-kaynaklı çapraz-doğrulama

Altınset karşılaştırması (kaynak-doğrulamalı agent) + cowork HTML-vs-JSONL denetimi (`analiz/`) + ham-korpus
hakemliği. Halüsinasyon-eleme: kaynaklar çeliştiğinde ham veri hakem (cowork "269 temiz" dedi → ham "bleed",
A haklı). 4 gerçek zehir doğru katmanda çözüldü.

**Coverage sonucu:** kanun %100 (871/871), madde %97.4. Farkların %19.8'inde biz haklı (altınset şişkin,
30/30 kaynak-doğrulandı). Korpus altınsetten iyi durumda.

---

## FAZ 17 — Anchor kör noktası (parser) — commit `78df287`

**Sorun:** FAZ 15 `_KANUN_SONU_ANCHOR = (Bakanlar Kurulu|Cumhurbaşkanı) yürütür`. Eski kanunlarda
`<Bakanlık> Bakanı/Bakanları yürütür` (269:6 "Savunma ve Maliye Bakanları yürütür") kaçıyordu → 6 madde
kanun-sonu ek bleed'li.

**Fix:** Anchor'a yeni dal `\w+(\s+ve\s+\w+)? Bakan(ı|ları) yürütür`. Mevcut tümü-büyük-kuyruk guard'ı aynen.
**6 madde** (269:6, 1473:8, 1264:12, 1053:12, 439:17, 168:7), 0-FP. FAZ 15 kardeşi.

## FAZ 18a — Madde-arası bleed, kolonlu başlık (parser) — commit `7eefffd` + `51b4f42`

**Sorun:** Bir maddenin sonuna sonraki maddenin kolonlu başlığı yapışık (`...çekilebilirler. Müracaat,
şikayet ve dava açma:`). Mevcut `_BLEED_BASLIK` dardı (max 5 kelime, virgülsüz).

**Fix:** `_BLEED_BASLIK` genişletildi (virgül + `{0,9}` kelime) + `_LISTE_BASI` guard (liste-başı cümleleri
`şunlardır:` korunur). Reviewer bulgusu → guard'a 7 kök eklendi (kişiler/şartlar/unsurlar/nedenler/sebepler/
esaslar/haller). Belirsiz vaka 2 (193:46, 2802:36) → 0-FP güvenliği için korundu. **~256 madde**, 0-FP.

## FAZ 18b — Madde-arası bleed, roma başlık (parser) — commit `ad3590b`

**Sorun:** Roma-numaralı sonraki madde başlığı yapışık (`...yapılır. III - Kuruluş:`). Gerçek veri: 1739
(Milli Eğitim Temel K.), FSEK, İİK.

**Fix:** `_BLEED_ROMA_BASLIK` + `_ROMA_IMZA_SAYAC` TEK-ROMA guard (metinde >1 roma = madde-içi liste, KIRPMA
→ FSEK/TTK iç-roma-listeleri dolaylı korunur). **41 madde** kesildi, 0-FP. E-tuzağı (5846:3/63/90/Geçici8)
etkilendi ama fıkra 0 değişti (yapı korundu, text-kuyruk kırpımı meşru).

**Ertelenen (0-FP imkansız/riskli):** kolonsuz başlık (1853, ayrılamaz), bent-harf (10, TTK iç-bent), roma
E-tuzağı (192). HTML-tabanlı gelecek iş.

## FAZ 19 — Tertip-çakışması (retrieval/metadata) — commit `1c3ea40`

**Sorun:** Kanun numaraları tertip'e göre tekrar (14 kanun_no, 2 farklı kanun; 657 = Devlet Memurları +
Harita GM; 3201 = Emniyet + Yurt Dışı). İçerik güvende (chunk id benzersiz) ama `metadata.kanun_no`
retrieval-filtrede karışır.

**Fix:** `corpus.py` metadata'ya `mevzuat_id = m.id.split("-")[0]` (id ilk parçası = mid, benzersiz) açık
alanı eklendi. Mevcut alanlar değişmedi, salt-ekleme, geriye-uyumlu. Retrieval gelecekte kanun_no yerine
mevzuat_id ile filtreleyebilir. Korpus içeriği DEĞİŞMEZ.

## FAZ 20 — Gövde-kaybı 213:93 (corpus filtre) — commit `f96b0fc` (5 iterasyon)

**Sorun (teşhis):** VUK 213:93 "Tebliğ esasları" korpusta yoktu. Kök neden FETCH DEĞİL — `_ISLENMIS_NOTU`
regex'i (redirect-notu eleyici) 93'ün meşru gövdesindeki cümle-içi "vergilendirme ile ilgili olup" ifadesini
yanlışlıkla redirect-notu sanıp maddeyi tamamen eliyordu. Kapsam: sistematik değil, tekil (916 kanun tarandı).

**Fix (5 iterasyon — whack-a-mole → üçlü-istisna):** regex-genişletme yaklaşımı (parantez-zorunlu, sınır)
168/60 FP regresyon üretti. NİHAİ: `_ISLENMIS_NOTU` ORİJİNAL (parantez-opsiyonel) korundu; `_sadece_islenmis_notu`'ya
üçlü-istisna: gövde (1) parantezle başlamıyor + (2) >200 kar + (3) redirect-başlangıcı değil (tarih/`N sayılı`/
`MADDE N` ile başlamaz) → gerçek hüküm KORU. **+2 madde** (213:93 + 7143:Geçici 4), 0 redirect-sızması.

**Ders:** test fixture gerçek uzunluğu yansıtmalı (kısaltılmış 116-kar fixture `>200` şartını yanlış eletti).

---

## Toplam Regresyon Kapısı (5-katman)

- **Test:** 246 passed (230 baz + 16 yeni FAZ 17-20).
- **916-kanun compare** (FAZ 16 sonrası → şimdi): text-değişen **303 madde** (FAZ 17: 6, 18a: ~256, 18b: 41),
  eklenen **+2/-0** (213:93, 7143:Geçici 4). Status-flip **0**. Fıkra/bent/mülga dağılımı DEĞİŞMEDİ (ort 1.48,
  sahte-bent 13, mülga %11). Metadata: +mevzuat_id (tüm chunk, FAZ 19).
- **Confusion matrix** (FAZ 17+18a): 262 kesim, **0 FP** (heuristik 5 "şüphe" ham-doğrulamada hepsi TP:
  5846:33 FSEK m34 başlığı, 2709:60 Anayasa m61 başlığı).
- **E-tuzağı** (TMK/TBK/TTK/FSEK/Anayasa): 6 madde text-değişti AMA fıkra dağılımı DEĞİŞMEDİ (yapı korundu,
  bleed-çöpü kırpımı meşru).

## Etki

- ~303 madde bleed-çöpü (sonraki madde başlığı / kanun-sonu ek) text-kuyruğundan temizlendi.
- 2 gerçek madde (213:93 VUK, 7143:Geçici 4) korpusa kazandırıldı.
- 14 tertip-çakışan kanun için benzersiz `mevzuat_id` metadata → retrieval doğruluğu (gelecek).
- **0-FP, yapı korundu, status-flip 0.** "Çalışan şeyleri bozma" hedefi tutturuldu.

## Ertelenenler (bilinen-sınır, gelecek)

- FAZ 18b kolonsuz başlık (1853), bent-harf (10), roma E-tuzağı (192): 0-FP imkansız/riskli → HTML-tabanlı.
- FAZ 20 "cümle-ortası referans" redirect FN'i: mevcut korpusta 0, teorik gelecek riski.
