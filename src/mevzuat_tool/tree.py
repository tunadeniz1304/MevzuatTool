"""madde_tree metnini yapısal index'e ayrıştır (Faz 3 metadata join girdisi).

get_mevzuat_madde_tree çıktısı girintili bir ağaçtır:
    - DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
      - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
        - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
parse_tree bunu by_no lookup + ordered olay listesine çevirir.
"""
import re
from dataclasses import dataclass

_LEVEL_KW = ("KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "AYRIM")
_MADDE_RE = re.compile(
    r"Madde No:\s*(?P<no>\S+?)\s*-\s*(?P<title>.*?)\s*\(maddeId:(?P<mid>\d+)\)\s*$"
)
_LEVEL_RE = re.compile(
    r"(?P<label>.+?)\s*-\s*(?P<title>.*?)\s*\(maddeId:(?P<mid>\d+)\)\s*$"
)


def _clean_title(t: str) -> str | None:
    t = (t or "").strip().rstrip(":").strip()
    return t or None


@dataclass
class TreeNode:
    no: str
    baslik: str | None
    kisim_no: str | None
    kisim_baslik: str | None
    bolum_no: str | None
    bolum_baslik: str | None
    hiyerarsi_yolu: str | None
    maddeId: str | None


@dataclass
class TreeIndex:
    by_no: dict
    ordered: list


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
            kisim = next(((l, t) for (i, l, t) in stack if "KISIM" in l), (None, None))
            bolum = next(((l, t) for (i, l, t) in stack if "BÖLÜM" in l), (None, None))
            path_parts = [f"{l} - {t}" for (i, l, t) in stack]
            path_parts.append(f"Madde {no}")
            node = TreeNode(
                no=no, baslik=_clean_title(m.group("title")),
                kisim_no=kisim[0], kisim_baslik=kisim[1],
                bolum_no=bolum[0], bolum_baslik=bolum[1],
                hiyerarsi_yolu=" › ".join(path_parts), maddeId=m.group("mid"),
            )
            by_no[no] = node
            ordered.append({"kind": "madde", "node": node})
            continue

        if any(kw in content for kw in _LEVEL_KW):
            ml = _LEVEL_RE.match(content)
            if ml:
                label = ml.group("label").strip()
                title = _clean_title(ml.group("title"))
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                stack.append((indent, label, title))
                ordered.append({"kind": "level", "label": label, "title": title})
    return TreeIndex(by_no=by_no, ordered=ordered)
