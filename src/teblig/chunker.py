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

3. EN-DERİN SEVİYE = ATOMİK BİRİM (chunk boyutu ölçümüyle karar verildi)
   Üst seviyeyi chunk yapmak içeriği kesiyor (BGE-M3 tavanı ~25K karakter):

     belge    seviye        chunk  medyan krk   >25K   kanun-maddesi boyutunda
     350474   1  (N.)          16     28.252      8    0
     350474   2  (N.N.)        38      9.581      7    5
     350474   3  (N.N.N.)     134      2.638      1   75   ← seçildi
     120107   ROMA (I-)         9     40.739      6    0
     120107   N-              107      2.434      3   55   ← seçildi
     120106   ROMA (I-)         4      2.871      0    3   ← seçildi (N- yok)

   Sabit seviye seçilemez: `120106`'da doğru birim ROMA, `120107`'de `N-`.
   → `split_bolumler` **mevcut en derin seviyeyi** birim yapar, üst seviyeleri hiyerarşi
   metadata'sı olarak taşır (kanunun `tree.py` + `chunker.py` iş bölümünün karşılığı).
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
# Paragraf başında (satır başı veya \x1f sonrası) numara + ayraç + BÜYÜK harf.
# Seviyeler tek desende: '2', '2.1', '2.1.1', '2.2.4.1' — nokta sayısı = derinlik.
_ONDALIK = re.compile(
    rf"(?:^|{_PARA})[ \t]*(\d{{1,2}}(?:\.\d{{1,2}})*)\.[ \t]+(?=[A-ZÇĞİÖŞÜ])"
)
# Roma: 'I-', 'II-', 'VIII-' + BÜYÜK harf (üst bölüm; 120107, 120106)
_ROMA = re.compile(rf"(?:^|{_PARA})[ \t]*([IVX]{{1,5}})[ \t]*[-–][ \t]*(?=[A-ZÇĞİÖŞÜ])")
# Roma altındaki rakam-tire alt-başlık: '1- Alacağın Türü' (Title-Case)
_N_TIRE = re.compile(rf"(?:^|{_PARA})[ \t]*(\d{{1,3}})[ \t]*[-–][ \t]*(?=[A-ZÇĞİÖŞÜ])")

_MIN_BOLUM = 2          # en az 2 başlık olmalı (tek eşleşme desen değil, rastlantı)
_BASLIK_MAX = 120       # başlık satırı bu kadardan uzunsa cümledir, başlık değil
_MIN_GOVDE = 200        # bir seviyenin medyan gövdesi bundan küçükse: başlık listesi/cetvel, bölüm değil
_HEDEF_MAX = 25000      # BGE-M3 pratik tavanı (~8192 token); bunu aşan chunk kesilir


def _derinlik(no: str) -> int:
    return no.count(".") + 1


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


def split_bolumler(metin: str) -> list[Birim]:
    """`MADDE` işareti yokken: numaralı bölüm hiyerarşisini çöz, EN DERİN seviyeyi birim yap.

    Neden en derin (ölçüm, modül docstring'i): üst seviyeler 28K-40K karakter medyanlı chunk
    üretir → BGE-M3 tavanını (~25K) aşar, içerik kesilir. En derin seviye 2.4K-2.6K medyan
    verir — kanun maddesi boyutuna (medyan ~404 krk, p90 1741) yakın, aranabilir.

    Üst seviyeler kaybolmaz: her birimin `ust` alanında [(no, başlık)] olarak taşınır
    (kanunun kitap/kısım/bölüm hiyerarşi-yolu karşılığı).

    Bölüm bulunamazsa boş liste döner (çağıran tek-chunk'a düşer)."""
    ondalik = list(_ONDALIK.finditer(metin))
    roma = list(_ROMA.finditer(metin))
    ntire = list(_N_TIRE.finditer(metin))

    # ROMA + N- ailesi (120107: I- üst, 1- alt) — roma varsa bu aile kazanır.
    if len(roma) >= _MIN_BOLUM:
        ust_dilim = _dilimle(metin, roma)
        # Alt seviye (N-) yalnız SIRALI ve gövdesi makul ise atomik birim olur; yoksa roma kalır.
        if len(ntire) >= _MIN_BOLUM:
            n, medyan, _asan = _seviye_puanla(metin, ntire)
            sirali = _sirali_kosu([m.group(1) for m in ntire]) >= _MIN_BOLUM
            if sirali and _MIN_GOVDE <= medyan <= _HEDEF_MAX:
                out = []
                for no, bas, b, s in _dilimle(metin, ntire):
                    ustler = [(rno, rbas) for rno, rbas, rb, rs in ust_dilim if rb <= b < rs]
                    out.append(Birim(no=no, body=metin[b:s].strip(), tip="bolum",
                                     baslik=bas, ust=ustler))
                return out
        # yalnız roma (120106) — ya da N- güvenilmez (cetvel/liste). Roma gövdesi de makul olmalı.
        _n, r_medyan, _a = _seviye_puanla(metin, roma)
        if r_medyan > _HEDEF_MAX:
            return []                          # tek-parça roma → tek-chunk'tan farksız
        return [Birim(no=no, body=metin[b:s].strip(), tip="bolum", baslik=bas)
                for no, bas, b, s in ust_dilim]

    # ROMA yok ama N- var: sıralı + gövdesi makul ise bölüm say (aksi halde fıkra/cetvel → boş).
    if len(ntire) >= _MIN_BOLUM:
        n, medyan, _asan = _seviye_puanla(metin, ntire)
        if (_sirali_kosu([m.group(1) for m in ntire]) >= _MIN_BOLUM
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
    """Ondalık hiyerarşide ATOMİK SEVİYEYİ seç, üstlerini metadata yap.

    NEDEN "en derin" DEĞİL (ölçümde çıkan üç hata):
      · 350474 (613K): en derin `5.2.1.1.5` yalnız birkaç yerde var → 28 birim, `2.`/`3.`
        bölümlerinin içeriği hiç birim olmadı (KAYIP) ve üst-zincir karıştı.
      · 328127 (101K): en derin `4.2.3.1.3` → 3 birim, biri 65K (tavanı 2.6× aşıyor).
      · 106345 ( 27K): `1. Form…  2. Form…` cetvel listesi → 51 birim, medyan 91 krk (çöp).

    DOĞRU SEÇİM: geçerli seviyeler arasından **en az tavan-aşan** olanı seç.
    Ön eleme: (a) en az `_MIN_BOLUM` işaret, (b) sıralı-koşu şartı (kanun `_bentler` koşu
    mantığı — tablo satırı `1. Yıl / 2. Yıl` sıçrar), (c) `_MIN_GOVDE` ≤ medyan gövde ≤
    `_HEDEF_MAX`: alt sınır başlık listesi/cetveli eler (106345: medyan 91 krk), üst sınır
    "tek parça" seviyeleri eler (106785 seviye-1: 2 birim, medyan 414K → tek-chunk'tan farksız).
    Sonra puan: önce tavanı aşan birim sayısı (az iyi), eşitse medyanı büyük (dolgun) seviye.
    350474'te bu seviye 3'tür (134 birim, medyan 2638, 1 aşan); "en derin" kuralı seviye 5'i
    seçip 28 birim + 195K'lık dev chunk üretiyordu.
    Hiçbiri geçmezse bölüm yok sayılır (çağıran tek-chunk'a düşer)."""
    seviyeler = sorted({_derinlik(m.group(1)) for m in ondalik})
    adaylar = []
    for d in seviyeler:
        ms = [m for m in ondalik if _derinlik(m.group(1)) == d]
        n, medyan, asan = _seviye_puanla(metin, ms)
        if n < _MIN_BOLUM:
            continue
        if _sirali_kosu([m.group(1) for m in ms]) < _MIN_BOLUM:
            continue                          # sıralı değil → tablo/cümle rakamı
        if not (_MIN_GOVDE <= medyan <= _HEDEF_MAX):
            continue                          # cetvel (çok küçük) ya da tek-parça (çok büyük)
        adaylar.append((asan, -medyan, d, ms))
    if not adaylar:
        return []

    adaylar.sort()                            # en az aşan; eşitse medyanı büyük (dolgun) olan
    _asan, _negmed, derinlik, yaprak = adaylar[0]
    ust_dilimler = {
        d: _dilimle(metin, [m for m in ondalik if _derinlik(m.group(1)) == d])
        for d in seviyeler if d < derinlik
    }
    out = []
    for no, bas, b, s in _dilimle(metin, yaprak):
        ustler = []
        for d in sorted(ust_dilimler):
            # kapsayan üst dilim (no önek uyumu da aranır: '2.1' → üstü '2')
            for uno, ubas, ub, us in ust_dilimler[d]:
                if ub <= b < us and no.startswith(uno + "."):
                    ustler.append((uno, ubas))
                    break
        out.append(Birim(no=no, body=metin[b:s].strip(), tip="bolum",
                         baslik=bas, ust=ustler))
    return out


# ── 3. ANA GİRİŞ ────────────────────────────────────────────────────────────
def split_birimler(metin: str) -> list[Birim]:
    """Tebliğ metnini atomik birimlere böl.

    Sıra (ölçümle belirlendi):
      1. Tebliğ-sonu ek kuyruğunu kırp (sahte madde kaynağı).
      2. `MADDE N` varsa madde birimi (924 tebliğin %96.2'si).
      3. Yoksa numaralı bölüm hiyerarşisi (en derin seviye).
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
