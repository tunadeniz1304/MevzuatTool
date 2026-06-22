"""Article + TreeIndex → zengin Madde (Faz 3 metadata join).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma (sonraki bölüm/madde başlığı) kırpılır.
"""
from dataclasses import dataclass

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


def _bleed_markers(tree, no):
    """no'dan sonra content'e sızabilecek ağaç-otoriteli string'ler (sonraki level başlıkları
    + bir sonraki maddenin başlığı)."""
    idx = None
    for k, ev in enumerate(tree.ordered):
        if ev["kind"] == "madde" and ev["node"].no == no:
            idx = k
            break
    if idx is None:
        return []
    markers = []
    for ev in tree.ordered[idx + 1:]:
        if ev["kind"] == "level":
            if ev["label"]:
                markers.append(ev["label"])
            if ev["title"]:
                markers.append(ev["title"])
        else:  # madde → bir sonraki madde, başlığını ekle ve dur
            if ev["node"].baslik:
                markers.append(ev["node"].baslik)
            break
    return markers


def _strip_bleed(body, markers):
    cut = len(body)
    for mk in markers:
        idx = body.find(mk)
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
    for art in articles:
        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
            markers = _bleed_markers(tree, art.no)
        else:
            baslik, maddeId = None, None
            markers = []
        body = _strip_bleed(art.body, markers)
        out.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(body),
        ))
    return out
