"""HTML'i madde işaretiyle böl (Faz B paylaşılan temel).

Ham HTML tek belge; madde işareti '<span>...Madde N – ...' biçiminde tag-gömülü.
split_html_articles bunu {madde_no: html_parça} sözlüğüne böler. html_table ve
html_dipnot bunu ortak kullanır (DRY).
"""
import re

_MADDE_KW = r"[Mm][Aa][Dd][Dd][Ee]"
_PREFIX = (
    r"(?:"
    r"[Ee][Kk]"
    r"|[Gg][Ee][Çç][İIiı][Cc][İIiı]"
    r"|[Mm][Üü][Kk][Ee][Rr][Rr][Ee][Rr]"
    r")\s+"
)
_NUM = r"\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?"

# Madde işareti: isteğe bağlı önek (Ek/Geçici/Mükerrer), ardından 'Madde N'.
# Tag-gömülü olduğu için sadece metin desenini arar (etrafındaki tag'leri umursamaz).
# Numaradan sonra ara-gürültü tüketilir: <a> dipnot tag'leri, [n] işaretleri, boşluk
# (ör. Gümrük "Madde 15<a href=#_ftn14>[14]</a> -"). Sonra ayraç (chunker ile simetrik):
#   (a) TİRE  [-–—]  (ASCII/en-dash/em-dash)
#   (b) TİRESİZ ama hemen ardından '(' künyesi VEYA BÜYÜK-HARF başlık
#       (ör. Borçlar "MADDE 428 İşyerinin...", İş "Madde 87 (Mülga:...)").
# Tiresiz dalın büyük-harf/paren şartı, gövde-içi küçük-harf "madde 10 hükmü" atıflarını
# yanlış-pozitif madde saymaz (yan-etki guard'ı). re.DOTALL: \r\n/whitespace toleransı.
_ARA = r"(?:\[\d+\]|<[^>]+>|\s)*"
_AYRAC = r"(?:[-–—]|(?=[(]|[A-ZÇĞİÖŞÜ]))"
_MADDE_ISARET = re.compile(
    rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM})\.?{_ARA}{_AYRAC}",
    re.DOTALL,
)


def _canon_prefix(prefix: str) -> str:
    p = prefix.lower()
    if p.startswith("ek"):
        return "Ek"
    if p.startswith("g"):
        return "Geçici"
    if p.startswith("m"):
        return "Mükerrer"
    return prefix


def split_html_articles(html: str) -> dict[str, str]:
    matches = list(_MADDE_ISARET.finditer(html))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        prefix = m.group(1)
        number = m.group(2)
        if prefix:
            no = f"{_canon_prefix(prefix.strip())} {number}"
        else:
            no = number
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        out[no] = html[start:end]
    return out
