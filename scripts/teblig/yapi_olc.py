"""TEBLİĞ YAPI ÖLÇÜMÜ — parser yazmadan ÖNCE ham veriyi tanı (ADR-0014: "önce ölç, sonra yaz").

Cache'lenmiş tebliğ HTML + ağaçlarını tarar ve şu soruları SAYIYLA yanıtlar:
  1. Kaçında madde ağacı var / yok?
  2. Ağacı olanlarda BÖLÜM hiyerarşisi var mı (kanun gibi) yoksa düz madde listesi mi?
  3. Madde işareti hangi desende? ('MADDE 1 –', 'Madde 1-', 'N.', hiç yok...)
  4. Ağaçsız olanlarda metinde madde işareti var mı? (varsa metinden parse edilebilir)
  5. Gövde-sonu 'Ek-1/EK-2 form' kuyruğu ne kadar yaygın? (kanunun kanun-sonu cetvel eki muadili)
  6. Belge başında 'Kurum/Tebliğin Adı/Tebliğ No/RG Tarihi' metadata bloğu var mı?

Çıktı: konsol raporu + data/teblig/_yapi_raporu.json (parser tasarımının girdisi).

Çalıştırma:  python scripts/teblig/yapi_olc.py
"""
import json
import pathlib
import re
import sys
from collections import Counter

# Windows konsolu (cp1254) '→', 'ğ' gibi karakterlerde patlar → stdout'u UTF-8'e sar.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "src"))
from teblig.fetch import strip_html, parse_tree_json

RAW = pathlib.Path("data/teblig/raw")
OUT = pathlib.Path("data/teblig/_yapi_raporu.json")

# Madde işareti aileleri (kanun chunker'ından esinlendi ama tebliğe göre GENİŞ tutuldu —
# amaç sınıflandırma, çıkarım değil).
DESENLER = {
    "MADDE_N_tire":   re.compile(r"MADDE\s+\d+\s*[-–—]"),          # 'MADDE 1 –'  (yeni tebliğ)
    "Madde_N_tire":   re.compile(r"\bMadde\s+\d+\s*[-–—]"),        # 'Madde 1-'   (eski)
    "MADDE_N_duz":    re.compile(r"MADDE\s+\d+\s+[A-ZÇĞİÖŞÜ]"),    # 'MADDE 5 Yetki'
    "sira_N_nokta":   re.compile(r"(?m)^\s*\d+\.\s+[A-ZÇĞİÖŞÜ]"),  # '1. Giriş'   (serbest metin)
    "sira_N_tire":    re.compile(r"(?m)^\s*\d+\s*-\s*[A-ZÇĞİÖŞÜ]"),
    "roma_baslik":    re.compile(r"(?m)^\s*[IVX]+\s*[-.]\s"),
    "fikra_paren":    re.compile(r"\(\d+\)\s"),                     # '(1) '
}
# Kanun-sonu cetvel eki muadili: tebliğde 'Ek-1', 'EK-2', 'Ek 1:' form kuyruğu
EK_KUYRUK = re.compile(r"(?im)^\s*EK\s*[-–]?\s*\d+[A-Z]?\s*[:.]?\s*$")
# Belge başı metadata bloğu (kanunda YOK): 'Kurum ... Tebliğin Adı ... Resmî Gazete Tarihi'
BAS_METADATA = re.compile(r"Kurum.{0,80}Tebli[ğg]in\s*Ad[ıi]", re.DOTALL)


def _tree_ozet(mid: str):
    """(agac_var, madde_sayisi, bolum_var) — ağaç cache'inden."""
    p = RAW / f"treejson_{mid}.json"
    if not p.exists():
        return False, 0, False
    nodes = parse_tree_json(json.loads(p.read_text(encoding="utf-8")))
    madde = bolum = 0

    def gez(ns):
        nonlocal madde, bolum
        for n in ns:
            if n.madde_no is not None:
                madde += 1
            else:
                t = (n.title or n.madde_baslik or "").upper()
                if any(k in t for k in ("BÖLÜM", "KISIM", "KİTAP")):
                    bolum += 1
            gez(n.children)

    gez(nodes)
    return True, madde, bolum > 0


def main():
    if not RAW.exists():
        print(f"HATA: {RAW} yok. Önce çek: python -m teblig.fetch")
        return
    htmls = sorted(RAW.glob("html_*.html"))
    if not htmls:
        print(f"HATA: {RAW} içinde html_*.html yok.")
        return

    agacsiz_kayit = set()
    p_ag = RAW / "_agacsiz.txt"
    if p_ag.exists():
        agacsiz_kayit = set(p_ag.read_text(encoding="utf-8").split())

    sayac = Counter()
    desen_sayac = Counter()
    agacsiz_ama_maddeli = []
    agacli_madde_dagilim = []
    kayitlar = []

    for hp in htmls:
        mid = hp.stem.replace("html_", "")
        metin = strip_html(hp.read_text(encoding="utf-8", errors="replace"))
        agac_var, n_madde, bolum_var = _tree_ozet(mid)

        # hangi madde deseni baskın?
        bulunan = {ad: len(rx.findall(metin)) for ad, rx in DESENLER.items()}
        madde_desenleri = {k: v for k, v in bulunan.items()
                           if k.startswith(("MADDE", "Madde")) and v > 0}
        baskin = max(madde_desenleri, key=madde_desenleri.get) if madde_desenleri else None

        sayac["toplam"] += 1
        if agac_var:
            sayac["agacli"] += 1
            agacli_madde_dagilim.append(n_madde)
            if bolum_var:
                sayac["agacli_bolumlu"] += 1
        else:
            sayac["agacsiz"] += 1
            if baskin:
                sayac["agacsiz_ama_metinde_madde_var"] += 1
                agacsiz_ama_maddeli.append(mid)
            else:
                sayac["agacsiz_ve_maddesiz"] += 1   # <-- EN ZOR GRUP

        if baskin:
            desen_sayac[baskin] += 1
        else:
            desen_sayac["(madde isareti YOK)"] += 1

        if EK_KUYRUK.search(metin):
            sayac["ek_form_kuyrugu_var"] += 1
        if BAS_METADATA.search(metin[:2000]):
            sayac["bas_metadata_blogu_var"] += 1

        kayitlar.append({
            "mid": mid, "agac_var": agac_var, "agac_madde": n_madde,
            "bolum_var": bolum_var, "baskin_desen": baskin,
            "metin_uzunluk": len(metin), "desenler": bulunan,
        })

    t = sayac["toplam"]
    def yuzde(n):
        return f"{n:5d}  ({n/t*100:5.1f}%)" if t else "0"

    print("=" * 68)
    print(f"TEBLİĞ YAPI RAPORU — {t} belge (cache: {RAW})")
    print("=" * 68)
    print("\n1) MADDE AĞACI")
    print(f"   ağacı VAR              : {yuzde(sayac['agacli'])}")
    print(f"     · bölüm hiyerarşili  : {yuzde(sayac['agacli_bolumlu'])}  (kanun gibi)")
    print(f"   ağacı YOK              : {yuzde(sayac['agacsiz'])}")
    print(f"     · metinde madde VAR  : {yuzde(sayac['agacsiz_ama_metinde_madde_var'])}  → metinden parse edilebilir")
    print(f"     · madde işareti YOK  : {yuzde(sayac['agacsiz_ve_maddesiz'])}  ← EN ZOR GRUP (serbest metin)")

    print("\n2) BASKIN MADDE İŞARETİ")
    for ad, n in desen_sayac.most_common():
        print(f"   {ad:22s}: {yuzde(n)}")

    print("\n3) EK BULGULAR")
    print(f"   'Ek-N' form kuyruğu    : {yuzde(sayac['ek_form_kuyrugu_var'])}  (kanun-sonu cetvel eki muadili)")
    print(f"   başta metadata bloğu   : {yuzde(sayac['bas_metadata_blogu_var'])}  (kanunda YOK)")

    if agacli_madde_dagilim:
        d = sorted(agacli_madde_dagilim)
        print(f"\n4) AĞAÇLI TEBLİĞLERDE MADDE SAYISI")
        print(f"   medyan {d[len(d)//2]} | min {d[0]} | max {d[-1]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"ozet": dict(sayac), "desenler": dict(desen_sayac), "kayitlar": kayitlar},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDetay -> {OUT}")


if __name__ == "__main__":
    main()
