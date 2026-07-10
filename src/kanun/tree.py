"""madde_tree metnini yapısal index'e ayrıştır (Faz 3 metadata join girdisi).

get_mevzuat_madde_tree çıktısı girintili bir ağaçtır:
    - DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
      - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
        - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
Seviye satırları AYRAÇSIZ da gelebilir (Medeni 4721: '- BİRİNCİ KİTAP (maddeId:...)',
gerçek başlık yok) — bu durumda başlık None tutulur (no-tekrarı YAPILMAZ). BAŞLANGIÇ
gibi no'suz tek-kelime kaplar da seviye sayılır (altındaki maddeler köksüz kalmasın).
parse_tree bunu by_no lookup + ordered olay listesine çevirir.
"""
import re
from dataclasses import dataclass

# Seviye anahtar kelimeleri. BAŞLANGIÇ no'suz tek-kelime kaptır; KİTAP/KISIM/BÖLÜM/AYIRIM
# 'SIRA NO + (opsiyonel başlık)' biçimindedir. FASIL eski kanunlarda AYIRIM eşdeğeri.
_LEVEL_KW = ("KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "AYRIM", "FASIL", "BAŞLANGIÇ")

_MADDE_RE = re.compile(
    r"Madde No:\s*(?P<no>\S+?)(?:\s*-\s*(?P<title>.*?))?\s*\(maddeId:(?P<mid>\d+)(?:\s*\|[^)]*)?\)\s*$"
)
# Seviye satırı: 'LABEL' VEYA 'LABEL - TITLE', ardından '(maddeId:...)'. Başlık (' - TITLE')
# OPSİYONEL — ayraçsız seviye satırı (Medeni) da eşleşir, title grubu None kalır.
_LEVEL_RE = re.compile(
    r"(?P<label>.+?)(?:\s+-\s+(?P<title>.*?))?\s*\(maddeId:(?P<mid>\d+)(?:\s*\|[^)]*)?\)\s*$"
)


def _clean_title(t: str | None) -> str | None:
    t = (t or "").strip().rstrip(":").strip()
    return t or None


@dataclass
class TreeNode:
    no: str
    baslik: str | None
    kitap_no: str | None
    kitap_baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    ayirim_no: str | None
    ayirim_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None


@dataclass
class TreeIndex:
    by_no: dict
    ordered: list


def _ara(stack, *anahtarlar):
    """Stack'te (indent, label, title) içinde label'ı verilen anahtarlardan birini içeren
    EN YAKIN (en derin) seviyeyi (no, baslik) olarak döndür; yoksa (None, None)."""
    for (_i, label, title) in reversed(stack):
        if any(k in label.upper() for k in anahtarlar):
            return (label, title)
    return (None, None)


def parse_tree(text: str) -> TreeIndex:
    by_no: dict = {}
    ordered: list = []
    stack: list = []  # (indent, label, title) ancestor yığını

    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)
        if not stripped.startswith("- "):
            continue
        content = stripped[2:]

        m = _MADDE_RE.match(content)
        if m:
            no = m.group("no")
            kitap = _ara(stack, "KİTAP")
            kisim = _ara(stack, "KISIM")
            bolum = _ara(stack, "BÖLÜM")
            ayirim = _ara(stack, "AYIRIM", "AYRIM", "FASIL")
            # hiyerarşi yolu: başlık varsa 'LABEL - TITLE', yoksa sadece 'LABEL' (no-tekrarı yok).
            path_parts = [f"{l} - {t}" if t else l for (_i, l, t) in stack]
            path_parts.append(f"Madde {no}")
            node = TreeNode(
                no=no, baslik=_clean_title(m.group("title")),
                kitap_no=kitap[0], kitap_baslik=kitap[1],
                kisim_no=kisim[0], kisim_baslik=kisim[1],
                bolum_no=bolum[0], bolum_baslik=bolum[1],
                ayirim_no=ayirim[0], ayirim_baslik=ayirim[1],
                hiyerarsi_yolu=" › ".join(path_parts), maddeId=m.group("mid"),
            )
            by_no[no] = node
            ordered.append({"kind": "madde", "node": node})
            continue

        if any(kw in content.upper() for kw in _LEVEL_KW):
            ml = _LEVEL_RE.match(content)
            if ml:
                label = ml.group("label").strip()
                # Başlık YOKSA None (no-tekrarı yapma). Ayraçsız seviye satırı title=None gelir.
                title = _clean_title(ml.group("title"))
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                # BAŞLANGIÇ düzleştirme: bedesten KİTAP'ı BAŞLANGIÇ'ın altına girintiler ama hukuken
                # KİTAP onun KARDEŞİDİR. Gerçek atalık seviyesi (KİTAP/KISIM/...) gelince stack'teki
                # BAŞLANGIÇ kabını düşür → KİTAP altı maddeler BAŞLANGIÇ'ı taşımaz.
                if "BAŞLANGIÇ" not in label.upper():
                    while stack and "BAŞLANGIÇ" in stack[-1][1].upper():
                        stack.pop()
                stack.append((indent, label, title))
                ordered.append({"kind": "level", "label": label, "title": title})
    return TreeIndex(by_no=by_no, ordered=ordered)
