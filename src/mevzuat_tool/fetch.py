"""Bedesten API'sinden rate-limit'e (429/Retry-After) saygılı, cache'li, devam-edilebilir veri çekimi.

KÖK NEDEN (ölçüldü): bedesten.adalet.gov.tr token-bucket uyguluyor — ~10 istek/pencere, dolunca
HTTP 429 + 'Retry-After: <sn>' header'ı döndürüyor. mevzuat-mcp'nin bedesten_client'ı bu 429'u
ve header'ı YUTUP boş veri döndürüyor → throttle görünmez oluyor, kör backoff başarısız.

Bu modül SAF stdlib + httpx — bedesten_client/bedesten_models/pydantic'e BAĞIMLI DEĞİL (ABI
uyumsuzluğundan etkilenmez, her python'da test edilir/çalışır). Gerekli saf-fonksiyonlar (HTML
strip, base64 decode, istek-sarmalama) ve ağaç-parse buraya gömülüdür.

429'da Retry-After'ı OKUR, tam o kadar bekler, retry eder; proaktif olarak kova dolmadan da hız
ayarlar (_RateState). Production-ingest omurgası: `python -m mevzuat_tool.fetch` ile deterministik,
sıfır-kayıp çeker; cache (data/raw/html_<mid>.html) sayesinde kesinti-güvenli (docker-dostu).
"""
import asyncio
import base64
import html as _htmllib
import json
import pathlib
import re
from dataclasses import dataclass, field

# --- Bedesten API sabitleri (bedesten_client'tan; saf, bağımlılık değil) ---
BASE_URL = "https://bedesten.adalet.gov.tr/mevzuat"
APP_NAME = "UyapMevzuat"
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "AdaletApplicationName": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"),
}

_DEFAULT_COOLDOWN = 17.0   # Retry-After yoksa varsayılan (gözlemlenen pencere)
_BUCKET = 10               # token-bucket kapasitesi (ölçüldü)


# --- Gömülü saf-fonksiyonlar (bedesten_client kopyası, bağımlılık kaldırmak için) ---
def _wrap(data: dict) -> dict:
    return {"data": data, "applicationName": APP_NAME}


def _wrap_paging(data: dict, page: int, page_size: int) -> dict:
    # Bedesten formatı: paging bilgisi data İÇİNDE pageNumber/pageSize; üst düzeyde paging:True flag'i.
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
    """Ham HTML → düz metin (etiket sök + entity çöz)."""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _htmllib.unescape(text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# --- Ağaç düğümü (BedMaddeNode yerine hafif, pydantic'siz) ---
@dataclass
class TreeNode:
    madde_no: str | None
    madde_id: str | None
    title: str | None
    madde_baslik: str | None
    children: list = field(default_factory=list)


def parse_tree_json(children: list) -> list:
    """Ham API children listesini TreeNode ağacına çevir (alias: maddeId/maddeNo/maddeBaslik)."""
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


# --- Rate-limit çekirdeği ---
class _RateState:
    """Proaktif hız ayarı: kova dolmadan önce bekleme öner (reaktif 429'u en aza indir)."""
    def __init__(self, bucket: int = _BUCKET, cooldown: float = _DEFAULT_COOLDOWN):
        self.bucket = bucket
        self.cooldown = cooldown
        self._used = 0

    def before_request(self) -> float:
        if self._used >= self.bucket:
            self._used = 1
            return self.cooldown
        self._used += 1
        return 0.0

    def on_429(self):
        self._used = 0


async def _post_with_retry(client, url, payload, rate: _RateState, *,
                           sleep=asyncio.sleep, max_tries: int = 6):
    """429 görürse Retry-After kadar bekleyip retry eder. Başarıda JSON body döndürür.
    sleep: test edilebilirlik için enjekte edilebilir async fonksiyon."""
    for _ in range(max_tries):
        pre = rate.before_request()
        if pre > 0:
            await sleep(pre)
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            rate.on_429()
            ra = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
            wait = float(ra) + 0.5 if ra else _DEFAULT_COOLDOWN
            await sleep(wait)
            continue
        await sleep(2.0)   # diğer hatalar: kısa bekle, retry
    raise RuntimeError(f"{url}: {max_tries} denemede başarısız (rate-limit/hata)")


class MevzuatFetcher:
    """Yüksek seviye, cache'li, Retry-After-uyumlu çekici. httpx lazy import (test saf kalır)."""

    def __init__(self, cache_dir: str = "data/raw"):
        import httpx
        self.cache = pathlib.Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._client = httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0)
        self._rate = _RateState()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def fetch_kanun_ids(self, page_size: int = 20, use_cache: bool = True):
        """Tüm KANUN listesini (no, mid, ad). Cache varsa onu kullanır (liste nadiren değişir).
        searchDocuments rate-limit'i çok sıkı; cache + sayfa-arası proaktif hız (_RateState) yeter."""
        ids_path = self.cache / "_kanun_ids.txt"
        if use_cache and ids_path.exists():
            rows = [tuple(l.split("\t")) for l in ids_path.read_text(encoding="utf-8").splitlines()
                    if len(l.split("\t")) >= 3]
            if rows:
                return [(r[0], r[1], r[2]) for r in rows]
        out, page, total = [], 1, None
        while page <= 200:   # sonsuz-döngü guard'ı (916 kanun / 20 ≈ 46 sayfa)
            inner = {"phrase": "", "mevzuatTurList": ["KANUN"],
                     "sortFields": ["RESMI_GAZETE_TARIHI"], "sortDirection": "desc"}
            body = await _post_with_retry(self._client, "/searchDocuments",
                                          _wrap_paging(inner, page, page_size), self._rate)
            data = body.get("data") or {}
            docs = data.get("mevzuatList") or []
            total = data.get("total", total)
            if not docs:
                break
            for d in docs:
                out.append((str(d.get("mevzuatNo", "")), str(d.get("mevzuatId", "")),
                            (d.get("mevzuatAdi") or "").replace("\t", " ")))
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
        """Madde ağacı (TreeNode listesi). Ham API children JSON'unu diske cache'ler (devam-güvenli;
        tekrar-üretim ucuzlar). Boş gelirse gerçek 0-madde (Retry-After yutulmaz; boş cache YAZILMAZ
        ki sonraki gerçek çekim engellenmesin)."""
        path = self.cache / f"treejson_{mid}.json"
        if use_cache and path.exists():
            children = json.loads(path.read_text(encoding="utf-8"))
            return parse_tree_json(children)
        body = await _post_with_retry(self._client, "/mevzuatMaddeTree",
                                      _wrap({"mevzuatId": mid}), self._rate)
        if body.get("metadata", {}).get("FMTY") != "SUCCESS":
            return []
        data = body.get("data") or {}
        children = data.get("children", []) if isinstance(data, dict) else data
        if children:
            path.write_text(json.dumps(children, ensure_ascii=False), encoding="utf-8")
        return parse_tree_json(children)

    async def fetch_html(self, mid: str, use_cache: bool = True) -> str:
        """Ham HTML (base64 çözülmüş). Diske cache'ler, devam-güvenli."""
        path = self.cache / f"html_{mid}.html"
        if use_cache and path.exists():
            return path.read_text(encoding="utf-8")
        body = await _post_with_retry(self._client, "/getDocumentContent",
                                      _wrap({"documentType": "MEVZUAT", "id": mid}), self._rate)
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
    """python -m mevzuat_tool.fetch — id listesi + ilk N kanun HTML cache (CLI/docker giriş)."""
    import os
    limit = int(os.environ.get("FETCH_LIMIT", "0")) or None
    async with MevzuatFetcher() as f:
        ids_path = f.cache / "_kanun_ids.txt"
        if ids_path.exists():
            ids = [tuple(l.split("\t")) for l in ids_path.read_text(encoding="utf-8").splitlines()
                   if len(l.split("\t")) >= 3]
            print(f"[cache] {len(ids)} id zaten var", flush=True)
        else:
            ids = await f.fetch_kanun_ids()
            ids_path.write_text("\n".join(f"{n}\t{m}\t{a}" for n, m, a in ids), encoding="utf-8")
            print(f"[OK] {len(ids)} kanun id -> {ids_path}", flush=True)
        if limit:
            ids = ids[:limit]
        for i, (no, mid, ad) in enumerate(ids, 1):
            await f.fetch_html(mid)
            if i % 25 == 0:
                print(f"  {i}/{len(ids)} cache'lendi", flush=True)
        print(f"[OK] {len(ids)} kanun HTML cache'lendi -> {f.cache}", flush=True)


if __name__ == "__main__":
    asyncio.run(_main())
