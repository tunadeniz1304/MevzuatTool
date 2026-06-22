"""Dipnot apendiksi ayırma + [n]→madde bağı (Faz 3 follow-up #1, #2).

Mevzuat içeriğinin sonunda toplu dipnot tanımları (`[1] ... [2] ...`) son maddenin
gövdesine sızar. Bu modül kuyruktan ardışık dipnot bloğunu ayırır ve gövde içi `[n]`
işaretlerini ilgili dipnotlara bağlar.
"""
import re
from dataclasses import dataclass

_DIPNOT_SATIR = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
_ESIK = 3  # apendiks sayılması için min ardışık [n] satırı


@dataclass
class Dipnot:
    no: int
    text: str


def split_dipnot_apendiksi(body: str) -> tuple[str, list["Dipnot"]]:
    lines = body.splitlines()
    # Kuyruktan geriye, ardışık [n] satırlarının başlangıç indeksini bul.
    start = len(lines)
    i = len(lines) - 1
    while i >= 0:
        if _DIPNOT_SATIR.match(lines[i]):
            start = i
            i -= 1
        elif lines[i].strip() == "":
            i -= 1  # boş satırlar bloğu bölmez
        else:
            break
    blok = [l for l in lines[start:] if _DIPNOT_SATIR.match(l)]
    if len(blok) < _ESIK:
        return body, []
    dipnotlar = []
    for l in blok:
        m = _DIPNOT_SATIR.match(l)
        dipnotlar.append(Dipnot(no=int(m.group(1)), text=m.group(2).strip()))
    clean = "\n".join(lines[:start]).strip()
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
