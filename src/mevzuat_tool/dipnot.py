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
# Gerçek apendiks işaretleri YOĞUNDUR (kuyrukta toplu '[1] tanım. [2] tanım.', kısa aralıklı).
# Yayılmış işaretler (madde gövdesine binlerce karakter arayla dağılmış REFERANSLAR, tanım değil)
# apendiks DEĞİLDİR — eşiği aşan ortalama aralık over-split sinyalidir (7174 M8: ort ~5690 krk).
_MAX_ORT_ARALIK = 800  # apendiks bloğunda işaretler arası ortalama mesafe üst sınırı (krk)


@dataclass
class Dipnot:
    no: int
    text: str


def split_dipnot_apendiksi(body: str) -> tuple[str, list["Dipnot"]]:
    """Gövde kuyruğundaki dipnot apendiksini ayır.

    Apendiks başlangıç adayı '[1]' bulunduktan sonra, takip eden işaretlerin YOĞUN (kısa aralıklı,
    kuyrukta toplu blok) olması beklenir. İşaretler madde gövdesine geniş aralıkla yayılmışsa
    (her biri bir fıkranın değişiklik-dipnotu REFERANSI, tanım bloğu değil), apendiks değildir →
    gövde korunur (7174 M8 over-split bug: [1][2][3] ~5690 krk arayla dağılmış referanslar).
    """
    marks = [(m.start(), int(m.group(1))) for m in _ISARET_KONUM.finditer(body)]
    # Apendiks başlangıcı: no==1 olan ve ardından >=_ESIK işaretçi gelen ilk konum.
    start = None
    for k, (pos, no) in enumerate(marks):
        if no == 1 and len(marks) - k >= _ESIK:
            # Yoğunluk kontrolü: bu '[1]'den sonraki işaretlerin ortalama aralığı dar olmalı.
            blok = [p for p, _ in marks[k:]]
            araliklar = [blok[i + 1] - blok[i] for i in range(len(blok) - 1)]
            ort = sum(araliklar) / len(araliklar) if araliklar else 0
            if ort > _MAX_ORT_ARALIK:
                continue   # işaretler yayılmış → apendiks değil (madde-içi referanslar)
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
