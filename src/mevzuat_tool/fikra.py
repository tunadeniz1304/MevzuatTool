"""Fıkra/bent/alt-bent ağacı + seviye-bazlı yürürlük (Faz 3 follow-up #5, #6).

Madde gövdesi iç içe `fikralar → bentler → alt_bentler` yapısına bölünür. Resmî hiyerarşi:
Fıkra: `(1)` (yeni stil) veya numarasız tek paragraf. Bent (fıkra içinde): `a)` (harf) veya
`1.` (numara). Alt-bent (bent içinde): `1)` (parantez-rakam). Her seviye kendi yürürlük
durumunu `extract_status` ile alır.
"""
import re
from dataclasses import dataclass, field

from mevzuat_tool.chunker import extract_status

_FIKRA_BOL = re.compile(r"(?=\(\d+\)\s)")
_FIKRA_NO = re.compile(r"^(\(\d+\))")
# Boşluk-sınırlı (normalize-sonrası tek-satır metin) bent işaretçileri:
_BENT_NUM_ISARET = re.compile(r"(?:(?<=\s)|^)(\d+)\.\s")
_BENT_HARF_ISARET = re.compile(r"(?:(?<=\s)|^)([a-zçğıöşü])\)\s")
# Alt-bent işaretçisi (resmî: bent içinde '1)' '2)' parantez-rakam). Bent harfi 'a)' ile
# karışmaz çünkü bu RAKAM+yarım-paren; sıralı 1,2,3 koşusu aranır (yıl/atıf gürültüsünü ele).
_ALTBENT_ISARET = re.compile(r"(?:(?<=\s)|^)(\d+)\)\s")


@dataclass
class AltBent:
    isaret: str
    text: str
    yurutluk: str


@dataclass
class Bent:
    isaret: str
    text: str
    yurutluk: str
    alt_bentler: list = field(default_factory=list)


@dataclass
class Fikra:
    no: str | None
    text: str
    bentler: list
    yurutluk: str


def _alt_bentler(text: str) -> list:
    # Alt-bent: bent içinde SIRALI 1,2,3,... ile '1)' (parantez-rakam). Sıralı koşu şartı
    # yıl/madde atıflarını ('7)' tek başına) eler — _bentler'in numara mantığıyla aynı.
    seq, beklenen = [], 1
    for m in _ALTBENT_ISARET.finditer(text):
        if int(m.group(1)) == beklenen:
            seq.append(m)
            beklenen += 1
    if len(seq) < 2:
        return []
    out = []
    for i, m in enumerate(seq):
        bas = m.start()
        son = seq[i + 1].start() if i + 1 < len(seq) else len(text)
        parca = text[bas:son].strip()
        out.append(AltBent(isaret=m.group(0).strip(), text=parca, yurutluk=extract_status(parca)))
    return out


def _kes(text, matches):
    """matches: re.Match listesi (sıralı). Her işaretçiden bir sonrakine kadar olan dilim."""
    out = []
    for i, m in enumerate(matches):
        bas = m.start()
        son = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        isaret = m.group(0).strip()  # "1." | "a)"
        parca = text[bas:son].strip()
        out.append(Bent(isaret=isaret, text=parca, yurutluk=extract_status(parca),
                        alt_bentler=_alt_bentler(parca)))
    return out


def _bentler(text: str) -> list:
    # Numara bentleri: yalnız 1,2,3,... ile başlayan SIRALI koşu (yıl/madde atıflarını ele).
    num_all = list(_BENT_NUM_ISARET.finditer(text))
    num_seq = []
    beklenen = 1
    for m in num_all:
        if int(m.group(1)) == beklenen:
            num_seq.append(m)
            beklenen += 1
    harf = list(_BENT_HARF_ISARET.finditer(text))
    # İlk-stil-kazanır (kod-sırası; spec 'karışık stil tek fıkrada varsayılmaz').
    if harf:
        return _kes(text, harf)
    if len(num_seq) >= 2:
        return _kes(text, num_seq)
    return []


def parse_fikralar(body: str) -> list:
    body = body.strip()
    if not body:
        return []
    parcalar = [p.strip() for p in _FIKRA_BOL.split(body) if p.strip()]
    if not parcalar or not _FIKRA_NO.match(parcalar[0]):
        return [Fikra(no=None, text=body, bentler=_bentler(body),
                      yurutluk=extract_status(body))]
    out = []
    for p in parcalar:
        mno = _FIKRA_NO.match(p)
        no = mno.group(1) if mno else None
        out.append(Fikra(no=no, text=p, bentler=_bentler(p), yurutluk=extract_status(p)))
    return out
