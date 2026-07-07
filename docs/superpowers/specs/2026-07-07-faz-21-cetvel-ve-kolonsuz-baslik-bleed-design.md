# FAZ 21 — CETVEL/LİSTE Sızması + Kolonsuz Komşu-Başlık Bleed — Tasarım

> Durum: onaylandı · Kaynak: `docs/olcum-sonuclari/madde-gen-karsilastirma-raporu.md` (madde_gen kıyas hakemliği)
> İlke: **A yaklaşımı — mevcut fonksiyonları genişlet, çalışanı bozma, 0-FP.**
> Master: [../../yapisal-sadakat-master-plan.md](../../yapisal-sadakat-master-plan.md)

## Amaç

madde_gen (altınset) kıyas-hakemliğinde kaynak-doğrulanan iki gerçek bleed ailesini 0-FP ile temizlemek:
1. **CETVEL/LİSTE sızması** (~35 madde): "Yürütme" maddesine kanun-sonu ekli tablo/cetvel/liste yapışmış. En çarpıcı: **488 m33 (Damga Vergisi) = 33.368 kar çöp**.
2. **Kolonsuz komşu-başlık sızması** (~57 üst-sınır): madde sonuna sonraki maddenin kolonsuz başlığı yapışmış (`"...uygulanır. Yürürlükten kaldırılan hükümler"`). FAZ 18'de ertelenmişti.

**Kapsam DIŞI:** madde ekleme/silme, yürürlük değişimi, fetch/parse değişikliği. Bu fix'ler yalnız var olan chunk'ların **kuyruğunu kırpar** — içerik ekleme/kayıp YOK.

## Üretim mimarisi (kaynak-doğrulandı — build_corpus.py:42-48)

```
normalize_text(content)
  → split_articles(text)          # chunker.py: madde-bölme + _strip_kanun_sonu_ek + _BLEED_BASLIK/_BLEED_ROMA guard
  → enrich(arts, tree, mid, ...)   # enrich.py: _strip_bleed (tree-marker + _KAPANIS_BASLIK_RE + sarkan-numara)
  → maddeler_to_chunks(...)        # corpus.py: korpus.jsonl
```

İki katman da üretimde sırayla bleed kırpar. **KRİTİK:** `split_articles(text)` yalnız `text` alır (kanun_no GÖRMEZ); `enrich(arts, tree, mid, ...)` **mid (mevzuat_id) görür** → E-tuzağı ayrımı gereken fix ENRICH katmanına konur.

## Kök-neden analizi (ölçümle doğrulanmış)

### CETVEL neden kaçıyor (chunker katmanı)
`_strip_kanun_sonu_ek` (chunker.py:163) yürütme-anchor'ı sonrası kuyruğu, büyük-harf oranı **>0.85 (tümü-büyük)** ise kesiyor. 488 m33 kuyruğu `"(1) SAYILI TABLO Damga Vergisine Tâbi Kâğıtlar..."` → Title-Case tablo başlıkları yüzünden oran **0.28**, guard "meşru küçük-harf kuyruk" sanıp KESMİYOR. (Canlı test: `_strip_kanun_sonu_ek` 488-benzeri gövdeyi kesmedi, doğrulandı.)

### Neden "tablo görünce direkt kes" YANLIŞ (0-FP kritik)
`SAYILI TABLO/CETVEL/LİSTE` imzası korpusta **1249 kez** geçiyor; yalnız **35'i yürütme-sonrası** (kanun-sonu ek), **1214'ü madde-içi meşru atıf** (`"...4760 sayılı ÖTV Kanununa ekli (III) sayılı liste"`). İmza tek başına kesim çıpası olamaz → **yürütme-anchor'ı ZORUNLU**.

### Kolonsuz başlık neden kaçıyor (enrich katmanı)
`enrich._KAPANIS_BASLIK` (enrich.py:82) SABİT bir sözlük — "Yürürlükten kaldırılan hükümler", "Uygulanmayacak hükümler" ZATEN kesiliyor. Ama **birleşik varyantlar** yakalanmıyor: `"Değiştirilen ve yürürlükten kaldırılan hükümler"`, `"...ilişkin geçiş hükümleri"`, `"Diğer geçiş hükümleri"` sözlükte yok → kesilmeden kalıyor. E-tuzağı zaten yorumlarda tartışılmış (79-81: belirsiz başlıklar EKLENMEDİ).

## Değişiklikler (A yaklaşımı)

### Fix 1 — CETVEL dalı (chunker.py `_strip_kanun_sonu_ek` içinde)

Yeni regex (modül düzeyinde):
```python
# Yürütme-anchor sonrası kuyruk kanun-sonu ekli TABLO/CETVEL/LİSTE imzasıyla BAŞLIYORSA
# (Title-Case tablo başlıkları büyük-harf oranını düşürüp mevcut >0.85 guard'ı kaçırıyor).
_SAYILI_EK_BASI = re.compile(
    r"(?i)^\(?\s*[IVXLC0-9]+\s*\)?\s*SAYILI\s+(?:TABLO|CETVEL|LİSTE|LISTE)"
)
```

`_strip_kanun_sonu_ek` akışına (mevcut büyük-harf dalından ÖNCE) dal eklenir:
```python
a = _KANUN_SONU_ANCHOR.search(body)
if not a:
    return body
kuyruk = body[a.end():].lstrip(". \n")
if len(kuyruk) < 30:
    return body
if _SAYILI_EK_BASI.match(kuyruk):          # YENİ DAL: tablo-imzasıyla başlıyorsa
    return body[:a.end()].strip()          # tümü-büyük şartına bakmadan kes
buyuk_oran = _buyuk_oran_kunyesiz(kuyruk)  # MEVCUT DAL (değişmez)
if buyuk_oran is None or buyuk_oran <= 0.85:
    return body
return body[:a.end()].strip()
```

**0-FP kapıları:** (1) yürütme-anchor ZORUNLU → 1214 madde-içi atıf dokunulmaz; (2) imza kuyruğun BAŞINDA (`.match`) → cümle-ortası tablo tetiklemez; (3) mevcut büyük-harf dalı bit-bit korunur → FAZ 15/17'nin 432 kesimi değişmez.

**Etki:** ~35 madde (488 m33 dahil).

### Fix 2 — Kolonsuz komşu-başlık: `enrich._KAPANIS_BASLIK` genişletme + E-tuzağı guard

**A. Sözlüğe birleşik varyantlar eklenir** (`_KAPANIS_BASLIK`, enrich.py:82). Her eklenen başlık, korpus-genelinde "neredeyse-asla-meşru-cümle-sonu-değil" adversaryal doğrulamadan geçmeli (mevcut C1/Z3 disiplini):
```python
# FAZ 21 eklenenler (ham-doğrulandı, hepsi sonraki-madde başlığı):
"Değiştirilen ve yürürlükten kaldırılan hükümler",
"Yürürlükten kaldırılan ve değiştirilen hükümler",
"Kaldırılan hükümler", "Kaldırılan ve uygulanmayacak hükümler",
"Diğer geçiş hükümleri", "Diğer hükümler", "Diğer kanun hükümleri",
"Saklı hükümler", "Uygulanmayacak ve yürürlükten kaldırılan hükümler",
"Diğer kanunlara eklenen hükümler", "Diğer kanunların değiştirilen hükümleri",
```
"...ilişkin geçiş hükümleri" gibi ÖNEK-DEĞİŞKEN kalıplar sözlükle yakalanamaz → ayrı DAR regex (aşağıda).

**B. Önek-değişken "…ilişkin/…ile ilgili geçiş hükümleri" DAR deseni** (yeni, `_KAPANIS_BASLIK_RE`'ye kardeş):
```python
# Sonraki maddenin '<özne> ilişkin geçiş hükümleri' / '<özne> ile ilgili hükümler' başlığı gövde
# SONUNA yapışmış. DAR: cümle-sonu + kısa özne (nokta/virgül/kolon YOK) + 'geçiş hükümleri'/'ilgili
# hükümler' + gövde SONU. Gerçek veri: 6362 Geç4, 5510 Geç19.
_KAPANIS_ILISKIN_RE = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][^.,;:]{3,80}?"
    r"(?:ilişkin\s+geçiş\s+hükümleri|ile\s+ilgili\s+hükümler(?:i)?|kapsamındaki\s+.*?hükümler)\s*$"
)
```

**C. E-tuzağı guard'ı** (`_strip_bleed` içinde). enrich `kanun_no` görür → 5 korunan kanunda kolonsuz-başlık kesimi (yeni sözlük + DAR desen) UYGULANMAZ:
```python
_ETUZAK = {"4721", "6098", "6102", "5846", "2709"}  # madde-içi kenar-başlık kullanır
# _strip_bleed imzasına kanun_no eklenir; E-tuzağı ise yeni FAZ 21 kesimleri atlanır.
# MEVCUT _KAPANIS_BASLIK_RE / tree-marker / sarkan-numara davranışı DEĞİŞMEZ (geriye uyumlu).
```

Not: `_strip_bleed` şu an `(body, level_markers, madde_markers)` alıyor. `kanun_no` parametresi eklenir (enrich çağrısında zaten mevcut) — VEYA yeni FAZ 21 kesimleri `enrich` gövdesinde kanun_no kontrolüyle koşullu uygulanır. Plan aşamasında en az-invaziv yol (imza vs koşullu-çağrı) seçilir; mevcut çağrının davranışı korunur.

**0-FP kapıları (5 katman):** (1) E-tuzağı hariç (10 vaka doğrulandı, hepsi meşru kenar-başlık); (2) gövde-sonu `$` şartı (mevcut _KAPANIS_BASLIK_RE ile aynı) → cümle-ortası kesilmez; (3) başlık içinde noktalama yok `[^.,;:]`; (4) sabit sözlük VEYA dar önek-değişken kalıp; (5) her yeni başlık/kesim confusion-matrix + ham-doğrulama.

**Etki:** ~57 üst-sınır; ham-doğrulama sonrası netleşir (5510 Geç19, 6362 Geç4 dahil).

## Test + Regresyon (5 katman — FAZ 15-20 disiplini)

1. **TDD birim testleri:**
   - CETVEL (`tests/test_chunker.py`): 488-benzeri, 5809 m69, 5564 m9 kesiliyor; FP-koruma: madde-içi "ekli (III) sayılı liste" (7440 m2 / 7326 m1) KESİLMİYOR; yürütmesiz tablo dokunulmuyor; mevcut tümü-büyük dalı korunuyor.
   - Kolonsuz başlık (`tests/test_enrich.py`): 5510 Geç19 / 6362 Geç4 / 7036 m9 kesiliyor; FP-koruma: E-tuzağı (2709 m27, 6102 m607) DOKUNULMUYOR; "...usul ve esaslar belirlenir." meşru cümle-sonu kesilmiyor.
2. **Confusion matrix:** fix-öncesi/sonrası korpus diff → her yeni kesim tek tek incelenir, şüpheli ham-doğrulanır. Hedef 0-FP.
3. **916-kanun regresyon:** text-değişen ≈ beklenen (CETVEL ~35 + başlık ~57 üst-sınır); **status-flip=0, madde sayısı ±0, fıkra/bent/mülga dağılımı değişmez, beklenmedik text-değişen=0.**
4. **E-tuzağı kapısı:** 5 korunan kanunda fıkra/bent dağılımı bit-bit aynı (kolonsuz-başlık fix bu kanunları hiç işlemez → beklenen değişim 0).
5. **Tam suite:** mevcut 247 + yeni testler yeşil.

**Kırmızı çizgi:** herhangi bir katmanda beklenmedik 1 FP → o alt-kalıp/başlık daraltılır veya çıkarılır. 0-FP'den taviz YOK. Bir madde bile yanlış kesilmektense o vaka çözülmeden bırakılır.

## Uygulama sırası (ayrı commit'ler)

1. **CETVEL** (chunker, güvenli — anchor zaten var) → tam regresyon → yeşilse commit.
2. **Kolonsuz başlık** (enrich, riskli — ertelenmişti) → tam regresyon + ham-doğrulama → yeşilse commit.

Biri sorun çıkarırsa diğeri etkilenmez.

## Ertelenen (bu faz DIŞI)

- Kapsam gri-alanı: 2954 Geç1-3, 2559 Geç1, 2983 Geç3, 1567 Geç2 (~10-15 madde) — kaynak-belirsiz (bedesten vs mevzuat.gov.tr konsolidasyon farkı), fetch-incelemesi gerektirir. FAZ 20 (213:93) ailesi.
- CETVEL ailesinde yürütme-anchor'ı OLMAYAN olası cetvel-sızmaları (bu fazda anchor zorunlu).
- "…ilişkin geçiş hükümleri" dışındaki tümüyle serbest-önekli başlık varyantları (0-FP riski yüksek olanlar) — ham-doğrulamada FP çıkarsa ertelenir.
