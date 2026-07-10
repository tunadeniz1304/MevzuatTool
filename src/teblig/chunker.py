"""TEBLİĞ metnini atomik birimlere böl (madde VEYA bölüm).

`src/kanun/chunker.py`'den KOPYALANDI (ADR-0014: türler arası sıfır kod paylaşımı) ve
924 gerçek tebliğ HTML'i üzerinde ölçülerek tebliğe uyarlandı. Kanun tarafını import ETMEZ.

═══ ÖLÇÜM (924 tebliğ, 2026-07-10) ═══
Kanun parser'ı hiç değiştirilmeden tebliğe uygulandığında:
  · %96.2'sinde madde buldu; ağaçlı 27 tebliğin 27'sinde ağaçla BİREBİR uyumlu.
  · Tek sistematik hata: kanun-sonu ek sızması (38 tebliğ, 107 sahte madde).
  · Kalan %3.8 (43 belge) gerçekten `MADDE` işareti taşımıyor — farklı yapıda.

═══ TEBLİĞE ÖZGÜ ÜÇ FARK ═══

1. KANUN-SONU EK KIRPMA (bu dosyada `_strip_teblig_sonu_ek`)
   Kanunda anchor `"Bakanlar Kurulu/Cumhurbaşkanı ... yürütür"`; tebliğde `"Ticaret Bakanı"`,
   `"Hazine ve Maliye Bakanı"` vb. → anchor deseni farklı. Anchor sonrası kuyruk:
     · `Ek-2B` maliyet formu → `Hammadde 1 (Raw Material 1)` satırı `Madde 1 (` sanılıyor (72 sahte)
     · tarife tablosu → `MADDE 104  İlanın şekli  30.000` satırı madde sanılıyor (35 sahte)
   Ölçüm: kırpma 107 sahte maddeyi eledi, **0 gerçek madde kaybı** (27/27 ağaç tam korundu).

2. BÖLÜM HİYERARŞİSİ (`split_bolumler`) — `MADDE` işareti YOKSA
   43 belgenin bir kısmı madde yerine numaralı bölüm kullanıyor:
     · roma  : `I- AMAÇ, KAPSAM`  → altında  `1- Alacağın Türü`      (120107, 539K)
     · ondalık: `2. Verginin Konusu` → `2.1.` → `2.1.1.` → `2.2.4.1.` (350474, 613K)

3. YAPRAK DÜĞÜM = ATOMİK BİRİM (maksimum granülerite; `_ondalik_bolumler`)
   Tek bir derinlik seçilemez — dallar farklı derinliklere iner. 350474'te aynı belgede
   `1.` (alt-numarasız) ile `4.1.7.1.1` (5 seviye) yan yana. Sabit seviye seçmek iki şeyi
   birden bozuyordu: seçili derinlikte numarası olmayan bölümlerin metni kayboluyor,
   daha derin dallar ise kesiliyordu.

   → Çocuğu olmayan her düğüm birimdir. Çocuğu OLAN düğümün giriş metni de
     (`_MIN_GIRIS` üstündeyse) ayrı birimdir — kanundaki 'madde giriş fıkrası + bentler'
     yapısının karşılığı. Üst zincir `Birim.ust`'te taşınır.

     belge    kural     birim  medyan   max     >25K  kapsama
     350474   seviye     134    2.637   56.525    1    77.3%   ← 139K krk aranamıyordu
     350474   YAPRAK     303    1.324   20.664    0   100.0%
     328127   seviye      27    2.449   22.455    0    95.9%
     328127   YAPRAK      68      989   11.134    0    99.3%

   Roma ailesinde (120106, 120107) aynı kural `_roma_yapraklari` ile uygulanır: alt-başlığı
   olmayan roma bölümü kendisi yapraktır (105921'de 6 bölümün 5'i böyle — eski kural
   içeriklerini yok ediyordu, alt kapsama yalnız %5.8).

4. CHUNKER'IN SINIRI — kalan dev chunk'lar `fikra.py`'nin işi
   Yaprak kuralından sonra tavanı (25K krk) aşan 7 birim kalıyor; hepsi İÇİNDE `(n)` fıkra
   ve `a)`/`aa)` bent taşıyor. Kanun tarafında korpus chunk'ı madde değil FIKRA'dır.
   Ölçüm (kanun `fikra.py` referans olarak uygulandığında): 7 dev chunk → 1.
   Kalan tek belge 328127 (91.097 krk) tablo ağırlıklı; tablolar `metadata.tablolar`'a
   taşınınca erir. Yani bölüm deseni tarafında yapılacak iş bitmiştir.
"""
import re
from dataclasses import dataclass, field

# ── Madde işareti (kanunla aynı aile; tebliğde `MADDE 1 –` baskın: 924/924 örnekte) ──
_MADDE_KW = r"[Mm][Aa][Dd][Dd][Ee]"
_PREFIX = r"(?:[Ee][Kk]|[Gg][Ee][Çç][İIiı][Cc][İIiı]|[Mm][Üü][Kk][Ee][Rr][Rr][Ee][Rr])\s+"
_MADDE_FULL = r"MADDE"
_NUM = r"\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?"
_FN = r"(?:\[\d+\])*"
_TAIL = rf"{_FN}\s*\.?"
_AYRAC_A = r"(?:\s*-\s*|\s+(?=[(]))"
_AYRAC_B = r"(?:\s*-\s*|\s+(?=[(]|[A-ZÇĞİÖŞÜ][a-zçğıöşü]))"
_MADDE = re.compile(
    rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM}){_TAIL}{_AYRAC_A}"
    rf"|\b({_PREFIX})?{_MADDE_FULL}\s+({_NUM}){_TAIL}{_AYRAC_B}"
)

_PARA = "\x1f"   # strip_html'in koyduğu paragraf sınırı


def _canon_prefix(p: str) -> str:
    p = p.lower()
    return "Ek" if p.startswith("ek") else "Geçici" if p.startswith("g") else \
           "Mükerrer" if p.startswith("m") else p


@dataclass
class Birim:
    """Atomik birim: `madde` (MADDE N) veya `bolum` (I- / 2.1.1.).

    tip='madde' → no='5', ust=[] (hiyerarşi ağaçtan gelir)
    tip='bolum' → no='2.1.1', ust=[('2','Verginin Konusu'), ('2.1','Verginin konusu')]
    """
    no: str
    body: str
    tip: str = "madde"
    baslik: str | None = None
    ust: list = field(default_factory=list)   # [(no, başlık)] üst seviyeler, kökten yaprağa


# ── 1. TEBLİĞ-SONU EK KIRPMA ────────────────────────────────────────────────
# Kapanış: "Bu Tebliğ hükümlerini <...> Bakanı/Bakanları yürütür."
# (Kanun: "Bakanlar Kurulu/Cumhurbaşkanı yürütür" — tebliğde bakanlık adı serbest.)
_TEBLIG_SONU_ANCHOR = re.compile(
    r"(?i)bu\s+tebli[ğg]\s+h[üu]k[üu]mlerini[^.]{0,90}?y[üu]r[üu]t[üu]r\s*\.?"
)
# Kuyruk imzası: `Ek-1`, `EK-2A` form başlığı.
_EK_BASI = re.compile(r"(?i)^\s*EK\s*[-–]?\s*\d+[A-Z]?\b")
_BUYUK_ESIK = 0.85       # kuyruk tümü-büyük mü? (kanunla aynı eşik)
_MIN_KUYRUK = 30         # bu kadar kısa kuyruk zaten çöp değil


def _buyuk_oran(s: str, pencere: int = 80) -> float | None:
    harf = [c for c in s[:pencere] if c.isalpha()]
    return (sum(c.isupper() for c in harf) / len(harf)) if harf else None


def _strip_teblig_sonu_ek(metin: str) -> str:
    """Yürütme anchor'ı sonrası ek/cetvel kuyruğunu kırp (ölçüm: 107 sahte madde elendi, 0 kayıp).

    Anchor yoksa ya da kuyruk ne `Ek-N` ile başlıyor ne de tümü-büyük ise metin DEĞİŞMEZ.
    Son anchor kullanılır (metinde `yürütür` birden çok geçebilir: alıntı/atıf)."""
    a = None
    for a in _TEBLIG_SONU_ANCHOR.finditer(metin):
        pass
    if a is None:
        return metin
    kuyruk = metin[a.end():].lstrip(". \n" + _PARA)
    if len(kuyruk) < _MIN_KUYRUK:
        return metin
    if _EK_BASI.match(kuyruk):
        return metin[:a.end()]
    oran = _buyuk_oran(kuyruk)
    if oran is not None and oran > _BUYUK_ESIK:
        return metin[:a.end()]
    return metin


# ── 2. BÖLÜM HİYERARŞİSİ (MADDE yoksa) ──────────────────────────────────────
# Numara + nokta + BÜYÜK harf. İki konum kabul edilir:
#   (a) paragraf başı  (satır başı veya \x1f sonrası)         → `\x1f2.1. Verginin konusu`
#   (b) KELİME sonrası (aynı paragrafta sıkışmış alt-başlık)  → `2.1. Verginin konusu 2.1.1. Konsolide…`
#
# (b) NEDEN GEREKLİ (ölçüm, 350474): `2.1.1.` metinde 11 kez geçiyor, paragraf başında yalnız 1
# kez — HTML başlık ile alt-başlığı aynı <p> içine koymuş. Yalnız (a) ile 18 gerçek başlık
# kaybediliyordu (`4.1.1. IIR kapsamında…`, `6.1.1.1.1. Gelir ve kurumlar vergisi…`).
# (b) NEDEN GÜVENLİ: lookbehind KELİME karakteri arar, cümle-sonu (`.`/`:`) DEĞİL. Cümle-içi atıf
# (`… 2.1. maddesinde`) küçük harfle devam ettiği için BÜYÜK-harf lookahead'i eler.
# Ölçüm: 350474 +18 işaret (12/12 gözle doğrulandı, hepsi gerçek başlık); 328127 +0 (gürültü yok).
_ONDALIK = re.compile(
    rf"(?:(?:^|{_PARA})[ \t]*|(?<=[\wçğıöşüÇĞİÖŞÜ]) )"
    rf"(\d{{1,2}}(?:\.\d{{1,2}})*)\.[ \t]+(?=[A-ZÇĞİÖŞÜ])"
)
# Roma: 'I-', 'II-', 'VIII-' + BÜYÜK harf (üst bölüm; 120107, 120106)
_ROMA = re.compile(rf"(?:^|{_PARA})[ \t]*([IVX]{{1,5}})[ \t]*[-–][ \t]*(?=[A-ZÇĞİÖŞÜ])")
# Roma altındaki rakam alt-başlığı. İki ayraç varyantı, KULLANIM BAĞLAMI FARKLI:
#
#   _N_TIRE      '1- Alacağın Türü'         → roma VAR ya da YOK, her iki kolda kullanılır
#   _N_ROMA_ALTI '1- …' VEYA '1. Verginin Konusu'  → YALNIZ roma bağlamında
#
# Nokta varyantı neden bağlama bağlı (ölçüm): 107458'de roma altı NOKTA kullanıyor; tire-only
# desen bunu göremeyip 36.191 krk'lık tek chunk üretiyordu (tavanı 1.45× aşar) → 18 birim,
# max 10.370. AMA `1.` deseni `_ONDALIK` ağacının KÖKÜ ile birebir çakışır: nokta varyantını
# roma-dışı kolda da kullansaydık, 350474'ün `1. Bir / 2. Iki` kökleri N- ailesine kaçar,
# `1.1`, `2.1` alt dalları hiç görülmez, ondalık ağacı çökerdi (regresyon testle yakalandı).
# Roma varsa hiyerarşi zaten iki seviyeli ve sabittir → çakışma yok.
_N_TIRE = re.compile(rf"(?:^|{_PARA})[ \t]*(\d{{1,3}})[ \t]*[-–][ \t]*(?=[A-ZÇĞİÖŞÜ])")
_N_ROMA_ALTI = re.compile(rf"(?:^|{_PARA})[ \t]*(\d{{1,3}})[ \t]*(?:[-–][ \t]*|\.[ \t]+)(?=[A-ZÇĞİÖŞÜ])")

_MIN_BOLUM = 2          # en az 2 başlık olmalı (tek eşleşme desen değil, rastlantı)
_BASLIK_MAX = 120       # başlık satırı bu kadardan uzunsa cümledir, başlık değil
_MIN_GOVDE = 200        # birimlerin MEDYAN gövdesi bundan küçükse: cetvel/liste, bölüm değil
_MIN_GIRIS = 200        # ara düğümün giriş metni bundan kısaysa salt başlıktır, birim değil
_HEDEF_MAX = 25000      # BGE-M3 pratik tavanı (~8192 token); bunu aşan chunk kesilir
_MIN_KOSU_ORANI = 0.5   # N- kolunda işaretlerin en az yarısı ardışık olmalı (107811: 0.25 → elenir)


def _derinlik(no: str) -> int:
    return no.count(".") + 1


def _azalan_kardesleri_ele(isaretler: list) -> list:
    """Aynı önek altında numarası GERİLEYEN (veya tekrar eden) işaretleri at.

    NEDEN (ölçüm, 350474): metin sonundaki tablo `1. Yıl`, `2. Yıl`, `3. Yıl` başlıkları
    kök bölüm numaralarıyla ÇAKIŞIYOR — no benzersiz değil, konum benzersiz. Yaprak ağacı
    bu sahte düğümlerle bozuluyordu (`2` bir yerde 699 krk giriş, başka yerde 7 krk hücre).

    KURAL: gerçek bölüm numaraları bir önek altında ARTAR (`6.1` → `6.2` → `6.3`). Tablo satırı
    `1`'e geri döner. Önek DEĞİŞİRSE gerileme sayılmaz (`2.3` → `3.1` meşrudur; yeni üst-bölüm).
    Kanun `fikra.py::_bentler` koşu şartının kardeş-grubuna uyarlanmış hali.

    ÖLÇÜM: 350474'te 4/4 sahte elendi, 0 gerçek başlık kurban edildi. 328127/106345'te 0 eleme.
    """
    out = []
    son: dict[str, int] = {}          # önek -> o önek altında görülen son numara
    for m in isaretler:
        onek, _, sonp = m.group(1).rpartition(".")
        try:
            v = int(sonp)
        except ValueError:
            out.append(m)
            continue
        onceki = son.get(onek)
        if onceki is not None and v <= onceki:
            continue                  # gerileme/tekrar → tablo satırı, bölüm değil
        son[onek] = v
        out.append(m)
    return out


def _sirali_kosu(nolar: list[str]) -> int:
    """Aynı seviyedeki numaraların en uzun ardışık (1,2,3…) koşusu.

    Kanun `fikra.py::_bentler`'deki koşu şartının karşılığı: gerçek bölüm numaraları sıralıdır;
    tablo satırı / cümle içi rakam sıçrar (`1. Yıl / 2. Yıl / 1. Yıl` → 350474'te gerçek veri).

    ÖNEK BAZLI: ondalık numaralar üst-bölüm içinde sıfırlanır (`1.1, 1.2` → `2.1, 2.2`).
    Koşu her önek (`1.`, `2.`) için AYRI hesaplanır, en uzunu döner. Düz numaralarda
    (`I-` altındaki `1-, 2-, 3-`) önek boştur → tek grup, davranış aynı.
    Ayrıca '1'e dönüş koşuyu kırmaz, yeniden başlatır (üst-bölüm değişimi)."""
    if not nolar:
        return 0
    gruplar: dict[str, list[int]] = {}
    for n in nolar:
        onek, _, son = n.rpartition(".")
        try:
            gruplar.setdefault(onek, []).append(int(son))
        except ValueError:
            continue

    en_iyi = 0
    for sonlar in gruplar.values():
        kosu = 0
        beklenen = 1
        for s in sonlar:
            if s == beklenen:
                kosu += 1
                beklenen += 1
            elif s == 1:
                kosu, beklenen = 1, 2
            else:
                kosu, beklenen = 0, 1
            en_iyi = max(en_iyi, kosu)
    return en_iyi


def _baslik_al(metin: str, konum: int) -> str:
    """İşaretten sonraki metni başlık olarak al: paragraf sınırına veya cümle sonuna kadar."""
    son = metin.find(_PARA, konum)
    if son == -1:
        son = len(metin)
    ham = metin[konum:min(son, konum + _BASLIK_MAX)].strip()
    # Başlık cümleyle devam ediyorsa ilk cümleyi al (ondalık başlıklar gövdeye yapışabilir).
    m = re.match(r"^([^.]{2,%d})" % _BASLIK_MAX, ham)
    return (m.group(1) if m else ham).strip()


def _dilimle(metin: str, isaretler: list) -> list:
    """[(no, baslik, bas, son)] — her işaretten bir sonrakine kadar."""
    out = []
    for i, m in enumerate(isaretler):
        bas = m.start()
        son = isaretler[i + 1].start() if i + 1 < len(isaretler) else len(metin)
        out.append((m.group(1), _baslik_al(metin, m.end()), bas, son))
    return out


def _roma_yapraklari(metin: str, roma: list, alt: list) -> list[Birim]:
    """Roma bölümlerini ve alt-başlıklarını yaprak kuralıyla birleştir.

    NEDEN (ölçüm, 105921): 6 roma bölümünün yalnız 1'inde alt-başlık vardı. Yalnız alt-başlıkları
    birim yapmak diğer 5 bölümün içeriğini yok ediyordu — `I- VERGİNİN KONUSU` (10.321 krk),
    `V- MATRAH, ORAN VE YETKİ` (7.137 krk) … alt kapsama yalnız %5.8. 107458/106785/120107'de
    de her birinde 1 roma bölümü (`II-`, `VII-`) kayboluyordu.

    Kural (`_ondalik_bolumler` yaprak kuralının roma karşılığı):
      · alt-başlığı OLMAYAN roma bölümü      → kendisi birim (yaprak)
      · alt-başlığı OLAN roma bölümünün girişi:
            ≥ `_MIN_GIRIS` → ayrı birim (giriş metni; kanunun 'madde giriş fıkrası' karşılığı)
            <  `_MIN_GIRIS` → salt başlık; `ust` metadata'sında yaşar
      · her alt-başlık → birim, `ust` = kapsayan roma
    """
    rd = _dilimle(metin, roma)
    out = []
    for rno, rbas, rb, rs in rd:
        icerdeki = [m for m in alt if rb <= m.start() < rs]
        if not icerdeki:
            out.append(Birim(no=rno, body=metin[rb:rs].strip(), tip="bolum", baslik=rbas))
            continue
        giris_son = icerdeki[0].start()
        if giris_son - rb >= _MIN_GIRIS:
            out.append(Birim(no=rno, body=metin[rb:giris_son].strip(), tip="bolum", baslik=rbas))
        for i, m in enumerate(icerdeki):
            son = icerdeki[i + 1].start() if i + 1 < len(icerdeki) else rs
            out.append(Birim(no=m.group(1), body=metin[m.start():son].strip(), tip="bolum",
                             baslik=_baslik_al(metin, m.end()), ust=[(rno, rbas)]))
    return out


def split_bolumler(metin: str) -> list[Birim]:
    """`MADDE` işareti yokken: numaralı bölüm hiyerarşisini çöz, atomik birimleri döndür.

    İki aile var, yapıları farklı:
      · ROMA + N- (120106, 120107): hiyerarşi iki seviyeli ve SABİT. `N-` alt-başlıkları
        sıralı ve gövdesi makulse atomik birim; değilse `I-` roma bölümleri birim olur.
      · ONDALIK (350474, 328127): derinlik dala göre değişir → `_ondalik_bolumler`, yaprak kuralı.

    Üst seviyeler kaybolmaz: her birimin `ust` alanında [(no, başlık)] olarak taşınır
    (kanunun kitap/kısım/bölüm hiyerarşi-yolu karşılığı).

    Bölüm bulunamazsa boş liste döner (çağıran tek-chunk'a düşer)."""
    ondalik = list(_ONDALIK.finditer(metin))
    roma = list(_ROMA.finditer(metin))
    ntire = list(_N_TIRE.finditer(metin))

    # ROMA + N- ailesi (120107: I- üst, 1- alt) — roma varsa bu aile kazanır.
    if len(roma) >= _MIN_BOLUM:
        # Roma bağlamında alt-başlık ayracı NOKTA da olabilir (107458). Çakışma yok: roma varsa
        # ondalık ağaç kökü aranmaz. Alt seviye yalnız SIRALI + gövdesi makulse atomik birim.
        alt = list(_N_ROMA_ALTI.finditer(metin))
        if len(alt) >= _MIN_BOLUM:
            _n, medyan, _asan = _seviye_puanla(metin, alt)
            # NOT: azalan-kardeş kapısı burada UYGULANMAZ — roma altında numara her bölümde
            # meşru olarak 1'e döner (106785: I- altında 1..6, II- altında 1..24). Önek
            # numarada değil KONUMDA. `_sirali_kosu` 1'e dönüşü zaten koşu-başı sayar.
            if (_sirali_kosu([m.group(1) for m in alt]) >= _MIN_BOLUM
                    and _MIN_GOVDE <= medyan <= _HEDEF_MAX):
                return _roma_yapraklari(metin, roma, alt)
        # yalnız roma (120106) — ya da alt güvenilmez (cetvel/liste). Roma gövdesi de makul olmalı.
        _n, r_medyan, _a = _seviye_puanla(metin, roma)
        if r_medyan > _HEDEF_MAX:
            return []                          # tek-parça roma → tek-chunk'tan farksız
        return [Birim(no=no, body=metin[b:s].strip(), tip="bolum", baslik=bas)
                for no, bas, b, s in _dilimle(metin, roma)]

    # ROMA yok ama N- var: sıralı + gövdesi makul ise bölüm say (aksi halde fıkra/cetvel → boş).
    if len(ntire) >= _MIN_BOLUM:
        n, medyan, _asan = _seviye_puanla(metin, ntire)
        # KOŞU ORANI (ölçüm, 107811): `_sirali_kosu >= 2` tek başına çok zayıf — 8 işaretin
        # 2'si ardışık olsa geçiyordu. 107811'in no'ları ['3','4','1','2','6','10','2','3']
        # (koşu/n = 0.25); bunlar bölüm değil madde-içi bent numaraları, içlerinde `a) b) c)`
        # var ve 74.512 krk'lık dev chunk üretiyorlardı. Gerçek bölüm listesi çoğunlukla ardışıktır.
        if (_sirali_kosu([m.group(1) for m in ntire]) >= max(_MIN_BOLUM, int(n * _MIN_KOSU_ORANI))
                and _MIN_GOVDE <= medyan <= _HEDEF_MAX):
            return [Birim(no=no, body=metin[b:s].strip(), tip="bolum", baslik=bas)
                    for no, bas, b, s in _dilimle(metin, ntire)]

    # ONDALIK ailesi (350474: 2. → 2.1. → 2.1.1. → … → 5.2.1.1.5)
    if len(ondalik) >= _MIN_BOLUM:
        return _ondalik_bolumler(metin, ondalik)

    return []


def _seviye_puanla(metin: str, isaretler: list) -> tuple[int, int, int]:
    """Bir seviyenin (birim_sayisi, medyan_govde, tavan_asan) üçlüsü."""
    if len(isaretler) < _MIN_BOLUM:
        return 0, 0, 0
    boy = sorted(s - b for _no, _bas, b, s in _dilimle(metin, isaretler))
    return len(boy), boy[len(boy) // 2], sum(1 for x in boy if x > _HEDEF_MAX)


def _ondalik_bolumler(metin: str, ondalik: list) -> list[Birim]:
    """Ondalık hiyerarşide YAPRAK düğümleri atomik birim yap; üst zinciri metadata'ya taşı.

    ═══ NEDEN "TEK SEVİYE SEÇ" DEĞİL (ölçümle terk edildi) ═══
    Eski kural tek bir derinlik seçip (`adaylar[0]`) yalnız o derinliğin işaretleriyle
    dilimliyordu. İki kusuru vardı:
      · İÇERİK KAYBI: seçilen derinlikte numarası olmayan bölümlerin metni hiçbir birime
        girmiyordu. 350474'te kapsama %77.3 — 139.021 karakter (%22.7) aranamaz haldeydi.
      · GRANÜLERİTE KAYBI: `2.1.1.1.1` gibi daha derin dallar seçilen seviyede kesiliyordu.

    ═══ YAPRAK KURALI (uygulanan) ═══
    Her işaret bir düğüm. Bir sonraki işaret `<no>.` öneki taşıyorsa bu düğümün ÇOCUĞU vardır.
      · çocuksuz düğüm → gövde = bir sonraki işarete kadar          → BİRİM (yaprak)
      · çocuklu düğüm  → gövde = ilk çocuğuna kadar (giriş metni)
            giriş ≥ `_MIN_GIRIS` → BİRİM (kanunun 'madde giriş fıkrası'nın karşılığı)
            giriş <  `_MIN_GIRIS` → salt başlık; birim değil, `ust` metadata'sında yaşar
    Derinlik dala göre değişir — 350474'te 1..5 arası, en derin yaprak `4.1.7.1.1`.

    ═══ ÖLÇÜM (yaprak vs seviye) ═══
      belge    kural     birim  medyan   max    >25K  kapsama
      350474   seviye     134    2637   56.525    1    77.3%
      350474   YAPRAK     303    1324   20.664    0   100.0%   ← dev chunk 0, kayıp 0
      328127   seviye      27    2449   22.455    0    95.9%
      328127   YAPRAK      68     989   11.134    0    99.3%

    Ön koşullar (0-yanlış-pozitif kapıları):
      (a) `_azalan_kardesleri_ele` — tablo satırı `1. Yıl / 2. Yıl` kök no'larla çakışır.
      (b) `_sirali_kosu ≥ _MIN_BOLUM` — numaralar gerçekten ardışık mı?
      (c) medyan gövde ≥ `_MIN_GOVDE` — 106345 cetveli (medyan 92 krk) bölüm değil, çöp.
    Hiçbiri geçmezse bölüm yok sayılır (çağıran tek-chunk'a düşer)."""
    ondalik = _azalan_kardesleri_ele(ondalik)
    if len(ondalik) < _MIN_BOLUM:
        return []
    nolar = [m.group(1) for m in ondalik]
    if _sirali_kosu(nolar) < _MIN_BOLUM:
        return []                             # sıralı değil → tablo/cümle rakamı

    n = len(ondalik)
    secili = []                               # (indeks, no, bas, son)
    for i, m in enumerate(ondalik):
        no = nolar[i]
        sonraki = ondalik[i + 1].start() if i + 1 < n else len(metin)
        cocuklu = i + 1 < n and nolar[i + 1].startswith(no + ".")
        if cocuklu and sonraki - m.start() < _MIN_GIRIS:
            continue                          # salt başlık → `ust` zincirinde yaşar
        secili.append((i, no, m.start(), sonraki))
    if len(secili) < _MIN_BOLUM:
        return []

    # ÇÖP KAPISI (106345): birimlerin medyan gövdesi çok küçükse bu bir cetvel/liste.
    boy = sorted(s - b for _i, _no, b, s in secili)
    if boy[len(boy) // 2] < _MIN_GOVDE:
        return []

    # Üst zincir: her düğümün önek-atalarını başlıklarıyla topla (`2.1.1` → `2`, `2.1`).
    baslik = {}
    for i, m in enumerate(ondalik):
        baslik.setdefault(nolar[i], _baslik_al(metin, m.end()))

    out = []
    for _i, no, b, s in secili:
        ustler = []
        parcalar = no.split(".")
        for k in range(1, len(parcalar)):
            uno = ".".join(parcalar[:k])
            if uno in baslik:
                ustler.append((uno, baslik[uno]))
        out.append(Birim(no=no, body=metin[b:s].strip(), tip="bolum",
                         baslik=baslik[no], ust=ustler))
    return out


# ── 3. ANA GİRİŞ ────────────────────────────────────────────────────────────
def split_birimler(metin: str) -> list[Birim]:
    """Tebliğ metnini atomik birimlere böl.

    Sıra (ölçümle belirlendi):
      1. Tebliğ-sonu ek kuyruğunu kırp (sahte madde kaynağı).
      2. `MADDE N` varsa madde birimi (924 tebliğin %96.2'si).
      3. Yoksa numaralı bölüm hiyerarşisi (yaprak düğümler + dolgun ara-düğüm girişleri).
      4. O da yoksa boş liste → çağıran (corpus) tek-chunk'a düşer (düz metin tebliği).
    """
    metin = _strip_teblig_sonu_ek(metin)
    m = list(_MADDE.finditer(metin))
    if m:
        out = []
        for i, mm in enumerate(m):
            bas = mm.end()
            son = m[i + 1].start() if i + 1 < len(m) else len(metin)
            prefix = (mm.group(1) or mm.group(3) or "").strip()
            numara = mm.group(2) or mm.group(4)
            no = f"{_canon_prefix(prefix)} {numara}" if prefix else numara
            out.append(Birim(no=no, body=metin[bas:son].strip(), tip="madde"))
        return out
    return split_bolumler(metin)
