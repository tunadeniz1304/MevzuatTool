"""GÖVDE DOĞRULUĞU — pipeline'ın madde gövdesi resmî tek-madde gövdesiyle örtüşüyor mu?

Ground-truth gövde: get_article_content(madde_id) (bedesten resmî tek-madde metni).
Pipeline gövde: enrich() çıktısındaki Madde.body.
Metrik: resmî gövdenin anlamlı kelimelerinin kaçı pipeline gövdesinde var (içerik-recall) +
ilk-cümle örtüşmesi. Düşük örtüşme = gövde eksik/karışık/taşmış.
"""
import asyncio, re, sys, pathlib
sys.path.insert(0,"src")
from kanun.fetch import MevzuatFetcher, _wrap, _decode_base64, strip_html, _post_with_retry
from kanun.normalize import normalize_text
from kanun.chunker import split_articles
from kanun.tree import parse_tree
from kanun.enrich import enrich

# eval_corpus'tan serialize_tree'yi yeniden kullan
import importlib.util
spec=importlib.util.spec_from_file_location("ec","scripts/eval_corpus.py")
ec=importlib.util.module_from_spec(spec); spec.loader.exec_module(ec)

LAWS={"7528":"Öğretmenlik","6698":"KVKK","6754":"Bilirkişilik"}

def kelimeler(t):
    t=normalize_text(t).lower()
    # madde-no/başlık gürültüsünü at, anlamlı kelimeler (>=4 harf)
    return set(w for w in re.findall(r"[a-zçğıöşü]{4,}", t))

def ilk_cumle(t):
    t=normalize_text(t)
    m=re.search(r"\(1\)\s*(.{15,80})", t)   # ilk fıkra metni
    return (m.group(1)[:60] if m else t[:60]).lower().strip()

async def madde_ids(f, mid):
    tree=await f.fetch_tree(mid)
    out={}
    def w(n):
        if n.madde_no is not None: out[str(n.madde_no).strip()]=n.madde_id
        for c in (n.children or []): w(c)
    for n in tree: w(n)
    return out

async def main():
    async with MevzuatFetcher() as f:
        ids={l.split("\t")[0]:l.split("\t")[1] for l in pathlib.Path("data/kanun/raw/_kanun_ids.txt").read_text(encoding="utf-8").splitlines() if len(l.split("\t"))>=2}
        for no,lbl in LAWS.items():
            mid=ids[no]
            # pipeline
            html=await f.fetch_html(mid)
            content=f.html_to_text(html)
            tree=parse_tree(ec.serialize_tree(await f.fetch_tree(mid)))
            maddeler,_=enrich(split_articles(normalize_text(content)), tree, mid)
            byno={m.no:m for m in maddeler}
            # resmî gövde ground-truth (her madde_id için get_article_content)
            mids=await madde_ids(f, mid)
            tam=kismi=dusuk=yok=0; ornek=[]
            for mno,mdid in list(mids.items()):
                if mno not in byno:
                    yok+=1; continue
                body=await _post_with_retry(f._client,"/getDocumentContent",
                      _wrap({"documentType":"MADDE","id":mdid}), f._rate)
                resmi=strip_html(_decode_base64((body.get("data") or {}).get("content","")))
                pk=kelimeler(byno[mno].body); rk=kelimeler(resmi)
                if not rk: continue
                ortusme=len(pk & rk)/len(rk)   # resmî kelimelerin kaçı pipeline'da
                if ortusme>=0.95: tam+=1
                elif ortusme>=0.80: kismi+=1
                else:
                    dusuk+=1
                    if len(ornek)<3: ornek.append((mno, round(ortusme,2), resmi[:50]))
            print(f"[{lbl} {no}] {len(mids)} madde: tam(>=95%)={tam} kısmi(80-95%)={kismi} DÜŞÜK(<80%)={dusuk} pipeline'da-yok={yok}")
            for mno,o,r in ornek: print(f"    DÜŞÜK Madde {mno} örtüşme={o}: resmî='{r}...'")
asyncio.run(main())
