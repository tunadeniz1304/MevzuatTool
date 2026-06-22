"""Dipnot apendiksi ayırma + [n]→madde bağı (Faz 3 follow-up #1, #2).

Mevzuat içeriğinin sonunda toplu dipnot tanımları (`[1] ... [2] ...`) son maddenin
gövdesine sızar. Bu modül kuyruktan ardışık dipnot bloğunu ayırır ve gövde içi `[n]`
işaretlerini ilgili dipnotlara bağlar.
"""
import re
from dataclasses import dataclass

_ISARET_KONUM = re.compile(r"\[(\d+)\]")
_ENTRY_BOL = re.compile(r"(?=\[\d+\]\s)")
_ENTRY_PARSE = re.compile(r"\[(\d+)\]\s*(.*)", re.DOTALL)
_ESIK = 3  # apendiks sayılması için min ardışık [n] işaretçisi


@dataclass
class Dipnot:
    no: int
    text: str


def split_dipnot_apendiksi(body: str) -> tuple[str, list["Dipnot"]]:
    marks = [(m.start(), int(m.group(1))) for m in _ISARET_KONUM.finditer(body)]
    # Apendiks başlangıcı: no==1 olan ve ardından >=_ESIK işaretçi gelen ilk konum.
    start = None
    for k, (pos, no) in enumerate(marks):
        if no == 1 and len(marks) - k >= _ESIK:
            start = pos
            break
    if start is None:
        return body, []
    clean = body[:start].strip()
    apendiks = body[start:]
    dipnotlar: list[Dipnot] = []
    for parca in _ENTRY_BOL.split(apendiks):
        parca = parca.strip()
        m = _ENTRY_PARSE.match(parca)
        if m:
            dipnotlar.append(Dipnot(no=int(m.group(1)), text=m.group(2).strip()))
    if len(dipnotlar) < _ESIK:
        return body, []
    return clean, dipnotlar


_ISARET = re.compile(r"\[(\d+)\]")


def baglanan_dipnotlar(body: str, tum_dipnotlar: list["Dipnot"]) -> list["Dipnot"]:
    by_no = {d.no: d for d in tum_dipnotlar}
    out: list[Dipnot] = []
    gorulen: set[int] = set()
    for m in _ISARET.finditer(body):
        no = int(m.group(1))
        if no in by_no and no not in gorulen:
            out.append(by_no[no])
            gorulen.add(no)
    return out
