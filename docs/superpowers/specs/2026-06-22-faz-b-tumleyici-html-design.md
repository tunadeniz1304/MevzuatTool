# Tasarım: Faz B — Tümleyici HTML Modülü (tablo + dipnot-anchor)

**Tarih:** 2026-06-22
**Branch:** `phase-b/html-structure-analysis`
**Kapsam:** MD omurgaya paralel, ham HTML'den yapı kazanan tümleyici katman — yalnız
tablolu maddelere `<table>→Markdown` cebi + dipnot `#_ftnN` anchor-bağı.
**Önkoşul:** Faz 3 pipeline (split_articles → enrich) main'de. recall=1.000, metadata=%100, 46 test.

---

## 1. Amaç

Mevcut MD omurga **çalışıyor** (madde recall=1.000, metadata alan doğruluğu=%100, kanıtlı).
İki workflow analizi (2026-06-22) tek gerçek yapısal kaybın **tablolar** olduğunu, ikincil
bir kazanımın **dipnot anchor-bağı** olduğunu gösterdi. Bu tasarım, MD omurgaya **dokunmadan**,
ham HTML'den (mevzuat-mcp `bedesten_client.get_document_content`) bu iki yapıyı kazanan
tümleyici bir katman ekler.

### Çözülen iki kayıp
1. **Tablolar:** `_strip_html` (MCP'nin plain yolu) `<table>`'ı düz-metne çeviriyor; 2D
   satır↔sütun (dilim↔oran) ilişkisi kopuyor (örn. GVK Madde 103 tarifesi, VUK ceza cetveli).
   Ham HTML'de `<tr>/<td>` **temiz** (workflow: `irregular_rows=0`).
2. **Dipnot bağı:** Faz 3 `[n]→dipnot` bağını regex (numara-eşleme) ile kurdu. HTML
   `<a href="#_ftnN">` anchor'ı bunu **yapısal** (benzersiz hedef id) kurar — regex'in
   numara-benzersizliği/tek-referans varsayımlarına ihtiyaç duymadan.

### Bilinçli kapsam sınırı (workflow uyarısı, kabul edilmiş)
- **Retrieval-nötr kabul:** recall zaten tavanda (1.000); tablo token'ları (`%15-%40`, dilim,
  tutar) düz-metinde de sağlam → retrieval bunları getiriyor. Faz B'nin değeri retrieval
  değil, **chunk kalitesi / generation hazırlığı** (2D ilişkiyi koruyarak saklama). Bu yüzden
  dar ve hedefli tutulur.
- **15 tablonun yalnız 9'u içerik;** 6'sı değişiklik-künyesi apendiks cetveli (hücrelerin %78'i)
  → Faz 3'te zaten ayrılan metadata → **header-blacklist ile dışarıda.**

## 2. Kapsam

**Dahil:**
- `scripts/fetch_html.py`: ham HTML çek (cp1254→utf8) + cache.
- `html_split.py`: HTML'i madde-regex'le böl (paylaşılan).
- `html_table.py`: içerik `<table>` → Markdown (apendiks blacklist hariç).
- `html_dipnot.py`: `#_ftnN` anchor-bağı.
- `enrich.py`: 2 opsiyonel parametre (None-default, geriye uyumlu).
- `Madde.tablolar: list[str]` alanı.
- `scripts/eval_html.py`: gerçek-veri invariant (offline, cache'li).

**Hariç:**
- Tam HTML migration (MD omurga redesign) — workflow: yüksek maliyet, sıfır doğruluk kazancı,
  çalışan %95'i riske atar. Kullanıcı onayı: YAPMA.
- 6 apendiks/değişiklik-künyesi tablosu (header-blacklist).
- Vurgu (`<b>`/`<i>`), referans-link grafiği (GraphRAG, ADR yasak), nbsp/tırnak normalize
  (ayrı bug-fix) — followups'ta ERTELE.
- Generation (CLAUDE.md kapsam dışı).

**Dokunulmaz (8 modül):** normalize, chunker, tree, dipnot, degisiklik, fikra, ids, eval_tree.

## 3. Mimari

MD omurgaya **paralel** HTML yolu; `enrich`'te birleşir.

```
            ┌─ content_<id>.md ──→ normalize → split_articles → [Article] ─┐
mevzuat-mcp ┤                                                              │
            └─ html_<id>.html (ham, fetch_html.py) ───────────────────┐    │
                                                                      ▼    ▼
   html_table.parse_tables(html)  ──→ {madde_no: [md_table]} ──────→ enrich(
   html_dipnot.parse_anchors(html) ─→ {madde_no: [Dipnot]} ───────→   articles, tree, kanun_no,
   (ikisi de html_split kullanır)                                      html_tables=None,    ← YENİ
                                                                       html_dipnotlar=None) ← YENİ
                                                                     → ([Madde], dipnotlar)
```

**Modül sorumlulukları:**
| Dosya | Tür | Sorumluluk | Durum |
|---|---|---|---|
| `scripts/fetch_html.py` | script | ham HTML çek + cp1254→utf8 + cache | yeni |
| `html_split.py` | modül | `split_html_articles(html) -> {no: html}` | yeni |
| `html_table.py` | modül | içerik `<table>` → Markdown | yeni |
| `html_dipnot.py` | modül | `#_ftnN` anchor-bağı | yeni |
| `enrich.py` | modül | 2 opsiyonel param, None-default | değişir |

## 4. Veri modeli

```python
@dataclass
class Madde:
    # ... mevcut 16 alan DEĞİŞMEZ ...
    tablolar: list[str] = field(default_factory=list)   # YENİ: markdown pipe-tablolar
```
- `body_temiz`: markdown tablo **sona eklenir** (`\n\n` + tablo); bozuk düz-metin iz **bırakılır**
  (iz-bulma kırılganlığı yok; embedding hem ham hem yapısal görür).
- `dipnotlar`: HTML varsa **anchor-bağı (asıl)**; HTML yoksa regex-bağı (fallback, mevcut).

`Dipnot` dataclass'ı `dipnot.py`'den yeniden kullanılır (`no:int, text:str`) — yeni tip yok.

## 5. Modül imzaları

```python
# html_split.py
def split_html_articles(html: str) -> dict[str, str]:
    """HTML'i 'MADDE N -' (chunker._MADDE'nin HTML-uyarlaması) ile böl.
    Dönüş: {madde_no: html_parça}. Tag-içine gömülü madde işaretini bulur."""

# html_table.py
_APENDIKS_BASLIK = ("Değiştiren", "Yürürlüğe Giriş", "Değişiklik Yapan", "Resmî Gazete")

def parse_tables(html: str) -> dict[str, list[str]]:
    """split_html_articles ile böl; her maddedeki içerik <table>'larını
    (apendiks-başlık blacklist hariç) Markdown'a çevir. Dönüş: {madde_no: [md_table]}."""

def _table_to_markdown(table_html: str) -> str:
    """stdlib html.parser ile <tr>/<td> çıkar; html.unescape + nbsp→boşluk; pipe-table kur."""

def _is_apendiks(table_html: str) -> bool:
    """Tablo metni _APENDIKS_BASLIK'ten birini içeriyor mu."""

# html_dipnot.py
def parse_anchors(html: str) -> dict[str, list]:
    """split_html_articles ile böl; her maddenin <a href="#_ftnN"> işaretlerini
    kuyruktaki <a name="_ftnN"> tanımına bağla. Dönüş: {madde_no: [Dipnot(no, text)]}."""

# enrich.py — yeni imza
def enrich(articles, tree, kanun_no,
           html_tables: dict | None = None,
           html_dipnotlar: dict | None = None) -> tuple[list, list]:
    """html_* None → mevcut davranış birebir (46 test korunur)."""
```

## 6. Orkestrasyon

`enrich` her madde için (mevcut 1-6 adım değişmez), ardından:

7. **Tablo (yeni):** `html_tables` verildiyse →
   `madde.tablolar = html_tables.get(no, [])`; her markdown tablo için
   `body_temiz += "\n\n" + tablo`.
8. **Dipnot (değişen):**
   - `html_dipnotlar` verildiyse → `madde.dipnotlar = html_dipnotlar.get(no, [])` (**anchor asıl**).
   - verilmediyse → mevcut regex-bağı (`baglanan_dipnotlar`, fallback).
   - **Sorumluluk ayrımı:** `enrich` runtime'da yalnız BİR bağ üretir (HTML varsa anchor, yoksa
     regex) — gereksiz çift hesap yapmaz. `anchor==regex` karşılaştırması **`eval_html.py`'nin
     işidir** (her iki bağı ayrı çağırıp kıyaslar); `enrich` bu kıyası yapmaz.

**Dipnot-anchor yapısı (workflow kanıtı):**
- İşaret: `<a href="#_ftnN" name="_ftnrefN"><span class=MsoFootnoteReference>[N]</span></a>`
- Tanım: `<a name="_ftnN" href="#_ftnrefN">[N]</a>` + serbest metin (kuyrukta, konteyner yok).
- `parse_anchors`: işaret→`#_ftnN`→tanım, **benzersiz hedef id** ile eşler.

## 7. HTML erişim & encoding

`scripts/fetch_html.py`:
- mevzuat-mcp paketinin `bedesten_client.BedestenClient().get_document_content(mid)` metodunu
  **kütüphane olarak import** eder (MCP server çalıştırmaz; client public metod).
- Dönen ham HTML `charset=Windows-1254` olabilir → **cp1254→utf-8 doğru decode** (mojibake
  "T�RK" önlenir). `bedesten_client` base64→utf-8 decode ediyor; fetch script doğrular,
  gerekirse cp1254 düzeltir.
- `data/raw/html_<id>.html` olarak cache'ler (mevcut `content_<id>.md` deseni gibi).
- Tablo parser ek olarak `html.unescape` + `nbsp→boşluk` uygular.

## 8. Hata yönetimi (çökmez, graceful degrade)
- `html_<id>.html` cache yok → `html_tables=None` → mevcut MD davranışı (degrade).
- Bozuk `<table>` → o tabloyu atla, diğerleri devam.
- Anchor tanımı bulunamadı → o dipnotu atla, raporla.
- HTML'de madde no plain'de yok → eşleşmeyen tabloyu/dipnotu yok say.
- Boş HTML → boş dict.

## 9. Test stratejisi (TDD)

**Birim (sentetik HTML fixture, ağsız):**
| Test | Kapsam |
|---|---|
| `test_html_split.py` | `MADDE N -` HTML bölme, no→parça, başsız/bozuk parça |
| `test_html_table.py` | `<table>`→pipe-table, apendiks-blacklist atlama, nbsp/unescape, boş tablo |
| `test_html_dipnot.py` | işaret→tanım eşleme, çoklu dipnot, eşleşmeyen anchor |
| `test_enrich.py` (mevcut) | **+yeni:** html_*=None → eski davranış birebir (46 korunur); param verilince tablolar+anchor |

**Gerçek-veri — `scripts/eval_html.py` (offline, cache'li):**
- 9 içerik tablosu Markdown'a çevriliyor (GVK 6, VUK 2, KVKK 1); 6 apendiks atlanıyor.
- **`anchor==regex` invariant:** 4 kanunda anchor-bağı = regex-bağı (workflow: 533 işaret,
  mismatch=0). **Uyuşmazlık → RAPORLA (hangi madde, fark), ÇÖKME** — anchor kazanır, sapma görünür.
- GVK Madde 103 `tablolar` dolu + markdown pipe içeriyor.

**Dokunulmaz:** `eval_metrics.py`, `eval_metadata.py` (HTML-bağımsız metrikleri korur).

## 10. Bilinen risk / kabul
- **HTML madde-bölme:** plain `chunker._MADDE`'nin HTML-uyarlaması; madde işareti tag'e gömülü
  (`<b>Madde 6-</b>`) → regex tag-toleranslı olmalı. TDD ile gerçek veride sağlamlaştırılır.
- **Word-export gürültüsü:** `<span style>`, `<p class=MsoNormal>` → tablo parser yalnız
  `<table>/<tr>/<td>` umursar, style görmezden gelinir.
- **Anchor≠regex (hipotetik):** workflow'da olmadı; olursa eval raporlar, anchor kazanır
  (çökmez). Karar: anchor asıl.

## 11. Commit disiplini
- Branch `phase-b/html-structure-analysis` (mevcut, güncel main'den).
- Atomik commit'ler; `type(scope): özet`; commit mesajında AI co-author / "Generated with"
  **YOK**; `main`'e doğrudan push yok.
- ADR-not: `get_document_content` MCP-tool API'si değil paketin iç public metodu — ilke #1
  ("yalnız mevzuat-mcp API'leri") için küçük gerekçeli sapma; decisions.md'ye not eklenir
  (uygulama sırasında, ayrı).
