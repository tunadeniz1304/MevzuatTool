"""İçeriksiz 'MADDE N ilâ M' aralık-madde tespiti (eval metrik dürüstlüğü).

Değişiklik-paketlerinde 'MADDE 1 ilâ 64 - İlgili Kanunlara işlenmiştir' veya
'MADDE 9 ila 11- (... yerine işlenmiştir)' biçimi, N..M maddelerini TEK blokta özetler;
ayrı gövdeleri yoktur. Bedesten ağacı bunları ayrı sayar ama içerikte yok → yapay FN.
islenmis_aralik_maddeleri o aralıktaki tüm madde no'larını döndürür; eval bunları
gerçek-kayıp dışında tutar (recall paydası dürüstleşir). Pipeline'ın madde tanımına dokunmaz.
"""
import re

# (1) 'MADDE N ilâ/ila (MADDE )?M' — kapalı aralık N..M.
_ARALIK = re.compile(r"MADDE\s+(\d+)\s+il[âa]\s+(?:MADDE\s+)?(\d+)", re.IGNORECASE)

# (2) 'MADDE N- M- K- ...' gruplu-tire zinciri: 'MADDE N-' + ardından (sayı-tire) tekrarı.
#     Gerçek-veri kanıtı: ikincil no'ların gövdesi YOK (içeriksiz; hep aynı kanunu değiştirip
#     'yerine işlenmiştir'). Düzensiz boşluk toleranslı (ör. '12- 13- 14- 15-16-').
_GRUP = re.compile(r"MADDE\s+(\d+)\s*-\s*((?:\d+\s*-\s*)+)", re.IGNORECASE)

# (3) 'MADDE N ve M-' bağlaç ile iki madde.
_VE = re.compile(r"MADDE\s+(\d+)\s+ve\s+(\d+)\s*-", re.IGNORECASE)


def islenmis_aralik_maddeleri(text: str) -> set:
    """İçeriksiz 'aralık/gruplu' madde no'larını döndür (ilâ, gruplu-tire, 've').
    Eval bunları gerçek-kayıp dışında tutar (parse edilemez içerik = kusur değil)."""
    out: set = set()
    # (1) ilâ aralığı: N..M
    for m in _ARALIK.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b:
            out.update(str(i) for i in range(a, b + 1))
    # (2) gruplu-tire: N + tüm ikincil sayılar
    for m in _GRUP.finditer(text):
        out.add(m.group(1))
        out.update(re.findall(r"\d+", m.group(2)))
    # (3) 've': her iki no
    for m in _VE.finditer(text):
        out.add(m.group(1))
        out.add(m.group(2))
    return out
