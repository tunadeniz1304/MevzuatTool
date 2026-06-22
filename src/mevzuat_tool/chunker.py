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
_NUM = r"\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?"
# Numaradan sonra opsiyonel: [dipnot] işaret(ler)i (ör. Gümrük "Madde 15[14][15] -") + nokta
# (ör. TCK "MADDE 61. -"). Tire şartı KORUNUR → "5. fıkra" / "5[3] fıkra" madde sayılmaz.
_MADDE = re.compile(rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM})(?:\[\d+\])*\s*\.?\s*-\s*")


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
        prefix = (m.group(1) or "").strip()
        number = m.group(2)
        no = f"{_canon_prefix(prefix)} {number}" if prefix else number
        out.append(Article(no=no, body=text[start:end].strip()))
    return out


def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]


def extract_status(body: str) -> str:
    return "mülga" if re.search(r"(?i)\(\s*mülga", body) else "yürürlükte"
