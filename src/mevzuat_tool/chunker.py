import re
from dataclasses import dataclass

# Madde işareti ailesi — Türkçe büyük/küçük harf güvenli (i/İ için (?i) yerine char-class).
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
_FN = r"(?:\[\d+\])*"  # numara sonrası [dipnot] işaretleri (ör. Gümrük "Madde 15[14][15] -")

# Madde işareti iki dal halinde (capture grupları her ikisinde de: 1=prefix, 2=numara):
#  Dal A — karışık 'Madde' (en yaygın): ayraç = TİRE veya numaradan sonra '(' künyesi.
#    Tire şartı "5. fıkra"yı, paren-lookahead "madde 10 hükmü"yü (küçük-harf gövde atfı) eler.
#  Dal B — tam-büyük 'MADDE': ek olarak TİRESİZ büyük-harf başlık da kabul (Borçlar "MADDE 428
#    İşyerinin..."). Gerçek-veri kanıtı: tiresiz başlıklar HEP tam-büyük 'MADDE'; karışık 'Madde
#    32 Tebliğ' biçimi her zaman gövde-içi ATIF → yalnız tam-büyük dalda büyük-harf ayracı açılır,
#    böylece karışık-büyük atıflar yanlış-pozitif madde SAYILMAZ.
# Ortak son-ek: numara sonrası [dipnot] + opsiyonel nokta (TCK "MADDE 61. -").
_TAIL = rf"{_FN}\s*\.?"
_AYRAC_A = r"(?:\s*-\s*|\s+(?=[(]))"
_AYRAC_B = r"(?:\s*-\s*|\s+(?=[(]|[A-ZÇĞİÖŞÜ]))"
_MADDE = re.compile(
    rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM}){_TAIL}{_AYRAC_A}"
    rf"|\b({_PREFIX})?{_MADDE_FULL}\s+({_NUM}){_TAIL}{_AYRAC_B}"
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


@dataclass
class Article:
    no: str
    body: str


def split_articles(text: str) -> list[Article]:
    matches = list(_MADDE.finditer(text))
    out: list[Article] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Dal A (karışık 'Madde') grup 1,2 — Dal B (tam-büyük 'MADDE') grup 3,4.
        prefix = (m.group(1) or m.group(3) or "").strip()
        number = m.group(2) or m.group(4)
        no = f"{_canon_prefix(prefix)} {number}" if prefix else number
        out.append(Article(no=no, body=text[start:end].strip()))
    return out


def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]


def extract_status(body: str) -> str:
    return "mülga" if re.search(r"(?i)\(\s*mülga", body) else "yürürlükte"
