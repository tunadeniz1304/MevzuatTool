"""Article + TreeIndex → zengin Madde (Faz 3 metadata join + follow-up zenginleştirme).

Düz maddeler ağaçtan tam metadata alır; Geçici/Ek/Mükerrer maddeler tip flag'i +
konum-mirası alır. Gövde sonundaki yapısal sızma kırpılır. Ek olarak: dipnot apendiksi
ayrılır (#1), [n]→madde bağlanır (#2), değişiklik künyeleri yapısallaştırılır (#3),
fıkra/bent ağacı + bent yürürlük (#5, #6), benzersiz id (#7).
"""
import re
from dataclasses import dataclass, field

from mevzuat_tool.chunker import Article, extract_status
from mevzuat_tool.tree import TreeIndex
from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi, baglanan_dipnotlar
from mevzuat_tool.degisiklik import Degisiklik, parse_kunyeler, temizle_kunyeler
from mevzuat_tool.fikra import Fikra, parse_fikralar
from mevzuat_tool.ids import assign_ids

_TIPI = (("Geçici", "gecici"), ("Ek", "ek"), ("Mükerrer", "mukerrer"))


def _is_guvenilir_marker(mk: str) -> bool:
    """Bleed marker'ı güvenilir mi? Çok kısa / salt rakam-noktalama olanlar gövdede rastgele
    eşleşir (ör. '4' -> '442 sayılı'da kesim) → marker sayma."""
    mk = (mk or "").strip()
    if len(mk) < 5:                       # 'A.', 'I.', '4', 'a)' gibi kısa etiketler güvenilmez
        return False
    if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", mk):  # salt sayı/noktalama
        return False
    return True


_LEVEL_KW = ("KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "AYRIM", "FASIL")


def _is_level_marker(mk: str) -> bool:
    """Yapısal seviye başlığı mı (KISIM/BÖLÜM...)? Bunlar güçlü bleed sinyali — gövdede rastgele
    tekrar etmez, nerede eşleşirse kesilebilir. Madde-başlığı marker'ları ise zayıf (gövdede
    tekrar edebilir) → yalnız gövde kuyruğunda kesilir."""
    return any(kw in mk.upper() for kw in _LEVEL_KW)


def _bleed_markers(tree, no):
    """(level_markerlar, madde_baslik_markerlar) — ikisi farklı güven seviyesinde kullanılır."""
    idx = None
    for k, ev in enumerate(tree.ordered):
        if ev["kind"] == "madde" and ev["node"].no == no:
            idx = k
            break
    if idx is None:
        return [], []
    level, madde = [], []
    for ev in tree.ordered[idx + 1:]:
        if ev["kind"] == "level":
            for t in (ev["label"], ev["title"]):
                if t and _is_guvenilir_marker(t):
                    (level if _is_level_marker(t) else madde).append(t)
        else:
            if ev["node"].baslik and _is_guvenilir_marker(ev["node"].baslik):
                madde.append(ev["node"].baslik)
            break
    return level, madde


# Bleed yalnız gövdenin SONUNDA olur (split bir sonraki 'Madde N-'e kadar alır; sızan başlık
# gövde kuyruğuna gelir). İki güven seviyesi:
#  - LEVEL marker (KISIM/BÖLÜM): güçlü sinyal, gövdede rastgele tekrar etmez → her yerde kes.
#  - MADDE-başlığı marker ('Başkan', 'Arşiv araştırması'): zayıf, gövdede/bentte tekrar edebilir
#    → yalnız gövdenin son %15'inde ve sonrasında çok az metin kalıyorsa kes (gerçek kuyruk-bleed).
_MADDE_MARKER_SON_ORAN = 0.85   # madde-başlığı marker'ı yalnız gövdenin son %15'inde kesebilir


def _strip_bleed(body, level_markers, madde_markers):
    cut = len(body)
    for mk in level_markers:                # güçlü: her konumda kes
        idx = body.find(mk)
        if idx != -1:
            cut = min(cut, idx)
    esik = int(len(body) * _MADDE_MARKER_SON_ORAN)
    for mk in madde_markers:                # zayıf: yalnız son %15'te kes
        idx = body.rfind(mk)
        if idx != -1 and idx >= esik:
            cut = min(cut, idx)
    return body[:cut].strip()


# Gövde BAŞINDA içeriksiz-aralık yönlendirme notu: bir sonraki içeriksiz maddenin '11- (...
# yerine işlenmiştir.)' notu önceki maddenin gövdesine sızmış (chunker 'MADDE' kelimesiz '11-'i
# madde başı saymaz). Güvenli sinyal: gövde RAKAM-tire-paren ('11- (') ile BAŞLIYOR (gerçek fıkra
# '(1)' parenle başlar, karışmaz) + 'işlenmiştir'/'ilgili olup' bağlamı var. Yalnız baştaki bu
# notu (ve devamındaki zinciri) kırp; gerçek içerikli maddelere dokunma (6769 M165 '(1)'le başlar).
_BAS_ISLENMIS_ARALIK = re.compile(
    r"^\s*\d+\s*-\s*\([^)]*?(?:işlenmiş|ilgili\s+olup)[^)]*\)"
    r"(?:\s*MADDE\s+\d+\s+il[aâ]\s+\d+\s*-\s*\([^)]*\))*\s*",
    re.IGNORECASE,
)


def _strip_leading_islenmis_aralik(body):
    """Gövde başındaki içeriksiz-aralık yönlendirme notu zincirini kırp (yoksa olduğu gibi)."""
    return _BAS_ISLENMIS_ARALIK.sub("", body, count=1).strip()


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
    tablolar: list = field(default_factory=list)


def _madde_tipi(no: str) -> str:
    for prefix, tipi in _TIPI:
        if no.startswith(prefix + " "):
            return tipi
    return "asil"


def enrich(articles, tree, kanun_no, html_tables=None, html_dipnotlar=None):
    maddeler: list[Madde] = []
    global_dipnotlar: list[Dipnot] = []
    cur_kisim = (None, None)
    cur_bolum = (None, None)
    cur_path = None

    for art in articles:
        # 1. Dipnot apendiksini gövde kuyruğundan ayır (#1).
        # Yoğunluk kontrolü madde-içi yayılmış '[n]' referanslarını apendiks sanmaz (7174 M8).
        body_no_apdx, apdx = split_dipnot_apendiksi(art.body)
        global_dipnotlar.extend(apdx)

        tipi = _madde_tipi(art.no)
        node = tree.by_no.get(art.no)
        if node is not None and tipi == "asil":
            cur_kisim = (node.kisim_no, node.kisim_baslik)
            cur_bolum = (node.bolum_no, node.bolum_baslik)
            cur_path = node.hiyerarsi_yolu
            baslik, maddeId = node.baslik, node.maddeId
            level_mk, madde_mk = _bleed_markers(tree, art.no)
        else:
            baslik, maddeId = None, None
            level_mk, madde_mk = [], []

        # 2. Sızma kırpma — level marker güçlü (her yerde), madde-başlığı zayıf (yalnız kuyrukta).
        body = _strip_bleed(body_no_apdx, level_mk, madde_mk)
        # 2b. Gövde başına sızmış içeriksiz-aralık yönlendirme notunu ('11- (...işlenmiştir)') kırp.
        body = _strip_leading_islenmis_aralik(body)

        # 3. Değişiklik künyeleri (#3) + temiz gövde.
        kunyeler = parse_kunyeler(body)
        body_temiz = temizle_kunyeler(body)

        # 4. Fıkra/bent ağacı + bent yürürlük (#5, #6).
        fikralar = parse_fikralar(body)

        # 5. Madde yürürlüğü FIKRA AĞACINDAN: birden çok numaralı fıkra varsa, TÜMÜ mülga ise madde
        #    mülga; en az biri yürürlükte ise madde yürürlükte. (5651 M3: 1 fıkra iptal/çoğu aktif →
        #    yürürlükte; 7081 M10: tüm fıkralar mülga → mülga.) Numaralı fıkra yoksa (tek paragraf /
        #    künye-maddesi) konum-duyarlı metin tespitine düş (M9: künye-iptal → mülga).
        numarali = [f for f in fikralar if f.no is not None]
        if numarali:
            yurutluk = "mülga" if all(f.yurutluk == "mülga" for f in numarali) else "yürürlükte"
        else:
            yurutluk = extract_status(body, konum_duyarli=True)

        maddeler.append(Madde(
            no=art.no, body=body, madde_tipi=tipi, madde_baslik=baslik,
            kisim_no=cur_kisim[0], kisim_baslik=cur_kisim[1],
            bolum_no=cur_bolum[0], bolum_baslik=cur_bolum[1],
            hiyerarsi_yolu=cur_path, maddeId=maddeId,
            yurutluk=yurutluk,
            body_temiz=body_temiz, fikralar=fikralar,
            degisiklik_gecmisi=kunyeler,
        ))

    # İkinci geçiş: dipnot bağı + HTML enjeksiyonu.
    for m in maddeler:
        # Dipnot: HTML anchor varsa ASIL, yoksa regex fallback (mevcut).
        if html_dipnotlar is not None and m.no in html_dipnotlar:
            m.dipnotlar = html_dipnotlar[m.no]
        else:
            m.dipnotlar = baglanan_dipnotlar(m.body, global_dipnotlar)
        # Tablo: HTML markdown tablolar varsa tablolar alanına + body_temiz'e ekle.
        if html_tables is not None and m.no in html_tables:
            m.tablolar = html_tables[m.no]
            for md in m.tablolar:
                m.body_temiz = (m.body_temiz + "\n\n" + md).strip()

    # 6. Benzersiz id (#7).
    assign_ids(maddeler, kanun_no)

    return maddeler, global_dipnotlar
