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
# Gerçek apendiks gövdenin KUYRUĞUNDA olur (toplu tanım bloğu). Gövdenin ilk kısmında başlayan
# '[1]' apendiks DEĞİLDİR — gövde-içi değişiklik referansıdır (5335 M30 over-truncation bug:
# '[1]' 28. krk'da, ardından yoğun [2..5] referans → 3998ch gövde 28ch'a kesiliyordu). Apendiks
# başlangıcı gövdenin en az bu oranından SONRA olmalı.
# Gerçek apendiks: '[1]'den SONRASI neredeyse tümüyle dipnot tanımlarından ibarettir (her [n]
# kısa bir tanım metni). Bug deseninde (5335 M30) '[1]'den sonra hâlâ UZUN düz gövde-metni vardır
# (son '[n]' işaretinden sonra binlerce karakter). Ayırt edici: son işaretten sonraki kuyruk kısa
# olmalı; uzunsa bunlar gövde-içi referanstır, apendiks değil.
_MAX_SON_ISARET_KUYRUK = 400  # apendiks: son [n]'den sonra en fazla bu kadar metin (tek tanım boyu)
# Gerçek apendikste '[1]' ÖNCESİ kısım madde gövdesidir (anlamlı uzunlukta). Bug deseninde
# (102939 M11, 5335 M30) '[1]' gövdenin hemen başında (öncesi ~birkaç on karakter) ama toplam
# gövde uzun → '[1]' öncesi metin gövdenin küçük bir oranıysa VE öncesi mutlak olarak kısaysa,
# bu gövde-içi referanstır. Kısa gerçek-apendiks maddesinde ([1] öncesi kısa ama gövde de kısa)
# bu tetiklenmez çünkü toplam-uzunluk şartı var.
_MIN_ONCE_METIN = 300   # '[1]' öncesi madde-metni en az bu kadar olmalı (uzun gövdelerde)
_UZUN_GOVDE = 1200      # bu eşik üstü gövdelerde '[1]' öncesi metin _MIN_ONCE_METIN'den az olamaz


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
            # Konum kontrolü: uzun gövdede '[1]' öncesi madde-metni anlamlı olmalı. '[1]' gövdenin
            # hemen başındaysa (öncesi çok kısa) ama gövde uzunsa → gövde-içi referans (102939 M11:
            # '[1]'@40, gövde 2996 → kesilmemeli). Kısa gerçek-apendiks maddesi (gövde<_UZUN_GOVDE)
            # etkilenmez.
            if len(body) > _UZUN_GOVDE and pos < _MIN_ONCE_METIN:
                continue
            # Yoğunluk kontrolü: bu '[1]'den sonraki işaretlerin ortalama aralığı dar olmalı.
            blok = [p for p, _ in marks[k:]]
            araliklar = [blok[i + 1] - blok[i] for i in range(len(blok) - 1)]
            ort = sum(araliklar) / len(araliklar) if araliklar else 0
            if ort > _MAX_ORT_ARALIK:
                continue   # işaretler yayılmış → apendiks değil (madde-içi referanslar)
            # Kuyruk kontrolü: gerçek apendikste SON '[n]'den sonra yalnız o dipnotun (kısa) tanımı
            # kalır. Bug deseninde (5335 M30) son işaretten sonra hâlâ UZUN gövde-metni vardır →
            # işaretler gövde-içi referans, apendiks değil.
            if len(body) - blok[-1] > _MAX_SON_ISARET_KUYRUK:
                continue
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
