# -*- coding: utf-8 -*-
"""altınset/madde_gen_prompted.jsonl -> `ilgi` alanında sızıntı ölçümü + temiz süzme.

Sızıntı = ilgi metni, kendi maddesini ele veren lexical ipucu içeriyor:
  1. kanun_no birebir ("2918 sayılı", "2918 s.")
  2. madde_no  ("5 inci madde", "17/c", "Madde 5", "5. madde")
  3. kanun adı (birebir, >=3 kelimelik anlamlı kısmı)

Çıktı:
  - Konsol: tam sayım + oranlar + tür kırılımı
  - data/gold/altinset_temiz.jsonl : sızıntısız kayıtlar (ilgi'si sorgu olarak kullanılabilir)
  - data/gold/altinset_sizintili.jsonl : sızıntılı kayıtlar (ayrı — sonra maskeleme için)
"""
import json
import re
import os
import unicodedata

SRC = "altınset/madde_gen_prompted.jsonl"
OUT_TEMIZ = "data/gold/altinset_temiz.jsonl"
OUT_SIZ = "data/gold/altinset_sizintili.jsonl"

# Türkçe küçük harfe indir (İ/I sorununu düzgün çöz)
def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()

# --- Madde-no sızıntı kalıpları ---
# "5 inci madde", "5 nci madde", "17 nci maddesi", "Madde 5", "5. madde", "5.madde",
# "17/c", "geçici 3 üncü madde", "ek 2 nci madde"
_MADDE_PATLARI = [
    re.compile(r"\bmadde\s*\d+", re.I),                       # Madde 5
    re.compile(r"\b\d+\s*[./]\s*[a-zçğıöşü]\b", re.I),        # 17/c
    re.compile(r"\b\d+\s*\.?\s*(inci|nci|ncı|uncu|üncü|ıncı)\s*madde", re.I),  # 5 inci madde
    re.compile(r"\b\d+\s*\.\s*madde", re.I),                  # 5. madde
    re.compile(r"\b(geçici|ek)\s*\d+", re.I),                 # geçici 3, ek 2
    re.compile(r"\bmükerrer\s*\d+", re.I),
]

def kanun_no_sizinti(ilgi_l, kanun_no):
    kn = str(kanun_no).strip()
    if not kn or not kn.isdigit():
        return False
    # "2918 sayılı", "2918 s.", "2918 numaralı", ya da sadece "2918" ardından Kanun
    if re.search(r"\b" + re.escape(kn) + r"\b\s*(sayılı|s\.|numaralı|say\.)", ilgi_l):
        return True
    if re.search(r"\b" + re.escape(kn) + r"\b\s*say", ilgi_l):
        return True
    return False

def madde_no_sizinti(ilgi):
    for p in _MADDE_PATLARI:
        if p.search(ilgi):
            return True
    return False

def kanun_adi_sizinti(ilgi_l, kanun_adi):
    """Kanun adının anlamlı (>=3 kelime, dolgu kelimeler hariç) bir dizisi ilgi'de birebir geçiyor mu?"""
    if not kanun_adi:
        return False
    ad_l = tr_lower(kanun_adi)
    kelimeler = [w for w in re.split(r"\s+", ad_l) if len(w) > 2]
    if len(kelimeler) < 3:
        # kısa adlar (ör. "harcırah kanunu") tam eşleşme ara
        return ad_l in ilgi_l
    # ardışık 3-gram penceresi
    for i in range(len(kelimeler) - 2):
        ucgram = " ".join(kelimeler[i:i + 3])
        if ucgram in ilgi_l:
            return True
    return False


def main():
    n = 0
    s_kanun = s_madde = s_ad = 0
    sizintili = 0
    temiz_kayit = []
    siz_kayit = []
    ilgi_yok = 0

    with open(SRC, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            ilgi = r.get("ilgi") or ""
            if not ilgi:
                ilgi_yok += 1
                continue
            ilgi_l = tr_lower(ilgi)

            f_kanun = kanun_no_sizinti(ilgi_l, r.get("kanun_no"))
            f_madde = madde_no_sizinti(ilgi)
            f_ad = kanun_adi_sizinti(ilgi_l, r.get("kanun_adi"))

            if f_kanun:
                s_kanun += 1
            if f_madde:
                s_madde += 1
            if f_ad:
                s_ad += 1

            if f_kanun or f_madde or f_ad:
                sizintili += 1
                r["_sizinti"] = {"kanun_no": f_kanun, "madde_no": f_madde, "kanun_adi": f_ad}
                siz_kayit.append(r)
            else:
                temiz_kayit.append(r)

    temiz = len(temiz_kayit)
    print("=" * 60)
    print(f"TOPLAM kayıt            : {n}")
    print(f"ilgi'si boş             : {ilgi_yok}")
    print(f"ilgi'si dolu (taranan)  : {n - ilgi_yok}")
    print("-" * 60)
    print(f"SIZINTILI (herhangi)    : {sizintili}  (%{100*sizintili/(n-ilgi_yok):.1f})")
    print(f"TEMIZ                   : {temiz}  (%{100*temiz/(n-ilgi_yok):.1f})")
    print("-" * 60)
    print("Sızıntı türü kırılımı (çakışabilir):")
    print(f"  kanun_no ifşası       : {s_kanun}  (%{100*s_kanun/(n-ilgi_yok):.1f})")
    print(f"  madde_no ifşası       : {s_madde}  (%{100*s_madde/(n-ilgi_yok):.1f})")
    print(f"  kanun adı ifşası      : {s_ad}  (%{100*s_ad/(n-ilgi_yok):.1f})")
    print("=" * 60)

    os.makedirs(os.path.dirname(OUT_TEMIZ), exist_ok=True)
    with open(OUT_TEMIZ, "w", encoding="utf-8") as out:
        for r in temiz_kayit:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_SIZ, "w", encoding="utf-8") as out:
        for r in siz_kayit:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Temiz  -> {OUT_TEMIZ} ({temiz} kayıt)")
    print(f"Sızıntı-> {OUT_SIZ} ({sizintili} kayıt)")


if __name__ == "__main__":
    main()
