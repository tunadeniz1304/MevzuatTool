# FAZ 21 — CETVEL + Kolonsuz-Başlık Bleed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** madde_gen kıyasında kaynak-doğrulanan iki bleed ailesini (yürütme+cetvel sızması, kolonsuz komşu-başlık sızması) 0-FP ile temizlemek.

**Architecture:** İki bağımsız fix, iki katmanda. (1) CETVEL → `chunker.py` `_strip_kanun_sonu_ek` içine yürütme-anchor sonrası tablo-imzalı kuyruk dalı. (2) Kolonsuz-başlık → `enrich.py`'ye **AYRI bir FAZ 21 kesim bloğu**: `_FAZ21_KAPANIS_RE` (dar sabit-sözlük varyantları) + `_KAPANIS_ILISKIN_RE` (önek-değişken) — her ikisi de **gövde-sonu (`$`) anchor'lı, `esik` şartına TABİ DEĞİL**, `_strip_bleed`'e `kanun_no` parametresiyle E-tuzağı guard'lı. Mevcut C1/`_KAPANIS_BASLIK_RE`/`esik` davranışı bit-bit korunur; FAZ 21 kesimi ayrı yoldan çalışır.

**KRİTİK KEŞİF (ölçümle doğrulandı):** Mevcut C1 kesimi `esik` (gövdenin son %15'i) şartına bağlı. Gerçek bleed vakalarının ÇOĞU (7330 m9, 7036 m9, 6491 m26, 6428 m10 — kısa maddeler) başlık kuyruğu son %15'ten ÖNCE başladığı için `esik` şartını GEÇEMEZ → sözlüğe eklemek TEK BAŞINA yetmez. Bu yüzden FAZ 21 kesimi `esik`-siz, `$`-anchor'lı ayrı bloktur. `$`-anchor + dar-kalıp + E-tuzağı guard yeterli 0-FP sağlar: korpus taramasında `esik`-siz + `$`-anchor 39 kesim üretti, E-tuzağı guard'ı olmadan 4 FP (6098 m47, 2709 m35/m48/m92 = kendi kenar-başlıkları); guard bu 4'ü tam eler → 0 FP.

**Tech Stack:** Python 3.11+, pytest, re (regex). Windows: `PYTHONIOENCODING=utf-8`, `.venv/Scripts/python.exe`.

## Global Constraints

- **0-FP mutlak:** hiçbir madde-içi meşru içerik kesilmemeli. Herhangi bir regresyon katmanında beklenmedik 1 FP → o kalıp/başlık daraltılır veya çıkarılır. Bir madde bile yanlış kesilmektense o vaka çözülmeden bırakılır.
- **CETVEL fix'inde yürütme-anchor ZORUNLU:** `SAYILI TABLO/CETVEL/LİSTE` imzası korpusta 1249 kez geçer, yalnız 35'i yürütme-sonrası ek; 1214'ü madde-içi meşru atıf. Anchor olmadan kesim = 1214 FP.
- **E-tuzağı (4721, 6098, 6102, 5846, 2709) kolonsuz-başlık fix'inden HARİÇ:** bu 5 kanun madde-içi kenar-başlık kullanır ("X ile ilgili hükümler" bleed değil, maddenin kendi başlığı).
- **Mevcut davranış korunur:** `_strip_kanun_sonu_ek` tümü-büyük dalı, `_KAPANIS_BASLIK_RE`, tree-marker, sarkan-numara — hiçbiri değişmez, yalnız EKLENİR.
- **Ayrı commit'ler:** CETVEL (Task 1-2) ve kolonsuz-başlık (Task 3-5) ayrı commit; biri diğerini etkilemez.
- **Commit disiplini:** AI co-author/"Generated with" satırı YASAK. `type(scope): özet` formatı. Branch: `faz-21/cetvel-kolonsuz-baslik-bleed` (zaten açık).
- **Test komutu:** `cd <repo> && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest <path> -v` (repo kökünde `pytest.ini` var, `src` layout).

---

## Dosya Yapısı

| Dosya | Sorumluluk | Değişim |
|---|---|---|
| `src/mevzuat_tool/chunker.py` | madde-bölme + kanun-sonu ek kırpma | `_SAYILI_EK_BASI` regex ekle (modül düzeyi) + `_strip_kanun_sonu_ek`'e dal |
| `src/mevzuat_tool/enrich.py` | tree-marker + kapanış-başlık bleed | `_KAPANIS_BASLIK` genişlet + `_KAPANIS_ILISKIN_RE` ekle + `_strip_bleed(...,kanun_no)` E-tuzağı guard + çağrı güncelle |
| `tests/test_chunker.py` | chunker birim testleri | CETVEL kesim + FP-koruma testleri |
| `tests/test_enrich.py` | enrich birim testleri | kolonsuz-başlık kesim + E-tuzağı + FP-koruma testleri |

---

## Task 1: CETVEL kesim — kırmızı test + regex + dal

**Files:**
- Modify: `src/mevzuat_tool/chunker.py` (modül düzeyine `_SAYILI_EK_BASI`; `_strip_kanun_sonu_ek` gövdesi ~163-176)
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: mevcut `_KANUN_SONU_ANCHOR`, `_buyuk_oran_kunyesiz`, `_strip_kanun_sonu_ek(body: str) -> str`.
- Produces: `_strip_kanun_sonu_ek` davranışı — yürütme-anchor sonrası kuyruk `SAYILI TABLO/CETVEL/LİSTE` ile başlıyorsa anchor'a kadar keser (imza değişmez, hâlâ `(body: str) -> str`).

- [ ] **Step 1: Kırmızı test yaz** (`tests/test_chunker.py` sonuna ekle)

```python
from mevzuat_tool.chunker import _strip_kanun_sonu_ek


def test_cetvel_bleed_yurutme_sonrasi_tablo_kesilir():
    # 488 m33 kalıbı: yürütme maddesi + kanun-sonu (1) SAYILI TABLO (Title-Case, tümü-büyük DEĞİL).
    body = ("Bu kanunu Bakanlar Kurulu yürütür. (1) SAYILI TABLO Damga Vergisine Tâbi "
            "Kâğıtlar I. Akitlerle ilgili kâğıtlar A. Belli parayı ihtiva eden kâğıtlar: "
            "1. Mukavelenameler (Binde 7,5)")
    out = _strip_kanun_sonu_ek(body)
    assert out == "Bu kanunu Bakanlar Kurulu yürütür."
    assert "TABLO" not in out


def test_cetvel_bleed_liste_ve_cetvel_varyanti_kesilir():
    for kelime in ("LİSTE", "CETVEL"):
        body = (f"Bu Kanunu Cumhurbaşkanı yürütür. (2) SAYILI {kelime} Ekli kadro ve "
                "pozisyonlar listesi burada devam eder ve uzar gider metin metin metin")
        out = _strip_kanun_sonu_ek(body)
        assert out == "Bu Kanunu Cumhurbaşkanı yürütür.", kelime


def test_cetvel_fp_madde_ici_sayili_liste_atifi_kesilmez():
    # Madde-içi meşru atıf: yürütme YOK → dokunulmamalı (1214 vakadan temsilci).
    body = ("Bu maddenin uygulanmasında 4760 sayılı Özel Tüketim Vergisi Kanununa ekli "
            "(III) sayılı liste kapsamındaki mallar dikkate alınır.")
    assert _strip_kanun_sonu_ek(body) == body


def test_cetvel_fp_yurutme_var_ama_tablo_yok_mevcut_dal_korunur():
    # Yürütme var, kuyruk tablo-imzasız küçük-harf düz metin → mevcut >0.85 dalı KESMEZ (davranış korunur).
    body = ("Bu Kanunu Bakanlar Kurulu yürütür. bu ekli metin küçük harfle devam eden "
            "meşru olmayan ama tablo imzası taşımayan bir kuyruktur ve kesilmemelidir")
    assert _strip_kanun_sonu_ek(body) == body
```

- [ ] **Step 2: Testi çalıştır, KIRMIZI doğrula**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_chunker.py::test_cetvel_bleed_yurutme_sonrasi_tablo_kesilir -v`
Expected: FAIL — `assert out == "Bu kanunu Bakanlar Kurulu yürütür."` (mevcut kod kesmez, TABLO kuyrukta kalır).

- [ ] **Step 3: `_SAYILI_EK_BASI` regex'i ekle** (chunker.py, `_KANUN_SONU_ANCHOR` tanımının hemen ardına, ~satır 128 sonrası)

```python
# FAZ 21 — CETVEL/LİSTE sızması: yürütme-anchor sonrası kuyruk kanun-sonu ekli TABLO/CETVEL/LİSTE
# imzasıyla BAŞLIYORSA (Title-Case tablo başlıkları büyük-harf oranını 0.85 eşiğinin altına düşürüp
# mevcut _buyuk_oran_kunyesiz guard'ını kaçırıyor — 488 m33 = 33K çöp). İmza ((1)/(III) SAYILI TABLO..)
# yalnız kuyruğun BAŞINDA (.match) aranır → cümle-ortası tablo atfı tetiklemez. Anchor ZORUNLU
# olduğundan (bu fonksiyona sadece anchor bulununca gelinir) madde-içi meşru '... sayılı liste'
# atıfları (1214 vaka, yürütmesiz) ETKİLENMEZ.
_SAYILI_EK_BASI = re.compile(
    r"(?i)^\(?\s*[IVXLC0-9]+\s*\)?\s*SAYILI\s+(?:TABLO|CETVEL|LİSTE|LISTE)"
)
```

- [ ] **Step 4: `_strip_kanun_sonu_ek`'e dal ekle** (chunker.py ~163-176)

Mevcut gövde:
```python
def _strip_kanun_sonu_ek(body: str) -> str:
    """..."""
    a = _KANUN_SONU_ANCHOR.search(body)
    if not a:
        return body
    kuyruk = body[a.end():].lstrip(". \n")
    if len(kuyruk) < 30:            # kuyruk yok/kısa → temiz madde
        return body
    buyuk_oran = _buyuk_oran_kunyesiz(kuyruk)
    if buyuk_oran is None or buyuk_oran <= 0.85:  # küçük-harf kuyruk (meşru/düz-metin çöp) → KESME
        return body
    return body[:a.end()].strip()   # anchor'a kadar tut, tümü-büyük kuyruğu (künye dahil) at
```

`if len(kuyruk) < 30:` bloğundan SONRA, `buyuk_oran = ...` satırından ÖNCE şu iki satırı ekle:
```python
    if _SAYILI_EK_BASI.match(kuyruk):   # FAZ 21: tablo-imzalı ek → tümü-büyük şartına bakma, kes
        return body[:a.end()].strip()
```

- [ ] **Step 5: Testleri çalıştır, YEŞİL doğrula**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_chunker.py -v -k cetvel`
Expected: 4 test PASS.

- [ ] **Step 6: Tüm chunker testleri regresyon**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_chunker.py -v`
Expected: tüm mevcut + 4 yeni test PASS (regresyon yok).

---

## Task 2: CETVEL — tam-korpus regresyon + commit

**Files:**
- Değişiklik yok; ölçüm + commit. (Regresyon script'i geçici, commit'e dahil edilmez.)

**Interfaces:**
- Consumes: Task 1'in `_strip_kanun_sonu_ek` davranışı, mevcut `data/corpus/korpus.jsonl` (baz).

- [ ] **Step 1: Fix-öncesi korpusu baz al**

Mevcut `data/corpus/korpus.jsonl` fix-ÖNCESİ baz (Task 1 henüz korpusu yeniden üretmedi — chunker değişti ama korpus.jsonl eski). Baz kopyasını scratchpad'e al:
```bash
cp data/corpus/korpus.jsonl "$SCRATCH/korpus_faz21_baz.jsonl"
```
(`$SCRATCH` = oturum scratchpad dizini.)

- [ ] **Step 2: Confusion-matrix ölçümü — CETVEL kesimi neyi etkiliyor?**

Scratchpad'e geçici script yaz (`$SCRATCH/cetvel_confusion.py`), her korpus chunk'ının text'ine `_strip_kanun_sonu_ek`'i uygula, DEĞİŞEN maddeleri listele:
```python
import sys; sys.path.insert(0, "src")
import json
from mevzuat_tool.chunker import _strip_kanun_sonu_ek
degisen = []
for line in open("data/corpus/korpus.jsonl", encoding="utf-8"):
    d = json.loads(line); t = d["text"]
    yeni = _strip_kanun_sonu_ek(t)
    if yeni != t:
        degisen.append((d["metadata"]["kanun_no"], d["metadata"]["madde_no"],
                        len(t), len(yeni), t[len(yeni):len(yeni)+80]))
print(f"CETVEL kesim etkileyen madde: {len(degisen)}")
for kn, mno, el, yl, kuyruk in sorted(degisen, key=lambda x: -(x[2]-x[3]))[:50]:
    print(f"  {kn} m{mno} | {el}->{yl} | kesilen bas: {kuyruk!r}")
```
Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe "$SCRATCH/cetvel_confusion.py"`
Expected: ~35 madde; her kesilen kuyruk `SAYILI TABLO/CETVEL/LİSTE...` ile başlamalı (çöp), 488 m33 listede (~33K→küçük).

- [ ] **Step 3: Her kesimi doğrula — 0 FP**

Step 2 çıktısındaki HER maddenin kesilen kuyruğunu incele. Kesilen kısım gerçekten kanun-sonu ek tablosu mu? Şüpheli (kesilen kısım madde-içi içerik gibi görünen) TEK vaka varsa → DUR, `_SAYILI_EK_BASI`'yi daralt (Task 1'e dön). Hepsi çöpse devam.
Beklenen: kesilen tüm kuyruklar `[IVX0-9] SAYILI TABLO/CETVEL/LİSTE` imzalı ekler → 0 FP.

- [ ] **Step 4: Commit** (yalnız chunker + test; geçici script'ler commit'lenmez)

```bash
git add src/mevzuat_tool/chunker.py tests/test_chunker.py
git commit -m "fix(chunker): FAZ 21 yurutme+cetvel bleed — SAYILI TABLO/CETVEL/LISTE eki kirp

Yurutme-anchor sonrasi kuyruk tablo-imzasiyla basliyorsa tumu-buyuk sartina
bakmadan kes (Title-Case tablo basliklari 0.85 esigini kaciriyordu; 488 m33=33K).
Anchor zorunlu -> 1214 madde-ici 'sayili liste' atifi etkilenmez. ~35 madde, 0-FP."
```

---

## Task 3: Kolonsuz-başlık — `_strip_bleed`'e E-tuzağı guard + kırmızı test

**Files:**
- Modify: `src/mevzuat_tool/enrich.py` (`_strip_bleed` imzası ~107, çağrı ~211, `_ETUZAK` sabiti ekle)
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: mevcut `_strip_bleed(body, level_markers, madde_markers) -> str`, `_KAPANIS_BASLIK_RE`, `enrich(articles, tree, kanun_no, ...)`.
- Produces: `_strip_bleed(body, level_markers, madde_markers, kanun_no=None) -> str` — `kanun_no` E-tuzağı içindeyse FAZ 21 kesimleri (Task 4-5'te eklenecek yeni desenler) atlanır. `kanun_no=None` → geriye uyumlu (mevcut çağrılar/testler bozulmaz).

**NOT:** Task 3 saf yapısal değişiklik (imza genişletme + guard iskeleti). Kırmızı-yeşil döngüsü yerine "regresyon-korundu" (mevcut testler + geriye-uyumluluk testi hep yeşil) kanıtı uygulanır. Davranış değiştiren asıl kesimler Task 4-5'te TDD ile gelir.

- [ ] **Step 1: Geriye-uyumluluk testi yaz** (`tests/test_enrich.py` sonuna)

```python
from mevzuat_tool.enrich import _strip_bleed


def test_strip_bleed_kanun_no_parametresi_geriye_uyumlu():
    # kanun_no verilmezse (default None) mevcut _KAPANIS_BASLIK 'Yürürlük' kesimi aynen çalışmalı.
    body = "Bu madde uygulanır. Yürürlük"
    out = _strip_bleed(body, [], [])
    assert out == "Bu madde uygulanır."
```

- [ ] **Step 2: Testi çalıştır — imza değişmeden önce yeşil olduğunu gör**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py::test_strip_bleed_kanun_no_parametresi_geriye_uyumlu -v`
Expected: PASS (mevcut `_strip_bleed(body, [], [])` çalışır, `Yürürlük` kapanış-başlığı kesilir). Bu testin AMACI: Step 3 imzayı genişlettikten SONRA da yeşil kalmasını garanti etmek (geriye-uyumluluk kanıtı).

- [ ] **Step 3: `_ETUZAK` sabiti + `_strip_bleed` imzası** (enrich.py)

`_KAPANIS_BASLIK` tanımının (satır ~82) hemen ÜSTÜNE ekle:
```python
# FAZ 21 — E-tuzağı: madde-içi kenar-başlık kullanan kanunlar (TMK/TBK/TTK/FSEK/Anayasa). Bunların
# 'X ile ilgili hükümler' başlıkları bleed DEĞİL, maddenin kendi başlığıdır → kolonsuz-başlık
# kesiminden HARİÇ tutulur.
_ETUZAK = {"4721", "6098", "6102", "5846", "2709"}
```

`_strip_bleed` imzasını değiştir (satır 107):
```python
def _strip_bleed(body, level_markers, madde_markers, kanun_no=None):
```
(Gövde şimdilik AYNI kalır; FAZ 21 desenleri Task 4-5'te eklenip `kanun_no not in _ETUZAK` ile korunacak.)

`enrich` içindeki çağrıyı güncelle (satır 211):
```python
        body = _strip_bleed(body_no_apdx, level_mk, madde_mk, kanun_no)
```

- [ ] **Step 4: Testi + tüm enrich testlerini çalıştır**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: yeni test + tüm mevcut testler PASS (imza genişlemesi geriye uyumlu, davranış değişmedi).

---

## Task 4: Kolonsuz-başlık — FAZ 21 dar-sözlük bloğu (`esik`-siz, `$`-anchor)

**Files:**
- Modify: `src/mevzuat_tool/enrich.py` (yeni `_FAZ21_KAPANIS_RE` regex + `_strip_bleed`'e AYRI FAZ 21 bloğu)
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: Task 3'ün `_strip_bleed(..., kanun_no=None)` + `_ETUZAK`.
- Produces: `_strip_bleed` içinde AYRI FAZ 21 kesim bloğu — dar sabit-sözlük başlıkları gövde-sonunda (`$`) ise, `esik` şartına TABİ OLMADAN, E-tuzağı-dışı kanunlarda kesilir.

**MİMARİ NOT:** Mevcut C1 (`_KAPANIS_BASLIK_RE` + `esik`) bloğuna DOKUNULMAZ. FAZ 21 kesimi AYRI bir regex (`_FAZ21_KAPANIS_RE`) + ayrı `if kanun_no not in _ETUZAK:` bloğuyla eklenir. Sebep (ölçümle): gerçek bleed vakalarının çoğu `esik` (son %15) şartını geçemiyor (kısa maddeler); FAZ 21 `$`-gövde-sonu anchor'ıyla `esik`'siz çalışır.

- [ ] **Step 1: Kırmızı testler yaz** (`tests/test_enrich.py`)

```python
def test_kolonsuz_baslik_birlesik_varyant_kesilir():
    # 6491 m26 / 7330 m9 kalıbı: birleşik varyant başlık gövde sonuna yapışık.
    body = ("Bu Kanun hükümleri yayımı tarihinde yürürlüğe girer. "
            "Değiştirilen ve yürürlükten kaldırılan hükümler")
    out = _strip_bleed(body, [], [], kanun_no="6491")
    assert out == "Bu Kanun hükümleri yayımı tarihinde yürürlüğe girer."


def test_kolonsuz_baslik_diger_hukumler_kesilir():
    body = ("Denetim usul ve esasları yönetmelikle belirlenir. Diğer hükümler")
    out = _strip_bleed(body, [], [], kanun_no="5216")
    assert out == "Denetim usul ve esasları yönetmelikle belirlenir."


def test_kolonsuz_baslik_etuzak_haric_kesilmez():
    # 6102 TTK / 6098 TBK: 'Saklı hükümler' maddenin KENDİ kenar-başlığı → E-tuzağı, KESME.
    body = ("Sebepsiz zenginleşmeden doğan haklar saklıdır. Saklı hükümler")
    out = _strip_bleed(body, [], [], kanun_no="6098")
    assert out == body  # E-tuzağı: dokunulmaz


def test_kolonsuz_baslik_mesru_cumle_sonu_kesilmez():
    # 'hükümler' geçmeyen meşru cümle sonu → dokunulmaz.
    body = ("Bu Kanunun uygulanmasına ilişkin usul ve esaslar yönetmelikle düzenlenir.")
    out = _strip_bleed(body, [], [], kanun_no="9999")
    assert out == body
```

- [ ] **Step 2: Testleri çalıştır, KIRMIZI doğrula**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py -v -k "birlesik_varyant or diger_hukumler"`
Expected: FAIL (bu varyant başlıklar `_KAPANIS_BASLIK`'te yok → kesilmiyor).

- [ ] **Step 3: `_FAZ21_KAPANIS_RE` regex ekle** (enrich.py, `_KAPANIS_BASLIK_RE` tanımının ardına ~94)

MEVCUT `_KAPANIS_BASLIK` tuple'ına ve `_KAPANIS_BASLIK_RE`'ye DOKUNMA. Yeni AYRI regex ekle:
```python
# FAZ 21 — kolonsuz komşu-madde başlığı (mevcut C1'in esik-siz kardeşi). Bu başlıklar kısa maddelerde
# gövdenin son %15'inden ÖNCE başlar → C1'in esik şartını geçemez; bu yüzden AYRI, esik-siz, gövde-sonu
# ($) anchor'lı desen. Dar sabit-sözlük (birleşik varyantlar); hepsi ham-doğrulandı = sonraki-madde
# başlığı, meşru-cümle-sonu değil. E-tuzağı guard'ı çağıran tarafta. Gerçek veri: 7330 m9, 6491 m26,
# 6428 m10, 5510 m104. Uzun-önce sırala (alternasyonda kısa varyant uzunu maskelemesin).
_FAZ21_BASLIKLAR = (
    "Değiştirilen ve yürürlükten kaldırılan hükümler",
    "Yürürlükten kaldırılan ve değiştirilen hükümler",
    "Uygulanmayacak ve yürürlükten kaldırılan hükümler",
    "Kaldırılan ve uygulanmayacak hükümler",
    "Kaldırılan ve uygulanmayacak olan hükümler",
    "Diğer kanunların değiştirilen hükümleri",
    "Diğer kanunlara eklenen hükümler",
    "Uygulanmayacak kanun hükümleri",
    "Yürürlükten kaldırılan hükümler",
    "Diğer geçiş hükümleri", "Diğer kanun hükümleri", "Diğer hükümler",
    "Kaldırılan hükümler", "Saklı hükümler", "Uygulanmayacak hükümler",
)
_FAZ21_KAPANIS_RE = re.compile(
    r"(?<=[.!?])\s+(?:"
    + "|".join(re.escape(b) for b in sorted(_FAZ21_BASLIKLAR, key=len, reverse=True))
    + r")\s*$"
)
```

- [ ] **Step 4: `_strip_bleed`'e AYRI FAZ 21 bloğu ekle**

`_strip_bleed` içinde, MEVCUT C1 bloğu (`_KAPANIS_BASLIK_RE` + `esik`, satır ~118-121) ve `body = body[:cut].strip()` satırından SONRA, `_SARKAN_KENAR_NUMARA_RE` bloğundan ÖNCE ekle. (C1 `cut`'a min uygular ve `body` kesilir; FAZ 21 kesilmiş body üzerinde ayrı çalışır — E-tuzağında hiç çalışmaz.)

Mevcut ilgili kısım:
```python
    mk = _KAPANIS_BASLIK_RE.search(body)
    if mk is not None and mk.start() >= esik:
        cut = min(cut, mk.start())
    body = body[:cut].strip()
    # Z4: sarkan kenar-numara/roman kuyruğu ...
    sk = _SARKAN_KENAR_NUMARA_RE.search(body)
    if sk is not None:
        body = body[:sk.start()].strip()
    return body
```
`body = body[:cut].strip()` ile `# Z4:` yorumu ARASINA ekle:
```python
    body = body[:cut].strip()
    # FAZ 21: kolonsuz komşu-madde başlığı (esik-siz, gövde-sonu). E-tuzağı (kenar-başlıklı kanunlar)
    # HARİÇ — 6098 'Saklı hükümler' / 2709 '... ile ilgili hükümler' maddenin KENDİ başlığı, bleed değil.
    if kanun_no not in _ETUZAK:
        f21 = _FAZ21_KAPANIS_RE.search(body)
        if f21 is not None:
            body = body[:f21.start()].strip()
    # Z4: sarkan kenar-numara/roman kuyruğu ...
```

- [ ] **Step 5: Testleri çalıştır, YEŞİL + tüm enrich regresyon**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: 4 yeni test (birlesik_varyant, diger_hukumler, etuzak_haric, mesru_cumle_sonu) + tüm mevcut PASS. Mevcut bir test kırılırsa: FAZ 21 bloğu AYRI olduğu için mevcut C1 davranışı değişmemeli — kırılırsa `_FAZ21_BASLIKLAR` sözlüğünde meşru-cümle-sonu olabilecek bir başlık var demektir, onu çıkar.

---

## Task 5: Kolonsuz-başlık — önek-değişken "…ilişkin geçiş hükümleri" deseni + korpus regresyon + commit

**Files:**
- Modify: `src/mevzuat_tool/enrich.py` (`_KAPANIS_ILISKIN_RE` ekle + `_strip_bleed`'e uygula)
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: Task 3-4'ün `_strip_bleed(..., kanun_no)` + `_ETUZAK` guard.
- Produces: `_strip_bleed` ayrıca önek-değişken kalıbı (`<özne> ilişkin geçiş hükümleri`) keser (E-tuzağı hariç, gövde-sonu, noktalamasız).

- [ ] **Step 1: Kırmızı testler yaz** (`tests/test_enrich.py`)

```python
def test_kolonsuz_baslik_iliskin_gecis_hukumleri_kesilir():
    # 6362 Geç4 kalıbı: '<özne> ilişkin geçiş hükümleri' önek-değişken.
    body = ("Nakit ödeme ve hisse senedi teslim yükümlülükleri karşılanır. "
            "Türkiye Sermaye Piyasaları ile Türkiye Değerleme Uzmanları Birliklerine "
            "ilişkin geçiş hükümleri")
    out = _strip_bleed(body, [], [], kanun_no="6362")
    assert out == "Nakit ödeme ve hisse senedi teslim yükümlülükleri karşılanır."


def test_kolonsuz_baslik_ile_ilgili_hukumler_kesilir():
    # '<özne> ile ilgili hükümler' varyantı (önek serbest).
    body = ("Bu fıkra kapsamındaki işlemler tamamlanır. "
            "İkrazatçılar ile ilgili hükümler")
    out = _strip_bleed(body, [], [], kanun_no="6361")
    assert out == "Bu fıkra kapsamındaki işlemler tamamlanır."


def test_iliskin_desen_etuzak_haric():
    body = ("Bir hüküm cümlesi burada biter. Şuna ilişkin geçiş hükümleri")
    out = _strip_bleed(body, [], [], kanun_no="4721")  # TMK = E-tuzağı
    assert out == body  # kesilmez


def test_iliskin_desen_cumle_ortasinda_kesmez():
    # 'ilişkin geçiş hükümleri' cümle ORTASINDA (gövde sonu değil) → dokunulmaz.
    body = ("Sözleşmeye ilişkin geçiş hükümleri bu maddede ayrıca düzenlenmiştir ve uygulanır.")
    out = _strip_bleed(body, [], [], kanun_no="9999")
    assert out == body
```

- [ ] **Step 2: Testleri çalıştır, KIRMIZI doğrula**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py -v -k "iliskin or ile_ilgili"`
Expected: FAIL (önek-değişken desen henüz yok).

- [ ] **Step 3: `_KAPANIS_ILISKIN_RE` ekle + FAZ 21 bloğuna uygula**

`_FAZ21_KAPANIS_RE` tanımının ardına (enrich.py) ekle:
```python
# FAZ 21 — önek-değişken kapanış-başlığı: '<kısa özne> ilişkin geçiş hükümleri' / '<özne> ile ilgili
# hükümler'. Sabit sözlükle yakalanamaz (önek serbest). DAR: cümle-sonu + BÜYÜK-HARF özne (nokta/
# virgül/kolon YOK, ≤80 kar) + sabit son-ek + gövde SONU ($). Cümle-ortası eşleşmez. Gerçek veri:
# 6362 Geç4 + 15 kesim. E-tuzağı çağıran blokta hariç. NOT: rakamla başlayan başlıklar ('506 sayılı
# Kanunun ... kapsamındaki hükümler', 5510 Geç19) BİLİNÇLİ dışarıda — büyük-harf-başlangıç 0-FP
# kapısıdır; rakam-başlangıca izin madde-içi atıf FP riski açar. 5510 ertelenenlerde.
_KAPANIS_ILISKIN_RE = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][^.,;:]{3,80}?"
    r"(?:ilişkin\s+geçiş\s+hükümleri|ile\s+ilgili\s+hükümler(?:i)?)\s*$"
)
```

`_strip_bleed` içinde, Task 4'te eklenen FAZ 21 bloğunun İÇİNE (aynı `if kanun_no not in _ETUZAK:` altına, `_FAZ21_KAPANIS_RE` kesiminden SONRA) ikinci kesim ekle. Blok son hali:
```python
    if kanun_no not in _ETUZAK:
        f21 = _FAZ21_KAPANIS_RE.search(body)
        if f21 is not None:
            body = body[:f21.start()].strip()
        f21i = _KAPANIS_ILISKIN_RE.search(body)          # FAZ 21 önek-değişken
        if f21i is not None:
            body = body[:f21i.start()].strip()
```
(İki kesim ardışık: önce sabit-sözlük, sonra önek-değişken; her biri kendi kuyruğunu gövde-sonundan kırpar.)

- [ ] **Step 4: Testleri çalıştır, YEŞİL + tüm enrich regresyon**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_enrich.py -v`
Expected: tüm testler (Task 3+4+5 yeni + mevcut) PASS.

- [ ] **Step 5: Tam-korpus confusion + regresyon** (kolonsuz-başlık)

Scratchpad script'i (`$SCRATCH/kolonsuz_confusion.py`) — her korpus chunk'ının text'ine `_strip_bleed(t, [], [], kanun_no)` uygula (kanun_no metadata'dan), DEĞİŞEN maddeleri listele:
```python
import sys; sys.path.insert(0, "src")
import json
from mevzuat_tool.enrich import _strip_bleed
degisen = []
for line in open("data/corpus/korpus.jsonl", encoding="utf-8"):
    d = json.loads(line); t = d["text"]; kn = str(d["metadata"]["kanun_no"])
    yeni = _strip_bleed(t, [], [], kn)
    if yeni != t:
        degisen.append((kn, d["metadata"]["madde_no"], t[len(yeni):][:70]))
print(f"kolonsuz-baslik kesim etkileyen: {len(degisen)}")
etuzak = {"4721","6098","6102","5846","2709"}
etuzak_hit = [x for x in degisen if x[0] in etuzak]
print(f"E-tuzagi kesim (0 OLMALI): {len(etuzak_hit)} {etuzak_hit}")
for kn, mno, kuyruk in degisen[:60]:
    print(f"  {kn} m{mno} | kesilen: {kuyruk!r}")
```
Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe "$SCRATCH/kolonsuz_confusion.py"`
Expected: E-tuzağı kesim = **0**. Kesilen tüm kuyruklar `...hükümler(i)` başlık kuyruğu. ~57 üst-sınır.

**NOT:** Bu script `_strip_bleed`'i marker'sız (`[], []`) çağırır — yani yalnız `_KAPANIS_BASLIK_RE`+`_KAPANIS_ILISKIN_RE` kesimlerini ölçer. Gerçek üretimde tree-marker'lar da devrede; bu ölçüm FAZ 21 kesimlerini İZOLE eder (doğru).

- [ ] **Step 6: Her kesimi doğrula — 0 FP**

Step 5 çıktısındaki HER kesimi incele. Kesilen kuyruk gerçekten sonraki-madde başlığı mı? Şüpheli (kesilen kısım madde-içi meşru "…hükümler" cümlesi) TEK vaka → DUR, o başlığı sözlükten çıkar VEYA `_KAPANIS_ILISKIN_RE`'yi daralt. Ham-doğrulama gerekirse mevzuat-mcp. Hepsi başlık-bleed'se devam.
Beklenen: 0 FP, E-tuzağı 0 kesim.

- [ ] **Step 7: Commit**

```bash
git add src/mevzuat_tool/enrich.py tests/test_enrich.py
git commit -m "fix(enrich): FAZ 21 kolonsuz komsu-baslik bleed — ayri esik-siz blok

Mevcut C1/_KAPANIS_BASLIK/esik davranisi DEGISMEDI. Ayri _FAZ21_KAPANIS_RE
(dar sabit-sozluk varyantlari) + _KAPANIS_ILISKIN_RE (onek-degisken '...iliskin
gecis/ile ilgili hukumler') gövde-sonu ($) anchor'li, esik-siz. _strip_bleed'e
kanun_no + E-tuzagi guard: TMK/TBK/TTK/FSEK/Anayasa kenar-basliklari korunur.
~54 madde, E-tuzagi 0, 0-FP."
```

---

## Task 6: Tam suite + final doğrulama

**Files:** değişiklik yok; doğrulama.

- [ ] **Step 1: Tüm test suite**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest -v`
Expected: mevcut 247 + yeni testler (Task 1: 4, Task 3: 1, Task 4: 4, Task 5: 3 = 12) hepsi PASS.

- [ ] **Step 2: Birleşik regresyon özeti**

CETVEL (~35) + kolonsuz-başlık (~57) toplam text-değişen madde sayısını ve **status-flip / madde-sayısı / E-tuzağı** invaryantlarını raporla (scratchpad özet script). status-flip=0, madde-sayısı ±0, E-tuzağı kesim=0 doğrula.

- [ ] **Step 3: Faz raporu yaz** (`docs/faz-planlari/faz-21-cetvel-kolonsuz-baslik-bleed.md`)

CETVEL + kolonsuz-başlık sonuçları, kesim sayıları, 0-FP kanıtı, ertelenenler. Master plan tablosuna (`docs/yapisal-sadakat-master-plan.md`) FAZ 21 satırı ekle.

- [ ] **Step 4: Commit**

```bash
git add docs/faz-planlari/faz-21-cetvel-kolonsuz-baslik-bleed.md docs/yapisal-sadakat-master-plan.md
git commit -m "docs(faz-21): CETVEL+kolonsuz-baslik bleed faz raporu + master plan satiri"
```

---

## Ertelenenler (bu faz DIŞI — 0-FP riski)

- **5510 Geç19** ve benzeri **rakamla-başlayan** kolonsuz başlıklar (`"506 sayılı Kanunun ... kapsamındaki sandıklar ve ilgili hükümler"`): `_KAPANIS_ILISKIN_RE` bilinçli olarak yalnız BÜYÜK-HARF-başlangıç kabul eder (0-FP kapısı). Rakam-başlangıca izin madde-içi atıf FP riski açar → ertelendi. Korpus taramasında `kapsamındaki` dalı 0 temiz kesim verdiği ölçümle doğrulandı.
- Kapsam gri-alanı (2954/2559/2983/1567 geçici maddeleri): FAZ 20 fetch ailesi, bu faz dışı.

## Notlar (implementer için)

- `data/corpus/korpus.jsonl` git-ignore'lu, ASLA commit'lenmez. Regresyon script'leri scratchpad'de kalır, commit'lenmez.
- `analiz/` klasörüne DOKUNMA (kullanıcının çalışma alanı).
- Tek ağır python süreci kullan (segfault riski). `PYTHONIOENCODING=utf-8` her komutta.
- Korpusu tam yeniden üretmek (build_corpus) bu planda GEREKMİYOR — regresyon, mevcut korpus.jsonl text'lerine fix fonksiyonlarını uygulayarak İZOLE ölçülür. Gerçek yeniden-üretim ayrı/manuel adım (kullanıcı çalıştırır).
- E-tuzağı guard testinde kırılan mevcut test çıkarsa: bu bir SİNYAL — o testin kanun_no'su gerçekten E-tuzağı mı yoksa guard fazla mı geniş, incele.
