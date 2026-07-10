"""İçerik <table> -> Markdown pipe-table (Faz B #4 tablo cebi).

Ham HTML'de vergi tarifeleri / ceza cetvelleri / kadro tabloları temiz <tr>/<td>.
Apendiks (değişiklik-künyesi) tabloları başlık-blacklist ile atlanır. stdlib html.parser
yerine basit regex (tablolar düzenli, irregular=0 — workflow kanıtı) + html.unescape.
"""
import html as _html
import re

from kanun.html_split import split_html_articles

_TABLE = re.compile(r"<table[^>]*>.*?</table>", re.DOTALL | re.IGNORECASE)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")

_APENDIKS_BASLIK = ("Değiştiren", "Yürürlüğe Giriş", "Değişiklik Yapan", "Resmî Gazete")


def _cell_text(cell_html: str) -> str:
    text = _TAG.sub("", cell_html)
    text = _html.unescape(text)
    text = text.replace("\xa0", " ")          # &nbsp; -> boşluk
    return re.sub(r"\s+", " ", text).strip()


def _is_apendiks(table_html: str) -> bool:
    text = _html.unescape(_TAG.sub(" ", table_html))
    return any(b in text for b in _APENDIKS_BASLIK)


def _table_to_markdown(table_html: str) -> str:
    rows = []
    for tr in _TR.findall(table_html):
        cells = [_cell_text(c) for c in _TD.findall(tr)]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]   # eksik hücreleri doldur
    lines = ["| " + " | ".join(rows[0]) + " |",
             "| " + " | ".join(["---"] * ncol) + " |"]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def parse_tables(html: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for no, parca in split_html_articles(html).items():
        mds = []
        for tbl in _TABLE.findall(parca):
            if _is_apendiks(tbl):
                continue
            md = _table_to_markdown(tbl)
            if md:
                mds.append(md)
        if mds:
            out[no] = mds
    return out
