"""TAM KORPUS ÖLÇÜMÜ — 916 KANUN'u canlı çek + pipeline parse + confusion/P/R/F1.

Kararlar (kullanıcı):
  - Esas-kanun vs DEĞİŞİKLİK-PAKETİ ('bazı kanunlarda değişiklik...') AYRI raporlanır.
  - Ground-truth = bedesten article-tree; AMA Ek/Geçici/Mükerrer/suffix FP'leri SAHTE-FP olarak
    ayrılır (Faz B kanıtı: bunlar ağacın eksiği, pipeline doğru) → 'düzeltilmiş precision'.
  - Recall + düzeltilmiş-precision + metadata doğruluğu + parse-sağlık + tablo/dipnot kapsama.

Veri çekme: src/mevzuat_tool/fetch.py (MevzuatFetcher) — 429/Retry-After-uyumlu, cache'li,
deterministik, sıfır-kayıp. Her kanunu JSONL'e yaz (kesinti-güvenli, devam edilebilir).

Çalıştırma: .venv/Scripts/python.exe scripts/eval_corpus.py   (fetch.py pydantic'siz, .venv yeter)
"""
import asyncio, json, pathlib, re, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from mevzuat_tool.fetch import MevzuatFetcher
from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich
from mevzuat_tool.html_table import parse_tables
from mevzuat_tool.html_dipnot import parse_anchors
from mevzuat_tool.aralik import islenmis_aralik_maddeleri

IDS_FILE = pathlib.Path("data/raw/_kanun_ids.txt")
RESULTS  = pathlib.Path("data/raw/_corpus_results.jsonl")  # her kanun bir satır (devam-güvenli)
_LEVEL_KW = ("KİTAP","KISIM","BÖLÜM","AYIRIM","AYRIM","FASIL")
_PREFIX_NO = ("Ek","Geçici","Mükerrer")

def is_degisiklik_paketi(ad: str) -> bool:
    u = ad.upper()
    return ("DEĞİŞİKLİK YAPILMASINA" in u or "BAZI KANUNLARDA" in u
            or "DEĞİŞİKLİK YAPILMASI HAKKINDA" in u)

def serialize_tree(nodes) -> str:
    lines=[]
    def is_level(n):
        if n.madde_no is not None: return False
        t=(n.title or n.madde_baslik or "")
        return any(k in t.upper() for k in _LEVEL_KW)
    def walk(n, depth):
        ind="  "*depth
        if n.madde_no is not None:
            b=(n.madde_baslik or "").strip()
            b=re.sub(r"^\s*Madde\s*No:\s*\S+\s*-?\s*","",b).strip()
            t=f" - {b}" if b else ""
            lines.append(f"{ind}- Madde No: {n.madde_no}{t} (maddeId:{n.madde_id})")
        elif is_level(n):
            # label = bölüm/kısım NO ('ÜÇÜNCÜ BÖLÜM'); başlık = madde_baslik'in 'NO - ' sonrası
            # GERÇEK metni ('Haklar ve Yükümlülükler'). madde_baslik 'NO - BAŞLIK' biçiminde gelir;
            # ayraç yoksa (başlıksız bölüm) başlık = label (no). title (sadece no) tek başına
            # başlığı kaybediyordu — madde_baslik'ten kurtarılır.
            lbl=(n.title or n.madde_baslik or "BÖLÜM").strip()
            mb=(n.madde_baslik or "").strip()
            parts=mb.split(" - ", 1)
            baslik=parts[1].strip() if len(parts)>1 and parts[1].strip() else lbl
            lines.append(f"{ind}- {lbl} - {baslik} (maddeId:{n.madde_id})")
        cd=depth+1 if (n.madde_no is None and is_level(n)) else depth
        for ch in (n.children or []): walk(ch, cd)
    for n in nodes: walk(n,0)
    return "\n".join(lines)

def gt_set(nodes):
    s=set()
    def w(n):
        if n.madde_no is not None: s.add(str(n.madde_no).strip())
        for c in (n.children or []): w(c)
    for n in nodes: w(n)
    return s

FIELDS=[("madde_baslik","baslik"),("maddeId","maddeId"),("hiyerarsi_yolu","hiyerarsi_yolu")]

def is_fake_fp(no: str) -> bool:
    """Ek/Geçici/Mükerrer ön-ekli VEYA suffix (123/A) → ağacın atladığı, pipeline'ın doğru bulduğu."""
    return any(no.startswith(p) for p in _PREFIX_NO) or "/" in no

async def eval_one(f, no, mid, ad):
    """MevzuatFetcher (Retry-After'lı) ile bir kanunu çek + pipeline parse + metrik.
    Fetcher 429'u hallediyor; boş gelen = gerçek 0-madde (anlaşma onayı vb.)."""
    nodes = await f.fetch_tree(mid)
    html = await f.fetch_html(mid)
    content = f.html_to_text(html)
    tree=parse_tree(serialize_tree(nodes)); gt=gt_set(nodes)
    arts=split_articles(normalize_text(content))
    ht=parse_tables(html) if html else None
    hd=parse_anchors(html) if html else None
    maddeler,gdip=enrich(arts, tree, mid, html_tables=ht, html_dipnotlar=hd)
    pred=set(m.no for m in maddeler)
    tp,fp,fn = gt&pred, pred-gt, gt-pred
    fake_fp = {x for x in fp if is_fake_fp(x)}
    real_fp = fp - fake_fp
    # B: 'MADDE N ilâ M ... işlenmiştir' aralık maddeleri içeriksiz → yapay-FN (gerçek kayıp değil).
    aralik = islenmis_aralik_maddeleri(content)
    aralik_fn = fn & aralik          # FN'in içeriksiz-aralık kısmı (parse edilemez, kusur değil)
    gercek_fn = fn - aralik_fn       # asıl kayıp
    # düzeltilmiş precision: sahte-FP'leri TP gibi say (paydadan düşür)
    prec_raw = len(tp)/(len(tp)+len(fp)) if (tp or fp) else 1.0
    prec_adj = len(tp)/(len(tp)+len(real_fp)) if (tp or real_fp) else 1.0
    rec = len(tp)/(len(tp)+len(fn)) if (tp or fn) else 1.0           # ham (aralık dahil)
    rec_adj = len(tp)/(len(tp)+len(gercek_fn)) if (tp or gercek_fn) else 1.0  # aralık hariç (dürüst)
    # metadata (TP'de)
    byp={m.no:m for m in maddeler}; fld={f[0]:[0,0] for f in FIELDS}
    for n2 in tp:
        m=byp[n2]; node=tree.by_no.get(n2)
        if not node: continue
        for ma,ta in FIELDS:
            tv=getattr(node,ta,None)
            if tv is None: continue
            fld[ma][1]+=1
            if getattr(m,ma,None)==tv: fld[ma][0]+=1
    return {
        "no":no,"mid":mid,"ad":ad[:60],"deg":is_degisiklik_paketi(ad),
        "gt":len(gt),"pred":len(pred),"tp":len(tp),"fp":len(fp),
        "fake_fp":len(fake_fp),"real_fp":len(real_fp),"fn":len(fn),
        "aralik_fn":len(aralik_fn),"gercek_fn":len(gercek_fn),
        "prec_raw":round(prec_raw,4),"prec_adj":round(prec_adj,4),
        "rec":round(rec,4),"rec_adj":round(rec_adj,4),
        "fn_ex":sorted(gercek_fn)[:6],"real_fp_ex":sorted(real_fp)[:6],
        "fld":fld,"n_tablo":sum(len(m.tablolar) for m in maddeler),
        "n_dipnot":sum(len(m.dipnotlar) for m in maddeler),"n_madde":len(maddeler),
        "html_ok": bool(html), "gercek_bos": (len(gt)==0), "content_len": len(content),
    }

async def main():
    import os
    LIMIT=int(os.environ.get("CORPUS_LIMIT","0")) or None   # ilk N kanun (0=hepsi)
    rows_done={}
    if RESULTS.exists():
        for ln in RESULTS.read_text(encoding="utf-8").splitlines():
            try: r=json.loads(ln); rows_done[r["mid"]]=r
            except: pass
    t0=time.monotonic()
    async with MevzuatFetcher() as f:
        ids=await f.fetch_kanun_ids()   # cache'ten 916
        if LIMIT: ids=ids[:LIMIT]
        pending=[(no,mid,ad) for no,mid,ad in ids if mid not in rows_done]
        print(f"{len(ids)} kanun hedef, {len(rows_done)} tamam, {len(pending)} çekilecek", flush=True)
        out=RESULTS.open("a", encoding="utf-8"); done=0
        for no,mid,ad in pending:
            try:
                r=await eval_one(f,no,mid,ad)
                out.write(json.dumps(r,ensure_ascii=False)+"\n"); out.flush(); done+=1
                if done%25==0: print(f"  {done}/{len(pending)} ({time.monotonic()-t0:.0f}s) son: {no} gt={r['gt']}", flush=True)
            except Exception as e:
                print(f"  [HATA] {no} ({mid}): {type(e).__name__} {str(e)[:50]}", flush=True)
        out.close()
    n_done=len([1 for ln in RESULTS.read_text(encoding='utf-8').splitlines() if ln.strip()])
    print(f"\nÇEKİM TAMAM: {n_done}/{len(ids)} kanun ({time.monotonic()-t0:.0f}s) -> {RESULTS}", flush=True)

if __name__=="__main__":
    asyncio.run(main())
