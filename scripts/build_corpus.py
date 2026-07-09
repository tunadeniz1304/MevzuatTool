"""KORPUS ÜRETİCİ (Faz 4) — KANUN'ları çek + parse + zengin {id,text,metadata} JSONL yaz.

Pipeline: fetch (cache'li HTML + tree) → normalize → split_articles → parse_tree →
enrich → maddeler_to_chunks → korpus.jsonl. Boş-gövde maddeler elenir; mülga işaretli kalır.

Çalıştırma:
  .venv/Scripts/python.exe scripts/build_corpus.py                 # hepsi (916)
  CORPUS_LIMIT=1 .venv/Scripts/python.exe scripts/build_corpus.py  # ilk 1 kanun (smoke)
  CORPUS_MID=104383 .venv/Scripts/python.exe scripts/build_corpus.py  # tek kanun (mevzuatId)
"""
import asyncio, json, os, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from mevzuat_tool.fetch import MevzuatFetcher
from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich
from mevzuat_tool.html_table import parse_tables
from mevzuat_tool.html_dipnot import parse_anchors
from mevzuat_tool.corpus import maddeler_to_chunks, yonlendirme_chunk

# serialize_tree eval_corpus'tan (TreeNode → bedesten serialize string → parse_tree girdisi)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "ec", str(pathlib.Path(__file__).resolve().parent / "eval_corpus.py"))
_ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ec)
serialize_tree = _ec.serialize_tree

OUT = pathlib.Path("data/corpus/korpus.jsonl")


def _norm_madde_no(x):
    """Atıf-madde eşleşmesi için madde_no normalizasyonu (tire/boşluk sil, İ→I, büyük harf)."""
    import re as _re
    x = str(x).strip().upper().replace("İ", "I")
    return _re.sub(r"[\s\-]+", "", x)


async def build_one(f, no, mid, ad, atif_madde=None):
    """Bir kanunu çek + parse + chunk listesi döndür.

    atif_madde: {(kanun_no, norm_madde_no)} — FAZ 22f: içeriksiz 'yerine işlenmiştir' maddesi
    normalde elenir; AMA bu sette (birileri atıf yapmış) ise YÖNLENDİRME chunk'ı üretilir
    (madde bulunur, gövde boş, hedef kanun etiketli). Atıf-farkındalık yalnız build katmanında."""
    nodes = await f.fetch_tree(mid)
    html = await f.fetch_html(mid)
    content = f.html_to_text(html)
    if not content:
        return []
    tree = parse_tree(serialize_tree(nodes))
    arts = split_articles(normalize_text(content))
    ht = parse_tables(html) if html else None
    hd = parse_anchors(html) if html else None
    # id MID tabanlı (globalde benzersiz; kanun_no tekrar edebilir — 6551 iki kanun) → enrich'e mid.
    # kanun_no (no) korpus metadata'sında AYRI taşınır.
    maddeler, _gdip = enrich(arts, tree, mid, html_tables=ht, html_dipnotlar=hd, gercek_kanun_no=no)
    chunks = maddeler_to_chunks(maddeler, kanun_ad=ad, kanun_no=no)
    # FAZ 22f: atıf-alan işlenmiş-maddeler için yönlendirme chunk'ı ekle (maddeler_to_chunks eledi).
    if atif_madde:
        no_norm = str(no).strip().lstrip("0") or "0"    # atıf seti kanun_no'yu sıfır-dolgusuz tutar
        mevcut = {_norm_madde_no(c["metadata"]["madde_no"]) for c in chunks}
        for m in maddeler:
            mn = _norm_madde_no(m.no)
            if (no_norm, mn) in atif_madde and mn not in mevcut:
                yc = yonlendirme_chunk(m, kanun_ad=ad, kanun_no=no)
                if yc is not None:
                    chunks.append(yc)
                    mevcut.add(mn)
    return chunks


def _load_atif_madde():
    """FAZ 22f: unique_atiflar.json'dan {(kanun_no, norm_madde_no)} seti — yönlendirme chunk'ı
    YALNIZ atıf-alan işlenmiş-maddeler için üretilir (korpus şişmesini önler, modülerlik: opsiyonel).
    Dosya yoksa boş set (yönlendirme enjeksiyonu devre dışı, davranış eskisi gibi)."""
    p = pathlib.Path("unique_atiflar.json")
    if not p.exists():
        return set()
    out = set()
    for a in json.loads(p.read_text(encoding="utf-8")):
        if a.get("madde_no"):
            kno = str(a["kanun_no"]).strip().lstrip("0") or "0"
            out.add((kno, _norm_madde_no(a["madde_no"])))
    return out


async def main():
    LIMIT = int(os.environ.get("CORPUS_LIMIT", "0")) or None
    ONLY_MID = os.environ.get("CORPUS_MID", "").strip() or None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atif_madde = _load_atif_madde()
    if atif_madde:
        print(f"[FAZ22f] {len(atif_madde)} atıf-madde yüklendi (yönlendirme enjeksiyonu aktif)", flush=True)
    t0 = time.monotonic()
    async with MevzuatFetcher() as f:
        ids = await f.fetch_kanun_ids()                 # cache'ten 916 (no, mid, ad)
        if ONLY_MID:
            ids = [(no, mid, ad) for (no, mid, ad) in ids if mid == ONLY_MID]
        elif LIMIT:
            ids = ids[:LIMIT]
        print(f"{len(ids)} kanun işlenecek -> {OUT}", flush=True)
        n_chunk = 0
        n_kanun = 0
        with OUT.open("w", encoding="utf-8") as out:
            for no, mid, ad in ids:
                try:
                    chunks = await build_one(f, no, mid, ad, atif_madde=atif_madde)
                    for c in chunks:
                        out.write(json.dumps(c, ensure_ascii=False) + "\n")
                    n_chunk += len(chunks)
                    n_kanun += 1
                    if n_kanun % 25 == 0:
                        print(f"  {n_kanun}/{len(ids)} kanun, {n_chunk} chunk "
                              f"({time.monotonic()-t0:.0f}s) son: {no}", flush=True)
                except Exception as e:
                    print(f"  [HATA] {no} ({mid}): {type(e).__name__} {str(e)[:60]}", flush=True)
    print(f"\nKORPUS TAMAM: {n_kanun} kanun, {n_chunk} chunk "
          f"({time.monotonic()-t0:.0f}s) -> {OUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
