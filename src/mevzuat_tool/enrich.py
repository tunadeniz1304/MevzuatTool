"""Article + TreeIndex → zengin Madde (Faz 3 metadata join + follow-up zenginleştirme).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma kırpılır. Ek olarak: dipnot apendiksi
ayrılır (#1), [n]→madde bağlanır (#2), değişiklik künyeleri yapısallaştırılır (#3),
fıkra/bent ağacı + bent yürürlük (#5, #6), benzersiz id (#7).
"""
from dataclasses import dataclass, field

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex
from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi, baglanan_dipnotlar
from mevzuat_tool.degisiklik import Degisiklik, parse_kunyeler, temizle_kunyeler
from mevzuat_tool.fikra import Fikra, parse_fikralar
from mevzuat_tool.ids import assign_ids

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


def _bleed_markers(tree, no):
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
        else:
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
    id: str = ""
    body_temiz: str = ""
    fikralar: list = field(default_factory=list)
    degisiklik_gecmisi: list = field(default_factory=list)
    dipnotlar: list = field(default_factory=list)


def _madde_tipi(no: str) -> str:
    for prefix, tipi in _TIPI:
        if no.startswith(prefix + " "):
            return tipi
    return "asil"


def enrich(articles, tree, kanun_no: str):
    maddeler: list[Madde] = []
    global_dipnotlar: list[Dipnot] = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None

    for art in articles:
        # 1. Dipnot apendiksini gövde kuyruğundan ayır (#1).
        body_no_apdx, apdx = split_dipnot_apendiksi(art.body)
        global_dipnotlar.extend(apdx)

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

        # 2. Sızma kırpma (mevcut mantık) — apendiks ayrılmış gövde üzerinde.
        body = _strip_bleed(body_no_apdx, markers)

        # 3. Değişiklik künyeleri (#3) + temiz gövde.
        kunyeler = parse_kunyeler(body)
        body_temiz = temizle_kunyeler(body)

        # 4. Fıkra/bent ağacı + bent yürürlük (#5, #6).
        fikralar = parse_fikralar(body)

        maddeler.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=extract_status(body),
            body_temiz=body_temiz, fikralar=fikralar,
            degisiklik_gecmisi=kunyeler,
        ))

    # 5. [n]→madde bağı (#2) — global dipnot listesi tamamlandıktan sonra.
    for m in maddeler:
        m.dipnotlar = baglanan_dipnotlar(m.body, global_dipnotlar)

    # 6. Benzersiz id (#7).
    assign_ids(maddeler, kanun_no)

    return maddeler, global_dipnotlar
