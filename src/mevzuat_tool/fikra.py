"""Fıkra/bent/alt-bent ağacı + seviye-bazlı yürürlük (Faz 3 follow-up #5, #6).

Madde gövdesi iç içe `fikralar → bentler → alt_bentler` yapısına bölünür. Resmî hiyerarşi:
Fıkra: `(1)` (yeni stil) veya numarasız tek paragraf. Bent (fıkra içinde): `a)` (harf) veya
`1.` (numara). Alt-bent (bent içinde): `1)` (parantez-rakam). Her seviye kendi yürürlük
durumunu `extract_status` ile alır.
"""
import re
from dataclasses import dataclass, field

from mevzuat_tool.chunker import extract_status

# Fıkra başı '(n)' YALNIZ metnin başında VEYA cümle-sonu (. : ! ?) / satır-sonu sonrasında.
# Cümle-ortası '(n)' (örn. 'eki (1), (2) sayılı cetveller', 'fıkrasının (2) bendi') fıkra DEĞİL,
# atıftır (A hatası). Lookbehind: başlangıç | noktalama+boşluk | yeni satır.
#
# EK SİNYAL — künye-fıkrası kapanışı sonrası fıkra (6698 M6): önceki fıkra '(Mülga:...md.)'
# künyesidir, sonu ')' ile biter (noktalama değil) → standart lookbehind '(3)'ü kaçırır. Ama
# ardından '(n) (' (açılış-paren = künye başı) gelirse bu GÜÇLÜ fıkra-başıdır; atıfta ('(2) sayılı',
# '(2) numaralı') açılış-paren gelmez. Bu yüzden ')' + boşluk + '(n)' + boşluk + '(' deseni de böler.
# EK SİNYAL 2 — lider künye/başlık sonrası '(1)' fıkrası (Bug 2: ÇEK 5941 M6, '(Başlığı ile
# Birlikte Değişik:...) (1) Karşılıksız...'). Künye ')' ile biter, ardından '(n)' + BÜYÜK harf gelir
# (gerçek fıkra metni). Atıf ('(2) numaralı', '(2) sayılı') KÜÇÜK harf devam eder → bölünmez.
# B1 (FAZ 2): cümle '.[1]' dipnot işaretiyle bitince '] ' + '(n)' de fıkra-başıdır — dipnot
# işareti standart '[.:!?]\s' lookbehind'ını maskeliyordu (189065-5: '(2)' fıkrası '(1)'e gömülü).
# AMA dipnot-']' sonrası '(n)' YALNIZ ardından BÜYÜK harf gelirse fıkra (gerçek fıkra metni başı).
# Cümle-ortası '(…)[10] (1) zimmet, irtikâp...' (103569-28): ')' + ']' + '(1)' + KÜÇÜK harf →
# cümle devamı, fıkra DEĞİL. Büyük-harf şartı bu yanlış-pozitifi eler.
# E1 (FAZ 12): GÖMÜLÜ FIKRA — bent listesi NOKTASIZ bitip ardından '(n) BÜYÜK' yeni fıkra geldiğinde
# (örn. '...Diğer gelirler (2) Başkanlığın giderleri şunlardır:') standart lookbehind (nokta/']'/'')')
# bunu kaçırıyordu → fıkra (2) fıkra (1)'in bentler[]'ine gömülü kalıyordu (102934-7, 103463-4 — gömülü
# (5)(6)(7), gömülü '(Mülga)' yürürlük filtresini de bozar). Kelime-karakteri (harf/rakam) sonrası
# '(n)' + BÜYÜK harf de fıkra-başı sayılır. ATIF-FP KORUMASI (kritik): '(n)' sonrası SIRA-SAYISI
# ('Birinci'..'Onuncu') veya atıf-öncülü ('Bu', 'Aynı', 'Söz', 'Yukarıdaki', 'Anılan', 'İlgili',
# 'Sözü', 'Bir') gelirse bu önceki fıkraya GÖNDERMEdir ('(2) Birinci fıkrada...'), fıkra DEĞİL —
# bölünmez (negatif-lookahead). 70 desen → 15 atıf elenir, ~55 gerçek gömülü fıkra ayrılır.
# E1 atıf-öncülleri: '(n)' sonrası bunlardan biri gelirse fıkra DEĞİL, önceki fıkraya göndermedir.
#  - sıra sayıları + 'Bu/Aynı/Söz...' = fıkra atfı ('(2) Birinci fıkrada...')
#  - SAYILI/Sayılı/Numaralı = ekli-belge atfı (CONFUSION MATRIX'ten 15 FP'nin kök neceni):
#    '(2) SAYILI ÇİZELGE...', '(2) Numaralı Alt Bendindeki Ceza...', '(15) Sayılı listede...',
#    '(2) Numaralı Kroki...' (103907-39, 103037-20, 104731-1, 105180-16). Bunlar cetvel/tablo/liste
#    numarasıdır, hüküm fıkrası değil. (B2 cetvel-guard'ın gömülü-fıkra dalındaki karşılığı.)
_ATIF_ONCUL = (r"(?:Birinci|İkinci|Üçüncü|Dördüncü|Beşinci|Altıncı|Yedinci|Sekizinci|Dokuzuncu|"
               r"Onuncu|Bu|Aynı|Söz|Sözü|Yukarıdaki|Anılan|İlgili|Bir|SAYILI|Sayılı|Numaralı)\b")
_FIKRA_BOL = re.compile(
    r"(?=(?:(?<=[.:!?]\s)|(?<=\n))\(\d+\)\s)"        # cümle-sonu/satır-sonu sonrası '(n)'
    r"|(?=(?<=\]\s)\(\d+\)\s(?=[A-ZÇĞİÖŞÜ]))"        # dipnot-']' sonrası '(n)' + BÜYÜK harf
    r"|(?=(?<=\)\s)\(\d+\)\s(?=\())"                  # künye-kapanışı ')' sonrası '(n) (' (künye başı)
    r"|(?=(?<=\)\s)\(\d+\)\s(?=[A-ZÇĞİÖŞÜ]))"        # künye-')' sonrası '(n)' + BÜYÜK harf (fıkra metni)
    r"|(?=(?<=[\wçğıöşüÇĞİÖŞÜ]\s)\(\d+\)\s(?=[A-ZÇĞİÖŞÜ])(?!" + _ATIF_ONCUL + r"))"
                                                      # E1: kelime sonrası '(n)' + BÜYÜK (gömülü fıkra);
                                                      # atıf/ekli-belge öncülü değilse böl
)
_FIKRA_NO = re.compile(r"^(\(\d+\))")
# B2 (FAZ 2): ekli cetvel başlığı '(N) SAYILI LİSTE/CETVEL/TARİFE/ÇİZELGE/KROKİ' — bu noktadan
# SONRASI cetveldir, fıkra/bent BÖLÜNMEZ (104030-5: '(1) SAYILI LİSTE ...' 862 sahte bent üretiyordu).
# Ayırt edici: BÜYÜK-harf belge türü (salt 'sayılı' değil — 'NNNN sayılı Kanun' atfı 6844 maddede meşru).
# FAZ 12 confusion matrix: ÇİZELGE/KROKİ eklendi (103907-39 '(1) SAYILI ÇİZELGE', 105180-16 kroki).
_CETVEL_BAS = re.compile(r"\(\d+\)\s+SAYILI\s+(?:LİSTE|CETVEL|TARİFE|ÇİZELGE|KROKİ)")
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


def _roman_i_idx(ms: list) -> set:
    """Z1: harf-işaret listesinde ROMAN 'i)' (3. seviye alt-alt-bent) konumlarını bul. Roman 'i)'
    harf-bent SANILIP listeye giriyor → bir önceki harf-bent boş kalıyor (içerik kaçar; 103017-Ek2
    Damga V.). KESİN sinyal (0 yanlış-pozitif): 'i)' işareti (a) TEKRARLI (harf-listede 'i' bir kez
    olur — 2+ kez = roman) VEYA (b) bir ÖNCEKİ harf-bent BOŞ (işareti hemen kendinden önce, araya
    metin girmemiş → önceki harf içeriksiz, içeriği bu 'i)'ye kaçmış). Meşru harf-bent 'i)'
    ('...h) i) j)...', ı) atlanmış) TEK + öncesi dolu → dokunulmaz."""
    i_konum = [k for k, m in enumerate(ms) if m.group(1) == "i"]
    if not i_konum:
        return set()
    roman = set()
    tekrarli = len(i_konum) >= 2
    for k in i_konum:
        if tekrarli:
            roman.add(k)
        elif k > 0:
            # önceki harf-bent boş mu? (önceki işaretin bitişi ile bu işaretin başı arası ~yok)
            onceki_govde = ms[k - 1].group(0)            # ör. 'f) '
            arada = ms[k].start() - ms[k - 1].end()      # önceki işaretten bu işarete metin var mı
            if arada <= 1:                                # 'f) i)' bitişik → f) boş, i) roman
                roman.add(k)
    return roman


def _harf_alt_bentler(text: str) -> list:
    # B3: numaralı üst-grup (1. 2.) dilimi içindeki harf-bentleri ALT-BENT yap ('a) b) c)').
    # Harfte sıralı-koşu şartı GEVŞEK (≥1 eşleşme) — harf işareti zaten güçlü sinyal; _alt_bentler'in
    # dilimleme deseni (her işaretten sonrakine) yeniden kullanılır.
    # Z1: roman 'i)' (3. seviye) işaret olarak ATLANIR — dilimleme onu bir önceki harf-bende yapıştırır
    # (ayrı alt-bent üretmez, önceki harf-bent boş kalmaz).
    ms = list(_BENT_HARF_ISARET.finditer(text))
    roman = _roman_i_idx(ms)
    harf = [m for k, m in enumerate(ms) if k not in roman]
    out = []
    for i, m in enumerate(harf):
        bas = m.start()
        son = harf[i + 1].start() if i + 1 < len(harf) else len(text)
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


def _kes_iki_seviye(text, num_matches):
    """B3: numaralı üst-grubu dilimle; her dilimdeki harf-bentleri ALT-BENT yap (iki seviye).
    Üst-bent text'i kendi harf alt-bentlerini içerir; alt_bentler yoksa boş liste (1. tek tanım)."""
    out = []
    for i, m in enumerate(num_matches):
        bas = m.start()
        son = num_matches[i + 1].start() if i + 1 < len(num_matches) else len(text)
        parca = text[bas:son].strip()
        out.append(Bent(isaret=m.group(0).strip(), text=parca, yurutluk=extract_status(parca),
                        alt_bentler=_harf_alt_bentler(parca)))
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
    # B3 (FAZ 3): İKİ-SEVİYELİ numaralı asıl-grup ('1. 2.' üst-bent + altında 'a) b)' alt-bent).
    # Gümrük 4458 M3 gibi: '1. ...; 2. a)...; b)...; 3. a)...' düz tek listeye eziliyordu. DAR tetik
    # (0 yanlış-pozitif): (A) sıralı numara-koşu ≥2, (B) en az bir numaralı dilimde harf var,
    # (C) toplam harf ≥2, (D) İLK yapısal işaret NUMARA (numara-üst hiyerarşisi).
    # (D) kritik: TTK 6102 (103039-55/181/960) hiyerarşi TERS — 'a) ... 1. ... 2. ... b)' (harf ÜST,
    # numara ALT). İlk işaret harf ise B3 tetiklenmez → harf üstte kalır. Kenar-numara (TMK/TBK
    # '1. Genel olarak') harf-bent içermez → (B) düşer; TTK M4 ('(1)' paren) sıralı '1.2.' yok → (A) düşer.
    if (len(num_seq) >= 2 and len(harf) >= 2
            and num_seq[0].start() < harf[0].start()):   # (D) numara harften ÖNCE = numara üst
        ust = _kes_iki_seviye(text, num_seq)
        if any(b.alt_bentler for b in ust):     # (B): en az bir üst-bentin altında harf alt-bent
            return ust
    # İlk-stil-kazanır (kod-sırası; spec 'karışık stil tek fıkrada varsayılmaz').
    if harf:
        return _kes(text, harf)
    if len(num_seq) >= 2:
        return _kes(text, num_seq)
    return []


# B4 (FAZ 6): liste-kapanış cümlesi son bentten ayrılır. GVK m.2 (103111-2) gibi liste-açan
# fıkralarda ('...şunlardır: 1. ..., 2. ..., 7. Diğer... . Bu Kanunda ... nazara alınır.') son
# bent dilimi metin sonuna kadar gittiği için fıkra-kapanış hükmü son bende yapışır. Bu cümle
# hiçbir bende ait DEĞİL — tüm fıkrayı kapatır. Çok DAR imza (0 yanlış-pozitif, 3 madde):
#   (1) bentler bir liste öğesi → son-bent HARİÇ hepsi KISA enum (virgül/; sonu, tek cümle),
#   (2) son bent = '<öğe>. <KAPANIŞ>' ve KAPANIŞ geri-atıflı bir hüküm cümlesi.
# Geri-atıf öncülü 'Ancak ...' istisnalarını (bende meşru 2. cümle) ve başlık sızmasını ELER.
_KAPANIS_GERI_ATIF = re.compile(
    r"^(?:Bu [Kk]anun(?:da|un)|Yukarıda|yukarıda|Bunlar|Bu fıkra(?:da)?\s|Şu kadar ki|Söz konusu)")


def _kisa_enum_bent(text: str) -> bool:
    """Bent metni kısa liste öğesi mi? (virgül/; ile biter, tek cümle, <70 krk — işaret hariç)."""
    govde = re.sub(r"^[0-9a-zçğıöşü]+[.)]\s*", "", text).strip()
    return (len(govde) < 70 and govde.rstrip().endswith((",", ";"))
            and not re.search(r"\.\s+[A-ZÇĞİÖŞÜ]", govde))


def _kapanis_ayir(bentler: list, fikra_text: str) -> list:
    """B4: liste-açan fıkrada son bende yapışmış geri-atıflı kapanış cümlesini son bentten AYIR.
    Yalnız DAR imza karşılanınca son bent kısaltılır (kapanış cümlesi fıkra.text'te kalır, kayıp
    yok). İmza tutmazsa bentler AYNEN döner (davranış değişmez)."""
    if len(bentler) < 2 or any(b.alt_bentler for b in bentler):
        return bentler
    # (1) fıkra giriş cümlesi ':' ile bitiyor mu (liste-açan)?
    idx = fikra_text.find(bentler[0].text)
    if idx <= 0 or not fikra_text[:idx].rstrip().endswith(":"):
        return bentler
    # (2) son-bent HARİÇ hepsi kısa enum
    if not all(_kisa_enum_bent(b.text) for b in bentler[:-1]):
        return bentler
    # (3) son bentte: '<işaret> <kısa-öğe>. <GERİ-ATIFLI KAPANIŞ>'
    son = bentler[-1]
    m = re.match(r"^([0-9a-zçğıöşü]+[.)]\s*.{0,75}?[,;.]?)\s*\.\s+(.{10,})$", son.text, re.DOTALL)
    if not m or not _KAPANIS_GERI_ATIF.match(m.group(2).strip()):
        return bentler
    # kapanış cümlesini son bentten çıkar; öğe sonundaki nokta korunur
    yeni_text = m.group(1).rstrip() + "."
    yeni_son = Bent(isaret=son.isaret, text=yeni_text,
                    yurutluk=extract_status(yeni_text), alt_bentler=son.alt_bentler)
    return bentler[:-1] + [yeni_son]


def _fikra_yurutluk(text, bentler):
    """Fıkra yürürlüğü (A2): bentler VARSA bent ağacından türet — tümü mülga ise fıkra mülga,
    en az biri yürürlükte ise fıkra yürürlükte (gömülü tek '(Mülga:)' bendi tüm fıkrayı mülga
    YAPMAZ; 103829-3). Bentsiz (düz) fıkrada davranış DEĞİŞMEZ: extract_status aynen."""
    if bentler:
        return "mülga" if all(b.yurutluk == "mülga" for b in bentler) else "yürürlükte"
    return extract_status(text)


def _parse_hukum(body: str) -> list:
    """Cetvelsiz hüküm gövdesini fıkra ağacına böl (asıl mantık)."""
    parcalar = [p.strip() for p in _FIKRA_BOL.split(body) if p.strip()]
    # Numaralı fıkra HİÇ yoksa tek numarasız fıkra. İlk parça '(1)' OLMASA bile (lider künye/başlık
    # '(Başlığı ile Değişik:...) (1) ...'), parçalarda numaralı fıkra varsa bölmeyi koru — lider
    # künye preamble olarak no=None ilk fıkra kalır (Bug 2: ÇEK 5941 M6). Numaralı fıkra yoksa collapse.
    if not parcalar or not any(_FIKRA_NO.match(p) for p in parcalar):
        bentler = _kapanis_ayir(_bentler(body), body)
        return [Fikra(no=None, text=body, bentler=bentler,
                      yurutluk=_fikra_yurutluk(body, bentler))]
    out = []
    for p in parcalar:
        mno = _FIKRA_NO.match(p)
        no = mno.group(1) if mno else None
        bentler = _kapanis_ayir(_bentler(p), p)
        out.append(Fikra(no=no, text=p, bentler=bentler, yurutluk=_fikra_yurutluk(p, bentler)))
    return out


# E2 (FAZ 13, İKİNCİL A): bent işareti Kiril homoglyph ('а)' U+0430 yerine Latin 'a)') olunca
# _BENT_HARF_ISARET tanımıyor → bent kayboluyor (103907-8 fıkra (3)/(4): 'а) Üç günlüğe...' bent a)
# kayıp). İŞARET KONUMUNDAKİ Kiril harfi Latin'e çevir (а→a, с→c, е→e, о→o, р→p, у→y, х→x; büyük de).
# YALNIZ 'Kiril)' deseni (bent/alt-bent işareti) — metin içeriğindeki Kiril'e dokunmaz (FP yok,
# çünkü desen tek-harf + ')' + işaret konumu). Türkçe metinde 'harf)' yalnız bent işaretidir.
_KIRIL_LATIN = str.maketrans("асеорухАСЕОРУХ", "aceopyxACEOPYX")
_KIRIL_ISARET = re.compile(r"(?:(?<=\s)|^)([асеорухАСЕОРУХ])\)")


def _normalize_kiril_isaret(body: str) -> str:
    """Bent-işareti konumundaki ('<boşluk>Kiril)') Kiril harfi Latin'e çevir. İçerik dokunulmaz."""
    return _KIRIL_ISARET.sub(lambda m: m.group(1).translate(_KIRIL_LATIN) + ")", body)


def parse_fikralar(body: str) -> list:
    body = _normalize_kiril_isaret(body.strip())
    if not body:
        return []
    # B2: ekli cetvel '(N) SAYILI LİSTE/CETVEL/TARİFE' başlığı varsa, o noktadan sonrası cetveldir —
    # fıkra/bent bölünmez, içerik son fıkraya eklenir (kayıp yok, sahte yapı üretilmez). Cetvel yoksa
    # _parse_hukum aynen çalışır (cetvelsiz davranış birebir korunur).
    mc = _CETVEL_BAS.search(body)
    if mc and mc.start() > 0:
        hukum, cetvel = body[:mc.start()].strip(), body[mc.start():].strip()
        fikralar = _parse_hukum(hukum)
        if fikralar and cetvel:
            son = fikralar[-1]
            fikralar[-1] = Fikra(no=son.no, text=(son.text + " " + cetvel).strip(),
                                 bentler=son.bentler, yurutluk=son.yurutluk)
        return fikralar
    return _parse_hukum(body)
