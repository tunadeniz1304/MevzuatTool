# -*- coding: utf-8 -*-
"""Atıf modu — ayrıştırıcı (kanun.retrieval.atif). Veri/model/ağ yok."""
import pytest

from kanun.retrieval.atif import (
    SON_FIKRA, Atif, Yorum, atif_ayristir, ayristir, katla, madde_anahtari, madde_no_goster,
)


def _tek(sorgu, **kw):
    atiflar = atif_ayristir(sorgu, **kw)
    assert len(atiflar) == 1, f"{sorgu!r} → {atiflar}"
    return atiflar[0]


def _ozet(a):
    return (a.kanun_nolari, a.madde_no, a.fikra, a.bent)


# ---- yardımcılar -------------------------------------------------------------------------------
def test_katla_uzunluk_korur_ve_harf_duyarsiz():
    for s in ("İİK'nın", "IIK", "Geçici Madde", "MÜKERRER", "Kişisel", "TCK’nın", "a b"):
        assert len(katla(s)) == len(s)
    assert katla("İİK") == katla("IIK") == katla("ıık") == "iik"
    assert katla("Geçici MADDE") == "gecici madde"
    assert katla("TCK’nın") == "tck'nin"


@pytest.mark.parametrize("madde_no, anahtar", [
    ("141", ("asil", "141")),
    ("123/A", ("asil", "123/A")),
    ("123/a", ("asil", "123/A")),
    ("Geçici 1", ("gecici", "1")),
    ("GEÇİCİ 1", ("gecici", "1")),
    ("Ek 3", ("ek", "3")),
    ("Mükerrer 298", ("mukerrer", "298")),
    ("Geçici 5/A", ("gecici", "5/A")),
    ("007", ("asil", "7")),
])
def test_madde_anahtari_korpus_gosterimi(madde_no, anahtar):
    assert madde_anahtari(madde_no) == anahtar


def test_madde_no_goster_geri_cevirir():
    assert madde_no_goster("gecici", "1") == "Geçici 1"
    assert madde_no_goster("mukerrer", "298") == "Mükerrer 298"
    assert madde_no_goster("asil", "123/A") == "123/A"


# ---- kanun tanıma ------------------------------------------------------------------------------
@pytest.mark.parametrize("sorgu, kanun_no", [
    ("5237 sayılı Kanun m. 141", "5237"),
    ("5237 sayılı Türk Ceza Kanununun 141. maddesi", "5237"),
    ("5237 s. K. md. 141", "5237"),
    ("5237 s.K. m.141", "5237"),
    ("Kanun No: 5237 Madde 141", "5237"),
    ("5237 sayılı TCK'nın 141 inci maddesi", "5237"),
    ("5237 numaralı Kanun 141. madde", "5237"),
    ("5237 sayılı'nın 141. maddesi", "5237"),
    ("TCK m. 141", "5237"),
    ("TCK’nın 141. maddesi", "5237"),
    ("türk ceza kanunu 141. madde", "5237"),
    ("TÜRK CEZA KANUNU'NUN 141'İNCİ MADDESİ", "5237"),
    ("CMK m. 141", "5271"),
    ("TMK m. 141", "4721"),
    ("Medeni Kanun m. 141", "4721"),
    ("TBK m. 141", "6098"),
    ("Borçlar Kanunu m. 141", "6098"),
    ("HMK m. 141", "6100"),
    ("İİK m. 141", "2004"),
    ("IIK m. 141", "2004"),
    ("icra iflas kanunu m. 141", "2004"),
    ("TTK m. 141", "6102"),
    ("VUK m. 141", "213"),
    ("GVK m. 141", "193"),
    ("KVK m. 141", "5520"),
    ("Kurumlar Vergisi K. m. 141", "5520"),
    ("KDVK m. 141", "3065"),
    ("KDV Kanunu m. 141", "3065"),
    ("AATUHK m. 141", "6183"),
    ("DMK m. 141", "657"),
    ("Devlet Memurları K. m. 141", "657"),
    ("İş K. m. 141", "4857"),
    ("İşK m. 141", "4857"),
    ("iş kanunu madde 141", "4857"),
    ("4857 sayılı İş Kanunu'nun 141. maddesi", "4857"),
    ("KVKK m. 141", "6698"),
    ("Anayasa m. 141", "2709"),
    ("Anayasa'nın 141. maddesi", "2709"),
    ("AY m. 141", "2709"),
    ("2709 sayılı Anayasa m. 141", "2709"),
])
def test_kanun_tanima(sorgu, kanun_no):
    a = _tek(sorgu)
    assert a.kanun_nolari == (kanun_no,) and a.madde_no == "141"


def test_kanun_kaynagi_ve_ad_ipucu():
    assert _tek("5237 sayılı Kanun m. 1").kanun_kaynak == "numara"
    assert _tek("TCK m. 1").kanun_kaynak == "kisaltma"
    assert _tek("Türk Ceza Kanunu m. 1").kanun_kaynak == "ad"
    a = _tek("6551 sayılı Mahalli İdareler Kanununun 5. maddesi")
    assert a.kanun_nolari == ("6551",) and a.kanun_ipucu == "mahalli idareler"


def test_korpus_adlari_ile_tanima_ve_uzun_ad_kazanir():
    adlar = [("deniz is kanunu", ("854",)), ("imar kanunu", ("3194",)), ("is kanunu", ("4857",))]
    assert _tek("İmar Kanunu 32. madde", kanun_adlari=adlar).kanun_nolari == ("3194",)
    assert _tek("imar kanununun 32. maddesi", kanun_adlari=adlar).kanun_kaynak == "korpus_adi"
    assert _tek("Deniz İş Kanunu m. 5", kanun_adlari=adlar).kanun_nolari == ("854",)
    assert atif_ayristir("İmar Kanunu 32. madde") == []          # korpus adları olmadan tanınmaz
    assert atif_ayristir("Deniz İş Kanunu m. 5") == []           # ve İş Kanunu (4857) SANILMAZ


# ---- madde / fıkra / bent ----------------------------------------------------------------------
@pytest.mark.parametrize("sorgu, beklenen", [
    ("TCK m. 141", ("141", None, None)),
    ("TCK md. 141", ("141", None, None)),
    ("TCK mad. 141", ("141", None, None)),
    ("Tck m 141", ("141", None, None)),
    ("TCK madde 141", ("141", None, None)),
    ("TCK 141. madde", ("141", None, None)),
    ("TCK'nın 141 inci maddesi", ("141", None, None)),
    ("TCK 141'inci maddesinin", ("141", None, None)),
    ("TCK 141", ("141", None, None)),
    ("TCK 141 hırsızlık suçu", ("141", None, None)),
    ("TTK m. 1530", ("1530", None, None)),
    ("TCK md.141/2", ("141", 2, None)),
    ("tck madde 141 fıkra 2", ("141", 2, None)),
    ("TCK m. 141 f. 2", ("141", 2, None)),
    ("TCK 141. maddenin 2. fıkrası", ("141", 2, None)),
    ("TCK 141 inci maddesinin 2 nci fıkrası", ("141", 2, None)),
    ("TCK 141. maddesinin ikinci fıkrası", ("141", 2, None)),
    ("TCK 141. maddesinin on birinci fıkrası", ("141", 11, None)),
    ("TCK 141. maddesinin (2) numaralı fıkrası", ("141", 2, None)),
    ("TCK m. 141 son fıkrası", ("141", SON_FIKRA, None)),
    ("TCK 102/2-a", ("102", 2, "a")),
    ("HMK m. 119/1-ğ", ("119", 1, "ğ")),
    ("HMK 119/1(ğ)", ("119", 1, "ğ")),
    ("CMK 100/3-a", ("100", 3, "a")),
    ("TMK m. 166/II", ("166", 2, None)),
    ("TCK m. 53 f. 1 b. a", ("53", 1, "a")),
    ("TCK m. 53 bent a", ("53", None, "a")),
    ("KVKK m. 11 (ç) bendi", ("11", None, "ç")),
    ("KVKK 11. madde a bendi", ("11", None, "a")),
    ("KVKK 11. madde ı) bendi", ("11", None, "ı")),
    ("6698 sayılı Kanunun 11. maddesinin birinci fıkrasının (ç) bendi", ("11", 1, "ç")),
    ("GVK 40. maddenin (1) numaralı bendi", ("40", None, "1")),
    ("GVK 40. maddenin 7. bendi", ("40", None, "7")),
    ("GVK m. 40 bent 7", ("40", None, "7")),
    ("VUK mükerrer 298", ("Mükerrer 298", None, None)),
    ("213 sayılı VUK Mükerrer Madde 298", ("Mükerrer 298", None, None)),
    ("GVK geçici 67", ("Geçici 67", None, None)),
    ("193 sayılı Kanunun geçici 67 nci maddesi", ("Geçici 67", None, None)),
    ("193 sayılı Kanun Geçici Madde 67", ("Geçici 67", None, None)),
    ("GVK geç. m. 67", ("Geçici 67", None, None)),
    ("657 sayılı Kanunun Ek 3. maddesi", ("Ek 3", None, None)),
    ("DMK ek madde 3", ("Ek 3", None, None)),
    ("6183 sayılı Kanunun 48/A maddesi", ("48/A", None, None)),
    ("AATUHK m. 48/a", ("48/A", None, None)),
])
def test_madde_fikra_bent(sorgu, beklenen):
    a = _tek(sorgu)
    assert (a.madde_no, a.fikra, a.bent) == beklenen


def test_madde_tipi_ve_numara_yorumda():
    a = _tek("GVK geçici 67")
    assert a.yorum == Yorum("gecici", "67")
    assert isinstance(a, Atif) and a.ham == "GVK geçici 67"


def test_belirsiz_harf_eki_alternatif_uretir():
    a = _tek("VUK 359/a")                                     # harfli madde 359/A ya da 359. madde (a) bendi
    assert a.yorum == Yorum("asil", "359/A")
    assert a.alternatifler == (Yorum("asil", "359", bent="a", aciklama="harf->bent"),)


def test_tek_harfli_roma_rakami_alternatif_uretir():
    a = _tek("TMK 166/I")                                     # harfli 166/I ya da 166. madde 1. fıkra
    assert a.yorum.madde_no == "166/I"
    assert a.alternatifler[0] == Yorum("asil", "166", fikra=1, aciklama="roma->fikra")
    assert _tek("TMK 166/II").alternatifler == ()             # çok harfli Roma rakamı belirsiz değil


def test_birden_cok_atif_sirasiyla():
    a = atif_ayristir("TCK m. 141 ve CMK m. 100")
    assert [_ozet(x) for x in a] == [(("5237",), "141", None, None), (("5271",), "100", None, None)]
    b = atif_ayristir("TCK m. 141 ve m. 142")                  # ikinci madde aynı kanuna bağlanır
    assert [x.madde_no for x in b] == ["141", "142"] and {x.kanun_nolari for x in b} == {("5237",)}


def test_kanun_maddeden_sonra_gelebilir():
    assert _ozet(_tek("141. madde TCK")) == (("5237",), "141", None, None)
    assert _ozet(_tek("geçici madde 1, 6111 sayılı kanun")) == (("6111",), "Geçici 1", None, None)


def test_ayni_atif_tekrari_tekillesir():
    assert len(atif_ayristir("TCK m. 141 (TCK m. 141)")) == 1


def test_tarih_madde_sonrasinda_atifi_bozmaz():
    assert _ozet(_tek("TCK 141, 2/3/2024 tarihli")) == (("5237",), "141", None, None)


# ---- yanlış-pozitif: doğal dil sorgusu atıf SANILMAMALI ------------------------------------------
@pytest.mark.parametrize("sorgu", [
    "kira artışı nasıl belirlenir",
    "memurun disiplin cezası",
    "işçinin kıdem tazminatı nasıl hesaplanır",
    "boşanma davasında velayet kime verilir",
    "2 yıl hapis cezası gerektiren suçlar",
    "TCK'da 2 yıl hapis cezası",
    "TCK 5 yıl",
    "hmk 2 hafta içinde istinaf",
    "İİK'ya göre haciz 7 gün içinde",
    "Medeni Kanun 3 ay bekleme süresi",
    "vergi usul kanununa göre 5 yıl zamanaşımı",
    "TCK 2004 yılında değişti",
    "TCK 5 %",
    "Türk Ceza Kanunu'nda hırsızlık suçu",
    "5237 sayılı kanun",
    "kişisel verilerin korunması kanunu kapsamında açık rıza",
    "madde 5",
    "141. madde",
    "TCK'daki 5 madde değişti",
    "TCK tehlikeli madde 3 ton",
    "uyuşturucu madde ticareti",
    "375 sayılı KHK m. 5",
    "375 sayılı Kanun Hükmünde Kararname m. 5",
    "1 sayılı Cumhurbaşkanlığı Kararnamesi madde 5",
    "2023/15 sayılı karar",
    "5 sayılı listenin 3. maddesi",
    "9200 sayılı Resmî Gazete'de yayımlanan 5. madde",
    "ek 3 ay süre verilir",
    "iş kazası tazminatı",
    "işkence suçu 5 yıl",
    "Anayasa Mahkemesi kararı 2023/45",
    "anayasal haklar",
    "bu ay 5. madde",
    "kdv oranı yüzde 18",
    "50 m2 daire TCK",
])
def test_dogal_dil_atif_sanilmaz(sorgu):
    assert atif_ayristir(sorgu) == []


def test_tani_neden_atif_olmadigini_soyler():
    assert "kanun tanındı (5237)" in ayristir("5237 sayılı kanun").tani()
    assert "kanun tanınmadı" in ayristir("madde 5").tani()
    assert ayristir("kira artışı").tani() == "sorguda kanun + madde atfı bulunamadı"
    assert ayristir("TCK m. 141").tani() == ""


def test_etiket():
    assert _tek("TCK 102/2-a").etiket() == "5237 s. K. m. 102 f. 2 b. a"
    assert _tek("TCK m. 141 son fıkrası").etiket() == "5237 s. K. m. 141 son f."
