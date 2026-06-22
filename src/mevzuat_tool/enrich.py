"""Article + TreeIndex → zengin Madde (Faz 3 metadata join).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma (sonraki bölüm/madde başlığı) kırpılır.
"""
import re
from dataclasses import dataclass

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


@dataclass
class Madde:
    no: str
    body: str
    madde_tipi: str
    madde_baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None
    yurutluk: str


def _madde_tipi(no: str) -> str:
    for prefix, tipi in _TIPI:
        if no.startswith(prefix + " "):
            return tipi
    return "asil"
