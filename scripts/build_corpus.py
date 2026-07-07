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
from mevzuat_tool.corpus import maddeler_to_chunks

# serialize_tree eval_corpus'tan (TreeNode → bedesten serialize string → parse_tree girdisi)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "ec", str(pathlib.Path(__file__).resolve().parent / "eval_corpus.py"))
_ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ec)
serialize_tree = _ec.serialize_tree

OUT = pathlib.Path("data/corpus/korpus.jsonl")


async def build_one(f, no, mid, ad):
    """Bir kanunu çek + parse + chunk listesi döndür."""
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
    return maddeler_to_chunks(maddeler, kanun_ad=ad, kanun_no=no)


async def main():
    LIMIT = int(os.environ.get("CORPUS_LIMIT", "0")) or None
    ONLY_MID = os.environ.get("CORPUS_MID", "").strip() or None
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
                    chunks = await build_one(f, no, mid, ad)
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
