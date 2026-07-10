"""Dipnot #_ftnN anchor-bağı (Faz B #2 — HTML-kesin [n]->dipnot).

İşaret (gövdede): <a href="#_ftnN" name="_ftnrefN">[N]</a>
Tanım (kuyrukta): <a href="#_ftnrefN" name="_ftnN">[N]</a> + serbest metin.
parse_anchors işaretin N'sini tanımın N'sine bağlar (benzersiz id, regex'ten yapısal üstün).
"""
import html as _html
import re

from kanun.dipnot import Dipnot
from kanun.html_split import split_html_articles

# İşaret: name="_ftnrefN" (gövde içi atıf işareti).
_ISARET = re.compile(r'name="_ftnref(\d+)"', re.IGNORECASE)
# Tanım: name="_ftnN" anchor'ı + onu izleyen serbest metin (sonraki anchor veya </div>'e kadar).
_TANIM = re.compile(
    r'name="_ftn(\d+)"[^>]*>.*?</a>(?P<text>.*?)(?=<a [^>]*name="_ftn(?:ref)?\d+"|</div>|</td>|$)',
    re.DOTALL | re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = _html.unescape(_TAG.sub(" ", text)).replace("\xa0", " ")
    # baştaki [N] tekrarını ve boşlukları temizle
    text = re.sub(r"^\s*\[\d+\]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_anchors(html: str) -> dict[str, list]:
    # Tüm tanımları topla: no -> metin (belge genelinde, tanımlar kuyrukta).
    tanimlar: dict[int, str] = {}
    for m in _TANIM.finditer(html):
        no = int(m.group(1))
        txt = _clean(m.group("text"))
        if txt and no not in tanimlar:
            tanimlar[no] = txt

    out: dict[str, list] = {}
    for madde_no, parca in split_html_articles(html).items():
        bagli = []
        gorulen = set()
        for mk in _ISARET.finditer(parca):
            no = int(mk.group(1))
            if no in tanimlar and no not in gorulen:
                bagli.append(Dipnot(no=no, text=tanimlar[no]))
                gorulen.add(no)
        if bagli:
            out[madde_no] = bagli
    return out
