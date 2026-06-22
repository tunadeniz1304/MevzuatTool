# Tasarım: Ağaç-tabanlı Metadata Zenginleştirme (Faz 3)

**Tarih:** 2026-06-22
**Branch:** `phase-3/tree-metadata`
**Kapsam:** Faz 3 — her chunk için zengin, filtrelenebilir metadata (roadmap.md Faz 3)
**Önkoşul:** Faz 2 chunker (`split_articles`) main'de mevcut.

---

## 1. Amaç

`split_articles` bugün yalnız `Article(no, body)` üretiyor; madde başlığı, hiyerarşi
(KISIM/BÖLÜM) ve madde tipi metadata'sı **yok**, ayrıca gövde sonunda yapısal
**sızma** (bir sonraki bölüm başlığı + sonraki maddenin başlığı) var.

Bu tasarım, `get_mevzuat_madde_tree` çıktısını (yapısal, temiz) content chunk'larıyla
**birleştirerek (join)** zengin `Madde` kayıtları üretir ve gövde sızmasını temizler.

### Çözülen iki kanıtlı problem
1. **Sızma (header bleed):** Madde gövdesi "bir sonraki `Madde N -` işaretine kadar"
   kesildiği için bölüm başlıkları + sonraki maddenin başlığı gövdeye sızıyor.
   Kanıt: GVK Madde 79 gövdesi "…Türk Parasına çevrilir. YEDİNCİ BÖLÜM Diğer Kazanç ve
   İratlar Gelire giren diğer kazanç ve iratlar:" diye bitiyor (canlı MCP'de de aynı).
2. **Eksik metadata:** madde başlığı, kısım/bölüm, madde tipi tutulmuyor.

## 2. Kapsam

**Dahil:**
- Yeni `tree.py`: girintili ağaç metnini yapısal index'e ayrıştırır.
- Yeni `enrich.py`: Article + tree → zengin `Madde` (join + miras + sızma kırpma).
- Yalnız `KANUN` türü (ADR-0013); doğrulama 4 kanun-only örnek (TCK/VUK/KVKK/GVK).

**Hariç:**
- Embedding / vektör store / retrieval (Faz 5–6).
- Korpus JSONL serileştirme `{id, text, metadata}` (Faz 4) — `Madde` dataclass onun
  girdisi olur ama serileştirme bu task'ta değil.
- `chunker.py` / `normalize.py` / `eval_tree.py` değişikliği (dokunulmaz).

## 3. Mimari

```
content → normalize → split_articles → [Article(no, body)]  ┐
                                                            ├─► enrich() ─► [Madde]
tree_<id>.txt → tree.parse_tree() ─► TreeIndex             ┘
```

**Modül sorumlulukları (her biri tek işli, ayrı test edilebilir):**
| Modül | Sorumluluk | Durum |
|---|---|---|
| `normalize.py` | metin temizleme | değişmez |
| `chunker.py` | madde bölme (`split_articles`) | değişmez |
| `eval_tree.py` | ağaç madde sayımı | değişmez |
| `tree.py` ★ | ağaç metni → `TreeIndex` | yeni |
| `enrich.py` ★ | Article + TreeIndex → `[Madde]` | yeni |

## 4. Veri modeli

```python
@dataclass
class Madde:
    no: str                    # "84" | "Geçici 84"
    body: str                  # sızma kırpılmış gövde
    madde_tipi: str            # "asil" | "gecici" | "ek" | "mukerrer"
    madde_baslik: str | None   # "Beyanname çeşitleri"
    kisim_no: str | None       # "DÖRDÜNCÜ KISIM"
    kisim_baslik: str | None   # "Verginin Tarhı"
    bolum_no: str | None       # "YEDİNCİ BÖLÜM"
    bolum_baslik: str | None   # "Diğer Kazanç ve İratlar"
    hiyerarsi_yolu: str | None # "BİRİNCİ KİTAP › ... › Madde 84" (hiçbir seviye kaybolmaz)
    maddeId: str | None        # "1279029" (prefixli'de None)
    yurutluk: str              # "yürürlükte" | "mülga"
```

`hiyerarsi_yolu`: TCK'da KİTAP, bazılarında AYIRIM seviyesi var; kisim/bolum convenience
alanları korunurken tam yol bu string'de saklanır (hiçbir seviye kaybolmaz).

## 5. `tree.py` tasarımı

**Girdi:** ham ağaç metni (`get_mevzuat_madde_tree` / `tree_<id>.txt`).
**Çıktı:** `TreeIndex` =
- `by_no: dict[str, TreeNode]` — `madde_no` ile O(1) lookup (join için)
- `ordered: list[...]` — KISIM/BÖLÜM/Madde olayları **sırayla** (miras + sızma için)

**Ayrıştırma (satır bazlı):**
- **Girinti** (baştaki boşluk) → hiyerarşi seviyesi; sabit isim varsayma, **ancestor
  stack** tut (derin girinti = push, sığ = pop).
- Satır sınıflandır: yapısal başlık (`KİTAP|KISIM|BÖLÜM|AYIRIM|AYRIM` içerir) mı, madde
  (`Madde No: N`) mi?
- `" - "` ile böl: `"BİRİNCİ KISIM - Mükellefiyet"` → (`kisim_no`, `kisim_baslik`);
  `"Madde No: 84 - Beyanname çeşitleri:"` → (`no="84"`, `baslik="Beyanname çeşitleri"`).
- Baş satırları (`Article Tree for…`, `Total nodes:`, boş) atla.

## 6. `enrich.py` tasarımı

`enrich(articles: list[Article], tree: TreeIndex) -> list[Madde]`

**Ağaç-güdümlü hizalama:** `tree.ordered` kanonik sırayı verir; content'teki düz maddeler
aynı sırada. İkisi paralel yürünür — düz maddelerin bölümü için content'ten regex'e gerek
yok, ağaç otorite.

Her madde için:
1. **Tip tespiti** (`madde_tipi`): `no`'dan → "Geçici X"→`gecici`, "Ek X"→`ek`,
   "Mükerrer X"→`mukerrer`, düz sayı→`asil`.
2. **Düz madde (asil) → ağaçtan join:** `tree.by_no[no]`'dan `madde_baslik`,
   `kisim_*`, `bolum_*`, `hiyerarsi_yolu`, `maddeId`.
3. **Prefixli madde → miras:** ağaçta olmadığı için paralel yürüyüşte **eşleşmeyen
   content kaydı** olarak görünür →
   - `madde_tipi` = flag,
   - `kisim/bolum/hiyerarsi_yolu` = yürüyüşte o noktadaki **güncel bölümden miras** (en son
     eşleşen ağaç düğümünün bölümü),
   - `madde_baslik` = content best-effort (işaretten önceki `:`'li satır), yoksa `None`,
   - `maddeId` = `None`.
4. **Yürürlük:** `extract_status(body)` (mevcut chunker fonksiyonu yeniden kullanılır).
5. **Sızma kırpma:** ağaç, Madde-N'den sonra gelen metni (sonraki bölüm başlığı + sonraki
   maddenin başlığı) bilir; bu **bilinen string'leri** gövde kuyruğunda bulup oradan keser
   (kör regex değil). String bulunamazsa gövde olduğu gibi kalır (no-op).

## 7. Hata yönetimi
- Content'te olup ağaçta olmayan **düz** madde → çökme yok; prefixli gibi ele al (bölüm
  miras, başlık/maddeId null), say + raporla.
- Bozuk ağaç satırı → atla (parse çökmesin).
- Boş ağaç/content → boş liste.
- Sızma kırpma: beklenen string yoksa → gövde değişmez (no-op).

## 8. Test stratejisi (TDD — önce test)

**Birim testleri (küçük sentetik fixture):**
- `tests/test_tree.py` ★: 3 seviyeli ağaç ayrıştırma, `" - "` bölme, baş satır atlama,
  KİTAP/AYIRIM → `hiyerarsi_yolu`, bozuk satır atlama.
- `tests/test_enrich.py` ★: düz join (asil + tüm alanlar), prefixli (flag + miras +
  maddeId=None), sızma kırpma (kuyruk temizlenir), mülga tespiti korunur.
- `tests/test_chunker.py` (mevcut 6) → **dokunulmadığı için yeşil kalır** (regresyon kanıtı).

**Gerçek-veri doğrulaması:** `scripts/eval_metadata.py` ★ — 4 kanunun cache'inde invariant:
- Madde 79 gövdesi `"YEDİNCİ BÖLÜM"` İÇERMEZ (sızma fix),
- Madde 84 `madde_baslik == "Beyanname çeşitleri"`,
- Geçici 84 `madde_tipi == "gecici"`.

**Kapsam (kanunlar):** kod generic; geliştirme GVK öncelikli (en zor), doğrulama 4 kanunda
(TCK→KİTAP, KVKK→BÖLÜM-only, VUK→ağır değişiklik, GVK→prefixli+sızma).

## 9. Bilinen risk / kabul
- **Prefixli maddelerin konum-mirası** en kırılgan kısım (GVK'da 133 prefixli madde ağaçta
  yok). Kabul: `kisim/bolum` = "en yakın önceki bölüm", `maddeId=None`, `baslik` best-effort.
  Mükemmel olmasa da flag + bölüm garanti. TDD ile gerçek GVK verisinde sağlamlaştırılır.

## 10. Commit disiplini
- Branch `phase-3/tree-metadata` (güncel main'den dallandı).
- Atomik commit'ler; `type(scope): özet`; commit mesajında AI co-author / "Generated with"
  **YOK**; `main`'e doğrudan push yok.
