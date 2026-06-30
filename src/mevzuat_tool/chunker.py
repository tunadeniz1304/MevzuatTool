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
# Dal B tiresiz başlık lookahead'i: '(' künyesi VEYA TITLE-CASE kelime (Başharf büyük + küçük
# harf devam, ör. 'İşyerinin'). Tümü-büyük kelime ('KAPSAMINDA') gövde-içi ATIF işaretidir →
# title-case şartı bu atıfları eler (gerçek veri: tiresiz başlıklar title-case, atıflar all-caps).
_AYRAC_A = r"(?:\s*-\s*|\s+(?=[(]))"
_AYRAC_B = r"(?:\s*-\s*|\s+(?=[(]|[A-ZÇĞİÖŞÜ][a-zçğıöşü]))"
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


# Gövde-taşma: HTML'de sonraki maddenin BAŞLIĞI ('Amaç:') marker'dan önce gelince önceki
# maddenin gövde kuyruğuna yapışır. Desen: gövde sonu '[.!?] <1-5 Title-Case kelime>:'.
# Bu yalnız bir sonraki madde VARSA kırpılır (son maddede yutacak başlık yoktur; gerçek
# 'şunlardır:' liste-başı korunur). Gerçek veri: yutulan başlıklar 'Yürütme','Kapsam',
# 'Tanımlar' gibi gerçek madde başlıkları; liste-başı kelimesi (şöyledir/şunlardır) hiç görülmedi.
_BLEED_BASLIK = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî]*(?:\s+[\wçğıöşüâî]+){0,4}:\s*$"
)

# Seviye-başlık bleed: gövde kuyruğuna sızan 'X. BÖLÜM/KISIM/KİTAP/AYIRIM/FASIL ...' yapısal
# başlığı. Madde içinde yeni bir BÖLÜM/KISIM başlamaz — o, bir sonraki yapısal birimin başlığıdır
# (chunker level-başlıkları madde saymaz, gövdeye sızar). Cümle-sonu (.!?:) VEYA ')' sonrası
# sıra-sözcüğü ('İKİNCİ','ALTINCI','ON BİRİNCİ','SON') + BÖLÜM/KISIM görülünce ORADAN gövde sonuna
# kadar kırp. 'ikinci fıkra' gibi sıra+fıkra/kişi BÖLÜM/KISIM olmadığı için dokunulmaz.
# Notlar: (1) 'ON BİRİNCİ' gibi bileşik sıra; (2) 'altıncı' dizgi bozuğu 'ALTlNCI' (küçük-l) için
# 'ı'↔'l' toleransı; (3) lookbehind'a ')' eklendi ('...md.) İKİNCİ BÖLÜM'). Gerçek veri: 3402,7545,7071.
# Sıra göstergesi sözcüğü: 'İKİNCİ','ALTINCI','ON BİRİNCİ'/'ONBİRİNCİ' (boşluklu|bitişik),
# 'altıncı' dizgi bozuğu 'ALTlNCI' için ı↔l toleransı, 'SON'. (Roma-rakamı 'III.' biçimi ek
# karmaşıklık/risk getirip korpusta etki etmediği için kapsanmadı — kalan ~50 kopuk-dizgi
# varyantı bilinen-sınır.)
_SIRA = (r"(?:on|yirmi)?\s*(?:bir[il]nci|ik[il]nci|üçüncü|dördüncü|beşinci|alt[il]ncı|"
         r"yed[il]nci|sek[il]z[il]nci|dokuzuncu|onuncu)|son")
# Lookbehind: cümle-sonu (.!?:), ')' VEYA dipnot işareti (']' — 'yapılır.[2] ÜÇÜNCÜ BÖLÜM').
_SEVIYE_BASLIK_BLEED = re.compile(
    r"(?i)(?<=[.!?:)\]])\s+(?:" + _SIRA + r")\s+(?:bölüm|kısım|kitap|ayrım|ayirim|fasıl)\b.*$"
)


# Kanun-sonu 'işlenemeyen madde eki': '(TARİHLİ VE NNNN) SAYILI ... KANUNA İŞLENEMEYEN ...'
# başlığı. Başka kanunlarla bu kanuna eklenmek istenip işlenememiş maddelerin listesidir — bu
# kanunun maddesi DEĞİL. Buradan sonrası madde olarak parse edilmemeli (yoksa tekrarlı 'Geçici 1'
# hayalet chunk'lar doğar: 6183'te 5 kez). Başlığı tarihiyle birlikte kes (önceki maddenin
# gövdesine '... TARİHLİ VE NNNN' kuyruğu kalmasın). 'işlenemeyen' kelimesinin normal içerikte
# geçmesinden ('sisteme işlenemeyen kayıt') ayırmak için 'SAYILI ... KANUN[uA] İŞLENEMEYEN' şart.
_ISLENEMEYEN_EKI = re.compile(
    r"(?i)(?:\d+/\d+/\d+\s+)?(?:tarihli\s+ve\s+\d+\s+)?sayılı\s+.{0,40}?kanun[ua]?\s+işlenemeyen"
)


def split_articles(text: str) -> list[Article]:
    # Kanun-sonu işlenemeyen-madde ekini at (başka kanunlara ait; hayalet chunk kaynağı).
    eki = _ISLENEMEYEN_EKI.search(text)
    if eki:
        text = text[:eki.start()]
    matches = list(_MADDE.finditer(text))
    out: list[Article] = []
    for i, m in enumerate(matches):
        start = m.end()
        son_madde = i + 1 >= len(matches)
        end = matches[i + 1].start() if not son_madde else len(text)
        # Dal A (karışık 'Madde') grup 1,2 — Dal B (tam-büyük 'MADDE') grup 3,4.
        prefix = (m.group(1) or m.group(3) or "").strip()
        number = m.group(2) or m.group(4)
        no = f"{_canon_prefix(prefix)} {number}" if prefix else number
        body = text[start:end].strip()
        # Seviye-başlık ('X. BÖLÜM/KISIM ...') gövde kuyruğuna sızmışsa oradan sona kadar kırp.
        # (son madde dâhil — kanun-sonu 'Çeşitli ve Son Hükümler' başlığı son maddede de sızabilir)
        body = _SEVIYE_BASLIK_BLEED.sub("", body).strip()
        if not son_madde:  # sonraki maddenin (kolonlu) başlığı gövde kuyruğuna sızmışsa kırp
            body = _BLEED_BASLIK.sub("", body).strip()
        out.append(Article(no=no, body=body))
    return out


def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]


# Nitelikli/kısmi mülga: yalnızca BİR fıkra/bent mülga → tüm madde mülga DEĞİL (C1).
# Ör: '(Mülga son fıkra: ...)', '(Mülga ikinci fıkra: ...)', '(Mülga üçüncü cümle: ...)'.
_KISMI_MULGA = re.compile(
    r"(?i)\(\s*mülga\s+(?:son|birinci|ikinci|üçüncü|dördüncü|beşinci|altıncı|yedinci|"
    r"sekizinci|dokuzuncu|onuncu|\d+\s*(?:\.|inci|ıncı|uncu|üncü|nci))\s+"
    r"(?:fıkra|cümle|bent|paragraf)"
)
# Mülga/İptal markeri: parantez içinde 'Mülga' veya AYM 'İptal' (';' sonrası dâhil). 'İptal'
# ardından doğrudan ':' VEYA '(birinci/ikinci/.. ) fıkra/bent/madde:' gelebilir — '(İptal fıkra:)' /
# '(İptal birinci fıkra:)' AYM kararı iptal sinyalidir (Bug 5: 102929-Ek1, 105335-1). FAZ 1 (A1+A3):
# '(İptal bent:)' (7405 M38, 7354 M5/M6) ve '(İptal madde:)' (221 / 103326-1..5, boş iptal maddesi)
# de simetrik olarak iptal sinyalidir — 'fıkra' yanına 'bent|madde' eklendi.
_MULGA_MARKER = re.compile(
    r"(?i)\(\s*mülga|;\s*mülga|\(\s*iptal\s*:|;\s*iptal\s*:"
    r"|\(\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:"
    r"|;\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:")

# Madde 'açılış künye bölgesi': gövde başındaki ardışık künye parantezleri + aralarındaki boşluk.
# İki künye biçimi:
#  (a) anahtar kelime: '(Değişik:...)','(Ek:...)','(Mülga:...)','(İptal:...)','(Yeniden düzenleme:..)'
#  (b) TARİH/ATIF ile başlayan: '(2/1/1961- 203/2 md. ile gelen ... teselsül ettirilmiştir.; Mülga:..)'
#      — 657 Ek2/Geçici1 gibi maddelerde künye tarihle başlar; anahtar kelime aramak yetmez.
# Gerçek içerik (künye-olmayan metin VEYA '(1)' fıkra numarası) başlayınca biter. Fıkra '(1)'
# rakam+KAPANIŞ-paren'dir ')' → tarih-künye '(2/1/1961-...' slash'lı, karışmaz.
# E3 (FAZ 14): künyeler arası '[n]' dipnot işareti ('(Ek:...)[13] (Mülga:...)') künye-dizisini
# kırıyordu → '(Mülga:)' açılış-bölgesinde sayılmıyor, madde yanlış 'yürürlükte' (103912-Gecici14).
# Künyeden sonra opsiyonel '[n]' dipnot işaretine izin ver (B1/D1 dipnot dersinin yürürlük versiyonu).
_KUNYE_PAREN = re.compile(
    r"(?i)^\s*(?:\(\s*(?:"
    r"(?:değişik|ek|mülga|iptal|yeniden\s+düzenleme|mülga\s+ve\s+yeniden)"   # (a) anahtar kelime
    r"|\d+/\d+/\d+"                                                          # (b) tarih ile başlar
    r"|\d+\s+sayılı"                                                         # (c) 'NNNN sayılı ...'
    r")[^)]*\)(?:\s*\[\d+\])?\s*)+"                                          # ')' + opsiyonel '[n]' + boşluk
)


def _madde_basi_iptal(body: str) -> bool:
    """Mülga/İptal markeri maddenin AÇILIŞ KÜNYE bölgesinde mi (→ tüm madde mülga)?
    Gerçek içerik başladıktan sonra geliyorsa bir fıkraya aittir (→ madde yürürlükte)."""
    m = _KUNYE_PAREN.match(body)
    kunye_son = m.end() if m else 0
    mk = _MULGA_MARKER.search(body)
    return mk is not None and mk.start() < max(kunye_son, 1)


def extract_status(body: str, konum_duyarli: bool = False) -> str:
    """Yürürlük durumu. konum_duyarli=False (varsayılan): metinde Mülga/İptal varsa o birim mülga
    — fıkra/bent/alt-bent gibi TEK hüküm birimleri için (içindeki Mülga o birime aittir).
    konum_duyarli=True: MADDE seviyesi için — Mülga/İptal yalnız açılış künye bölgesindeyse tüm
    madde mülga; gerçek içerik başladıktan sonra geliyorsa bir fıkraya aittir (madde yürürlükte).
    Bu ayrım 5651 M3/M5/M6 gibi 'içerikte AYM iptali olan ama maddenin kendisi yürürlükte'
    vakalarını madde-geneline aşırı-yaymayı önler."""
    # Önce kısmi/nitelikli mülgayı ele (madde/birim yürürlükte kalır); yalnız o varsa yürürlükte say.
    kismi = list(_KISMI_MULGA.finditer(body))
    kalan = _KISMI_MULGA.sub("", body) if kismi else body
    mk = _MULGA_MARKER.search(kalan)
    if mk is None:
        return "yürürlükte"
    if not konum_duyarli:
        return "mülga"      # tek-hüküm birimi: içindeki Mülga/İptal o birimi mülga yapar
    # Madde seviyesi: marker açılış künye bölgesinde → tüm madde mülga; içerikte → fıkra iptali.
    return "mülga" if _madde_basi_iptal(kalan) else "yürürlükte"
