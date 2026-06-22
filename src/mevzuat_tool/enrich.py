"""Article + TreeIndex → zengin Madde (Faz 3 metadata join).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma (sonraki bölüm/madde başlığı) kırpılır.
"""
import re
from dataclasses import dataclass

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))

_HEADER_RE = re.compile(r"[A-ZÇĞİÖŞÜ]{2,}\s+(?:KİTAP|KISIM|BÖLÜM|AYIRIM|AYRIM)\b")


def _strip_bleed(body: str, next_title: str | None) -> str:
    cut = len(body)
    m = _HEADER_RE.search(body)
    if m:
        cut = min(cut, m.start())
    if next_title:
        idx = body.find(next_title)
        if idx != -1:
            cut = min(cut, idx)
    return body[:cut].strip()


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


def enrich(articles, tree):
    out = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None
    for i, art in enumerate(articles):
        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
        else:
            baslik, maddeId = None, None
        next_title = None
        if i + 1 < len(articles):
            nxt = tree.by_no.get(articles[i + 1].no)
            next_title = nxt.baslik if nxt else None
        body = _strip_bleed(art.body, next_title)
        out.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(body),
        ))
    return out
