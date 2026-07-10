"""Bedesten API'sinden TEBLİĞ çekimi — ölçülmüş rate-limit'e uyumlu, cache'li, devam-edilebilir.

`src/kanun/fetch.py`'den KOPYALANDI (ADR-0014: türler arası sıfır kod paylaşımı) ve tebliğe
uyarlandı. Kanun tarafını import ETMEZ; oradaki bir değişiklik burayı bozamaz.

TEBLİĞ FARKLARI (kanun fetch'ine göre):
  1. `mevzuatTurList: ["TEBLIGLER"]` (kanun: ["KANUN"]).
  2. Cache dizini `data/teblig/raw/` (kanun korpusunu asla ezmez).
  3. **Madde ağacı OPSİYONEL.** Tebliğlerin bir kısmında ağaç YOK ("İlgili mevzuata ait ağaç
     yapısı mevcut değildir"). Ölçüm (9 örnek): 6'sında ağaç var, 3'ünde yok — ağaçsızlık yaşa
     değil belge tipine bağlı (tarife/duyuru/standart metinleri). `fetch_tree` boş liste döner,
     bu HATA DEĞİL; ağaçsız-boş cache YAZILMAZ ama `_agacsiz.txt`'ye kaydedilir (parser bilsin).
  4. **Rate-limit modeli ÖLÇÜLDÜ (2026-07-10, bedesten canlı).** Kanun fetch'inin
     "token-bucket 10 istek + 17 sn cooldown" varsayımı kısmen yanlıştı. Ölçülen gerçek:
       - Kova endpoint başına DEĞİL, **GLOBAL (IP)**: tree dolunca /getDocumentContent de 429.
       - `Retry-After` **DÜRÜST**: 30 dedi → 30.3 sn'de açıldı (erken deneme boşuna).
       - Kova **kademeli dolmuyor**: 10 istek sonrası 5 sn bekle → 0 istek geçer; 10 sn → 10 istek.
       - **İstek-arası aralık ÖNEMSİZ, pencere-başı SAYI önemli:** 0.5 sn aralıkla 11. istekte
         429; 3.0 sn aralıkla (6× yavaş) yine 12. istekte 429. Yavaşlamak kurtarmıyor.
       - Pencere ~29-30 sn, kota ~10 istek. (`10 istek + 26 sn bekle` → 429, `Retry-After=3`:
         yani 26 sn yetmedi, ~29 gerekiyordu.)
       - **Agresif strateji KAYBEDİYOR:** "durmadan at, 429'da Retry-After kadar bekle" ölçüldü
         → 0.279 i/s. "9 istek + 31 sn bekle" (sıfır 429) → 0.303 i/s. Temkinli %9 daha hızlı.
     Sonuç: `_HizSinirlayici` **parti modeli** uygular — `_PARTI` istek hızlıca, sonra
     `_PENCERE` sn bekle. Ölçülmüş sürdürülebilir verim ≈ 0.30 istek/sn.
  5. 429 gelirse `Retry-After` okunur ve tam o kadar beklenir (dürüst olduğu ölçüldü); parti
     boyutu kalıcı olarak 1 azaltılır (adaptif geri çekilme, aynı koşuda tekrar 429 yememek için).

Saf stdlib + httpx — pydantic/mevzuat-mcp'ye bağımlı değil.
Çalıştırma: `python -m teblig.fetch` (id listesi + HTML/ağaç cache).
"""
import asyncio
import base64
import html as _htmllib
import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field

# --- Bedesten API sabitleri ---
BASE_URL = "https://bedesten.adalet.gov.tr/mevzuat"
APP_NAME = "UyapMevzuat"
MEVZUAT_TUR = "TEBLIGLER"          # <-- tebliğ (kanun fetch'inde "KANUN")
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "AdaletApplicationName": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"),
}

# --- ÖLÇÜLMÜŞ rate-limit parametreleri (bkz. modül docstring §4) ---
# Sunucu: ~10 istek / ~29-30 sn pencere, IP başına. Aralık değil SAYI sınırlı.
# 9 istek (1 güvenlik payı) + 31 sn bekle = sıfır 429, 0.303 istek/sn (54 istek boyunca doğrulandı).
_PARTI = 9               # pencere başına istek (kota 10; 1 pay bırakılır)
_PARTI_ICI = 0.15        # parti içinde istek-arası (yanıt ~0.05 sn; sadece nazik olmak için)
_PENCERE = 31.0          # parti sonrası bekleme (ölçülen pencere ~29-30 sn + pay)
_DEFAULT_COOLDOWN = 30.0 # Retry-After header'ı yoksa varsayılan
# searchDocuments sayfa boyutu TAVANI 20'dir. Aşılırsa sunucu HTTP 200 + metadata.FMTY="ERROR"
# ("Kayıt sayısı 20'den fazla olamaz") döner ve liste boş gelir → sessiz 0-sonuç tuzağı.
_PAGE_SIZE = 20


# --- Gömülü saf-fonksiyonlar ---
def _wrap(data: dict) -> dict:
    return {"data": data, "applicationName": APP_NAME}


def _wrap_paging(data: dict, page: int, page_size: int) -> dict:
    d = dict(data)
    d["pageNumber"] = page
    d["pageSize"] = page_size
    return {"data": d, "applicationName": APP_NAME, "paging": True}


def _decode_base64(raw: str) -> str:
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return raw


def strip_html(html_text: str) -> str:
    """Ham HTML → düz metin (etiket sök + entity çöz), paragraf sınırları '\x1f' ile işaretli.

    Kanun tarafıyla aynı sözleşme: '<p>/<div>/<li>' → '\x1f' (Unit Separator, metinde asla geçmez),
    '<br>' → '\n'. Fıkra bölme bu sınıra dayanır. (Tebliğ metinlerinde de her fıkra ayrı <p>.)
    """
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:p|div|li)\b[^>]*>", "\x1f", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _htmllib.unescape(text)
    bloklar = []
    for blok in text.split("\x1f"):
        satirlar = [ln.strip() for ln in blok.split("\n")]
        icerik = "\n".join(ln for ln in satirlar if ln)
        if icerik:
            bloklar.append(icerik)
    return "\x1f".join(bloklar)


# --- Ağaç düğümü ---
@dataclass
class TreeNode:
    madde_no: str | None
    madde_id: str | None
    title: str | None
    madde_baslik: str | None
    children: list = field(default_factory=list)


def parse_tree_json(children: list) -> list:
    out = []
    for n in children or []:
        node = TreeNode(
            madde_no=(str(n["maddeNo"]) if n.get("maddeNo") is not None else None),
            madde_id=(str(n["maddeId"]) if n.get("maddeId") is not None else None),
            title=n.get("title"),
            madde_baslik=n.get("maddeBaslik"),
            children=parse_tree_json(n.get("children") or []),
        )
        out.append(node)
    return out


# --- Hız sınırlayıcı (ÖLÇÜLMÜŞ model: PARTİ — sabit aralık değil) ---
class _HizSinirlayici:
    """`parti` kadar istek hızlıca geçirir, sonra `pencere` sn bekler.

    NEDEN PARTİ (sabit aralık değil): ölçümde istek-arası aralığı 0.5→3.0 sn'ye çıkarmak
    (6× yavaş) hiçbir şey değiştirmedi — her iki durumda da ~11-12. istekte 429. Sunucu
    ortalama hızı değil, **pencere başına istek sayısını** sayıyor. Dolayısıyla yavaş gitmek
    sadece zaman kaybettirir; doğru davranış kotayı doldurup pencerenin dolmasını beklemek.

    429 görülürse `geri_cekil()` parti boyutunu kalıcı 1 azaltır (min 3) — aynı koşuda tekrar
    429 yememek için. (Ölçüm: temkinli strateji agresiften %9 hızlı; 429 ucuz değil.)
    """

    def __init__(self, parti: int = _PARTI, pencere: float = _PENCERE):
        self.parti = parti
        self.pencere = pencere
        self._sayac = 0

    async def bekle(self, sleep=asyncio.sleep):
        if self._sayac >= self.parti:
            await sleep(self.pencere)
            self._sayac = 0
        elif self._sayac > 0:
            await sleep(_PARTI_ICI)
        self._sayac += 1

    def geri_cekil(self):
        """429 sonrası: parti küçült (kota tahminimiz fazlaymış) ve sayacı sıfırla."""
        self.parti = max(3, self.parti - 1)
        self._sayac = 0


async def _post_with_retry(client, url, payload, hiz: _HizSinirlayici, *,
                           sleep=asyncio.sleep, max_tries: int = 6):
    """Parti sınırına uyarak POST; 429'da Retry-After kadar bekleyip retry.
    (Retry-After dürüst olduğu ölçüldü: 30 dedi → 30.3 sn'de açıldı; erken deneme boşuna.)
    sleep enjekte edilebilir (test)."""
    for _ in range(max_tries):
        await hiz.bekle(sleep=sleep)
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            hiz.geri_cekil()
            ra = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
            wait = float(ra) + 0.5 if ra else _DEFAULT_COOLDOWN
            await sleep(wait)
            continue
        await sleep(2.0)
    raise RuntimeError(f"{url}: {max_tries} denemede başarısız (rate-limit/hata)")


class TebligFetcher:
    """Cache'li, ölçülmüş-hız uyumlu tebliğ çekici. httpx lazy import."""

    def __init__(self, cache_dir: str = "data/teblig/raw"):
        import httpx
        self.cache = pathlib.Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._client = httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0)
        self._hiz = _HizSinirlayici()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def fetch_teblig_ids(self, page_size: int = _PAGE_SIZE, use_cache: bool = True):
        """Tüm TEBLİĞ listesini (no, mid, ad). Cache varsa onu kullanır (liste nadiren değişir).

        DİKKAT: `pageSize` **en fazla 20** olabilir. Daha büyük değer verilirse sunucu HTTP 200
        döndürür ama gövdede `metadata.FMTY="ERROR"` + "Kayıt sayısı 20'den fazla olamaz" der ve
        `mevzuatList` boş gelir → sessiz 0-sonuç. Bu yüzden aşağıda FMTY kontrolü ZORUNLU.
        4990 tebliğ / 20 = ~250 sayfa → ~250 istek (rate-limit'te ~14 dk).
        """
        ids_path = self.cache / "_teblig_ids.txt"
        if use_cache and ids_path.exists():
            rows = [tuple(l.split("\t")) for l in ids_path.read_text(encoding="utf-8").splitlines()
                    if len(l.split("\t")) >= 3]
            if rows:
                return [(r[0], r[1], r[2]) for r in rows]
        out, page, total = [], 1, None
        while page <= 400:   # guard (4990 / 20 ≈ 250 sayfa)
            inner = {"phrase": "", "mevzuatTurList": [MEVZUAT_TUR],
                     "sortFields": ["RESMI_GAZETE_TARIHI"], "sortDirection": "desc"}
            body = await _post_with_retry(self._client, "/searchDocuments",
                                          _wrap_paging(inner, page, page_size), self._hiz)
            # Sessiz-hata kapısı: sunucu 200 + FMTY=ERROR döndürebilir (ör. pageSize>20).
            fmty = (body.get("metadata") or {}).get("FMTY")
            if fmty != "SUCCESS":
                mesaj = (body.get("metadata") or {}).get("FMTE", "?")
                raise RuntimeError(f"searchDocuments hata (FMTY={fmty}): {str(mesaj)[:120]}")
            data = body.get("data") or {}
            docs = data.get("mevzuatList") or []
            total = data.get("total", total)
            if not docs:
                break
            for d in docs:
                out.append((str(d.get("mevzuatNo", "")), str(d.get("mevzuatId", "")),
                            (d.get("mevzuatAdi") or "").replace("\t", " ").replace("\r", " ")
                             .replace("\n", " ")))
            if page % 10 == 0 or page == 1:
                print(f"  [id] sayfa {page}: toplam {len(out)}/{total}", flush=True)
            if len(docs) < page_size or (total and len(out) >= total):
                break
            page += 1
        seen, uniq = set(), []
        for no, mid, ad in out:
            if mid and mid not in seen:
                seen.add(mid)
                uniq.append((no, mid, ad))
        if uniq:
            ids_path.write_text("\n".join(f"{n}\t{m}\t{a}" for n, m, a in uniq), encoding="utf-8")
        return uniq

    async def fetch_tree(self, mid: str, use_cache: bool = True) -> list:
        """Madde ağacı (TreeNode listesi). TEBLİĞLERDE AĞAÇ OPSİYONELDİR — yoksa [] döner.

        Ağaçsız tebliğ HATA DEĞİL (ölçüm: 9 örnekten 3'ü ağaçsız). Boş cache YAZILMAZ (sonraki
        gerçek çekimi engellemesin) ama mid `_agacsiz.txt`'ye eklenir → tekrar denenmez ve
        parser bu maddeleri metinden çıkarması gerektiğini bilir."""
        path = self.cache / f"treejson_{mid}.json"
        if use_cache and path.exists():
            children = json.loads(path.read_text(encoding="utf-8"))
            return parse_tree_json(children)
        agacsiz = self.cache / "_agacsiz.txt"
        if use_cache and agacsiz.exists() and mid in agacsiz.read_text(encoding="utf-8").split():
            return []
        body = await _post_with_retry(self._client, "/mevzuatMaddeTree",
                                      _wrap({"mevzuatId": mid}), self._hiz)
        if body.get("metadata", {}).get("FMTY") != "SUCCESS":
            with agacsiz.open("a", encoding="utf-8") as f:
                f.write(mid + "\n")
            return []
        data = body.get("data") or {}
        children = data.get("children", []) if isinstance(data, dict) else data
        if children:
            path.write_text(json.dumps(children, ensure_ascii=False), encoding="utf-8")
        else:
            with agacsiz.open("a", encoding="utf-8") as f:
                f.write(mid + "\n")
        return parse_tree_json(children)

    async def fetch_html(self, mid: str, use_cache: bool = True) -> str:
        """Ham HTML (base64 çözülmüş). Diske cache'ler, devam-güvenli."""
        path = self.cache / f"html_{mid}.html"
        if use_cache and path.exists():
            return path.read_text(encoding="utf-8")
        body = await _post_with_retry(self._client, "/getDocumentContent",
                                      _wrap({"documentType": "MEVZUAT", "id": mid}), self._hiz)
        if body.get("metadata", {}).get("FMTY") != "SUCCESS":
            return ""
        html = _decode_base64((body.get("data") or {}).get("content", ""))
        if html:
            path.write_text(html, encoding="utf-8")
        return html

    @staticmethod
    def html_to_text(html: str) -> str:
        return strip_html(html) if html else ""


async def _main():
    """python -m teblig.fetch — id listesi + tebliğlerin HTML + ağaç cache'i.

    Devam-güvenli: cache'li olanlar atlanır (istek bile atılmaz), kesintiden sonra kaldığı
    yerden sürer. Ölçülen verim ≈0.30 istek/sn → 4990 tebliğ × 2 istek ≈ 9 saat.

    Ortam değişkenleri:
      FETCH_LIMIT=N   ilk N tebliğ (pilot için; 0=hepsi)
      FETCH_PARTI=9   pencere başına istek (ölçülen kota 10, 1 pay)
      FETCH_PENCERE=31  parti sonrası bekleme sn
      FETCH_SADECE_HTML=1  ağaç isteme (istek sayısını yarıya indirir)
    """
    import os
    # Windows konsolu (cp1254) Türkçe/işaret karakterlerinde patlıyor → stdout'u UTF-8'e sar.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    limit = int(os.environ.get("FETCH_LIMIT", "0")) or None
    parti = int(os.environ.get("FETCH_PARTI", str(_PARTI)))
    pencere = float(os.environ.get("FETCH_PENCERE", str(_PENCERE)))
    sadece_html = os.environ.get("FETCH_SADECE_HTML", "") == "1"
    t0 = time.monotonic()
    async with TebligFetcher() as f:
        f._hiz.parti, f._hiz.pencere = parti, pencere
        verim = parti / (parti * _PARTI_ICI + pencere)
        print(f"[hiz] {parti} istek / {pencere} sn  (~{verim:.2f} istek/sn)"
              f"{'  [sadece HTML]' if sadece_html else ''}", flush=True)
        ids = await f.fetch_teblig_ids()
        print(f"[OK] {len(ids)} teblig id -> {f.cache/'_teblig_ids.txt'}", flush=True)
        if limit:
            ids = ids[:limit]
            print(f"[pilot] ilk {limit} teblig islenecek", flush=True)
        n_html = n_tree = n_agacsiz = n_hata = 0
        for i, (no, mid, ad) in enumerate(ids, 1):
            try:
                if await f.fetch_html(mid):
                    n_html += 1
                if not sadece_html:
                    if await f.fetch_tree(mid):
                        n_tree += 1
                    else:
                        n_agacsiz += 1
            except Exception as e:
                n_hata += 1
                print(f"  [HATA] {mid}: {type(e).__name__} {str(e)[:60]}", flush=True)
            if i % 10 == 0 or i == len(ids):
                gecen = time.monotonic() - t0
                kalan = (len(ids) - i) * (gecen / i)
                print(f"  {i}/{len(ids)}  html={n_html} agacli={n_tree} agacsiz={n_agacsiz}"
                      f"{f' hata={n_hata}' if n_hata else ''}  "
                      f"({gecen/60:.0f} dk gecti, ~{kalan/60:.0f} dk kaldi)", flush=True)
        print(f"\nTAMAM: {len(ids)} teblig - html={n_html}, agacli={n_tree}, "
              f"agacsiz={n_agacsiz}, hata={n_hata} ({(time.monotonic()-t0)/60:.0f} dk) "
              f"-> {f.cache}", flush=True)


if __name__ == "__main__":
    asyncio.run(_main())
