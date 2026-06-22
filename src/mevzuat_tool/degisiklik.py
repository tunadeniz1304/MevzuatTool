"""Değişiklik künyesi parser (Faz 3 follow-up #3).

Mevzuat gövdesindeki `(Değişik: 9/4/2003-4842/3 md.)` gibi inline künyeler ham metin
yerine yapısal `Degisiklik` kayıtlarına dönüştürülür. ham_metin her zaman korunur.
"""
import re
from dataclasses import dataclass

# Dış kalıp: (Değişik|Ek|Mülga ... : içerik) — kapsam = tip ile ":" arası serbest metin.
_KUNYE = re.compile(
    r"\((Değişik|Ek|Mülga|Ekleme|İptal)([^:)]*?):\s*([^)]*)\)"
)
_TARIH_KANUN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})-(\d+)/(\d+)\s*md\.")
_AYM = re.compile(r"Anayasa\s+Mahkemesi")

_TIP = {
    "Değişik": "degisik",
    "Ek": "ek",
    "Ekleme": "ek",
    "Mülga": "mulga",
    "İptal": "iptal",
}


@dataclass
class Degisiklik:
    tip: str
    tarih: str | None
    kanun_no: str | None
    madde: str | None
    kapsam: str | None
    ham_metin: str


def _iso_tarih(g, a, y) -> str:
    return f"{int(y):04d}-{int(a):02d}-{int(g):02d}"


def parse_kunyeler(body: str) -> list["Degisiklik"]:
    out: list[Degisiklik] = []
    for m in _KUNYE.finditer(body):
        anahtar, kapsam_raw, icerik = m.group(1), m.group(2), m.group(3)
        tip = _TIP.get(anahtar, "degisik")
        if anahtar != "İptal" and _AYM.search(icerik):
            tip = "iptal"
        kapsam = kapsam_raw.strip() or None
        tarih = kanun_no = madde = None
        tk = _TARIH_KANUN.search(icerik)
        if tk:
            tarih = _iso_tarih(tk.group(1), tk.group(2), tk.group(3))
            kanun_no = tk.group(4)
            madde = tk.group(5)
        out.append(Degisiklik(
            tip=tip, tarih=tarih, kanun_no=kanun_no, madde=madde,
            kapsam=kapsam, ham_metin=m.group(0),
        ))
    return out


def temizle_kunyeler(body: str) -> str:
    return re.sub(r"\s+", " ", _KUNYE.sub("", body)).strip()
