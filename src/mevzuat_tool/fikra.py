"""Fıkra/bent ağacı + bent-seviyesi yürürlük (Faz 3 follow-up #5, #6).

Madde gövdesi iç içe `fikralar → bentler` yapısına bölünür. Fıkra: `(1)` (yeni stil) veya
numarasız tek paragraf. Bent (fıkra içinde): `a)` (harf) veya `1.` (numara). Her fıkra ve
bent kendi yürürlük durumunu `extract_status` ile alır.
"""
import re
from dataclasses import dataclass

from mevzuat_tool.chunker import extract_status

_FIKRA_BOL = re.compile(r"(?=\(\d+\)\s)")
_FIKRA_NO = re.compile(r"^(\(\d+\))")
_BENT_HARF = re.compile(r"(?m)(?=^\s*[a-zçğıöşü]\)\s)")
_BENT_NUM = re.compile(r"(?m)(?=^\s*\d+\.\s)")
_BENT_HARF_ISARET = re.compile(r"^\s*([a-zçğıöşü]\))")
_BENT_NUM_ISARET = re.compile(r"^\s*(\d+\.)")


@dataclass
class Bent:
    isaret: str
    text: str
    yurutluk: str


@dataclass
class Fikra:
    no: str | None
    text: str
    bentler: list[Bent]
    yurutluk: str


def _bentler(text: str) -> list[Bent]:
    # İlk eşleşen stil kazanır (karışık stil tek fıkrada varsayılmaz).
    harf = [p for p in _BENT_HARF.split(text) if _BENT_HARF_ISARET.match(p)]
    num = [p for p in _BENT_NUM.split(text) if _BENT_NUM_ISARET.match(p)]
    if harf:
        parcalar, isaret_re = harf, _BENT_HARF_ISARET
    elif num:
        parcalar, isaret_re = num, _BENT_NUM_ISARET
    else:
        return []
    out: list[Bent] = []
    for p in parcalar:
        p = p.strip()
        isaret = isaret_re.match(p).group(1)
        out.append(Bent(isaret=isaret, text=p, yurutluk=extract_status(p)))
    return out


def parse_fikralar(body: str) -> list["Fikra"]:
    body = body.strip()
    if not body:
        return []
    parcalar = [p.strip() for p in _FIKRA_BOL.split(body) if p.strip()]
    fikralar: list[Fikra] = []
    if not parcalar or not _FIKRA_NO.match(parcalar[0]):
        # Hiç (N) yok → tek numarasız fıkra.
        fikralar.append(Fikra(no=None, text=body, bentler=_bentler(body),
                              yurutluk=extract_status(body)))
        return fikralar
    for p in parcalar:
        mno = _FIKRA_NO.match(p)
        no = mno.group(1) if mno else None
        fikralar.append(Fikra(no=no, text=p, bentler=_bentler(p),
                              yurutluk=extract_status(p)))
    return fikralar
