# -*- coding: utf-8 -*-
"""Atıf modu — ayrıştırıcı (kanun.retrieval.atif) + kesin getirme (kanun.retrieval.atif_getir).

Veri/model/ağ yok: korpus satırları aşağıda elle kurulur (çakışan kanun_no, aynı numaralı iki madde,
mülga madde, numaralı bentli eski stil madde, yönlendirme kaydı ...); dosya ofsetli indeks tmp_path'e
yazılan küçük bir JSONL ile sınanır.
"""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from kanun.ids import slug
from kanun.retrieval import atif_getir
from kanun.retrieval.atif import (
    SON_FIKRA, Atif, Yorum, atif_ayristir, ayristir, katla, madde_anahtari, madde_no_goster,
)
from kanun.retrieval.atif_getir import (
    MODLAR, AtifIndeks, KorpusDegisti, alt_parca_bul, atif_coz, atif_indeks_kur, modlu_ara,
)
from kanun.retrieval.search import AramaSonucu, BM25Index, HybridArama, Sonuc


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


# İcra ve ceza pratiğinde yerleşik noktalı yazım ('İ.İ.K.', 'T.M.K.') ve kısaltmadan sonra nokta ('TMK. 166')
# hiç tanınmıyordu → atıf sorgusu doğal dile gidiyordu.
@pytest.mark.parametrize("sorgu, beklenen", [
    ("İ.İ.K. m. 89", (("2004",), "89", None, None)),
    ("İ.İ.K.'nın 89. maddesi", (("2004",), "89", None, None)),
    ("T.M.K. m. 166", (("4721",), "166", None, None)),
    ("T.C.K. 141. madde", (("5237",), "141", None, None)),
    ("C.M.K. m. 231/5", (("5271",), "231", 5, None)),
    ("H.M.K. 107", (("6100",), "107", None, None)),
    ("TMK. 166", (("4721",), "166", None, None)),
])
def test_noktali_kisaltmalar_taninir(sorgu, beklenen):
    assert _ozet(_tek(sorgu)) == beklenen


def test_noktali_kisaltma_kimlik_numarasina_takilmaz():
    assert atif_ayristir("T.C. Kimlik No 12345") == []
    assert atif_ayristir("T.C.Kimlik 5. madde") == []


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


# 'İş K. 25/I-b' (haklı fesih atıflarının yerleşik yazımı): tek harfli Roma rakamından sonraki bent düşüyordu
# (harf ekinden sonrası alt-bent sayılıp okunmuyordu) → yalnız fıkra ya da madde dönüyordu.
@pytest.mark.parametrize("sorgu, birincil, alternatif", [
    ("İş Kanunu 25/I-b", ("25/I", None, "b"), ("25", 1, "b")),
    ("4857 sayılı Kanunun 25/I-b maddesi", ("25/I", None, "b"), ("25", 1, "b")),
    ("İş K. m. 25/V (a)", ("25/V", None, "a"), ("25", 5, "a")),
])
def test_tek_harfli_roma_fikradan_sonraki_bent_okunur(sorgu, birincil, alternatif):
    a = _tek(sorgu)
    assert (a.madde_no, a.fikra, a.bent) == birincil
    assert [(y.madde_no, y.fikra, y.bent, y.aciklama) for y in a.alternatifler] == [alternatif + ("roma->fikra",)]


def test_roma_olmayan_harf_ekinden_sonrasi_alt_bent_kalir():
    a = _tek("VUK 359/a-1")                                   # '1' alt-bent: okunmaz (bilinen sınır)
    assert a.yorum == Yorum("asil", "359/A") and a.alternatifler == (Yorum("asil", "359", bent="a",
                                                                           aciklama="harf->bent"),)


def test_birden_cok_atif_sirasiyla():
    a = atif_ayristir("TCK m. 141 ve CMK m. 100")
    assert [_ozet(x) for x in a] == [(("5237",), "141", None, None), (("5271",), "100", None, None)]
    b = atif_ayristir("TCK m. 141 ve m. 142")                  # ikinci madde aynı kanuna bağlanır
    assert [x.madde_no for x in b] == ["141", "142"] and {x.kanun_nolari for x in b} == {("5237",)}


def test_kanun_maddeden_sonra_gelebilir():
    assert _ozet(_tek("141. madde TCK")) == (("5237",), "141", None, None)
    assert _ozet(_tek("geçici madde 1, 6111 sayılı kanun")) == (("6111",), "Geçici 1", None, None)


# Yargı kararlarındaki kalıp: '5237 sayılı TCK'nın 6545 sayılı Kanunla değişik 141. maddesi'. Madde en yakın
# önceki kanuna bağlandığı için DEĞİŞTİREN kanuna (6545) gidiyordu: yanlış kanun ya da doğal dile düşüş.
@pytest.mark.parametrize("sorgu", [
    "TCK'nın 6545 sayılı Kanunla değişik 141. maddesi",
    "5237 sayılı Kanunun 5560 sayılı Kanun ile değişik 141. maddesi",
    "TCK'nın 6545 sayılı Kanun'la değiştirilen 141. maddesi",
    "Türk Ceza Kanunu'nun 6545 sayılı Kanunla eklenen 141. maddesi",
])
def test_degistiren_kanun_maddenin_sahibi_sayilmaz(sorgu):
    assert _ozet(_tek(sorgu)) == (("5237",), "141", None, None)


def test_degistiren_kanun_kendi_maddesiyle_ve_tek_basina():
    a = atif_ayristir("6545 sayılı Kanunun 68. maddesiyle değişik TCK'nın 141. maddesi")
    assert [_ozet(x) for x in a] == [(("6545",), "68", None, None), (("5237",), "141", None, None)]
    assert atif_ayristir("6545 sayılı Kanunla değişik 141. madde") == []      # asıl kanun anılmamış


# 'N/M. maddesi', 'N/M-a maddesi' (fıkra/bent bölü işaretiyle + madde sözü) yalnız kanundan HEMEN sonra
# (yalın numara yolu) okunuyordu; araya söz girince ('değişik', 'kapsamında') atıf kaçıyordu.
@pytest.mark.parametrize("sorgu, beklenen", [
    ("5237 sayılı TCK'nın 6352 sayılı Kanun ile değişik 220/6. maddesi", (("5237",), "220", 6, None)),
    ("5510 sayılı Kanun kapsamında 4/1-a maddesi", (("5510",), "4", 1, "a")),
    ("TCK'nın değişik 50/3. maddesi", (("5237",), "50", 3, None)),
    ("50/3. madde TCK", (("5237",), "50", 3, None)),
    ("İş Kanunu kapsamında 25/II-e maddesi", (("4857",), "25", 2, "e")),
])
def test_bolu_fikrali_madde_sozu_kanundan_uzakta_da_okunur(sorgu, beklenen):
    assert _ozet(_tek(sorgu)) == beklenen


def test_degisik_nitelemesi_tamlayan_kanunu_degistiren_yapmaz():
    # yalnız vasıta hâli ('Kanunla', 'Kanun ile') değiştiren kanundur; 'TCK'nın değişik' sahibin kendisi
    assert _ozet(_tek("TCK'nın değişik 141. maddesi")) == (("5237",), "141", None, None)
    assert _ozet(_tek("5237 sayılı Kanunun değişik 141. maddesi")) == (("5237",), "141", None, None)


def test_ayni_atif_tekrari_tekillesir():
    assert len(atif_ayristir("TCK m. 141 (TCK m. 141)")) == 1


def test_ardisik_bosluklar_atifi_bozmaz():
    # PDF / Word'den kopyalanan metinde çift boşluk ya da NBSP+boşluk olağan; desenler tek '\s?' bekliyordu
    assert _ozet(_tek("TCK m.  141")) == (("5237",), "141", None, None)
    assert _ozet(_tek("5237  sayılı  Kanun  m. 141")) == (("5237",), "141", None, None)
    assert _ozet(_tek("TCK m. 141  f.  2")) == (("5237",), "141", 2, None)
    assert atif_ayristir("Deniz  İş  Kanunu  m. 5") == []          # İş Kanunu (4857) SANILMAZ
    assert _tek("TCK  m.  141").ham == "TCK m. 141"


def test_tarih_madde_sonrasinda_atifi_bozmaz():
    assert _ozet(_tek("TCK 141, 2/3/2024 tarihli")) == (("5237",), "141", None, None)


@pytest.mark.parametrize("sorgu, madde_no", [
    ("4857 sayılı İş Kanunu m. 53 yıllık ücretli izin", "53"),     # açık 'm.': süre sözcüğü kapı değil
    ("İş Kanunu madde 63 haftalık çalışma süresi", "63"),         # 'madde N' yalnız fiziksel miktarla düşer
    ("TMK m. 24 kişilik hakları", "24"),
    ("TMK 24 kişilik hakkının korunması", "24"),                  # 'kişilik' sayım sözcüğü değil
    ("TMK 166 evlilik birliğinin sarsılması", "166"),
    ("TCK md. 2 yıl", "2"),
])
def test_konu_sozcugu_birim_sanilmaz(sorgu, madde_no):
    assert _tek(sorgu).madde_no == madde_no


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
    "TMK 4 çocuk velayet",
    "İş K. 50 işçi çalıştıran işyeri",
    "TCK 18 yaşından küçükler",
    "TCK'ya ek 3 madde eklendi",
    "geçici 3 aylık görevlendirme TCK",
    "TCK 5 bin lira adli para cezası",
])
def test_dogal_dil_atif_sanilmaz(sorgu):
    assert atif_ayristir(sorgu) == []


# Kanundan hemen sonraki yalın sayı bir MİKTARIN başı olabilir: tarih, aralık, kıyas, oran, yaş. Bu
# sorgular otomatik modda ilgisiz tek bir maddeye (TCK m.1, m.2 ...) skor 1.0 ile kaçırılıyordu.
@pytest.mark.parametrize("sorgu", [
    "Türk Medeni Kanunu 1 Ocak 2002'de yürürlüğe girdi",
    "TCK 1 Haziran 2005 tarihinde yürürlüğe girdi",
    "6698 sayılı Kanun 7 Nisan 2016",
    "TCK 2-5 yıl hapis cezası",
    "TCK 2 ila 5 yıl hapis cezası gerektiren suçlar",
    "TCK 3 ile 7 yıl arası",
    "İş Kanunu 30 ila 50 işçi",
    "İş Kanunu 30'dan fazla işçi çalıştıran işyeri",
    "TCK 2'den fazla kişi",
    "İş Kanunu 100 ve daha fazla işçi",
    "İş Kanunu 30 veya daha fazla işçi",
    "TCK 1/3 oranında indirim",
    "İİK 1/4 oranında haciz",
    "TCK 1/2 nispetinde artırılır",
    "KDV Kanunu 20 oranında vergi",
    "TMK 18 yaşındaki çocuk",
    "TCK 15 yaşındaki çocuk cinsel istismar",
    "TCK 3 kişiyle birlikte işlenen hırsızlık",
    "uyuşturucu madde 10 gramdan fazla TCK",
    "uyuşturucu madde 5 kilogram TCK",
])
def test_yalin_sayi_miktar_ifadesiyse_atif_sanilmaz(sorgu):
    assert atif_ayristir(sorgu) == []


@pytest.mark.parametrize("sorgu, maddeler", [
    ("TCK 141 ila 145", ["141"]),                 # birimsiz aralık madde aralığıdır (yalnız ilk uç)
    ("TCK m. 141-145", ["141"]),
    ("TCK 62 1/6 indirim", ["62"]),               # kesir maddeden SONRA: madde 62 kalır
    ("TCK 141 ve 142", ["141"]),
    ("İş Kanunu 17 ihbar süresi", ["17"]),
])
def test_miktar_kapisi_gercek_atifi_dusurmez(sorgu, maddeler):
    assert [a.madde_no for a in atif_ayristir(sorgu)] == maddeler


# 'eski/mülga/önceki' ya da yabancı ülke nitelemeli kanun adı BUGÜNKÜ Türk kanunu değildir: 'eski İş Kanunu'
# 1475, 'eski TCK' 765, 'İsviçre Borçlar Kanunu' OR. Kısaltma/ad tablosu bunları 4857 / 5237 / 6098'e eşleyip
# başka kanunun maddesini kesin atıf diye döndürüyordu.
@pytest.mark.parametrize("sorgu", [
    "eski TCK'nın 141. maddesi",
    "mülga TCK m. 491",
    "eski Borçlar Kanunu m. 18",
    "mülga Borçlar Kanunu 18. madde",
    "eski İş Kanunu'nun 14. maddesi",
    "önceki Türk Ticaret Kanunu m. 18",
    "İsviçre Borçlar Kanunu m. 41",
    "Alman Medeni Kanunu m. 1",
    "ESKİ TCK M. 141",
])
def test_nitelemeli_kanun_adi_guncel_kanuna_eslenmez(sorgu):
    assert atif_ayristir(sorgu) == []


def test_nitelemeli_korpus_adi_ve_numarali_yazim():
    adlar = [("imar kanunu", ("3194",))]
    assert atif_ayristir("eski İmar Kanunu m. 18", kanun_adlari=adlar) == []
    assert _ozet(_tek("765 sayılı eski TCK m. 491")) == (("765",), "491", None, None)   # numara açık
    assert _ozet(_tek("yeni TCK m. 141")) == (("5237",), "141", None, None)
    # eski kanunun maddesi sonraki (güncel) kanuna da bağlanmaz
    assert [_ozet(a) for a in atif_ayristir("eski TCK m. 491 ve TCK m. 142")] == [(("5237",), "142", None, None)]
    assert "numarasıyla" in ayristir("eski TCK m. 141").tani()


# Madde sözünden hemen önce kanun DIŞI bir belge (yönetmelik, tebliğ, KHK, sözleşme ...) geliyorsa madde o
# belgenindir; sorgunun başka yerindeki kanuna bağlanıp o kanunun maddesi diye dönüyordu.
@pytest.mark.parametrize("sorgu", [
    "Yıllık Ücretli İzin Yönetmeliği'nin 5. maddesi İş Kanunu",
    "İş Kanunu'na dayanılarak çıkarılan yönetmeliğin 5. maddesi",
    "657 sayılı DMK ve 375 sayılı KHK'nın ek 9. maddesi",
    "TCK ve Avrupa İnsan Hakları Sözleşmesi'nin 6. maddesi",
    "KDVK ve KDV Genel Uygulama Tebliğinin 3. maddesi",
    "Anayasa değişikliği teklifinin 5. maddesi",
])
def test_baska_belgenin_maddesi_kanuna_baglanmaz(sorgu):
    assert atif_ayristir(sorgu) == []


# 'N sayılı' + TAM başlık: yalnız ilk sözcüğe bakan ret listesi ('KHK', 'Cumhurbaşkanlığı Kararnamesi')
# uzun resmî başlıkları kaçırıyordu → CB kararnamesi / KHK / tebliğ numarası kanun numarası sanılıyordu.
@pytest.mark.parametrize("sorgu", [
    "1 sayılı Cumhurbaşkanlığı Teşkilatı Hakkında Cumhurbaşkanlığı Kararnamesi uyarınca 5. madde",
    "696 sayılı Olağanüstü Hal Kapsamında Bazı Düzenlemeler Yapılması Hakkında Kanun Hükmünde Kararname "
    "uyarınca 3. madde",
    "5 sayılı Genel Tebliğ kapsamında 3. madde",
])
def test_sayili_tam_baslikli_kanun_disi_belge_kanun_sayilmaz(sorgu):
    assert atif_ayristir(sorgu) == []


def test_kararname_onaylayan_kanun_kanundur():
    a = _tek("7071 sayılı Olağanüstü Hal Kapsamında Bazı Düzenlemeler Yapılması Hakkında Kanun Hükmünde "
             "Kararnamenin Değiştirilerek Kabul Edilmesine Dair Kanun'un 3. maddesi")
    assert (a.kanun_nolari, a.madde_no) == (("7071",), "3")


def test_belge_sozu_maddeden_sonra_gelirse_atif_kalir():
    assert _ozet(_tek("TCK'nın 5. maddesi ve yönetmelik")) == (("5237",), "5", None, None)


def test_tumu_buyuk_harfli_sorguda_ay_yalniz_guclu_bicimle_anayasa():
    # 'AY' Anayasa'dır kuralı büyük harfe dayanır; tümü büyük harfli sorguda bu sinyal yoktur
    assert atif_ayristir("HER AY 1 TARİHİNDE KİRA ÖDENİR") == []
    assert _ozet(_tek("AY M. 10")) == (("2709",), "10", None, None)
    assert _ozet(_tek("AY 10'a göre eşitlik")) == (("2709",), "10", None, None)


def test_tani_neden_atif_olmadigini_soyler():
    assert "kanun tanındı (5237)" in ayristir("5237 sayılı kanun").tani()
    assert "kanun tanınmadı" in ayristir("madde 5").tani()
    assert ayristir("kira artışı").tani() == "sorguda kanun + madde atfı bulunamadı"
    assert ayristir("TCK m. 141").tani() == ""


def test_etiket():
    assert _tek("TCK 102/2-a").etiket() == "5237 s. K. m. 102 f. 2 b. a"
    assert _tek("TCK m. 141 son fıkrası").etiket() == "5237 s. K. m. 141 son f."


# =================================================================================================
# Kesin getirme — sahte korpus (gerçek korpus şeması: {id, text, metadata{..., fikralar[]}})
# =================================================================================================
def _f(no, text, bentler=(), yurutluk="yürürlükte"):
    return {"no": no, "text": text, "bentler": list(bentler), "yurutluk": yurutluk}


def _b(isaret, text, yurutluk="yürürlükte"):
    return {"isaret": isaret, "text": text, "yurutluk": yurutluk, "alt_bentler": []}


def _chunk(mid, kanun_no, madde_no, kanun_ad, fikralar=(), yurutluk="yürürlükte", text=None, id_ek="",
           **metadata):
    meta = {"mevzuat_id": mid, "kanun_no": kanun_no, "kanun_ad": kanun_ad, "madde_no": madde_no,
            "madde_baslik": f"Başlık {madde_no}", "madde_tipi": madde_anahtari(madde_no)[0],
            "yurutluk": yurutluk, "fikralar": list(fikralar)}
    meta.update(metadata)
    return {"id": f"{mid}-{slug(madde_no)}{id_ek}",
            "text": f"{kanun_ad} {madde_no} metni" if text is None else text, "metadata": meta}


TCK, KVKK, GVK, VUK, TMK = ("TÜRK CEZA KANUNU", "KİŞİSEL VERİLERİN KORUNMASI KANUNU",
                            "GELİR VERGİSİ KANUNU", "VERGİ USUL KANUNU", "TÜRK MEDENİ KANUNU")
KORPUS = [
    _chunk("100", "5237", "141", TCK, [_f("(1)", "(1) Zilyedinin rızası olmadan ..."),
                                       _f("(2)", "(2) Değeri az olan ...")]),
    _chunk("100", "5237", "142", TCK, [_f("(1)", "(1) Hırsızlık suçunun; a) ... b) ... işlenmesi hâlinde",
                                          [_b("a)", "a) Kime ait olursa olsun kamu kurum ..."),
                                           _b("b)", "b) Halkın yararlanmasına mahsus ...")])]),
    _chunk("100", "5237", "143", TCK, [_f(None, "(Mülga: 1/1/2020-9999/1 md.)", yurutluk="mülga")],
           yurutluk="mülga"),
    _chunk("200", "6698", "11", KVKK, [_f("(1)", "(1) Herkes, veri sorumlusuna başvurarak ...",
                                          [_b("a)", "a) Kişisel veri işlenip işlenmediğini öğrenme,"),
                                           _b("b)", "b) Bilgi talep etme,"),
                                           _b("ç)", "ç) Aktarıldığı üçüncü kişileri bilme,")])]),
    # eski stil: numarasız tek fıkra + numaralı bentler (GVK m.40 deseni) → 'fıkra N' = 'N.' bendi
    _chunk("300", "193", "40", GVK, [_f(None, "Safi kazancın tespiti için ...: 1. ... 2. ... 7. ...",
                                        [_b("1.", "1. Ticari kazancın elde edilmesi ..."),
                                         _b("2.", "2. Hasılatın elde edilmesi ..."),
                                         _b("7.", "7. İşle ilgili zararlar ...")])]),
    # tertip çakışması: aynı kanun_no (6551) altında iki ayrı kanun (iki mevzuat_id)
    _chunk("400", "6551", "5", "ÖRNEK MAHALLİ İDARELER KANUNU"),
    _chunk("401", "6551", "5", "ÖRNEK ENERJİ PİYASASI KANUNU"),
    _chunk("400", "6551", "9", "ÖRNEK MAHALLİ İDARELER KANUNU"),
    # aynı kanunda aynı numaralı iki madde (ids.py: -1 / -2)
    _chunk("500", "6111", "Geçici 1", "ÖRNEK YAPILANDIRMA KANUNU", id_ek="-1"),
    _chunk("500", "6111", "Geçici 1", "ÖRNEK YAPILANDIRMA KANUNU", id_ek="-2"),
    _chunk("600", "6183", "48", "AMME ALACAKLARININ TAHSİL USULÜ HAKKINDA KANUN"),
    _chunk("600", "6183", "48/A", "AMME ALACAKLARININ TAHSİL USULÜ HAKKINDA KANUN"),
    _chunk("700", "213", "359", VUK, [_f(None, "Aşağıda yazılı fiilleri ...",
                                         [_b("a)", "a) Vergi kaçakçılığı ..."), _b("b)", "b) ...")])]),
    _chunk("700", "213", "Mükerrer 298", VUK),
    _chunk("800", "4721", "166", TMK, [_f(f"({i})", f"({i}) TMK 166 fıkra {i}") for i in range(1, 5)]),
    _chunk("810", "7000", "5", "ÖRNEK DENEME KANUNU", [_f("(1)", "(1) deneme")]),
    _chunk("810", "7000", "5/I", "ÖRNEK DENEME KANUNU"),
    _chunk("900", "5000", "7", "ÖRNEK YÖNLENDİRME KANUNU", text="", madde_tipi="islenmistir_yonlendirme",
           tasindigi_kanun="5237", yerine_islenmistir=True),
    _chunk("950", "3194", "32", "İMAR KANUNU", [_f(None, "Bu Kanuna aykırı yapılan yapılar ...")]),
    _chunk("951", "854", "5", "DENİZ İŞ KANUNU"),
    _chunk("952", "4857", "5", "İŞ KANUNU"),
    # numaralı fıkra (2) VE (1) içinde '2.' bendi: '29/2' fıkra (2)'ye gider, bent ipucu uyarısı
    _chunk("310", "3065", "29", "KATMA DEĞER VERGİSİ KANUNU",
           [_f("(1)", "(1) indirim: 1. ... 2. ...", [_b("1.", "1. birinci bent"), _b("2.", "2. ikinci bent")]),
            _f("(2)", "(2) ikinci fıkra")]),
    # çakışma + aynı kanunda tekrar karışık: 6552 m.8 iki kanunda, biri iki kez
    _chunk("402", "6552", "8", "ÖRNEK ALFA KANUNU"),
    _chunk("403", "6552", "8", "ÖRNEK BETA KANUNU"),
    _chunk("403", "6552", "8", "ÖRNEK BETA KANUNU", id_ek="-2"),
    # çakışma + alternatif yorum: '12/a' → yalnız (a) bendi olan kanun kalır
    _chunk("404", "6553", "12", "ÖRNEK GAMA KANUNU", [_f(None, "giriş", [_b("a)", "a) gama bendi")])]),
    _chunk("405", "6553", "12", "ÖRNEK DELTA KANUNU", [_f(None, "bentsiz")]),
]


@pytest.fixture(scope="module")
def indeks():
    return AtifIndeks.bellekten(KORPUS)


def _coz(sorgu, indeks):
    atiflar = atif_ayristir(sorgu, kanun_adlari=indeks.kanun_adlari)
    assert len(atiflar) == 1, f"{sorgu!r} → {atiflar}"
    return atif_coz(atiflar[0], indeks)


def _idler(cozum):
    return [e.kayit.madde_id for e in cozum.eslesmeler]


# ---- indeks ------------------------------------------------------------------------------------
def test_indeks_anahtarlari(indeks):
    assert len(indeks) == len(KORPUS)
    assert indeks.kanun_var("5237") and indeks.kanun_var("05237") and not indeks.kanun_var("9999")
    assert [k.madde_id for k in indeks.bul("5237", "asil", "141")] == ["100-141"]
    assert [k.madde_id for k in indeks.bul("6111", "gecici", "1")] == ["500-Gecici1-1", "500-Gecici1-2"]
    assert indeks.bul("5237", "gecici", "141") == []            # tip anahtarın parçası


def test_indeks_kanun_adlari_uzun_once(indeks):
    adlar = dict(indeks.kanun_adlari)
    assert adlar["turk ceza kanunu"] == ("5237",) and adlar["deniz is kanunu"] == ("854",)
    uzunluklar = [len(a) for a, _ in indeks.kanun_adlari]
    assert uzunluklar == sorted(uzunluklar, reverse=True)


# ---- madde / fıkra / bent ----------------------------------------------------------------------
def test_kesin_madde(indeks):
    c = _coz("TCK m. 141", indeks)
    assert c.durum == "eslesti" and _idler(c) == ["100-141"] and not c.coklu_mevzuat
    e = c.eslesmeler[0]
    assert e.alt_parca is None and e.metin == "TÜRK CEZA KANUNU 141 metni" and e.uyarilar == []


def test_fikra_alt_parcasi(indeks):
    p = _coz("TCK 141/2", indeks).eslesmeler[0].alt_parca
    assert (p.fikra, p.bent, p.metin, p.yurutluk, p.tolerans) == (
        "(2)", None, "(2) Değeri az olan ...", "yürürlükte", None)


def test_fikrasiz_bent(indeks):
    p = _coz("TCK m. 142 (b) bendi", indeks).eslesmeler[0].alt_parca
    assert (p.fikra, p.bent, p.metin) == ("(1)", "b)", "b) Halkın yararlanmasına mahsus ...")


def test_fikra_ve_bent_turkce_harf(indeks):
    p = _coz("KVKK 11/1-ç", indeks).eslesmeler[0].alt_parca
    assert (p.fikra, p.bent, p.metin) == ("(1)", "ç)", "ç) Aktarıldığı üçüncü kişileri bilme,")


def test_son_fikra(indeks):
    assert _coz("TCK m. 141 son fıkrası", indeks).eslesmeler[0].alt_parca.fikra == "(2)"


def test_fikra_bent_toleransi(indeks):
    e = _coz("GVK m. 40 fıkra 7", indeks).eslesmeler[0]
    assert (e.alt_parca.bent, e.alt_parca.metin, e.alt_parca.tolerans) == (
        "7.", "7. İşle ilgili zararlar ...", "fikra->bent")
    assert any("(7) numaralı fıkra yok" in u for u in e.uyarilar)
    e2 = _coz("193 sayılı Kanunun 40. maddesinin 2. fıkrası", indeks).eslesmeler[0]
    assert (e2.alt_parca.bent, e2.alt_parca.tolerans) == ("2.", "fikra->bent")


def test_numarali_fikrasiz_eski_stilde_bent_konumsal_fikradan_once(indeks):
    p = _coz("GVK 40/1", indeks).eslesmeler[0].alt_parca     # tek numarasız fıkra + '1.' bendi → bent
    assert (p.bent, p.tolerans) == ("1.", "fikra->bent")
    p2 = _coz("3194 sayılı Kanun m. 32/1", indeks).eslesmeler[0].alt_parca   # bentsiz: konumsal 1. fıkra
    assert p2.fikra is None and p2.bent is None and p2.tolerans is None and p2.metin.startswith("Bu Kanuna")


def test_fikra_bulununca_ayni_numarali_bent_uyarisi(indeks):
    e = _coz("KDVK 29/2", indeks).eslesmeler[0]
    assert (e.alt_parca.fikra, e.alt_parca.bent, e.alt_parca.tolerans) == ("(2)", None, None)
    assert e.uyarilar == ["maddede '2.' işaretli bent de var (bende fıkra denmiş olabilir)"]


def test_fikra_bulunamazsa_madde_yine_doner(indeks):
    c = _coz("TCK 141/5", indeks)
    assert c.durum == "eslesti" and c.eslesmeler[0].alt_parca is None
    assert c.eslesmeler[0].uyarilar == ["5. fıkra bulunamadı"]


def test_bent_bulunamazsa_fikra_doner(indeks):
    e = _coz("TCK m. 141/2-z", indeks).eslesmeler[0]
    assert (e.alt_parca.fikra, e.alt_parca.bent) == ("(2)", None)
    assert e.uyarilar == ["(z) bendi bulunamadı; fıkra döndü"]


@pytest.mark.parametrize("fikra, bent, beklenen", [
    (None, None, (None, True)),
    (1, None, ("(1)", True)),
    (9, None, (None, False)),
])
def test_alt_parca_bul_dogrudan(fikra, bent, beklenen):
    p, tam, _ = alt_parca_bul([_f("(1)", "(1) x")], fikra, bent)
    assert ((p.fikra if p else None), tam) == beklenen


# ---- yürürlük / eşleşmeme ----------------------------------------------------------------------
def test_mulga_madde_yururluk_bilgisiyle_doner(indeks):
    e = _coz("TCK m. 143", indeks).eslesmeler[0]
    assert e.kayit.yurutluk == "mülga" and e.metadata["yurutluk"] == "mülga"
    assert any("mülga" in u for u in e.uyarilar)


def test_olmayan_madde(indeks):
    c = _coz("TCK m. 999", indeks)
    assert (c.durum, c.eslesmeler) == ("madde_yok", []) and "999" in c.aciklama


def test_bilinmeyen_kanun(indeks):
    c = _coz("9999 sayılı Kanun m. 1", indeks)
    assert c.durum == "kanun_yok" and "9999" in c.aciklama


# ---- kanun_no çakışması / aynı numara ----------------------------------------------------------
def test_kanun_no_cakismasi_ipucusuz_hepsi_doner(indeks):
    c = _coz("6551 sayılı Kanun m. 5", indeks)
    assert c.durum == "eslesti" and c.coklu_mevzuat
    assert {e.kayit.mevzuat_id for e in c.eslesmeler} == {"400", "401"}
    assert "ÖRNEK ENERJİ PİYASASI KANUNU" in c.aciklama and "mevzuat_id 400" in c.aciklama


def test_kanun_no_cakismasi_ad_ipucuyla_cozulur(indeks):
    c = _coz("6551 sayılı Örnek Enerji Piyasası Kanununun 5. maddesi", indeks)
    assert _idler(c) == ["401-5"] and not c.coklu_mevzuat and c.aciklama is None


def test_kanun_no_cakismasi_madde_tek_kanundaysa_o_doner(indeks):
    c = _coz("6551 sayılı Kanun m. 9", indeks)
    assert _idler(c) == ["400-9"] and not c.coklu_mevzuat


def test_ayni_kanunda_ayni_numarali_iki_madde(indeks):
    c = _coz("6111 sayılı Kanun geçici madde 1", indeks)
    assert _idler(c) == ["500-Gecici1-1", "500-Gecici1-2"] and not c.coklu_mevzuat
    assert all("aynı numaralı" in u for e in c.eslesmeler for u in e.uyarilar)


def test_cakisma_ve_tekrar_karisik_uyari_yalniz_tekrarlilarda(indeks):
    c = _coz("6552 sayılı Kanun m. 8", indeks)
    assert _idler(c) == ["402-8", "403-8", "403-8-2"] and c.coklu_mevzuat
    tekrar = {e.kayit.madde_id: any("aynı numaralı" in u for u in e.uyarilar) for e in c.eslesmeler}
    assert tekrar == {"402-8": False, "403-8": True, "403-8-2": True}


def test_alternatif_yorum_cakismayi_daraltirsa_coklu_dusmez(indeks):
    c = _coz("6553 sayılı Kanun m. 12/a", indeks)              # 12/A yok; (a) bendi yalnız 404'te
    assert c.yorum.aciklama == "harf->bent" and _idler(c) == ["404-12"]
    assert not c.coklu_mevzuat and c.aciklama is None


# ---- belirsiz slash eki ------------------------------------------------------------------------
def test_harfli_madde(indeks):
    assert _idler(_coz("6183 sayılı Kanun m. 48/A", indeks)) == ["600-48A"]


def test_harf_eki_harfli_madde_yoksa_bent_olur(indeks):
    c = _coz("VUK 359/a", indeks)
    assert c.yorum.aciklama == "harf->bent" and _idler(c) == ["700-359"]
    assert c.eslesmeler[0].alt_parca.bent == "a)" and "harfli maddesi yok" in c.eslesmeler[0].uyarilar[0]


def test_harf_eki_alternatifi_tam_bulunmazsa_kabul_edilmez(indeks):
    assert _coz("VUK 359/c", indeks).durum == "madde_yok"     # ne 359/C ne de 359'un (c) bendi var


def test_roma_fikra(indeks):
    assert _coz("TMK 166/II", indeks).eslesmeler[0].alt_parca.fikra == "(2)"
    c = _coz("TMK 166/I", indeks)                              # 166/I harfli maddesi yok → 1. fıkra
    assert c.yorum.aciklama == "roma->fikra" and c.eslesmeler[0].alt_parca.fikra == "(1)"


def test_roma_fikra_alternatifi_benti_de_getirir(indeks):
    c = _coz("KVKK 11/I-b", indeks)                           # 11/I harfli maddesi yok → (1) fıkra (b) bendi
    assert c.yorum.aciklama == "roma->fikra"
    assert (c.eslesmeler[0].alt_parca.fikra, c.eslesmeler[0].alt_parca.bent) == ("(1)", "b)")


def test_tek_harf_roma_harfli_madde_varsa_harfli_kazanir(indeks):
    c = _coz("7000 sayılı Kanun m. 5/I", indeks)
    assert _idler(c) == ["810-5I"] and c.yorum.aciklama is None


def test_mukerrer_madde(indeks):
    assert _idler(_coz("VUK mükerrer 298", indeks)) == ["700-Mukerrer298"]


def test_yonlendirme_kaydi(indeks):
    e = _coz("5000 sayılı Kanun m. 7", indeks).eslesmeler[0]
    assert e.metin == "" and any("5237 sayılı kanuna işlenmiş" in u for u in e.uyarilar)


# ---- korpus adlarıyla tanıma -------------------------------------------------------------------
def test_korpus_adiyla_cozum(indeks):
    assert _idler(_coz("İmar Kanunu 32. madde", indeks)) == ["950-32"]
    assert _idler(_coz("Deniz İş Kanunu m. 5", indeks)) == ["951-5"]       # İş Kanunu (952) değil
    assert _idler(_coz("İş Kanunu m. 5", indeks)) == ["952-5"]


def test_basin_is_kanunu_5953_is_kanunu_sayilmaz(indeks):
    # 'Basın İş Kanunu' = 5953 sayılı Kanun (resmî adı 'Basın Mesleğinde Çalışanlarla ...'); korpus adı
    # 'İŞ KANUNU' (4857) içinde geçtiği için korpus adı yolunda 4857 sanılıyordu
    for kw in ({}, {"kanun_adlari": indeks.kanun_adlari}):
        assert _tek("Basın İş Kanunu m. 5", **kw).kanun_nolari == ("5953",)
        assert _tek("Basın İş Kanunu'nun 6. maddesi", **kw).kanun_nolari == ("5953",)
    assert _coz("Basın İş Kanunu m. 5", indeks).durum == "kanun_yok"       # 952-5 (İş K.) DÖNMEZ


# ---- dosya ofsetli indeks (servis yolu) --------------------------------------------------------
def _korpus_yaz(yol, satirlar):
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        for r in satirlar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.write("\n")                                       # boş satırlar atlanmalı


def test_dosyadan_indeks_ofsetle_okur(tmp_path):
    yol = tmp_path / "korpus.jsonl"
    _korpus_yaz(yol, KORPUS)
    ix = atif_indeks_kur(str(yol))
    assert len(ix) == len(KORPUS)
    kayit = ix.bul("6698", "asil", "11")[0]
    assert kayit.chunk is None and isinstance(kayit.ofset, int)   # tam satır bellekte tutulmaz
    c = atif_coz(atif_ayristir("KVKK 11/1-ç")[0], ix)
    assert c.eslesmeler[0].alt_parca.metin == "ç) Aktarıldığı üçüncü kişileri bilme,"
    assert ix.chunk(kayit) == KORPUS[3]


def test_dosya_degisirse_korpus_degisti(tmp_path):
    yol = tmp_path / "korpus.jsonl"
    _korpus_yaz(yol, KORPUS)
    ix = atif_indeks_kur(str(yol))
    _korpus_yaz(yol, list(reversed(KORPUS)))                   # ofsetler artık başka satırları gösterir
    with pytest.raises(KorpusDegisti):
        ix.chunk(ix.bul("5237", "asil", "141")[0])


def test_dosya_okunamazsa_korpus_degisti(tmp_path):
    yol = tmp_path / "korpus.jsonl"
    _korpus_yaz(yol, KORPUS)
    ix = atif_indeks_kur(str(yol))
    yol.unlink()                                                # servis açıkken taşındı / silindi
    with pytest.raises(KorpusDegisti, match="yeniden başlatın"):
        ix.chunk(ix.bul("5237", "asil", "141")[0])


# =================================================================================================
# Mod seçimi — otomatik / atif / dogal
# =================================================================================================
class SahteDogal:
    """HybridArama.ara arayüzü; çağrıları kaydeder."""

    def __init__(self):
        self.cagrilar = []

    def ara(self, sorgu, top_k=10, yururlukte_only=True, rerank=None):
        self.cagrilar.append({"sorgu": sorgu, "top_k": top_k, "yururlukte_only": yururlukte_only,
                              "rerank": rerank})
        return AramaSonucu([Sonuc("x-1", "1", "K", "1", 0.5)], sure_ms={"toplam": 1.0})


def _satirlar(s):
    return [(i, e.kayit.madde_id) for i, e in s.satirlar]


def test_mod_dogal_ayristirma_yapmaz(indeks):
    d = SahteDogal()
    s = modlu_ara(d, indeks, "TCK m. 141", mod="dogal", top_k=3)
    assert (s.mod, s.istenen_mod, s.durum, s.dusus, s.atiflar) == ("dogal", "dogal", None, False, [])
    assert d.cagrilar == [{"sorgu": "TCK m. 141", "top_k": 3, "yururlukte_only": True, "rerank": None}]


def test_otomatik_dogal_dil_sorgusu_aynen_dogal_aramaya_gider(indeks):
    d = SahteDogal()
    s = modlu_ara(d, indeks, "kira artışı nasıl belirlenir", top_k=5, yururlukte_only=False, rerank=True)
    assert (s.mod, s.durum, s.aciklama, s.dusus) == ("dogal", None, None, False)
    assert d.cagrilar == [{"sorgu": "kira artışı nasıl belirlenir", "top_k": 5, "yururlukte_only": False,
                           "rerank": True}]
    assert s.sure_ms == {"toplam": 1.0}                         # doğal dil süreleri dokunulmadan


def test_otomatik_atif_sorgusu_kesin_getirir(indeks):
    d = SahteDogal()
    s = modlu_ara(d, indeks, "TCK 141/2")
    assert (s.mod, s.durum) == ("atif", "eslesti") and d.cagrilar == []     # doğal dil hiç çağrılmaz
    assert _satirlar(s) == [(1, "100-141")]
    assert set(s.sure_ms) == {"ayristirma", "getirme", "toplam"}


def test_mod_atif_atif_sorgusu(indeks):
    s = modlu_ara(SahteDogal(), indeks, "KVKK 11/1-ç", mod="atif")
    assert (s.mod, s.istenen_mod) == ("atif", "atif") and s.satirlar[0][1].alt_parca.bent == "ç)"


def test_eslesmeyen_atif_dogal_dile_duser(indeks):
    d = SahteDogal()
    s = modlu_ara(d, indeks, "TCK m. 999")
    assert (s.mod, s.durum, s.dusus) == ("dogal", "eslesme_yok", True)
    assert "999" in s.aciklama and "doğal dil" in s.aciklama
    assert len(d.cagrilar) == 1 and s.cozumler[0].durum == "madde_yok" and s.dogal is not None


def test_bilinmeyen_kanun_dogal_dile_duser(indeks):
    s = modlu_ara(SahteDogal(), indeks, "9999 sayılı Kanun m. 1")
    assert (s.mod, s.durum) == ("dogal", "eslesme_yok") and "9999" in s.aciklama


def test_mod_atif_ayristirilamazsa_dogal_dile_duser(indeks):
    s = modlu_ara(SahteDogal(), indeks, "kira artışı", mod="atif")
    assert (s.mod, s.durum, s.aciklama) == ("dogal", "ayristirilamadi", "sorguda kanun + madde atfı bulunamadı")
    assert "kanun tanındı (5237)" in modlu_ara(SahteDogal(), indeks, "5237 sayılı kanun", mod="atif").aciklama


def test_otomatik_kismi_atif_aciklamasiz_dogal_dil(indeks):
    s = modlu_ara(SahteDogal(), indeks, "5237 sayılı kanun")      # yalnız kanun: otomatikte sessiz doğal dil
    assert (s.mod, s.durum, s.aciklama) == ("dogal", None, None)


def test_indeks_yoksa_dogal_dile_duser():
    s = modlu_ara(SahteDogal(), None, "TCK m. 141")
    assert (s.mod, s.durum) == ("dogal", "indeks_yok") and len(s.atiflar) == 1


def test_kismi_eslesme(indeks):
    s = modlu_ara(SahteDogal(), indeks, "TCK m. 141 ve TCK m. 999")
    assert (s.mod, s.durum) == ("atif", "kismi")
    assert _satirlar(s) == [(1, "100-141")] and "999" in s.aciklama


def test_coklu_atif_sirasi_ve_top_k(indeks):
    s = modlu_ara(SahteDogal(), indeks, "6551 sayılı Kanun m. 5 ve TCK m. 141")
    assert _satirlar(s) == [(1, "400-5"), (1, "401-5"), (2, "100-141")]
    assert "birden çok kanunda" in s.aciklama
    assert _satirlar(modlu_ara(SahteDogal(), indeks, "6551 sayılı Kanun m. 5 ve TCK m. 141", top_k=2)) == [
        (1, "400-5"), (1, "401-5")]


def test_ayni_madde_ayni_alt_parca_bir_kez_doner(indeks):
    s = modlu_ara(SahteDogal(), indeks, "TCK m. 141 son fıkrası ve TCK m. 141/2")   # ikisi de (2)
    assert len(s.atiflar) == 2 and _satirlar(s) == [(1, "100-141")]


def test_ayni_maddenin_farkli_alt_parcalari_ayri_satir(indeks):
    s = modlu_ara(SahteDogal(), indeks, "TCK m. 141/1 ve m. 141/2")
    assert _satirlar(s) == [(1, "100-141"), (2, "100-141")]
    assert [e.alt_parca.fikra for _, e in s.satirlar] == ["(1)", "(2)"]


def test_atif_modunda_yururluk_filtresi_uygulanmaz(indeks):
    s = modlu_ara(SahteDogal(), indeks, "TCK m. 143", yururlukte_only=True)
    assert s.mod == "atif" and s.satirlar[0][1].kayit.yurutluk == "mülga"


def test_gecersiz_mod():
    assert MODLAR == ("otomatik", "atif", "dogal")
    with pytest.raises(ValueError):
        modlu_ara(SahteDogal(), None, "x", mod="hepsi")


def test_ayristirici_hatasi_dogal_dili_bozmaz(indeks, monkeypatch):
    def patla(*a, **k):
        raise RuntimeError("bozuk")
    monkeypatch.setattr(atif_getir, "ayristir", patla)
    d = SahteDogal()
    s = modlu_ara(d, indeks, "kira artışı")
    assert (s.mod, s.durum) == ("dogal", None) and len(d.cagrilar) == 1
    assert modlu_ara(SahteDogal(), indeks, "TCK m. 141", mod="atif").durum == "ayristirilamadi"


# ---- doğal dil yolu HybridArama ile BİREBİR aynı (sahte Qdrant + sahte BM25) -------------------
def _nokta(kn, mn, skor):
    return SimpleNamespace(score=skor, payload={"kanun_no": kn, "madde_no": mn, "madde_id": f"{kn}-{mn}",
                                                 "kanun_ad": "K"})


class _SahteQdrant:
    def query_points(self, collection_name, query, using, limit, query_filter, with_payload):
        noktalar = {"dense": [_nokta("1", "1", 0.9), _nokta("1", "2", 0.5), _nokta("2", "1", 0.1)],
                    "sparse": [_nokta("1", "2", 12.0), _nokta("2", "1", 2.0)]}[using]
        return SimpleNamespace(points=noktalar[:limit])


class _SahteBM25:
    def get_scores(self, tokenler):
        return np.asarray([4.0, 0.0, 1.0])


def _hybrid():
    bm25 = BM25Index(_SahteBM25(), [("1", "1", "m11"), ("3", "7", "m37"), ("2", "1", "m21")])
    return HybridArama(lambda s: ([0.1] * 4, {"5": 0.3}), _SahteQdrant(), bm25)


@pytest.mark.parametrize("sorgu", ["kira artışı nasıl belirlenir", "memurun disiplin cezası",
                                   "5237 sayılı kanun", "TCK'da 2 yıl hapis cezası"])
def test_dogal_dil_sonucu_hybrid_arama_ile_birebir(indeks, sorgu):
    arama = _hybrid()
    beklenen = arama.ara(sorgu, top_k=3)
    s = modlu_ara(arama, indeks, sorgu, top_k=3)
    assert s.mod == "dogal" and isinstance(s.dogal, AramaSonucu)
    assert [(r.madde_id, r.anahtar, r.skor, r.rerank_skor) for r in s.dogal] == [
        (r.madde_id, r.anahtar, r.skor, r.rerank_skor) for r in beklenen]
    assert set(s.dogal.sure_ms) == set(beklenen.sure_ms) and s.dogal.rerank == beklenen.rerank
