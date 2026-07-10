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
_MADDE_FULL = r"MADDE"  # tam-büyük varyant (tiresiz başlıkların gerçek dizgisi)
_NUM = r"\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?"

# Madde işareti — chunker.py ile SİMETRİK iki dal (capture: A=1,2 / B=3,4).
# Numaradan sonra ara-gürültü tüketilir: <a> dipnot tag'leri, [n] işaretleri, boşluk +
# opsiyonel nokta (ör. Gümrük "Madde 15<a href=#_ftn14>[14]</a> -", TCK "Madde 61[3]. -").
#  Dal A — karışık 'Madde': ayraç = TİRE veya '(' künyesi (gövde-içi 'madde 10 hükmü' elenir).
#  Dal B — tam-büyük 'MADDE': ek olarak TİRESİZ büyük-harf başlık (Borçlar "MADDE 428 İşyerinin").
# Gerçek-veri: tiresiz başlıklar HEP tam-büyük 'MADDE'; karışık 'Madde 32 Tebliğ' her zaman
# gövde-içi ATIF → büyük-harf ayracı yalnız tam-büyük dalda açılır (karışık-büyük atıf FP'si elenir).
# re.DOTALL: \r\n/whitespace toleransı.
# Ara-gürültü: [n] işaretleri, HTML tag'leri, nokta, boşluk — hepsi numara ile ayraç arasında
# serbestçe tüketilir (ör. "61<a..>[3]</a>. -"). Ayraçtaki -\s- yerine boşlukları _ARA yutar.
_ARA = r"(?:\[\d+\]|<[^>]+>|\.|\s)*"
# Dal B tiresiz başlık lookahead'i: '(' künyesi VEYA TITLE-CASE kelime (Başharf büyük + küçük
# devam). Tümü-büyük kelime gövde-içi ATIF işaretidir → title-case şartı atıfları eler.
_AYRAC_A = r"(?:-|–|—|(?=[(]))"
_AYRAC_B = r"(?:-|–|—|(?=[(]|[A-ZÇĞİÖŞÜ][a-zçğıöşü]))"
_MADDE_ISARET = re.compile(
    rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM}){_ARA}{_AYRAC_A}"
    rf"|\b({_PREFIX})?{_MADDE_FULL}\s+({_NUM}){_ARA}{_AYRAC_B}",
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
        # Dal A (karışık 'Madde') grup 1,2 — Dal B (tam-büyük 'MADDE') grup 3,4.
        prefix = m.group(1) or m.group(3)
        number = m.group(2) or m.group(4)
        if prefix:
            no = f"{_canon_prefix(prefix.strip())} {number}"
        else:
            no = number
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        out[no] = html[start:end]
    return out
