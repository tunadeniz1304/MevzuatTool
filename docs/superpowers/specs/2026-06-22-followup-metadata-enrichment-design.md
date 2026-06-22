# Tasarım: Faz 3 Follow-up Metadata Zenginleştirme

**Tarih:** 2026-06-22
**Branch:** `phase-3/followup-amendments`
**Kapsam:** Faz 3 — dipnot ayıklama, değişiklik künyeleri, fıkra/bent bölme, bent-seviyesi
yürürlük, benzersiz id (roadmap.md Faz 3 Metadata)
**Önkoşul:** Faz 3 `tree.py` + `enrich.py` (Article + TreeIndex → Madde) main'de mevcut.
**Kaynak:** `docs/superpowers/followups.md` — `kanun193.pdf` (resmî GVK) ↔ pipeline karşılaştırması.

---

## 1. Amaç

Mevcut `enrich()` zengin madde-seviyesi metadata üretiyor (başlık, hiyerarşi, tip, sızma
kırpma). Ancak `kanun193.pdf` analizi 6 boşluk ortaya koydu (followups.md #1, #2, #3, #5,
#6, #7 — **#4 tablolar hariç**, kapsam dışı). Bu tasarım altısını tek bütünsel zenginleştirme
turunda kapatır: gövdeden yapısal veri (dipnot, değişiklik künyesi, fıkra/bent) ayıklanır,
ayrı birinci-sınıf alanlara konur, gövde retrieval için temizlenir, her chunk benzersiz id alır.

### Kapatılan 6 boşluk
1. **#1 Dipnot apendiksi sızması (bug):** İçeriğin sonundaki toplu `[n]` dipnot bloğu son
   maddenin gövdesine düşüyor (GVK Geçici 5 gövdesi 83.418 krk). Ayrıştırılacak.
2. **#2 Dipnot yapısallaştırma + `[n]→madde` bağı:** Dipnotlar `Dipnot` kayıtlarına; gövde
   içi `[n]` işaretleri ilgili dipnota bağlanır.
3. **#3 `(Değişik/Ek/Mülga/İptal: …)` künyeleri → değer:** İnline ham metin yerine yapısal
   `degisiklik_gecmisi` listesi.
4. **#5 Fıkra/bent bölme:** İç içe `fikralar → bentler` ağacı (mevcut `split_fikralar`
   yalnız `(N)` böler; `1.`/`a)` stillerini kaçırır).
5. **#6 Bent-seviyesi yürürlük:** Madde-seviyesi tek bayrak yetersiz; her fıkra/bent kendi
   `yurutluk`'unu alır ("kısmen mülga" tespiti).
6. **#7 Benzersiz id:** Çifte `Geçici 1` ve sonek `123/A` için çakışmasız `id` şeması.

## 2. Kapsam

**Dahil:**
- Yeni saf-fonksiyon parser modülleri: `dipnot.py`, `degisiklik.py`, `fikra.py`, `ids.py`.
- `enrich.py` ince orkestratöre dönüşür; yeni dataclass'lar + genişletilmiş `Madde`.
- `scripts/eval_metadata.py` genişletilir (yeni invariant'lar).
- Yalnız `KANUN` türü (ADR-0013); doğrulama mevcut 4 kanun cache'i (TCK/VUK/KVKK/GVK).

**Hariç:**
- **#4 tablolar** (vergi tarifesi) — zor, ayrı, kapsam dışı.
- Embedding / vektör store / retrieval (Faz 5–6).
- Korpus JSONL serileştirme `{id, text, metadata}` (Faz 4) — `Madde.id` onun girdisidir
  ama serileştirme bu task'ta değil.
- `chunker.py` / `normalize.py` / `tree.py` / `eval_tree.py` **dokunulmaz**.

## 3. Mimari

Yaklaşım: **ayrık parser modülleri + ince enrich orkestratörü**. Her özellik tek-işli saf
fonksiyon modülünde, bağımsız test edilir; `enrich()` onları sırayla çağırır. Projenin
mevcut deseniyle (`normalize`/`chunker`/`tree`/`enrich` — her sorumluluk ayrı modül) birebir
uyumlu.

```
content → normalize → split_articles → [Article(no, body)]  ┐
                                                            ├─► enrich(articles, tree, kanun_no)
tree_<id>.txt → parse_tree() ─► TreeIndex                   ┘        │
                                                                    ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ enrich orkestratör (her madde için):                                    │
   │   1. dipnot.split_dipnot_apendiksi(body)   → apendiks ayrılır (#1)       │
   │   2. tree-join + bleed-strip (mevcut, değişmez)                          │
   │   3. degisiklik.parse_kunyeler(body)       → degisiklik_gecmisi (#3)     │
   │   4. degisiklik.temizle_kunyeler(body)     → body_temiz (#3)             │
   │   5. fikra.parse_fikralar(body)            → fikralar + bent yür. (#5,#6)│
   │   6. chunker.extract_status(body)          → madde yurutluk (mevcut)     │
   │   sonrasında tüm maddeler için:                                          │
   │   7. dipnot.baglanan_dipnotlar(...)        → Madde.dipnotlar (#2)        │
   │   8. ids.assign_ids(maddeler, kanun_no)    → benzersiz id (#7)           │
   └────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
              (list[Madde], list[Dipnot global])
```

**Modül sorumlulukları:**
| Modül | Sorumluluk | Durum |
|---|---|---|
| `normalize.py` | metin temizleme | değişmez |
| `chunker.py` | madde bölme, `extract_status` | değişmez |
| `tree.py` | ağaç → `TreeIndex` | değişmez |
| `dipnot.py` ★ | apendiks ayırma + `[n]→madde` bağ (#1, #2) | yeni |
| `degisiklik.py` ★ | künye parse + gövde temizleme (#3) | yeni |
| `fikra.py` ★ | fıkra/bent ağacı + bent yürürlük (#5, #6) | yeni |
| `ids.py` ★ | benzersiz id atama (#7) | yeni |
| `enrich.py` ★ | orkestratör + dataclass'lar | değişir |

## 4. Veri modeli

```python
@dataclass
class Bent:
    isaret: str             # "a)" | "1." | "8."
    text: str
    yurutluk: str           # "yürürlükte" | "mülga"

@dataclass
class Fikra:
    no: str | None          # "(1)" | None (numarasız eski-stil fıkra)
    text: str
    bentler: list[Bent]     # boş olabilir
    yurutluk: str

@dataclass
class Degisiklik:
    tip: str                # "degisik" | "ek" | "mulga" | "iptal"
    tarih: str | None       # ISO "2003-04-09" (parse edilemezse None)
    kanun_no: str | None    # "4842"
    madde: str | None       # "3"
    kapsam: str | None      # "birinci fıkra" | "ibare" | "cümle" | None
    ham_metin: str          # "(Değişik: 9/4/2003-4842/3 md.)" — HER ZAMAN dolu

@dataclass
class Dipnot:
    no: int                 # 167
    text: str               # dipnot tanımının tam metni

@dataclass
class Madde:
    # --- mevcut alanlar (DEĞİŞMEZ — geriye uyumlu) ---
    no: str
    body: str               # HAM gövde (künyeler/dipnot işaretleri yerinde)
    madde_tipi: str
    madde_baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None
    yurutluk: str           # madde-seviyesi (mevcut, korunur)
    # --- YENİ alanlar ---
    id: str                 # "193-84" | "193-Gecici1-1" (benzersiz, #7)
    body_temiz: str         # künye temizlenmiş + apendiks ayrılmış (embedding için)
    fikralar: list[Fikra]   # iç içe fıkra→bent ağacı (#5, #6)
    degisiklik_gecmisi: list[Degisiklik]   # (#3)
    dipnotlar: list[Dipnot]                # bu maddeye bağlı dipnotlar (#2)
```

**Tasarım kararları:**
- `body` (ham) **değişmez** → mevcut testler + `eval_metadata.py` invariant'ları korunur.
- `body_temiz`: künyeler çıkarılmış + dipnot apendiksi ayrılmış. Embedding bunu kullanır,
  atıf modu `body`'yi döndürür.
- `yurutluk` (madde) korunur; `Fikra.yurutluk` + `Bent.yurutluk` eklenir → kısmen mülga.
- `dipnotlar` **hem madde-bazlı hem global**: `Madde.dipnotlar` = gövdedeki `[n]`'lere
  bağlananlar; `enrich()` ikinci dönüş değeri = tüm dipnotların global listesi (hiçbir
  `[n]`'e eşleşmeyenler kaybolmaz).

## 5. `enrich()` imzası

```python
def enrich(
    articles: list[Article],
    tree: TreeIndex,
    kanun_no: str,
) -> tuple[list[Madde], list[Dipnot]]:
    """Zenginleştirilmiş maddeler + global dipnot listesi döndürür."""
```

**Kırıcı değişiklik:** `enrich()` artık tuple döndürür. Mevcut çağıranlar (`eval_metadata.py`,
`test_enrich.py`) `maddeler, _ = enrich(...)` olarak güncellenir. `Madde` alanları **eklemeli**
(mevcut alanlar yerinde) olduğu için invariant assert'ler kırılmaz.

## 6. Parser detayları

### 6.1 `dipnot.py` (#1, #2)
```python
def split_dipnot_apendiksi(body: str) -> tuple[str, list[Dipnot]]:
    """Gövde KUYRUĞUNDAN geriye, ardışık `^\\[\\d+\\]\\s` satır bloğunu bul.
    Blok ≥3 ardışık satır ise apendiks say → (temiz_body, [Dipnot...]).
    Eşik altı veya yok → (body, []) (no-op)."""

def baglanan_dipnotlar(body: str, tum_dipnotlar: list[Dipnot]) -> list[Dipnot]:
    """Gövde içi `\\[(\\d+)\\]` işaretlerini bul → no'ya göre global dipnottan eşle."""
```
- **Güvenlik eşiği: ≥3 ardışık `[n]` satırı** → tek tük `[167]` referansını kesmez.
- Apendiks kuyruktadır (son maddede birikir); blok başlangıcından gövde sonuna kadar kesilir.

### 6.2 `degisiklik.py` (#3)
```python
def parse_kunyeler(body: str) -> list[Degisiklik]:
    """(Değişik|Ek|Mülga|...: …) ve İptal: Anayasa Mahkemesi künyelerini yapısal parse et."""

def temizle_kunyeler(body: str) -> str:
    """Künyeleri gövdeden çıkar (body_temiz için)."""
```
Regex katmanları:
- Dış kalıp: `\((Değişik|Ek|Mülga|Ekleme)([^:)]*?):\s*([^)]*)\)` → (tip, kapsam, içerik).
- İçerik: `(\d+/\d+/\d+)-(\d+)/(\d+)\s*md\.` → (tarih, kanun_no, madde).
- İptal özel: `İptal:\s*Anayasa Mahkemesi` → `tip="iptal"`.
- Tarih ISO: `9/4/2003` → `2003-04-09`; parse edilemezse `tarih=None`.
- `kapsam`: "birinci fıkra" / "ibare" / "cümle" → tipten sonraki serbest metin.
- **Garanti:** parse kısmen başarısız olsa bile `ham_metin` her zaman dolu (veri kaybı yok).

### 6.3 `fikra.py` (#5, #6)
```python
def parse_fikralar(body: str) -> list[Fikra]:
    """İç içe fıkra→bent ağacı; her düğüme extract_status uygula."""
```
- Fıkra ayır: `(?=\(\d+\)\s)` (yeni stil). Hiç `(N)` yoksa → tüm gövde tek `Fikra(no=None)`.
- Bent ayır (fıkra içinde): `(?=^\s*[a-zçğıöşü]\)\s)` (harf) **veya** `(?=^\s*\d+\.\s)` (numara).
  Bir fıkrada her iki stil birden görülürse, fıkrada **ilk eşleşen stil** o fıkranın bent
  stili olur (karışık stil tek fıkra içinde varsayılmaz; ilk-kazanır, deterministik).
- Her `Fikra.text` ve `Bent.text`'e `chunker.extract_status` → `yurutluk` (#6).

### 6.4 `ids.py` (#7)
```python
def assign_ids(maddeler: list[Madde], kanun_no: str) -> None:
    """In-place benzersiz id ata; çakışmada -{sıra} eki."""
```
- Temel: `f"{kanun_no}-{slug(no)}"`; `slug`: "Geçici 1"→"Gecici1", "123/A"→"123A".
- Çakışma: görülen id'leri set'te tut; tekrarda `-{artan}` ekle (deterministik, content sırası).

### Bilinçli sınırlamalar (YAGNI)
- Tarih parse-fail → `None` (zorlama yok); `ham_metin` kurtarır.
- Fıkra→bent iki seviye; daha derin nesting yok.
- Tablo içi sayılar (#4) dokunulmaz.

## 7. Hata yönetimi (çökmez)
- Bozuk künye → atla, `ham_metin` listede kalır.
- Dipnot eşik altı → no-op (gövde değişmez).
- Boş gövde → boş listeler.
- Tarih parse-fail → `None`, ham korunur.
- Eşleşmeyen `[n]` → global listede kalır (madde-bazlıda görünmez).

## 8. Test stratejisi (TDD — önce test)

**Birim testleri (küçük sentetik fixture):**
| Test dosyası | Kapsam |
|---|---|
| `tests/test_dipnot.py` ★ | apendiks ayırma (≥3 blok), eşik altı no-op, `[n]→madde` bağ, yoksa `(body,[])` |
| `tests/test_degisiklik.py` ★ | Değişik/Ek/Mülga/İptal tipleri, tarih ISO, kapsam, parse-fail→`ham_metin` korunur |
| `tests/test_fikra.py` ★ | `(N)` fıkra, numarasız tek fıkra, `a)` bent, `1.` bent, bent-seviyesi yürürlük |
| `tests/test_ids.py` ★ | temel id, çifte `Geçici 1`→`-1/-2`, sonek `123/A`→`123A` |
| `tests/test_enrich.py` | **güncellenir** — tuple dönüş + yeni alanlar; eski invariant'lar korunur |
| `tests/test_chunker.py`, `test_tree.py`, `test_normalize.py`, `test_eval_tree.py` | **dokunulmaz** (regresyon kanıtı) |

**Gerçek-veri doğrulaması — `scripts/eval_metadata.py` genişletilir:**
- Madde 70: `len(fikralar)==1`, `len(fikralar[0].bentler)==8` (#5).
- Geçici 5: `len(body_temiz) < 5000` (83K apendiks ayrıldı, #1) + global dipnot ~221 (#2).
- Künyeli madde: `len(degisiklik_gecmisi)>=1`, ilk künye `kanun_no` dolu (#3).
- Çifte `Geçici 1`: iki farklı `id` (#7).
- Kısmen mülga madde: `yurutluk=="yürürlükte"` ama bir `bentler[].yurutluk=="mülga"` (#6).

## 9. Bilinen risk / kabul
- **Künye parse çeşitliliği** en kırılgan kısım (GVK'da ~402 künye, çok format). Kabul:
  `ham_metin` her zaman korunur; yapısal alanlar best-effort, parse-fail→`None`.
- **Dipnot apendiksi tespiti** over-truncation riski taşır. Kabul: ≥3 ardışık satır eşiği +
  yalnız kuyruk → muhafazakar; gerçek GVK verisinde (221 satır) doğrulanır.
- **Bent ayırma yanlış-pozitif:** `1.` bent ile cümle-sonu-numara karışabilir. Kabul: satır
  başı (`^\s*`) ankraj + TDD ile gerçek veride sağlamlaştırılır.

## 10. Commit disiplini
- Branch `phase-3/followup-amendments` (mevcut, güncel main'den dallanmış).
- Atomik commit'ler; `type(scope): özet`; commit mesajında AI co-author / "Generated with"
  **YOK** (commit_discipline.md); `main`'e doğrudan push yok.
