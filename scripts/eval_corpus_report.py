"""Tam korpus sonuç raporu — _corpus_results.jsonl'i oku, agregat metrik + segment analizi.

Segmentler: ESAS kanun vs DEĞİŞİKLİK-paketi.
Metrikler: micro recall, ham precision, DÜZELTİLMİŞ precision (sahte-FP filtreli),
metadata doğruluğu, parse-sağlık (boş/çöken kanun), tablo/dipnot kapsama.
"""
import json, pathlib

R=pathlib.Path("data/raw/_corpus_results.jsonl")
rows=[json.loads(l) for l in R.read_text(encoding="utf-8").splitlines() if l.strip()]

def agg(rs):
    gt=sum(r["gt"] for r in rs); pred=sum(r["pred"] for r in rs)
    tp=sum(r["tp"] for r in rs); fp=sum(r["fp"] for r in rs)
    ffp=sum(r["fake_fp"] for r in rs); rfp=sum(r["real_fp"] for r in rs)
    fn=sum(r["fn"] for r in rs)
    afn=sum(r.get("aralik_fn",0) for r in rs); gfn=sum(r.get("gercek_fn", r["fn"]) for r in rs)
    rec=tp/(tp+fn) if (tp+fn) else 1.0
    rec_adj=tp/(tp+gfn) if (tp+gfn) else 1.0
    praw=tp/(tp+fp) if (tp+fp) else 1.0
    padj=tp/(tp+rfp) if (tp+rfp) else 1.0
    return dict(n=len(rs),gt=gt,pred=pred,tp=tp,fp=fp,fake_fp=ffp,real_fp=rfp,fn=fn,
                aralik_fn=afn,gercek_fn=gfn,rec=rec,rec_adj=rec_adj,praw=praw,padj=padj)

esas=[r for r in rows if not r["deg"]]
deg =[r for r in rows if r["deg"]]
bos =[r for r in rows if r["gt"]==0]          # ağaçta hiç madde yok (parse-dışı)
crash=[r for r in rows if r["gt"]>0 and r["pred"]==0]  # ağaçta var ama pipeline 0 → çöküş

print("="*94)
print(f"TAM KORPUS — {len(rows)} KANUN parse edildi")
print("="*94)
print(f"  Esas kanun: {len(esas)}  |  Değişiklik-paketi: {len(deg)}  |  "
      f"Ağaçta 0-madde: {len(bos)}  |  Pipeline-çöküş (gt>0,pred=0): {len(crash)}")

def show(label, a):
    print(f"\n{label}  (n={a['n']})")
    print(f"  GT={a['gt']}  Pred={a['pred']}  TP={a['tp']}  "
          f"FN={a['fn']} (aralık={a['aralik_fn']} gerçek={a['gercek_fn']})  "
          f"FP={a['fp']} (sahte={a['fake_fp']} gerçek={a['real_fp']})")
    print(f"  recall_ham={a['rec']:.4f}  recall_DÜRÜST(aralık-FN hariç)={a['rec_adj']:.4f}")
    print(f"  precision_ham={a['praw']:.4f}  precision_DÜZELTİLMİŞ(sahte-FP hariç)={a['padj']:.4f}")

print("\n"+"="*94); print("A) MADDE-SET — micro confusion + P/R/F1"); print("="*94)
show("TÜM KORPUS", agg(rows))
show("ESAS KANUNLAR (değişiklik-paketleri hariç)", agg(esas))
show("DEĞİŞİKLİK-PAKETİ KANUNLAR", agg(deg))

# metadata
print("\n"+"="*94); print("B) METADATA ALAN DOĞRULUĞU (TP maddelerde, esas+değişiklik)"); print("="*94)
fa={"madde_baslik":[0,0],"maddeId":[0,0],"hiyerarsi_yolu":[0,0]}
for r in rows:
    for k,(m,t) in r["fld"].items(): fa[k][0]+=m; fa[k][1]+=t
print(f"{'Alan':16}{'Match':>9}{'Total':>9}{'Doğruluk%':>11}")
for k,(m,t) in fa.items():
    acc=f"{m/t*100:>10.2f}" if t else f"{'—':>10}"
    print(f"{k:16}{m:>9}{t:>9}{acc}")

# parse-sağlık
print("\n"+"="*94); print("C) PARSE-SAĞLIK"); print("="*94)
print(f"  Ağaçta 0-madde (içerik kanunu değil — anlaşma onayı vb.): {len(bos)}")
print(f"  Pipeline-çöküş (ağaçta madde var ama pipeline 0 yakaladı): {len(crash)}")
if crash:
    print("    çöken kanunlar (ilk 10):")
    for r in crash[:10]: print(f"      [{r['no']}] gt={r['gt']} {r['ad']}")
# düşük-recall kanunlar (gerçek FN > 0)
low=[r for r in rows if r["fn"]>0 and r["gt"]>0]
low.sort(key=lambda r: r["fn"], reverse=True)
print(f"\n  Gerçek FN'i olan kanun sayısı: {len(low)} (toplam {sum(r['fn'] for r in low)} kaçan madde)")
print("    en çok FN'li 12 kanun:")
for r in low[:12]:
    print(f"      [{r['no']}] gt={r['gt']} fn={r['fn']} rec={r['rec']:.3f} ör={r['fn_ex']} | {r['ad'][:35]}")

# kapsama
print("\n"+"="*94); print("D) FAZ B KAPSAMA (tablo + dipnot)"); print("="*94)
tot_t=sum(r["n_tablo"] for r in rows); tot_d=sum(r["n_dipnot"] for r in rows)
with_t=[r for r in rows if r["n_tablo"]>0]; with_d=[r for r in rows if r["n_dipnot"]>0]
html_ok=[r for r in rows if r.get("html_ok")]
print(f"  HTML alınan kanun: {len(html_ok)}/{len(rows)}")
print(f"  Toplam içerik tablosu: {tot_t} ({len(with_t)} kanunda)")
print(f"  Toplam bağlı dipnot: {tot_d} ({len(with_d)} kanunda)")

# gerçek-FP (şüpheli) olan kanunlar — düz numara FP (Ek/Geçici değil)
sfp=[r for r in rows if r["real_fp"]>0]
sfp.sort(key=lambda r: r["real_fp"], reverse=True)
print("\n"+"="*94); print("E) GERÇEK-FP (düz-numara, ağaçta yok — şüpheli uydurma)"); print("="*94)
print(f"  Gerçek-FP'i olan kanun: {len(sfp)} (toplam {sum(r['real_fp'] for r in sfp)} şüpheli FP)")
for r in sfp[:12]:
    print(f"      [{r['no']}] real_fp={r['real_fp']} ör={r['real_fp_ex']} | {r['ad'][:35]}")
