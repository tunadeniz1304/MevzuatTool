"""İçeriksiz 'MADDE N ilâ M' aralık-madde tespiti (eval metrik dürüstlüğü).

Değişiklik-paketlerinde 'MADDE 1 ilâ 64 - İlgili Kanunlara işlenmiştir' veya
'MADDE 9 ila 11- (... yerine işlenmiştir)' biçimi, N..M maddelerini TEK blokta özetler;
ayrı gövdeleri yoktur. Bedesten ağacı bunları ayrı sayar ama içerikte yok → yapay FN.
islenmis_aralik_maddeleri o aralıktaki tüm madde no'larını döndürür; eval bunları
gerçek-kayıp dışında tutar (recall paydası dürüstleşir). Pipeline'ın madde tanımına dokunmaz.
"""
import re

# 'MADDE N ilâ/ila (MADDE )?M' — N başlangıç, M bitiş; arada opsiyonel ikinci 'MADDE'.
_ARALIK = re.compile(r"MADDE\s+(\d+)\s+il[âa]\s+(?:MADDE\s+)?(\d+)", re.IGNORECASE)


def islenmis_aralik_maddeleri(text: str) -> set:
    """Metindeki tüm 'MADDE N ilâ M' aralıklarını bul; N..M arası tüm madde no'larını döndür."""
    out: set = set()
    for m in _ARALIK.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b:
            out.update(str(i) for i in range(a, b + 1))
    return out
