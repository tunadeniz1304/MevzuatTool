"""HTML'i madde işaretiyle böl (Faz B paylaşılan temel).

Ham HTML tek belge; madde işareti '<span>...Madde N – ...' biçiminde tag-gömülü.
split_html_articles bunu {madde_no: html_parça} sözlüğüne böler. html_table ve
html_dipnot bunu ortak kullanır (DRY).
"""
import re

# Madde işareti: 'Madde N -' veya 'Madde N –' (en-dash), whitespace/\r\n toleranslı.
# Tag-gömülü olduğu için sadece metin desenini arar (etrafındaki tag'leri umursamaz).
_MADDE_ISARET = re.compile(
    r"[Mm][Aa][Dd][Dd][Ee]\s+(\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?)\s*[-–]",
    re.DOTALL,
)


def split_html_articles(html: str) -> dict[str, str]:
    matches = list(_MADDE_ISARET.finditer(html))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        no = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        out[no] = html[start:end]
    return out
