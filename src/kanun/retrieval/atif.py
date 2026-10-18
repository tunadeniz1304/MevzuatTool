# -*- coding: utf-8 -*-
"""Atıf ayrıştırıcı — "5237 sayılı Kanun m. 141/2-a" → yapısal atıf (kanun / madde / fıkra / bent).

DETERMİNİSTİK: düzenli ifade + küçük kısaltma/ad tablosu. Model/LLM YOK (ADR-0019). Çıktı korpus
gösterimine eşlenir: madde_no `141` · `123/A` · `Geçici 1` · `Ek 3` · `Mükerrer 298` (chunker.py),
fıkra no `(N)` (fikra.py), bent işareti `a)` / `1.`. Eşleştirme (madde var mı, hangi kanun) burada
YAPILMAZ — `atif_getir.py` korpus indeksinde çözer.

Tanınan biçimler — büyük/küçük harf, İ/I/ı/i ve Türkçe karakter duyarsız (`katla`):
  Kanun : '5237 sayılı Kanun', '5237 sayılı Türk Ceza Kanunu', '5237 sayılı TCK', '5237 s. K.',
          '5237 numaralı Kanun', 'Kanun No: 5237', kısaltma (TCK, İİK, KVKK ... — `KISALTMALAR`),
          yaygın ad ('Türk Ceza Kanunu', 'Medeni Kanun', 'İş K.' — `ADLAR`), 'Anayasa' / 'AY';
          verilirse korpustaki 916 resmî kanun adı (`kanun_adlari`, ör. 'İmar Kanunu').
  Madde : 'm. 141', 'md. 141', 'mad. 141', 'madde 141', '141. madde', '141 inci maddesi',
          '48/A maddesi', '220/6. maddesi', '4/1-a maddesi', 'Geçici 1' / 'geçici madde 1' /
          'geçici 1 inci madde', 'Ek 3' / 'ek madde 3',
          'Mükerrer 298', kanundan hemen sonra yalın numara ('TCK 141', 'HMK 119/1-ğ').
  Fıkra : 'f. 2', 'fıkra 2', '2. fıkra', '2 nci fıkrası', 'ikinci fıkrası', 'son fıkrası',
          '(2) numaralı fıkrası', madde/fıkra '141/2', Roma rakamı '166/II'.
  Bent  : 'b. a', 'bent a', '(a) bendi', 'a bendi', 'a) bendi', '(1) numaralı bendi', '3. bendi',
          satır içi '141/2-a', '119/1(ğ)', Roma fıkradan sonra '25/I-b', '25/II-e'.

ATIF = KANUN + MADDE (ikisi birden şart). Yalnız kanun ('5237 sayılı Kanun') ya da yalnız madde
('madde 5') atıf DEĞİLDİR → doğal dil modu. Yanlış-pozitif kapıları (doğal dil sorgusu atıf sanılmasın):
  - 'N madde' / 'N maddede' / 'ek 3 madde' (sıra eki YOK) bir SAYIMDIR ('TCK'daki 5 madde değişti') →
    madde sayılmaz; sıra eki ('141. madde', '141 inci'), harf eki ('48/A maddesi') ya da iyelik
    ('141 maddesi') şart.
  - Numaradan hemen sonra başka bir belge numarası ('5 sayılı', '2/3/2024', '1.5', '%') gelirse madde
    değildir; yalın numarada ('TCK 2') ve önekli numarada ('ek 3') süre/sayım sözcüğü de ('2 yıl', '3 ay',
    '4 çocuk', '18 yaşındaki') ve miktar/tarih devamı da ('1 Haziran 2005', '2-5 yıl', "30'dan fazla",
    '1/3 oranında'), 'madde 3' biçiminde fiziksel miktar da ('3 ton', '10 gramdan') madde numarasını
    düşürür. Açık 'm.' / 'md.' kısaltması güçlü sinyaldir: 'İş K. m. 53 yıllık izin' atıftır
    (`_MADDE_DEGIL_SONRA`).
  - 'NNNN sayılı' ardından KHK / Cumhurbaşkanlığı Kararnamesi / karar / yönetmelik / tebliğ / liste /
    cetvel / Resmî Gazete gelirse kanun değildir ('375 sayılı KHK', '2023/15 sayılı karar').
  - Madde sözünden hemen önce kanun dışı belge geliyorsa ('Yönetmeliğin 5. maddesi', "KHK'nın ek 9.
    maddesi", 'Sözleşmenin 6. maddesi') madde o belgenindir, sorgudaki bir kanuna bağlanmaz.
  - 'Anayasa Mahkemesi', 'anayasal' kanun sayılmaz; 'AY' yalnız büyük harfle yazılmışsa Anayasa'dır
    ('ay' = ay/süre). 'İş K.' 'iş kazası'nda tetiklenmez; 'Deniz İş Kanunu' (854) ve 'Basın İş Kanunu'
    (5953) İş Kanunu (4857) sayılmaz.
  - 'eski/mülga/önceki' ya da yabancı ülke ('İsviçre', 'Alman' ...) nitelemeli ad/kısaltma bugünkü kanun
    değildir ('eski İş Kanunu' 1475'tir, 4857 değil; 'İsviçre Borçlar Kanunu' 6098 değil) → atıf çıkmaz,
    maddesi başka kanuna da bağlanmaz (`_NITELEME`). Numarayla yazım geçerlidir ('765 sayılı eski TCK').

Belirsiz slash eki: '359/a' hem harfli madde (359/A) hem 359. maddenin (a) bendi; '166/I' hem harfli
madde hem Roma rakamıyla 1. fıkra olabilir. Ayrıştırıcı birincil yorumu (harfli madde) + alternatifleri
(`Atif.alternatifler`) üretir; seçim korpusa bakan çözücünün işidir (atif_getir.py).

Bilinen sınırlar: alt-bent ('359/a-1'nin '1'i) okunmaz; aralık açılmaz ('TCK m. 141-145' yalnız 141'i,
'5237 sayılı Kanunun 141-145. maddeleri' yalnız uçları 141 ve 145'i yakalar); numara sıralamasında kanun
önce geliyorsa ('TCK'nın 141 ve 142. maddeleri', 'TCK m. 141 ve m. 142') ikisi de, sonra geliyorsa
('141 ve 142. maddeler TCK') yalnız son numara yakalanır; kanunun
maddeden SONRA geldiği yazım ('m. 141 TCK') tek atıfta çalışır ama karışık sırada en yakın ÖNCEKİ
kanun seçilir; değiştiren kanun ('TCK'nın 6545 sayılı Kanunla değişik 141. maddesi') sahip sayılmaz.
"""
import re
from dataclasses import dataclass, field

SON_FIKRA = -1          # 'son fıkra' — çözücü maddenin son fıkrasını seçer

# ---- katlama: harf duyarsız, uzunluk koruyan eşleme ----------------------------------------
# Düzenli ifadeler katlanmış metinde çalışır; her karakter TEK karaktere eşlendiği için konumlar
# orijinal sorguyla birebir hizalıdır (bent harfi 'ç'/'ı' gibi ayrımlar orijinalden okunur).
_KATLAMA = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ç": "c", "ç": "c", "Ğ": "g", "ğ": "g",
    "Ö": "o", "ö": "o", "Ü": "u", "ü": "u", "Â": "a", "â": "a", "Î": "i", "î": "i", "Û": "u",
    "û": "u", "’": "'", "‘": "'", "`": "'", "´": "'", "–": "-", "—": "-", "‐": "-", "‑": "-",
    " ": " ", "\t": " ", "\n": " ", "\r": " ",
})


def katla(metin):
    """Türkçe-güvenli küçük harf + aksan/diakritik katlama ('İİK' → 'iik', 'Geçici' → 'gecici').
    Uzunluk korunur (konumlar orijinal metinle hizalı)."""
    t = metin.translate(_KATLAMA)
    k = t.lower()
    if len(k) != len(metin):          # lower() ile genişleyen nadir karakter → tek tek, genişletmeden
        k = "".join(c.lower() if len(c.lower()) == 1 else c for c in t)
    return k


def tr_kucuk(s):
    """Türkçe küçük harf (I→ı, İ→i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_buyuk(s):
    """Türkçe büyük harf (i→İ, ı→I)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def kanun_no_norm(no):
    """Kanun numarası karşılaştırma biçimi: boşluksuz, baştaki sıfırlar atılmış ('0213' → '213')."""
    s = str(no).strip()
    return s.lstrip("0") or s


# ---- madde numarası: korpus gösterimi <-> (tip, numara) anahtarı --------------------------
_TIP_ETIKET = {"gecici": "Geçici", "ek": "Ek", "mukerrer": "Mükerrer"}
_KORPUS_MADDE = re.compile(r"(?:(gecici|ek|mukerrer)\s+)?0*([0-9]+)(?:\s*/\s*(\S+))?")


def madde_anahtari(madde_no):
    """Korpus madde_no → (tip, numara). 'Geçici 1' → ('gecici', '1'); '123/a' → ('asil', '123/A');
    'Mükerrer 298' → ('mukerrer', '298'). Tip, madde_no önekinden okunur (madde_tipi alanından değil;
    yönlendirme chunk'ı da kendi numarasıyla bulunsun)."""
    s = " ".join(str(madde_no).split())
    m = _KORPUS_MADDE.fullmatch(katla(s))
    if m is None:
        return ("asil", tr_buyuk(s.replace(" ", "")))
    numara = m.group(2)
    if m.group(3):
        numara += "/" + tr_buyuk(s[m.start(3):m.end(3)])
    return (m.group(1) or "asil", numara)


def madde_no_goster(tip, numara):
    """(tip, numara) → korpus gösterimi ('gecici', '1') → 'Geçici 1'."""
    return numara if tip == "asil" else f"{_TIP_ETIKET[tip]} {numara}"


# ---- tablolar -------------------------------------------------------------------------------
# Kısaltma tablosu: (katlanmış kısaltma, kanun_no, kanun adı). Seçim ölçütü: Yargıtay/Danıştay karar
# dilinde ve doktrinde YERLEŞİK, tek anlamlı kısaltmalar; numaralar resmî kanun numaralarıdır. Görevde
# istenen 15 kısaltma + vergi/usul hukukunda sık geçen birkaç ek. Bilinçli kararlar:
#   - 'TMK' → 4721 (Türk Medeni Kanunu). Ceza hukukunda 'TMK' Terörle Mücadele K. (3713) için de
#     kullanılır; özel hukuktaki baskın kullanım seçildi. 3713 numarayla ('3713 sayılı') bulunur.
#   - 'KVK' → 5520 (Kurumlar Vergisi K., vergi hukukundaki yerleşik kullanım); Kişisel Verilerin
#     Korunması Kanunu 'KVKK' (6698). İkisi ayrı kısaltma olduğu için çakışmaz (uzun-önce eşleşir).
#   - 'BK' / 'MK' / 'HUMK' / 'CMUK' bilerek YOK: mülga eski kanunlarla (818 / 743 / 1086 / 1412)
#     karışır. Adla yazılan 'Borçlar Kanunu' / 'Medeni Kanun' bugünkü 6098 / 4721'e gider (ADLAR).
#   - 'AY' (Anayasa) yalnız orijinal metinde BÜYÜK harfle yazılmışsa (küçük 'ay' süre birimidir).
#   - 'İK' yok (insan kaynakları ile karışır); İş Kanunu 'İş K.' / 'İşK' / 'İş Kanunu' ile tanınır.
KISALTMALAR = (
    ("tck", "5237", "Türk Ceza Kanunu"),
    ("cmk", "5271", "Ceza Muhakemesi Kanunu"),
    ("tmk", "4721", "Türk Medeni Kanunu"),
    ("tbk", "6098", "Türk Borçlar Kanunu"),
    ("hmk", "6100", "Hukuk Muhakemeleri Kanunu"),
    ("iik", "2004", "İcra ve İflas Kanunu"),
    ("ttk", "6102", "Türk Ticaret Kanunu"),
    ("vuk", "213", "Vergi Usul Kanunu"),
    ("gvk", "193", "Gelir Vergisi Kanunu"),
    ("kvk", "5520", "Kurumlar Vergisi Kanunu"),
    ("kdvk", "3065", "Katma Değer Vergisi Kanunu"),
    ("aatuhk", "6183", "Amme Alacaklarının Tahsil Usulü Hakkında Kanun"),
    ("dmk", "657", "Devlet Memurları Kanunu"),
    ("kvkk", "6698", "Kişisel Verilerin Korunması Kanunu"),
    ("iyuk", "2577", "İdari Yargılama Usulü Kanunu"),
    ("fsek", "5846", "Fikir ve Sanat Eserleri Kanunu"),
    ("tkhk", "6502", "Tüketicinin Korunması Hakkında Kanun"),
    ("kmk", "634", "Kat Mülkiyeti Kanunu"),
    ("otvk", "4760", "Özel Tüketim Vergisi Kanunu"),
    ("dvk", "488", "Damga Vergisi Kanunu"),
    ("evk", "1319", "Emlak Vergisi Kanunu"),
    ("vivk", "7338", "Veraset ve İntikal Vergisi Kanunu"),
    ("mtvk", "197", "Motorlu Taşıtlar Vergisi Kanunu"),
    ("bgk", "2464", "Belediye Gelirleri Kanunu"),
    ("spkn", "6362", "Sermaye Piyasası Kanunu"),
    ("ssgssk", "5510", "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu"),
    ("pvsk", "2559", "Polis Vazife ve Salahiyet Kanunu"),
    ("ay", "2709", "Türkiye Cumhuriyeti Anayasası"),
)
_KISA_NO = {k: no for k, no, _ in KISALTMALAR}
_KISA_AD = {k: katla(ad) for k, _, ad in KISALTMALAR}      # kanun_no çakışırsa adla seçim ipucu

# Yaygın ad tablosu: (katlanmış ad sözcükleri — sondaki 'Kanunu' HARİÇ, kanun_no). Sonuna 'Kanun(u)'
# ya da 'K.' gelmesi şart ('Türk Ceza K.'). Resmî adlar korpustan da tanınır (`kanun_adlari`); bu tablo
# korpus olmadan da çalışsın ve konuşma dilindeki kısa adları ('Medeni Kanun', 'İcra İflas Kanunu',
# 'KDV Kanunu') yakalasın diye var. Daha uzun bir korpus adı aynı yerde eşleşirse o kazanır.
ADLAR = (
    (("turk", "ceza"), "5237"),
    (("ceza", "muhakemesi"), "5271"),
    (("turk", "medeni"), "4721"),
    (("medeni",), "4721"),
    (("turk", "borclar"), "6098"),
    (("borclar",), "6098"),
    (("hukuk", "muhakemeleri"), "6100"),
    (("icra", "ve", "iflas"), "2004"),
    (("icra", "iflas"), "2004"),
    (("turk", "ticaret"), "6102"),
    (("vergi", "usul"), "213"),
    (("gelir", "vergisi"), "193"),
    (("kurumlar", "vergisi"), "5520"),
    (("katma", "deger", "vergisi"), "3065"),
    (("kdv",), "3065"),
    (("amme", "alacaklarinin", "tahsil", "usulu", "hakkinda"), "6183"),
    (("devlet", "memurlari"), "657"),
    (("kisisel", "verilerin", "korunmasi"), "6698"),
    (("idari", "yargilama", "usulu"), "2577"),
    # resmî adı 'Basın Mesleğinde Çalışanlarla Çalıştıranlar ... Hakkında Kanun'; korpus adı 'İŞ KANUNU'
    # (4857) bu yaygın adın içinde geçer → burada olmasa korpus adı yolu 4857'ye eşlerdi
    (("basin", "is"), "5953"),
)

_ROMA = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
         "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18,
         "xix": 19, "xx": 20}
_SIRA_SOZ = {"birinci": 1, "ikinci": 2, "ucuncu": 3, "dorduncu": 4, "besinci": 5, "altinci": 6,
             "yedinci": 7, "sekizinci": 8, "dokuzuncu": 9}

# ---- düzenli ifadeler (KATLANMIŞ metin üzerinde) ---------------------------------------------
_ORD = r"(?:\s?\.(?![0-9])|\s?'?\s?(?:inci|nci|uncu|ncu)(?![a-z]))"      # sıra eki: '.', 'inci', "'nci"
# madde numarasının slash eki: '/2' fıkra · '/II' Roma fıkra · '/A' harf (harfli madde ya da bent);
# fıkradan sonra bent: '-a' ya da '(a)'
_SLASH = (r"(?:\s?/\s?(?P<ek>[0-9]{1,2}(?![0-9])|[ivx]{2,5}(?![a-z])|[a-z](?![a-z]))"
          r"(?:\s?-\s?(?P<eb1>[a-z]|[0-9]{1,2})(?![a-z0-9])|\s?\(\s?(?P<eb2>[a-z]|[0-9]{1,2})\s?\))?)?")
_NO = r"(?P<no>[0-9]{1,4})(?![0-9])"

_SAYILI = re.compile(r"(?<![0-9/.,])(?P<no>[0-9]{1,4})(?![0-9])\s?"
                     r"(?P<tur>sayili|sy\.|s\s?\.|numarali|no\.?\s?'?\s?l[iu]|nolu)")
_KANUN_NO = re.compile(r"(?<![a-z0-9])(?:kanun|k\.)\s?(?:no|numarasi|numara|nr)\.?\s?:?\s?"
                       r"(?P<no>[0-9]{1,4})(?![0-9/])")
_KISA = re.compile(r"(?<![a-z0-9])(?P<kisa>"
                   + "|".join(sorted(map(re.escape, _KISA_NO), key=len, reverse=True))
                   + r")(?:'[a-z]{1,6}|nin|nun|in|un|da|de|ta|te|ya|ye|den|dan|ten|tan)?(?![a-z0-9])")
_AD_DESENLERI = tuple(
    (re.compile(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, sozcukler)) + r"\s+k(?:anun[a-z']*|\.)"),
     no) for sozcukler, no in ADLAR)
_IS_KANUNU = re.compile(r"(?<![a-z0-9])(?<!deniz )(?<!basin )is\s?k(?:anun[a-z']*|\.|(?![a-z]))")
_ANAYASA = re.compile(r"(?<![a-z0-9])anayasa(?!l)[a-z']*")

_M_ONCE = re.compile(r"(?<![a-z0-9])(?:(?P<tip>gecici|gec\.|ek|mukerrer|muk\.)\s?)?"
                     r"(?P<kw>madde(?:si)?|md\.?|mad\.?|m\.?)\s?(?:no\s?[.:]?\s?)?" + _NO + _SLASH)
_M_ONEK = re.compile(r"(?<![a-z0-9])(?P<tip>gecici|ek|mukerrer)\s" + _NO + _SLASH
                     + r"(?P<ord>" + _ORD + r")?(?P<kw>\s?madde[a-z]*)?")
_M_SONRA = re.compile(r"(?<![0-9/.,a-z])" + _NO + _SLASH + r"(?P<ord>" + _ORD + r")?\s?madde(?P<mek>[a-z]*)")
_M_YALIN = re.compile(r"(?:'[a-z]{1,6})?[\s,:]{1,3}" + _NO + _SLASH)

_F_SOZ = re.compile(r"(?<![a-z])(?P<on>on\s?)?(?P<s>birinci|ikinci|ucuncu|dorduncu|besinci|altinci|"
                    r"yedinci|sekizinci|dokuzuncu|onuncu|yirminci|son)\s?fikra[a-z]*")
_F_SAYI = re.compile(r"(?<![0-9/.,a-z])(?P<n>[0-9]{1,2})(?![0-9])" + _ORD + r"\s?fikra[a-z]*")
_F_PAREN = re.compile(r"\(\s?(?P<n>[0-9]{1,2})\s?\)\s?(?:(?:numarali|nolu|no'?lu|sayili)\s)?fikra[a-z]*")
_F_ONCE = re.compile(r"(?<![a-z])(?:fikra(?:si)?|fik\.|fkr\.|f\.)\s?(?:no\s?[.:]?\s?)?\(?\s?"
                     r"(?P<n>[0-9]{1,2})(?![0-9])\s?\)?")

_B_PAREN = re.compile(r"\(\s?(?P<h>[a-z]|[0-9]{1,2})\s?\)\s?(?:(?:numarali|nolu|no'?lu|sayili)\s)?"
                      r"ben[dt][a-z]*")
_B_HARF = re.compile(r"(?<![a-z0-9(])(?P<h>[a-z])(?:\)\s?|\s)ben[dt][a-z]*")
_B_SAYI = re.compile(r"(?<![0-9/.,a-z])(?P<h>[0-9]{1,2})(?![0-9])(?:" + _ORD
                     + r"|\s?(?:numarali|nolu|no'?lu))\s?ben[dt][a-z]*")
_B_ONCE = re.compile(r"(?<![a-z])(?:bent|bendi|bnt\.?|b\.)\s?\(?\s?(?P<h>[a-z]|[0-9]{1,2})(?![a-z0-9])\s?\)?")

# Numaradan hemen sonra gelince "bu bir madde numarası değil" diyen kapı — biçimin GÜCÜNE göre kademeli:
#   guclu ('m. 53', 'md. 53', 'mad. 53'): yalnız başka bir belge numarası ('5 sayılı', '5 s. K.', '%') ya da
#         ondalık/tarih devamı ('1.5', '2/3/2024'). Süre birimi kontrol EDİLMEZ: 'İş K. m. 53 yıllık izin'
#         gerçek atıftır (53. madde tam da yıllık izin).
#   madde ('madde 3' — 'madde' aynı zamanda 'cisim' demek): + fiziksel miktar ('madde 3 ton', '5 kg').
#   zayif (kanundan sonra yalın numara 'TCK 2', önekli 'ek 3'): + süre/sayım sözcükleri ('TCK'da 2 yıl',
#         'ek 3 ay', 'TMK 4 çocuk', 'TCK 18 yaşından') + miktar/tarih ifadesinin devamı (`_MIKTAR_DEVAMI`):
#         tarih ('TCK 1 Haziran 2005'), birimli aralık ('TCK 2-5 yıl', 'İş K. 30 ila 50 işçi'), kıyas
#         ("İş K. 30'dan fazla", '100 ve daha fazla'), oran ('TCK 1/3 oranında'). Birimsiz aralık madde
#         aralığıdır ('TCK 141 ila 145' → 141).
# Sözcükler AÇIK çekim listesiyle yazıldı: önek eşleşmesi 'güncel' / 'kişisel' / 'evlilik' gibi sözcükleri
# birim sanıp gerçek atfı düşürürdü ('TMK 24 kişilik hakkı' atıftır, 'kişilik' listede yok).
_BELGE_DEVAMI = r"%|sayili|sy\.|s\s?\.\s?k|numarali|nolu|no\s?'?\s?lu"
_FIZIKSEL = (r"tl|lira(?:si|ya|lik)?|kurus|adet|metre|km|kg|ton|(?:kilo|mili)?gram(?:dan|a|i|lik)?|litre"
             r"|yuzde|bin|milyon|milyar")
_SURE_SAYIM = (r"yil(?:a|i|in|ina|inda|da|dan|lik|lar[a-z]*)?|sene(?:si|ye|de|den|lik)?"
               r"|gun(?:u|un|e|de|den|luk|ler[a-z]*)?|hafta(?:si|ya|da|dan|lik)?|saat(?:i|e|te|ten|lik)?"
               r"|dakika(?:si|ya|da|dan|lik)?|saniye(?:si|ye|de|den|lik)?|ay(?:a|da|dan|i|in|lik)?"
               r"|kez|defa|kere|kat|kati|tane|kisi(?:ye|yle|nin|den|de|ler[a-z]*)?"
               r"|cocuk(?:lu|u|un|a|lar[a-z]*)?|kardes(?:i|ler[a-z]*)?|isci(?:ye|nin|den|ler[a-z]*)?"
               r"|taksit(?:le|li|te)?|donem(?:de|lik)?"
               r"|yas(?:i|ini|inin|inda|indaki[a-z]*|indan|ina)?|puan|derece|sayfa")
_AY_ADLARI = r"ocak|subat|mart|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik"
_MIKTAR_DEVAMI = (r"(?:\s?(?:" + _AY_ADLARI + r")(?![a-z])"
                  r"|(?:\s?-\s?|\s(?:ila|ile|veya|ya da)\s)[0-9]+(?:[.,][0-9]+)?\s?(?:" + _FIZIKSEL + "|"
                  + _SURE_SAYIM + r")(?![a-z])"
                  r"|'?\s?(?:dan|den|tan|ten)\s(?:daha\s)?(?:fazla|az|cok|ziyade|buyuk|kucuk|yuksek|dusuk"
                  r"|uzun|kisa)(?![a-z])"
                  r"|\s(?:ve|veya|ya da)\s(?:daha\s)?(?:fazla|az|uzeri|ustu|alti)(?![a-z])"
                  r"|\s?(?:oran|nispet)[a-z]*)")
_MADDE_DEGIL_SONRA = {
    "guclu": re.compile(r"\s?(?:" + _BELGE_DEVAMI + r")|[.,/][0-9]"),
    "madde": re.compile(r"\s?(?:" + _BELGE_DEVAMI + r"|(?:" + _FIZIKSEL + r")(?![a-z]))|[.,/][0-9]"),
    "zayif": re.compile(r"\s?(?:" + _BELGE_DEVAMI + r"|(?:" + _FIZIKSEL + "|" + _SURE_SAYIM
                        + r")(?![a-z]))|[.,/][0-9]|" + _MIKTAR_DEVAMI),
}
_MADDE_SOZU = re.compile(r"\s?madde")
_KELIME = re.compile(r"[a-z0-9'][a-z0-9']*\.?")
# 'NNNN sayılı' ardından gelen İLK sözcük bunlardansa kanun DEĞİL: KHK, CB kararnamesi, karar,
# yönetmelik, tebliğ, liste/cetvel, Resmî Gazete sayısı, bent/fıkra numarası ... Öneklerle karşılaştırılır;
# kanun adlarının başında da geçebilen kısa sözcükler ('ek', 'alt', 'Cumhurbaşkanlığı ...', 'Resmî ...')
# yalnız tam sözcük ya da iki sözcüklü kalıp olarak dışlanır ('Cumhurbaşkanlığı Seçimi Kanunu' kanundur).
_SAYILI_RET_ON = ("khk", "cbk", "karar", "yonetmelik", "teblig", "genelge", "tuzuk", "liste", "cetvel",
                  "tablo", "cizelge", "kroki", "harita", "bent", "bend", "fikra", "madde", "sirkuler",
                  "ozelge", "protokol", "sozlesme", "anlasma", "dosya")
_SAYILI_RET_TAM = ("ek", "eki", "ekli", "ekte", "alt", "esas")
_SAYILI_RET_IKI = (("kanun", "hukmunde"), ("resmi", "gazete"), ("cumhurbaskanligi", "karar"))
# Ad/kısaltmadan hemen önce gelince onu BUGÜNKÜ Türk kanunu olmaktan çıkaran nitelemeler: 'eski İş Kanunu'
# (1475), 'mülga TCK' (765), 'İsviçre Borçlar Kanunu' (OR). Numaralı tanımaya uygulanmaz.
_NITELEME = ("eski", "mulga", "onceki", "evvelki", "isvicre", "alman", "fransiz", "italyan", "avusturya")
_SON_SOZCUK = re.compile(r"([a-z]+)[\s,]*$")
# Vasıta hâlindeki kanun ('Kanunla' / "Kanun'la" / 'Kanun ile') + 'değişik | değiştirilen | eklenen ...' →
# DEĞİŞTİREN kanun: ardından gelen madde onun değil, daha önce anılan kanunundur ('TCK'nın 6545 sayılı
# Kanunla değişik 141. maddesi'). Tamlayan hâli ('TCK'nın değişik 141. maddesi') sahibin kendisidir.
_DEGISIK_SOZ = r"(?:degisik|degistiril|eklen|ihdas|yapilan\sdegisiklik)"
_VASITA_EKI = re.compile(r"'?(?:yla|yle|la|le)$")
_DEGISIK_SONRA = re.compile(r"\s" + _DEGISIK_SOZ)
_ILE_DEGISIK_SONRA = re.compile(r"\sile\s" + _DEGISIK_SOZ)
# Madde sözünden HEMEN önce kanun dışı bir belge ('Yönetmeliğin 5. maddesi', "KHK'nın ek 9. maddesi",
# 'Sözleşmenin 6. maddesi', 'teklifinin 5. maddesi') → madde o belgenindir, hiçbir kanuna bağlanmaz.
_BELGE_MADDESI = re.compile(r"(?<![a-z0-9])(?:yonetmeli[gk]|teblig|tuzu[gk]|genelge|yonerge|karar|khk|cbk"
                            r"|sozlesme|anlasma|protokol|sartname|aihs|teklif|tasari)[a-z']*[\s,]*$")


# ---- veri sınıfları ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Yorum:
    """Bir atfın tek bir okunuşu: hangi madde, hangi fıkra/bent.
    fikra: 1-tabanlı fıkra sırası (SON_FIKRA = son fıkra); bent: 'a' / 'ç' / '1' (işaretsiz)."""
    madde_tipi: str = "asil"          # asil | gecici | ek | mukerrer
    madde_numara: str = ""            # '141' | '123/A'
    fikra: int | None = None
    bent: str | None = None
    aciklama: str | None = None       # alternatif yorum etiketi: 'harf->bent' | 'roma->fikra'

    @property
    def madde_no(self):
        return madde_no_goster(self.madde_tipi, self.madde_numara)


@dataclass(frozen=True)
class Atif:
    """Ayrıştırılmış atıf. `yorum` birincil okunuş; `alternatifler` belirsiz slash ekinin diğer
    okunuşları (çözücü sırayla dener). kanun_nolari çoğunlukla tek elemanlıdır (aynı resmî adı taşıyan
    birden çok kanun varsa hepsi)."""
    kanun_nolari: tuple
    yorum: Yorum
    alternatifler: tuple = ()
    kanun_kaynak: str = "numara"      # numara | kisaltma | ad | korpus_adi
    kanun_ipucu: str | None = None    # kanun adı sözcükleri (kanun_no çakışmasını adla çözmek için)
    ham: str = ""                     # sorgudaki atıf metni

    @property
    def yorumlar(self):
        return (self.yorum,) + tuple(self.alternatifler)

    @property
    def madde_no(self):
        return self.yorum.madde_no

    @property
    def fikra(self):
        return self.yorum.fikra

    @property
    def bent(self):
        return self.yorum.bent

    def etiket(self, yorum=None):
        """İnsan-okur kısa gösterim: '5237 s. K. m. 141 f. 2 b. a'."""
        y = yorum or self.yorum
        s = f"{'/'.join(self.kanun_nolari)} s. K. m. {y.madde_no}"
        if y.fikra is not None:
            s += " son f." if y.fikra == SON_FIKRA else f" f. {y.fikra}"
        if y.bent is not None:
            s += f" b. {y.bent}"
        return s


@dataclass
class _KanunTok:
    bas: int
    son: int
    nolar: tuple
    kaynak: str
    ipucu: str | None = None
    oncelik: int = 0                  # aynı açıklıkta: tablo/numara (0) > korpus adı (1)
    nitelik: str | None = None        # 'eski' / 'mülga' / 'isvicre' ...: bugünkü kanun değil (atıf üretmez)
    degistiren: bool = False          # 'N sayılı Kanunla değişik ...': sonraki maddenin sahibi değil


@dataclass
class _MaddeTok:
    bas: int
    son: int
    tip: str
    no: str
    harf: str | None = None           # tek harfli slash eki (orijinal karakter): harfli madde / bent
    roma_tek: bool = False            # harf aynı zamanda tek harfli Roma rakamı (I, V, X)
    fikra: int | None = None          # satır içi fıkra ('/2', '/II')
    bent: str | None = None           # satır içi bent ('/2-a', '/1(ğ)')


@dataclass
class _Tok:
    bas: int
    son: int
    deger: object


@dataclass
class Ayristirma:
    """`ayristir` çıktısı: atıflar + tanı için ham kanun/madde parçaları."""
    atiflar: list = field(default_factory=list)
    kanunlar: list = field(default_factory=list)
    kanunsuz_maddeler: list = field(default_factory=list)
    nitelikli_maddeler: list = field(default_factory=list)   # 'eski TCK m. 141' gibi: kanunu belirsiz

    def tani(self):
        """Atıf çıkmadıysa nedenini söyle (yanıttaki açıklama için)."""
        if self.atiflar:
            return ""
        if self.nitelikli_maddeler:
            return ("kanun adı eski/mülga ya da yabancı nitelemeli — bugünkü kanuna eşlenmedi; kanunu "
                    "numarasıyla yazın ('765 sayılı Kanun')")
        if self.kanunlar:
            nolar = sorted({n for t in self.kanunlar for n in t.nolar})
            return f"kanun tanındı ({', '.join(nolar)}) ama madde numarası bulunamadı"
        if self.kanunsuz_maddeler:
            return "madde numarası var ama kanun tanınmadı"
        return "sorguda kanun + madde atfı bulunamadı"


# ---- yardımcılar ------------------------------------------------------------------------------
def _cakisir(t, digerleri):
    return any(t.bas < o.son and o.bas < t.son for o in digerleri)


def _sec(toklar):
    """Çakışmayan en-soldaki-en-uzun seçim (eşit açıklıkta öncelik)."""
    secilen, son = [], -1
    for t in sorted(toklar, key=lambda t: (t.bas, -(t.son - t.bas), getattr(t, "oncelik", 0))):
        if t.bas >= son:
            secilen.append(t)
            son = t.son
    return secilen


def _ek_sonu(k, i):
    """Kanun adından sonraki çekim ekini de açıklığa kat ('kanununun', "kanunu'nun")."""
    while i < len(k) and (k[i].isalpha() or k[i] == "'"):
        i += 1
    return i


def _sayili_ret(sozcukler):
    """'NNNN sayılı' sonrası ilk sözcük(ler) kanun dışı bir belgeyi mi gösteriyor?"""
    ilk = sozcukler[0]
    ikinci = sozcukler[1] if len(sozcukler) > 1 else ""
    return (ilk.startswith(_SAYILI_RET_ON) or ilk in _SAYILI_RET_TAM
            or any(ilk.startswith(a) and ikinci.startswith(b) for a, b in _SAYILI_RET_IKI))


def _tasarim_mi(kelime, sonraki):
    """'NNNN sayılı' sonrasında kanunu belirten sözcük mü? (Kanun, K., yasa, Anayasa, kısaltma)"""
    w = kelime.rstrip(".")
    if w.startswith("kanun"):
        return not (sonraki or "").startswith("hukmunde")      # 'Kanun Hükmünde Kararname' adın parçası
    if w.startswith(("yasa", "anayasa")):
        return True
    if kelime in ("k.", "k"):
        return True
    kok = w.split("'")[0]
    return kok in _KISA_NO and kok != "ay"


# ---- kanun parçaları --------------------------------------------------------------------------
def _sayili_tokenleri(k):
    out = []
    for m in _SAYILI.finditer(k):
        no, tur = kanun_no_norm(m.group("no")), m.group("tur")
        kelimeler = [(w.group(), w.end()) for w in _KELIME.finditer(k, m.end(), min(len(k), m.end() + 240))]

        def sonraki(i):
            return kelimeler[i + 1][0] if i + 1 < len(kelimeler) else None

        if not tur.startswith("sayili"):
            # 's.' / 'numaralı' / "no'lu": belirsiz → HEMEN ardından kanun sözcüğü şart ('5237 s. K.')
            if kelimeler and _tasarim_mi(kelimeler[0][0], sonraki(0)):
                out.append(_KanunTok(m.start(), kelimeler[0][1], (no,), "numara"))
            continue
        asil = [w.rstrip(".") for w, _ in kelimeler if not w.startswith("'")]
        if asil and _sayili_ret(asil):
            continue                                            # KHK, karar, liste, Resmî Gazete ...
        son, ipucu = m.end(), []
        for i, (w, w_son) in enumerate(kelimeler[:16]):
            if w[0].isdigit():                                  # madde numarası başladı → ad bitti
                break
            if w.startswith("'"):                               # "sayılı'nın" eki
                if not ipucu:
                    son = w_son
                continue
            if _tasarim_mi(w, sonraki(i)):
                son = w_son
                break
            ipucu.append(w.rstrip("."))
        out.append(_KanunTok(m.start(), son, (no,), "numara", " ".join(ipucu) or None))
    return out


def _kanun_tokenleri(k, sorgu, kanun_adlari):
    toklar = _sayili_tokenleri(k)
    toklar += [_KanunTok(m.start(), m.end(), (kanun_no_norm(m.group("no")),), "numara")
               for m in _KANUN_NO.finditer(k)]
    for m in _KISA.finditer(k):
        kisa = m.group("kisa")
        if kisa == "ay" and sorgu[m.start():m.start() + 2] != "AY":
            continue                                            # küçük 'ay' = süre birimi
        toklar.append(_KanunTok(m.start(), m.end(), (_KISA_NO[kisa],), "kisaltma", _KISA_AD[kisa]))
    for desen, no in _AD_DESENLERI:
        toklar += [_KanunTok(m.start(), m.end(), (no,), "ad", m.group()) for m in desen.finditer(k)]
    toklar += [_KanunTok(m.start(), m.end(), ("4857",), "ad", "is kanunu") for m in _IS_KANUNU.finditer(k)]
    for m in _ANAYASA.finditer(k):
        if not re.match(r"\s*mahkeme", k[m.end():]):
            toklar.append(_KanunTok(m.start(), m.end(), ("2709",), "ad", "anayasa"))
    for ad, nolar in (kanun_adlari or ()):
        i = k.find(ad)
        while i != -1:
            if i == 0 or not k[i - 1].isalnum():
                toklar.append(_KanunTok(i, _ek_sonu(k, i + len(ad)), tuple(nolar), "korpus_adi", ad, 1))
            i = k.find(ad, i + 1)
    for t in toklar:
        if t.kaynak != "numara":
            m = _SON_SOZCUK.search(k[max(0, t.bas - 24):t.bas])
            if m and m.group(1) in _NITELEME:
                t.nitelik = m.group(1)
        t.degistiren = bool(_ILE_DEGISIK_SONRA.match(k, t.son)
                            or (_VASITA_EKI.search(k, t.bas, t.son) and _DEGISIK_SONRA.match(k, t.son)))
    return _sec(toklar)


# ---- madde parçaları --------------------------------------------------------------------------
def _slash_uygula(m, sorgu, tok):
    """_SLASH gruplarını madde parçasına işle. Geçersiz Roma rakamı → False (parça atılır)."""
    ek = m.group("ek")
    if ek is None:
        return True
    grup = "eb1" if m.group("eb1") is not None else ("eb2" if m.group("eb2") is not None else None)
    if ek.isdigit():
        tok.fikra = int(ek)
    elif len(ek) > 1:
        if ek not in _ROMA:
            return False
        tok.fikra = _ROMA[ek]
    else:
        tok.harf = sorgu[m.start("ek")]
        tok.roma_tek = ek in ("i", "v", "x")
        # harf ekinden sonraki '-1' alt-bent sayılır, okunmaz ('359/a-1'); tek harfli Roma rakamından
        # sonraki HARF ise benttir ('İş K. 25/I-b' = I. fıkra (b) bendi)
        if not (tok.roma_tek and grup and not m.group(grup).isdigit()):
            return True
    if grup:
        b = m.group(grup)
        tok.bent = str(int(b)) if b.isdigit() else tr_kucuk(sorgu[m.start(grup)])
    return True


def _madde_degil(k, son, guc):
    return bool(_MADDE_DEGIL_SONRA[guc].match(k, son))


def _madde_tokenleri(k, sorgu, kanunlar):
    adaylar = []
    for m in _M_ONCE.finditer(k):
        kw = m.group("kw")
        if kw == "m" and m.start("no") == m.end("kw"):          # 'm2', 'm3' (metrekare/küp) madde değil
            continue
        guc = "madde" if kw in ("madde", "maddesi", "m") else "guclu"
        t = _MaddeTok(m.start(), m.end(), _tip(m.group("tip")), m.group("no"))
        if _slash_uygula(m, sorgu, t) and not _madde_degil(k, m.end(), guc):
            adaylar.append(t)
    for m in _M_ONEK.finditer(k):
        kw = (m.group("kw") or "").strip()
        if kw and not (m.group("ord") or kw.startswith("maddesi")):
            continue                                            # 'Kanuna ek 3 madde eklendi' = sayım
        t = _MaddeTok(m.start(), m.end(), _tip(m.group("tip")), m.group("no"))
        if not _slash_uygula(m, sorgu, t):
            continue
        if not kw and _madde_degil(k, m.end(), "zayif"):         # 'ek 3 ay', 'ek 1 sayılı liste'
            continue
        adaylar.append(t)
    for m in _M_SONRA.finditer(k):
        if not (m.group("ord") or m.group("ek") or m.group("mek").startswith("si")):
            continue                                            # 'N madde(de)' = sayım, atıf değil
        t = _MaddeTok(m.start(), m.end(), "asil", m.group("no"))
        if _slash_uygula(m, sorgu, t):                          # '48/A maddesi', '220/6. maddesi', '4/1-a'
            adaylar.append(t)
    secilen = [t for t in _sec(adaylar) if not _cakisir(t, kanunlar) and int(t.no) > 0
               and not _BELGE_MADDESI.search(k[max(0, t.bas - 40):t.bas])]
    # kanundan hemen sonra yalın numara: 'TCK 141', "TCK'nın 141/2", 'HMK 119/1-ğ'
    for kt in kanunlar:
        m = _M_YALIN.match(k, kt.son)
        if m is None or _cakisir(_Tok(m.start("no"), m.end(), None), secilen + kanunlar):
            continue
        if _MADDE_SOZU.match(k, m.end("no")) or _madde_degil(k, m.end(), "zayif") or int(m.group("no")) == 0:
            continue
        t = _MaddeTok(m.start("no"), m.end(), "asil", m.group("no"))
        if _slash_uygula(m, sorgu, t):
            secilen.append(t)
    return sorted(secilen, key=lambda t: t.bas)


def _tip(onek):
    if not onek:
        return "asil"
    return {"gec.": "gecici", "muk.": "mukerrer"}.get(onek, onek)


# ---- fıkra / bent parçaları -------------------------------------------------------------------
def _fikra_tokenleri(k):
    out = []
    for m in _F_SOZ.finditer(k):
        s = m.group("s")
        if s == "son":
            deger = SON_FIKRA
        elif s == "onuncu":
            deger = 10
        elif s == "yirminci":
            deger = 20
        else:
            deger = _SIRA_SOZ[s] + (10 if m.group("on") else 0)
        out.append(_Tok(m.start(), m.end(), deger))
    for desen in (_F_SAYI, _F_PAREN, _F_ONCE):
        out += [_Tok(m.start(), m.end(), int(m.group("n"))) for m in desen.finditer(k) if int(m.group("n")) > 0]
    return _sec(out)


def _bent_tokenleri(k, sorgu):
    out = []
    for desen in (_B_PAREN, _B_HARF, _B_SAYI, _B_ONCE):
        for m in desen.finditer(k):
            if desen is _B_ONCE and k[max(0, m.start() - 4):m.start()] == "alt ":
                continue                                        # 'alt bendi' — alt-bent okunmaz
            h = m.group("h")
            deger = str(int(h)) if h.isdigit() else tr_kucuk(sorgu[m.start("h")])
            if deger != "0":
                out.append(_Tok(m.start(), m.end(), deger))
    return _sec(out)


# ---- eşleştirme -------------------------------------------------------------------------------
def _kanun_sec(kanunlar, mt):
    """Maddeye en yakın ÖNCEKİ kanun; yoksa en yakın SONRAKİ ('141. madde TCK'). Değiştiren kanun
    ('6545 sayılı Kanunla değişik') sahip sayılmaz; asıl kanun anılmamışsa madde kanunsuz kalır."""
    adaylar = [t for t in kanunlar if not t.degistiren]
    onceki = [t for t in adaylar if t.son <= mt.bas]
    if onceki:
        return onceki[-1]
    return next((t for t in adaylar if t.bas >= mt.son), None)


def _yorumlar(mt, fikra, bent):
    no = str(int(mt.no))
    if not mt.harf:
        return Yorum(mt.tip, no, fikra, bent), ()
    birincil = Yorum(mt.tip, f"{no}/{tr_buyuk(mt.harf)}", fikra, bent)
    alternatifler = []
    if mt.roma_tek and fikra is None:                           # '166/I' → 166. madde 1. fıkra
        alternatifler.append(Yorum(mt.tip, no, _ROMA[katla(mt.harf)], bent, "roma->fikra"))
    if bent is None:                                            # '359/a' → 359. madde (a) bendi
        alternatifler.append(Yorum(mt.tip, no, fikra, tr_kucuk(mt.harf), "harf->bent"))
    return birincil, tuple(alternatifler)


def ayristir(sorgu, kanun_adlari=None):
    """Sorgu → Ayristirma (atıflar + tanı parçaları).

    kanun_adlari: ops. [(katlanmış resmî ad, (kanun_no, ...)), ...] — korpustaki adlarla tanıma
    (`AtifIndeks.kanun_adlari`). Verilmezse yalnız numara + kısaltma + ADLAR tablosu kullanılır."""
    k = katla(sorgu)
    kanunlar = _kanun_tokenleri(k, sorgu, kanun_adlari)
    maddeler = _madde_tokenleri(k, sorgu, kanunlar)
    dolu = maddeler + kanunlar
    fikralar = [t for t in _fikra_tokenleri(k) if not _cakisir(t, dolu)]
    bentler = [t for t in _bent_tokenleri(k, sorgu) if not _cakisir(t, dolu + fikralar)]

    sonuc = Ayristirma(kanunlar=kanunlar)
    gorulen = set()
    for i, mt in enumerate(maddeler):
        kt = _kanun_sec(kanunlar, mt)
        if kt is None:
            sonuc.kanunsuz_maddeler.append(mt)
            continue
        if kt.nitelik:                  # 'eski TCK m. 491': madde o (belirsiz) kanuna ait → atıf değil
            sonuc.nitelikli_maddeler.append(mt)
            continue
        sinir = min([t.bas for t in maddeler[i + 1:]] + [t.bas for t in kanunlar if t.bas >= mt.son] + [len(k)])
        ft = bt = None
        fikra = mt.fikra
        if fikra is None:
            ft = next((t for t in fikralar if mt.son <= t.bas < sinir), None)
            fikra = ft.deger if ft else None
        bent = mt.bent
        if bent is None:
            bt = next((t for t in bentler if mt.son <= t.bas < sinir), None)
            bent = bt.deger if bt else None
        yorum, alternatifler = _yorumlar(mt, fikra, bent)
        anahtar = (kt.nolar, yorum)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        bas = min(kt.bas, mt.bas)
        son = max(kt.son, mt.son, ft.son if ft else 0, bt.son if bt else 0)
        sonuc.atiflar.append(Atif(kt.nolar, yorum, alternatifler, kt.kaynak, kt.ipucu,
                                  sorgu[bas:son].strip()))
    return sonuc


def atif_ayristir(sorgu, kanun_adlari=None):
    """Sorgu → [Atif, ...] (sorgudaki sırayla). Atıf yoksa boş liste → doğal dil modu."""
    return ayristir(sorgu, kanun_adlari).atiflar
