"""madde_gen_prompted.jsonl -> kendi kendine yeten prompted_view.html.
Sol: madde (kanun + madde/birim + metin) | Sağ: özet + ilgi + mod rozetleri.
Filtreler: atif / kapsam / uzunluk + arama. Veri gömülü; file:// ile açılır."""
import html
import json
from pathlib import Path

SRC = Path("C:\\Users\\tuna9\\OneDrive\\Masaüstü\\MevzuatTool\\altınset\\madde_gen_prompted.jsonl")
OUT = Path("C:\\Users\\tuna9\\OneDrive\\Masaüstü\\MevzuatTool\\prompted_view.html")

rows = []
for l in SRC.read_text(encoding="utf-8").splitlines():
    if not l.strip():
        continue
    try:
        r = json.loads(l)
    except json.JSONDecodeError:
        continue
    var = f" ({r['variant']})" if r.get("variant") else ""
    rows.append({
        "ka": f"{r.get('kanun_adi','')} ({r.get('kanun_no','')})",
        "baslik": f"{r.get('kanun_adi','')} (no {r.get('kanun_no','')}) — Madde {r.get('madde_no','')}{var}",
        "birim": r.get("birim", ""),
        "t": r.get("madde_text") or "",
        "o": r.get("ozet") or "",
        "i": r.get("ilgi") or r.get("raw") or "",
        "atif": r.get("atif", "?"), "kapsam": r.get("kapsam", "?"), "uzunluk": r.get("uzunluk", "?"),
        "stray": r.get("atif_kontrol") or [],
    })

import collections
ca = collections.Counter(r["atif"] for r in rows)
ck = collections.Counter(r["kapsam"] for r in rows)
cu = collections.Counter(r["uzunluk"] for r in rows)
stats = (f"Toplam: {len(rows)} birim &nbsp;|&nbsp; atif: {dict(ca)} &nbsp;|&nbsp; "
         f"kapsam: {dict(ck)} &nbsp;|&nbsp; uzunluk: {dict(cu)}")

kanun_counts = collections.Counter(r["ka"] for r in rows)
kanun_opts = '<option value="">— tüm kanunlar ({}) —</option>'.format(len(kanun_counts))
for k, n in sorted(kanun_counts.items(), key=lambda x: -x[1]):
    kanun_opts += f'<option value="{html.escape(k)}">{html.escape(k)} · {n}</option>'

page = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>madde_gen prompted çıktıları</title>
<style>
 *{box-sizing:border-box} body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;background:#eef1f5;color:#1b2330}
 header{position:sticky;top:0;background:#16202e;color:#fff;padding:11px 18px;z-index:9;box-shadow:0 2px 8px rgba(0,0,0,.25)}
 header h1{margin:0 0 5px;font-size:16px} .stats{font-size:12px;opacity:.85}
 .ctl{margin-top:9px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
 .ctl input{flex:1;min-width:220px;padding:7px 10px;border:none;border-radius:6px;font-size:14px}
 .ctl select{padding:7px 10px;border:none;border-radius:6px;font-size:13px;max-width:320px}
 #more{display:block;margin:6px auto 24px;padding:9px 22px;border:none;border-radius:8px;background:#4f8cff;color:#fff;font-size:14px;cursor:pointer}
 .grp{display:flex;gap:4px;align-items:center} .grp b{font-size:11px;opacity:.7;margin-right:2px}
 .ctl button{padding:5px 10px;border:none;border-radius:14px;background:#33425a;color:#fff;cursor:pointer;font-size:12px}
 .ctl button.on{background:#4f8cff}
 #list{padding:14px;max-width:1600px;margin:0 auto}
 .row{display:grid;grid-template-columns:1fr 1fr;background:#fff;border-radius:9px;margin-bottom:13px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.09)}
 .col{padding:14px 16px} .col.l{border-right:1px solid #eef0f3;background:#fafbfd}
 .baslik{font-weight:600;color:#26344c;font-size:13.5px;margin-bottom:2px}
 .birim{display:inline-block;font-size:11px;background:#e7edf6;color:#3a5party;padding:1px 8px;border-radius:10px;margin-bottom:8px;color:#3a5a86}
 .txt{white-space:pre-wrap;font-size:12.5px;color:#3a4356;max-height:320px;overflow:auto}
 .badges{margin-bottom:9px;display:flex;gap:6px;flex-wrap:wrap}
 .b{font-size:11px;padding:2px 9px;border-radius:11px;font-weight:600}
 .b.atifli{background:#dbeafe;color:#1e57b0}.b.atifsiz{background:#e9e3ff;color:#5b3ea8}
 .b.tam{background:#d9f5e3;color:#1c7a44}.b.kismi{background:#fff0d6;color:#9a6a00}
 .b.kisa{background:#f0f0f0;color:#555}.b.orta{background:#f0f0f0;color:#555}.b.uzun{background:#f0f0f0;color:#555}
 .b.stray{background:#ffe0e0;color:#a11}
 .lbl{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:#8a93a3;margin:11px 0 3px} .lbl:first-of-type{margin-top:0}
 .ozet{color:#1b2330} .ilgi{color:#37415a}
 @media(max-width:780px){.row{grid-template-columns:1fr}.col.l{border-right:none;border-bottom:1px solid #eef0f3}}
</style></head><body>
<header>
 <h1>madde_gen — prompt-tabanlı çıktılar</h1>
 <div class="stats">__STATS__</div>
 <div class="ctl">
  <input id="q" placeholder="ara (kanun/madde/özet/ilgi)...">
  <select id="kanun">__KANUN_OPTS__</select>
  <span class="grp"><b>atıf</b><button data-f="atif" data-v="" class="on">hepsi</button><button data-f="atif" data-v="atifli">atıflı</button><button data-f="atif" data-v="atifsiz">atıfsız</button></span>
  <span class="grp"><b>kapsam</b><button data-f="kapsam" data-v="" class="on">hepsi</button><button data-f="kapsam" data-v="tam">tam</button><button data-f="kapsam" data-v="kismi">kısmi</button></span>
  <span class="grp"><b>uzunluk</b><button data-f="uzunluk" data-v="" class="on">hepsi</button><button data-f="uzunluk" data-v="kisa">kısa</button><button data-f="uzunluk" data-v="orta">orta</button><button data-f="uzunluk" data-v="uzun">uzun</button></span>
 </div>
</header>
<div id="list"></div>
<script>
const DATA=JSON.parse(__DATA__);
const PAGE=300;
let q="",kanun="",F={atif:"",kapsam:"",uzunluk:""},shownN=PAGE;
const esc=s=>(s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const list=document.getElementById("list");
function filtered(){
 return DATA.filter(r=>{
   if(kanun && r.ka!==kanun) return false;
   for(const k in F){ if(F[k] && r[k]!==F[k]) return false; }
   if(q){const s=(r.baslik+" "+r.o+" "+r.i+" "+r.t).toLowerCase(); if(!s.includes(q)) return false;}
   return true;});
}
function render(){
 let rows=filtered();
 const shown=rows.slice(0,shownN);
 list.innerHTML=shown.map((r,idx)=>{
   const sb=r.stray&&r.stray.length?`<span class="b stray">stray: ${esc(r.stray.join(','))}</span>`:"";
   return `<div class="row">
    <div class="col l"><div class="baslik">#${idx+1} · ${esc(r.baslik)}</div>
      <span class="birim">${esc(r.birim)}</span>
      <div class="txt">${esc(r.t)}</div></div>
    <div class="col r">
      <div class="badges"><span class="b ${r.atif}">${esc(r.atif)}</span><span class="b ${r.kapsam}">${esc(r.kapsam)}</span><span class="b ${r.uzunluk}">${esc(r.uzunluk)}</span>${sb}</div>
      <div class="lbl">Özet</div><div class="ozet">${esc(r.o)}</div>
      <div class="lbl">İlgi</div><div class="ilgi">${esc(r.i)}</div></div></div>`;
 }).join("");
 const info=`<div style="text-align:center;padding:8px;color:#888">${rows.length} sonuç · ${Math.min(shownN,rows.length)} gösteriliyor</div>`;
 const more=rows.length>shownN?`<button id="more">daha fazla göster (+${PAGE})</button>`:"";
 list.insertAdjacentHTML("beforeend", info+more);
 const mb=document.getElementById("more");
 if(mb) mb.onclick=()=>{shownN+=PAGE;render();};
}
function reset(){shownN=PAGE;render();}
document.getElementById("q").addEventListener("input",e=>{q=e.target.value.toLowerCase().trim();reset();});
document.getElementById("kanun").addEventListener("change",e=>{kanun=e.target.value;reset();});
document.querySelectorAll(".ctl button").forEach(b=>b.onclick=()=>{
 const f=b.dataset.f;
 b.parentNode.querySelectorAll("button").forEach(x=>x.classList.remove("on"));
 b.classList.add("on");F[f]=b.dataset.v;reset();});
render();
</script></body></html>"""

page = (page.replace("__STATS__", stats)
            .replace("__KANUN_OPTS__", kanun_opts)
            .replace("__DATA__", json.dumps(json.dumps(rows, ensure_ascii=False))))
OUT.write_text(page, encoding="utf-8")
print(f"yazıldı -> {OUT} | {len(rows)} kayıt | {OUT.stat().st_size/1e6:.1f} MB")