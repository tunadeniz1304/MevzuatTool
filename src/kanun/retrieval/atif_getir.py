# -*- coding: utf-8 -*-
"""Atıf modu — kesin getirme (ADR-0019): ayrıştırılmış atıf → korpus maddesi (+ fıkra/bent alt-parçası).

Getirme yolu = BELLEK İÇİ korpus indeksi (Qdrant payload filtresi DEĞİL):
  - Anahtar (kanun_no, madde_tipi, madde_numara) → o maddenin korpus kayıtları (LİSTE: kanun_no tertip
    çakışması — 6551 iki kanun — ve aynı kanunda iki 'Geçici 1' olabilir; kayıt mevzuat_id'yi taşır).
  - Kayıt yalnız küçük alanları + korpus dosyasındaki bayt OFSETİNİ tutar; tam satır (metin + fikralar
    ağacı) eşleşince diskten okunur → ~31k maddelik indeks birkaç MB, fıkra ağaçları bellekte değil.
  - Neden Qdrant değil: payload'da mevzuat_id / madde_tipi / fikralar YOK (fıkra/bent getirilemez),
    kanun_no/madde_no payload index'i yok, ve Qdrant index'i korpusun gerisinde (1.678 maddede yürürlük
    uyuşmazlığı, ADR-0015) → atıf modu bayat yürürlük döndürürdü. Korpus tek doğruluk kaynağıdır.

Çözüm kuralları (`atif_coz`):
  - Kanun korpusta yoksa → 'kanun_yok'; kanun var madde yoksa → 'madde_yok' (çağıran doğal dile düşer).
  - Aynı kanun_no altında birden çok mevzuat_id (tertip çakışması) maddeyi taşıyorsa: sorgudaki kanun adı
    ipucu tek bir kanunu açıkça seçiyorsa o; yoksa HEPSİ döner ve `coklu_mevzuat=True` (sessizce
    birini seçmek yanlış kanunu "kesin" diye sunardı). Madde yalnız birinde varsa doğal olarak o döner.
  - Fıkra '(N)' numarasıyla aranır (numarasız tek fıkrada sıra). Fıkra→bent toleransı: atıf 'fıkra N'
    diyor, maddede N. fıkra yok ama 'N.' işaretli bent varsa o bent döner, `tolerans='fikra->bent'`
    (Türk hukuk dilinde numaralı bende 'fıkra' denir — status.md dürüstlük notu).
  - Yürürlük FİLTRELENMEZ: atıf edilen madde mülgaysa da döner; `yurutluk` + uyarı taşır (kesin atfı
    "bulunamadı" diye gizlemek yanıltıcı olurdu). Doğal dil modunun yürürlük filtresi değişmez.
  - Belirsiz slash eki ('359/a', '166/I'): birincil yorum (harfli madde) madde düzeyinde bulunursa
    kabul; değilse alternatif yorum yalnız istenen alt-parça TAM bulunursa kabul edilir.

Mod seçimi (`modlu_ara`): 'otomatik' (atıf ayrıştırılıp çözülürse atıf, değilse doğal dil), 'atif',
'dogal'. Atıf ayrıştırılamayan sorguda doğal dil çağrısı HybridArama.ara ile birebir aynıdır.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

from .atif import SON_FIKRA, ayristir, kanun_no_norm, katla, madde_anahtari, tr_kucuk

log = logging.getLogger(__name__)

MODLAR = ("otomatik", "atif", "dogal")
MULGA = "mülga"


class KorpusDegisti(RuntimeError):
    """İndeks kurulduktan sonra korpus dosyası değişmiş (ofsetler geçersiz) — servisi yeniden başlatın."""


# ---- indeks -----------------------------------------------------------------------------------
@dataclass
class AtifKaydi:
    madde_id: str
    mevzuat_id: str
    kanun_no: str
    kanun_ad: str
    madde_no: str
    madde_tipi: str
    yurutluk: str
    sira: int                         # korpus sırası (deterministik çıktı sırası)
    ofset: int | None = None          # korpus dosyasında satır başı (bayt)
    chunk: dict | None = None         # bellek içi kurulumda tam satır (test / küçük korpus)


def _kayit(r, sira, ofset=None, chunk=None):
    m = r["metadata"]
    return AtifKaydi(madde_id=str(r["id"]),
                     mevzuat_id=str(m.get("mevzuat_id") or str(r["id"]).split("-")[0]),
                     kanun_no=str(m["kanun_no"]), kanun_ad=m.get("kanun_ad") or "",
                     madde_no=str(m["madde_no"]), madde_tipi=m.get("madde_tipi") or "",
                     yurutluk=m.get("yurutluk") or "", sira=sira, ofset=ofset, chunk=chunk)


class AtifIndeks:
    """(kanun_no, madde_tipi, madde_numara) → [AtifKaydi]. `kanun_adlari` ayrıştırıcıya korpus adlarını verir."""

    def __init__(self, kayitlar, korpus_yol=None):
        self.korpus_yol = korpus_yol
        self._anahtar = {}
        self._kanunlar = set()
        adlar = {}
        for k in kayitlar:
            kn = kanun_no_norm(k.kanun_no)
            tip, numara = madde_anahtari(k.madde_no)
            self._anahtar.setdefault((kn, tip, numara), []).append(k)
            self._kanunlar.add(kn)
            ad = " ".join(katla(k.kanun_ad).split())
            if len(ad) >= 8:                                    # dejenere/boş adlar tanımaya katılmaz
                adlar.setdefault(ad, set()).add(kn)
        # uzun-önce: 'Türk Ticaret Kanununun Yürürlük ... Kanun' 'Türk Ticaret Kanunu'ndan önce denensin
        self.kanun_adlari = sorted(((a, tuple(sorted(n))) for a, n in adlar.items()),
                                   key=lambda x: (-len(x[0]), x[0]))
        self._n = len(kayitlar)

    @classmethod
    def bellekten(cls, chunks):
        """Korpus satırları (dict) listesinden indeks — testler ve küçük korpuslar için (tam satır bellekte)."""
        return cls([_kayit(r, i, chunk=r) for i, r in enumerate(chunks)])

    def __len__(self):
        return self._n

    def kanun_var(self, kanun_no):
        return kanun_no_norm(kanun_no) in self._kanunlar

    def bul(self, kanun_no, madde_tipi, madde_numara):
        return list(self._anahtar.get((kanun_no_norm(kanun_no), madde_tipi, madde_numara), ()))

    def chunk(self, kayit):
        """Kaydın tam korpus satırı (metin + metadata.fikralar). Dosyadan ofsetle okunur, id doğrulanır."""
        if kayit.chunk is not None:
            return kayit.chunk
        with open(self.korpus_yol, "rb") as f:
            f.seek(kayit.ofset)
            satir = f.readline()
        try:
            r = json.loads(satir)
        except ValueError:
            r = None
        if not isinstance(r, dict) or str(r.get("id")) != kayit.madde_id:
            raise KorpusDegisti(f"{self.korpus_yol}: ofset {kayit.ofset} artık {kayit.madde_id} değil — "
                                "korpus indeks kurulduktan sonra değişmiş; servisi yeniden başlatın")
        return r


def atif_indeks_kur(korpus_yol="data/kanun/korpus.jsonl"):
    """Korpus JSONL → AtifIndeks (tek geçiş; satırlar ikili modda okunur ki ofsetler bayt cinsinden olsun)."""
    kayitlar = []
    with open(korpus_yol, "rb") as f:
        while True:
            ofset = f.tell()
            satir = f.readline()
            if not satir:
                break
            if satir.strip():
                kayitlar.append(_kayit(json.loads(satir), len(kayitlar), ofset=ofset))
    return AtifIndeks(kayitlar, korpus_yol=korpus_yol)


# ---- alt-parça (fıkra / bent) -----------------------------------------------------------------
@dataclass
class AltParca:
    fikra: str | None                 # '(2)' ya da None (numarasız tek fıkra)
    bent: str | None                  # 'a)' / '1.' ya da None (fıkra düzeyi)
    metin: str
    yurutluk: str
    tolerans: str | None = None       # 'fikra->bent': atıftaki 'fıkra N', 'N.' bendine çözüldü


_FIKRA_NO = re.compile(r"\(\s*([0-9]+)\s*\)")


def _fikra_int(no):
    m = _FIKRA_NO.fullmatch((no or "").strip())
    return int(m.group(1)) if m else None


def _isaret(isaret):
    """Bent işareti → karşılaştırma biçimi: 'a)' → 'a', '1.' → '1', 'Ç)' → 'ç'."""
    return tr_kucuk((isaret or "").strip().rstrip(").").strip())


def _fikra_etiket(n):
    return "son fıkra" if n == SON_FIKRA else f"{n}. fıkra"


def _fikra_sec(fikralar, n):
    if not fikralar:
        return None
    if n == SON_FIKRA:
        return fikralar[-1]
    numarali = [f for f in fikralar if _fikra_int(f.get("no")) is not None]
    if numarali:
        return next((f for f in numarali if _fikra_int(f.get("no")) == n), None)
    return fikralar[n - 1] if 1 <= n <= len(fikralar) else None   # numarasız fıkralar: sıra


def _bent_ara(fikralar, hedef, yalniz_numarali=False):
    for fk in fikralar:
        for b in fk.get("bentler") or []:
            isr = (b.get("isaret") or "").strip()
            if _isaret(isr) == hedef and (not yalniz_numarali or isr.endswith(".")):
                return fk, b
    return None, None


def _parca(fk, b=None, tolerans=None):
    d = b if b is not None else fk
    return AltParca(fikra=fk.get("no"), bent=None if b is None else b.get("isaret"),
                    metin=d.get("text") or "", yurutluk=d.get("yurutluk") or "", tolerans=tolerans)


def alt_parca_bul(fikralar, fikra=None, bent=None):
    """Maddenin fikralar ağacında istenen fıkra/bendi bul → (AltParca | None, tam, uyarılar).
    tam=False: istenen düzey tam bulunamadı (madde ya da fıkra düzeyinde kalındı / hiç bulunamadı)."""
    if fikra is None and bent is None:
        return None, True, []
    hedef = None
    if fikra is not None:
        hedef = _fikra_sec(fikralar, fikra)
        if hedef is None:
            if fikra != SON_FIKRA:
                fk, b = _bent_ara(fikralar, str(fikra), yalniz_numarali=True)
                if b is not None:
                    uyari = [f"maddede {fikra}. fıkra yok; '{fikra}.' bendi döndü (numaralı bende fıkra denmesi)"]
                    if bent is not None:
                        uyari.append(f"({bent}) bendi aranmadı")
                    return _parca(fk, b, "fikra->bent"), bent is None, uyari
            return None, False, [f"{_fikra_etiket(fikra)} bulunamadı"]
        if bent is None:
            return _parca(hedef), True, []
    fk, b = _bent_ara([hedef] if hedef is not None else fikralar, bent)
    if b is not None:
        return _parca(fk, b), True, []
    if hedef is not None:
        return _parca(hedef), False, [f"({bent}) bendi bulunamadı; fıkra döndü"]
    return None, False, [f"({bent}) bendi bulunamadı"]


# ---- çözüm ------------------------------------------------------------------------------------
@dataclass
class AtifEslesme:
    kayit: AtifKaydi
    chunk: dict
    alt_parca: AltParca | None = None
    uyarilar: list = field(default_factory=list)
    tam: bool = True

    @property
    def metadata(self):
        return self.chunk.get("metadata") or {}

    @property
    def metin(self):
        return self.chunk.get("text") or ""


@dataclass
class AtifCozum:
    atif: object                      # atif.Atif
    durum: str                        # eslesti | kanun_yok | madde_yok
    eslesmeler: list = field(default_factory=list)
    yorum: object = None              # çözülen atif.Yorum (alternatif olabilir)
    coklu_mevzuat: bool = False       # birden çok mevzuat_id döndü (kanun_no çakışması çözülemedi)
    aciklama: str | None = None


_GENEL_SOZ = {"kanun", "kanunu", "kanunun", "kanuna", "kanunda", "hakkinda", "ile", "ve", "dair", "bazi",
              "kanunlarda", "degisiklik", "yapilmasina", "iliskin", "sayili", "turk", "turkiye"}


def _ad_kokleri(ad):
    return {w[:5] for w in re.findall(r"[a-z0-9]+", katla(ad or "")) if len(w) >= 3 and w not in _GENEL_SOZ}


def _cakisma_ayikla(kayitlar, ipucu):
    """Birden çok mevzuat_id → ad ipucu tek kanunu açıkça seçiyorsa onu bırak. → (kayıtlar, coklu)."""
    gruplar = {}
    for k in kayitlar:
        gruplar.setdefault(k.mevzuat_id, []).append(k)
    if len(gruplar) <= 1:
        return kayitlar, False
    kokler = _ad_kokleri(ipucu)
    if kokler:
        skor = {mid: len(kokler & _ad_kokleri(ks[0].kanun_ad)) for mid, ks in gruplar.items()}
        en = max(skor.values())
        enler = [mid for mid, s in skor.items() if s == en]
        if en > 0 and len(enler) == 1:
            return gruplar[enler[0]], False
    return kayitlar, True


def atif_coz(atif, indeks):
    """Atıf → AtifCozum. Yorumlar sırayla denenir (birincil, sonra alternatifler)."""
    nolar = [n for n in atif.kanun_nolari if indeks.kanun_var(n)]
    kanun_etiket = "/".join(atif.kanun_nolari)
    if not nolar:
        return AtifCozum(atif, "kanun_yok", aciklama=f"{kanun_etiket} sayılı kanun korpusta yok")
    for i, yorum in enumerate(atif.yorumlar):
        kayitlar = [k for n in nolar for k in indeks.bul(n, yorum.madde_tipi, yorum.madde_numara)]
        if not kayitlar:
            continue
        kayitlar, coklu = _cakisma_ayikla(sorted(kayitlar, key=lambda k: k.sira), atif.kanun_ipucu)
        ayni_no = len(kayitlar) - len({k.mevzuat_id for k in kayitlar})
        eslesmeler = []
        for k in kayitlar:
            chunk = indeks.chunk(k)
            md = chunk.get("metadata") or {}
            parca, tam, uyarilar = alt_parca_bul(md.get("fikralar") or [], yorum.fikra, yorum.bent)
            uyarilar = list(uyarilar)
            if yorum.aciklama == "harf->bent":
                uyarilar.insert(0, f"'{atif.yorum.madde_no}' harfli maddesi yok; {yorum.madde_no}. maddenin "
                                   f"({yorum.bent}) bendi olarak çözüldü")
            elif yorum.aciklama == "roma->fikra":
                uyarilar.insert(0, f"'{atif.yorum.madde_no}' harfli maddesi yok; Roma rakamı "
                                   f"{yorum.fikra}. fıkra olarak çözüldü")
            if (md.get("yurutluk") or k.yurutluk) == MULGA:
                uyarilar.append("madde mülga (yürürlükte değil) — atıf modunda yürürlük filtresi uygulanmaz")
            if md.get("tasindigi_kanun"):
                uyarilar.append(f"yönlendirme kaydı: hüküm {md['tasindigi_kanun']} sayılı kanuna işlenmiş")
            if ayni_no:
                uyarilar.append("bu kanunda aynı numaralı birden çok madde var")
            eslesmeler.append(AtifEslesme(k, chunk, parca, uyarilar, tam))
        if i > 0:                                               # alternatif yorum: yalnız TAM çözülenler
            eslesmeler = [e for e in eslesmeler if e.tam]
            if not eslesmeler:
                continue
        aciklama = None
        if coklu:
            adaylar = ", ".join(f"{k.kanun_no} '{k.kanun_ad}' (mevzuat_id {k.mevzuat_id})"
                                for k in {e.kayit.mevzuat_id: e.kayit for e in eslesmeler}.values())
            aciklama = (f"{yorum.madde_no}. madde birden çok kanunda var ({adaylar}); "
                        "kanun adı ipucu seçemedi, hepsi döndü")
        return AtifCozum(atif, "eslesti", eslesmeler, yorum, coklu, aciklama)
    return AtifCozum(atif, "madde_yok",
                     aciklama=f"{kanun_etiket} sayılı kanunda {atif.yorum.madde_no}. madde yok")


# ---- mod seçimi -------------------------------------------------------------------------------
@dataclass
class ModluSonuc:
    """modlu_ara çıktısı. mod: kullanılan mod ('atif' | 'dogal').
    durum: None (atıf denenmedi / ayrıştırılmadı) | 'eslesti' | 'kismi' | 'eslesme_yok' |
           'ayristirilamadi' (mod='atif' ama atıf yok) | 'indeks_yok'. mod='dogal' + durum dolu = düşüş."""
    mod: str
    istenen_mod: str
    dogal: object = None              # doğal dil yolunda HybridArama.ara çıktısı (AramaSonucu), dokunulmadan
    satirlar: list = field(default_factory=list)    # atıf modunda [(atif_sira 1-tabanlı, AtifEslesme)]
    atiflar: list = field(default_factory=list)
    cozumler: list = field(default_factory=list)
    durum: str | None = None
    aciklama: str | None = None
    sure_ms: dict = field(default_factory=dict)

    @property
    def dusus(self):
        """Atıf denendi ama doğal dil moduna düşüldü mü?"""
        return self.mod == "dogal" and self.durum is not None


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


def modlu_ara(dogal, indeks, sorgu, mod="otomatik", top_k=10, yururlukte_only=True, rerank=None):
    """Sorgu → ModluSonuc.

    dogal  : `ara(sorgu, top_k, yururlukte_only, rerank)` sunan nesne (HybridArama)
    indeks : AtifIndeks ya da None (yüklü değilse atıf denemesi doğal dile düşer)
    Doğal dil yolu her zaman `dogal.ara(sorgu, top_k=, yururlukte_only=, rerank=)` çağrısıdır — atıf
    ayrıştırılamayan sorgunun sonucu HybridArama.ara ile birebir aynıdır. Atıf modunda top_k kesilir,
    yururlukte_only ve rerank uygulanmaz (kesin getirme; sıra = atıfların sorgudaki sırası)."""
    if mod not in MODLAR:
        raise ValueError(f"mod={mod!r} — geçerli: {MODLAR}")

    def dogal_dil(durum=None, aciklama=None, atiflar=(), cozumler=()):
        sonuc = dogal.ara(sorgu, top_k=top_k, yururlukte_only=yururlukte_only, rerank=rerank)
        return ModluSonuc("dogal", mod, dogal=sonuc, atiflar=list(atiflar), cozumler=list(cozumler),
                          durum=durum, aciklama=aciklama, sure_ms=getattr(sonuc, "sure_ms", {}))

    if mod == "dogal":
        return dogal_dil()
    t0 = time.perf_counter()
    try:
        ayr = ayristir(sorgu, kanun_adlari=indeks.kanun_adlari if indeks is not None else None)
    except Exception:                                           # ayrıştırıcı hatası doğal dili bozmasın
        log.exception("atıf ayrıştırıcı hatası — doğal dil moduna düşülüyor")
        return dogal_dil("ayristirilamadi", "atıf ayrıştırıcı hatası") if mod == "atif" else dogal_dil()
    t_ayr = _ms(t0)
    if not ayr.atiflar:
        return dogal_dil("ayristirilamadi", ayr.tani()) if mod == "atif" else dogal_dil()
    if indeks is None:
        return dogal_dil("indeks_yok", "atıf ayrıştırıldı ama atıf indeksi yüklü değil → doğal dil",
                         ayr.atiflar)

    t1 = time.perf_counter()
    cozumler = [atif_coz(a, indeks) for a in ayr.atiflar]
    t_getir = _ms(t1)
    eslesen = [c for c in cozumler if c.eslesmeler]
    if not eslesen:
        neden = "; ".join(c.aciklama for c in cozumler if c.aciklama)
        return dogal_dil("eslesme_yok", f"{neden} → doğal dil moduna düşüldü", ayr.atiflar, cozumler)

    satirlar, gorulen = [], set()
    for i, c in enumerate(cozumler, 1):
        for e in c.eslesmeler:
            if e.kayit.madde_id not in gorulen:
                gorulen.add(e.kayit.madde_id)
                satirlar.append((i, e))
    notlar = [c.aciklama for c in cozumler if c.aciklama]
    return ModluSonuc("atif", mod, satirlar=satirlar[:top_k], atiflar=ayr.atiflar, cozumler=cozumler,
                      durum="eslesti" if len(eslesen) == len(cozumler) else "kismi",
                      aciklama="; ".join(notlar) or None,
                      sure_ms={"ayristirma": t_ayr, "getirme": t_getir, "toplam": _ms(t0)})
